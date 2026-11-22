"""YouTube publishing: desktop OAuth, OS credential vault, resumable upload queue.

Importing this module never starts a login or sends a video. All writes require
an explicit UI action. Secrets and upload session URLs are never returned to UI.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from . import db
from .config import DATA_DIR

router = APIRouter(prefix='/api/youtube')
ROOT = DATA_DIR / 'youtube'
SERVICE = 'ViralCut.YouTube'
ACCOUNT = hashlib.sha256(str(DATA_DIR.resolve()).encode()).hexdigest()[:24]
SCOPES = ['https://www.googleapis.com/auth/youtube.upload',
          'https://www.googleapis.com/auth/youtube.readonly']
_LOCK = threading.RLock()
_AUTH: dict[str, Any] = {}
_CANCEL: dict[str, threading.Event] = {}
_POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix='youtube-upload')


def _write(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    with temp.open('w', encoding='utf-8') as file:
        os.chmod(temp, 0o600)
        json.dump(data, file, ensure_ascii=False)
    temp.replace(path)


def _read(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def _vault():
    import keyring
    # A vault failure is actionable; never fall back to plaintext token files.
    return keyring


def _credentials():
    from google.oauth2.credentials import Credentials
    data = _vault().get_password(SERVICE, ACCOUNT)
    if not data:
        raise ValueError('Подключите канал YouTube в настройках')
    creds = Credentials.from_authorized_user_info(json.loads(data), SCOPES)
    if not creds.valid:
        from google.auth.transport.requests import Request
        creds.refresh(Request())
        _vault().set_password(SERVICE, ACCOUNT, creds.to_json())
    return creds


def _service(creds):
    from googleapiclient.discovery import build
    import httplib2
    from google_auth_httplib2 import AuthorizedHttp
    return build('youtube', 'v3', http=AuthorizedHttp(creds,http=httplib2.Http(timeout=60)), cache_discovery=False)


def _job_files():
    return sorted((ROOT/'uploads').glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)


def _active() -> bool:
    return any(_read(p).get('status') in ('queued','uploading','cancelling') for p in _job_files())


def _save_job(job: dict, **changes):
    with _LOCK:
        job.update(changes, updated_at=time.time())
        _write(ROOT/'uploads'/(job['id']+'.json'), job)


def recover():
    """Do not silently retry uploads after a crash: the remote video may exist."""
    with _LOCK:
        for path in _job_files():
            job = _read(path)
            if job.get('status') in ('queued','uploading','cancelling'):
                _save_job(job, status='interrupted', error='Приложение закрылось во время загрузки. Проверьте YouTube Studio перед повторной отправкой.')
                (ROOT/'staging'/(job['id']+'.mp4')).unlink(missing_ok=True)


@router.get('/status')
def status():
    configured = bool(_read(ROOT/'client.json'))
    try:
        connected = bool(_vault().get_password(SERVICE, ACCOUNT))
        error = ''
    except Exception:
        connected, error = False, 'Не удалось открыть системное хранилище паролей'
    return {'configured':configured, 'connected':connected,
            'channel':_read(ROOT/'channel.json') if connected else None,
            'connecting':bool(_AUTH.get('pending')), 'auth_error':_AUTH.get('error',''),
            'storage_error':error}


@router.post('/client')
async def configure_client(file: UploadFile = File(...)):
    raw = await file.read(65537)
    if len(raw)>65536:
        raise HTTPException(400, 'OAuth-файл слишком большой')
    try:
        config=json.loads(raw)
        installed=config['installed']
        if not str(installed['client_id']).endswith('.apps.googleusercontent.com') or not installed['client_secret']:
            raise ValueError()
        if installed.get('auth_uri') != 'https://accounts.google.com/o/oauth2/auth' or installed.get('token_uri') != 'https://oauth2.googleapis.com/token':
            raise ValueError()
    except (ValueError, KeyError, TypeError):
        raise HTTPException(400, 'Выберите JSON OAuth-клиента типа «Desktop app» из Google Cloud') from None
    with _LOCK:
        if _active() or _AUTH.get('pending'):
            raise HTTPException(409, 'Дождитесь завершения подключения или загрузки')
        try:
            if _vault().get_password(SERVICE, ACCOUNT):
                raise HTTPException(409, 'Сначала отключите текущий канал')
        except HTTPException: raise
        except Exception:
            raise HTTPException(503, 'Системное хранилище паролей недоступно') from None
        _write(ROOT/'client.json', {'installed':{k:installed[k] for k in ('client_id','client_secret','auth_uri','token_uri')}})
    return {'ok':True}


@router.post('/connect')
def connect():
    with _LOCK:
        config=_read(ROOT/'client.json')
        if not config:
            raise HTTPException(400, 'Сначала выберите OAuth-файл Google в настройках')
        if _AUTH.get('pending') or _active():
            raise HTTPException(409, 'Подключение или загрузка уже выполняется')
        from google_auth_oauthlib.flow import InstalledAppFlow
        flow=InstalledAppFlow.from_client_config(config, SCOPES, autogenerate_code_verifier=True)
        expected_state=secrets.token_urlsafe(32)
        deadline=time.monotonic()+600
        _AUTH.clear(); _AUTH.update(pending=True)

        class Callback(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                query=parse_qs(urlparse(self.path).query)
                if self.path.split('?')[0]!='/' or not secrets.compare_digest(query.get('state',[''])[0],expected_state):
                    self.send_error(400, 'Invalid OAuth state'); return
                message='Канал не подключён. Вернитесь в ViralCut и повторите подключение.'
                try:
                    if time.monotonic()>deadline or query.get('error') or not query.get('code'):
                        raise ValueError()
                    flow.fetch_token(code=query['code'][0], timeout=30)
                    creds=flow.credentials
                    service=_service(creds)
                    try:
                        result=service.channels().list(part='snippet',mine=True).execute()
                    finally: service.close()
                    channels=result.get('items',[])
                    if not channels:
                        raise ValueError()
                    channel={'id':channels[0]['id'],'title':channels[0]['snippet']['title']}
                    _vault().set_password(SERVICE,ACCOUNT,creds.to_json())
                    _write(ROOT/'channel.json',channel)
                    message='Канал подключён. Закройте эту вкладку и вернитесь в ViralCut.'
                except Exception:
                    _AUTH['error']='Не удалось подключить канал. Проверьте разрешения, настройки OAuth и наличие канала YouTube.'
                finally: _AUTH['pending']=False
                page=('<!doctype html><meta charset="utf-8"><title>ViralCut · YouTube</title><body style="background:#111118;color:#eee;font:18px system-ui;padding:60px"><h1>ViralCut · YouTube</h1><p>'+message+'</p></body>').encode()
                self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8')
                self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(page)))
                self.end_headers();self.wfile.write(page)

        server=HTTPServer(('127.0.0.1',0), Callback);server.timeout=1
        flow.redirect_uri=f'http://127.0.0.1:{server.server_port}/'
        url,_=flow.authorization_url(state=expected_state,access_type='offline',prompt='consent')
        def listen():
            try:
                while _AUTH.get('pending') and time.monotonic()<deadline: server.handle_request()
            finally:
                server.server_close()
                if _AUTH.get('pending'):
                    _AUTH.update(pending=False,error='Время подключения истекло. Попробуйте ещё раз.')
        threading.Thread(target=listen,name='youtube-oauth',daemon=True).start()
    return {'authorization_url':url}


@router.post('/disconnect')
def disconnect():
    with _LOCK:
        if _active() or _AUTH.get('pending'):
            raise HTTPException(409,'Дождитесь завершения подключения или загрузки')
        try:
            vault=_vault(); raw=vault.get_password(SERVICE,ACCOUNT)
            revoked=True
            if raw:
                import requests
                data=json.loads(raw)
                try:
                    response=requests.post('https://oauth2.googleapis.com/revoke',data={'token':data.get('refresh_token') or data.get('token')},timeout=15)
                    revoked=response.status_code in (200,400)
                except requests.RequestException: revoked=False
                vault.delete_password(SERVICE,ACCOUNT)
            (ROOT/'channel.json').unlink(missing_ok=True)
        except Exception:
            raise HTTPException(503,'Не удалось удалить подключение из системного хранилища') from None
    return {'ok':True,'revoked':revoked}


class PublishIn(BaseModel):
    title: str = Field(min_length=1,max_length=100)
    description: str = Field(default='',max_length=5000)
    privacy: str = Field(default='private',pattern='^(private|unlisted|public)$')
    made_for_kids: bool
    synthetic_media: bool = False
    paid_promotion: bool = False
    publish_at: str | None = None


def metadata(body: PublishIn) -> dict:
    title=body.title.strip()
    if not title or any(c in title+body.description for c in '<>'):
        raise ValueError('Название и описание не должны содержать символы < или >')
    if len(body.description.encode('utf-8'))>5000:
        raise ValueError('Описание слишком длинное: YouTube допускает до 5000 байт')
    state={'privacyStatus':body.privacy,'selfDeclaredMadeForKids':body.made_for_kids,
           'containsSyntheticMedia':body.synthetic_media}
    if body.publish_at:
        when=datetime.fromisoformat(body.publish_at.replace('Z','+00:00'))
        if when.tzinfo is None or when<=datetime.now(timezone.utc):
            raise ValueError('Выберите будущее время публикации')
        if body.privacy!='private':
            raise ValueError('Для публикации по расписанию нужен доступ «Личное»')
        state['publishAt']=when.astimezone(timezone.utc).isoformat()
    return {'snippet':{'title':title,'description':body.description,'categoryId':'22'},'status':state,
            'paidProductPlacementDetails':{'hasPaidProductPlacement':body.paid_promotion}}


def _upload(job: dict, snapshot: Path, payload: dict, cancel: threading.Event):
    service=None
    try:
        if cancel.is_set():
            _save_job(job,status='cancelled');return
        _save_job(job,status='uploading')
        from googleapiclient.http import MediaFileUpload
        service=_service(_credentials())
        request=service.videos().insert(part='snippet,status,paidProductPlacementDetails',body=payload,
                    media_body=MediaFileUpload(str(snapshot),mimetype='video/mp4',chunksize=8*1024*1024,resumable=True),notifySubscribers=False)
        result=None
        while result is None:
            if cancel.is_set():
                _save_job(job,status='cancelled');return
            progress,result=request.next_chunk(num_retries=5)
            if progress:
                _save_job(job,progress=round(progress.progress()*100))
        video_id=result['id']
        _save_job(job,status='done',progress=100,video_id=video_id,url='https://www.youtube.com/watch?v='+video_id,
                  message='Файл загружен. YouTube может ещё обрабатывать видео.')
    except Exception:
        _save_job(job,status='error',error='Не удалось завершить загрузку. Проверьте подключение, квоту YouTube API и разрешения аккаунта. Перед повтором проверьте YouTube Studio: видео могло уже загрузиться.')
    finally:
        if service: service.close()
        snapshot.unlink(missing_ok=True)
        with _LOCK: _CANCEL.pop(job['id'],None)


@router.post('/clips/{clip_id}/publish')
def publish(clip_id: str, body: PublishIn):
    try: payload=metadata(body)
    except ValueError as exc: raise HTTPException(400,str(exc)) from None
    clip=db.get_clip(clip_id)
    if not clip or clip['status']!='ready' or not clip.get('path'):
        raise HTTPException(409,'Сначала дождитесь готовности клипа')
    path=Path(clip['path'])
    if not path.is_file():raise HTTPException(404,'Файл клипа не найден')
    with _LOCK:
        try:
            if not _vault().get_password(SERVICE,ACCOUNT):
                raise HTTPException(400,'Подключите канал YouTube в настройках')
        except HTTPException:raise
        except Exception:raise HTTPException(503,'Хранилище паролей недоступно') from None
        fingerprint=f'{path.stat().st_size}:{path.stat().st_mtime_ns}'
        for job_file in _job_files():
            previous=_read(job_file)
            if previous.get('clip_id')==clip_id and previous.get('fingerprint')==fingerprint and previous.get('status') in ('queued','uploading','cancelling','done'):
                return previous
        job={'id':uuid.uuid4().hex,'clip_id':clip_id,'fingerprint':fingerprint,'status':'queued',
             'progress':0,'title':body.title.strip(),'privacy':body.privacy,'created_at':time.time(),
             'channel':_read(ROOT/'channel.json'),'publish_at':body.publish_at,'clip_updated_at':clip.get('updated_at')}
        snapshot=ROOT/'staging'/(job['id']+'.mp4');snapshot.parent.mkdir(parents=True,exist_ok=True)
        try:
            shutil.copyfile(path,snapshot)
            if f'{path.stat().st_size}:{path.stat().st_mtime_ns}'!=fingerprint:
                raise ValueError()
        except Exception:
            snapshot.unlink(missing_ok=True)
            raise HTTPException(409,'Клип изменился во время подготовки. Повторите после рендера.') from None
        cancel=threading.Event();_CANCEL[job['id']]=cancel
        _save_job(job)
        _POOL.submit(_upload,job,snapshot,payload,cancel)
        return job


@router.get('/uploads')
def uploads(clip_id: str | None = None):
    with _LOCK:
        items=[_read(path) for path in _job_files()]
    return [j for j in items if clip_id is None or j.get('clip_id')==clip_id][:50]


@router.post('/uploads/{job_id}/cancel')
def cancel_upload(job_id: str):
    with _LOCK:
        event=_CANCEL.get(job_id)
        if not event:raise HTTPException(409,'Загрузка уже завершена')
        event.set()
    return {'ok':True}
