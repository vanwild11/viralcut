"""Publishing contract checks. No request is ever sent to Google or YouTube."""
import asyncio
import io
import json
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse
from fastapi import HTTPException, UploadFile
from pydantic import ValidationError
from viralcut import youtube as y


class YoutubeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.patch=patch.object(y,'ROOT',self.root);self.patch.start()
        self.vault=Mock();self.vault.get_password.return_value='test-token'
        self.vault_patch=patch.object(y,'_vault',return_value=self.vault);self.vault_patch.start()
        y._AUTH.clear();y._CANCEL.clear()

    def tearDown(self):
        y._AUTH.clear();y._CANCEL.clear()
        self.vault_patch.stop();self.patch.stop();self.temp.cleanup()

    def body(self, **kw):
        return y.PublishIn(**{'title':'Тестовый клип','made_for_kids':False,**kw})

    def test_metadata_explicit_privacy_and_audience(self):
        data=y.metadata(self.body())
        self.assertEqual(data['status']['privacyStatus'],'private')
        self.assertFalse(data['status']['selfDeclaredMadeForKids'])
        self.assertEqual(data['snippet']['categoryId'],'22')
        with self.assertRaises(ValidationError):y.PublishIn(title='Без аудитории')
        with self.assertRaises(ValueError):y.metadata(self.body(title='  '))
        with self.assertRaises(ValueError):y.metadata(self.body(description='Я'*3000))

    def test_schedule_and_disclosures(self):
        future=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
        data=y.metadata(self.body(publish_at=future,paid_promotion=True,synthetic_media=True))
        self.assertEqual(data['status']['publishAt'],future)
        self.assertTrue(data['paidProductPlacementDetails']['hasPaidProductPlacement'])
        self.assertTrue(data['status']['containsSyntheticMedia'])
        for when in ('invalid','2020-01-01T00:00:00Z','2090-01-01T00:00:00'):
            with self.assertRaises(ValueError):y.metadata(self.body(publish_at=when))
        with self.assertRaises(ValueError):y.metadata(self.body(publish_at=future,privacy='public'))

    def test_client_import_rejects_non_google_endpoints(self):
        config={'installed':{'client_id':'test.apps.googleusercontent.com','client_secret':'test',
                'auth_uri':'https://evil.example/auth','token_uri':'https://oauth2.googleapis.com/token'}}
        upload=UploadFile(file=io.BytesIO(json.dumps(config).encode()),filename='client.json')
        with self.assertRaises(HTTPException):asyncio.run(y.configure_client(upload))
        self.assertFalse((self.root/'client.json').exists())

    def test_oauth_state_and_pkce_without_network(self):
        config={'installed':{'client_id':'test.apps.googleusercontent.com','client_secret':'test',
                'auth_uri':'https://accounts.google.com/o/oauth2/auth','token_uri':'https://oauth2.googleapis.com/token'}}
        y._write(self.root/'client.json',config)
        captured={}
        def server(address, handler):
            captured['handler']=handler
            return Mock(server_port=18765)
        with patch.object(y,'HTTPServer',side_effect=server),patch.object(y.threading.Thread,'start'):
            result=y.connect()
        params=parse_qs(urlparse(result['authorization_url']).query)
        self.assertEqual(params['redirect_uri'],['http://127.0.0.1:18765/'])
        self.assertEqual(params['code_challenge_method'],['S256'])
        handler=captured['handler'].__new__(captured['handler'])
        handler.path='/?state=wrong&code=unused'
        handler.send_error=Mock()
        handler.do_GET()
        handler.send_error.assert_called_once_with(400,'Invalid OAuth state')
        self.vault.set_password.assert_not_called()
        self.assertTrue(y._AUTH['pending'])
        # A genuine user denial ends login without exchanging a code.
        handler.path='/?state='+params['state'][0]+'&error=access_denied'
        handler.send_response=Mock();handler.send_header=Mock();handler.end_headers=Mock();handler.wfile=io.BytesIO()
        handler.do_GET()
        self.assertFalse(y._AUTH['pending'])
        self.vault.set_password.assert_not_called()

    def test_publish_snapshot_and_duplicate_guard(self):
        path=self.root/'clip.mp4';path.write_bytes(b'snapshot')
        clip={'id':'clip1','status':'ready','path':str(path),'updated_at':123}
        with patch.object(y.db,'get_clip',return_value=clip),patch.object(y._POOL,'submit') as submit:
            first=y.publish('clip1',self.body())
            second=y.publish('clip1',self.body(privacy='public'))
        self.assertEqual(first['id'],second['id'])
        submit.assert_called_once()
        self.assertEqual((self.root/'staging'/(first['id']+'.mp4')).read_bytes(),b'snapshot')
        self.assertNotIn('test-token',json.dumps(first))

    def test_resumable_upload_progress_and_cleanup(self):
        snapshot=self.root/'snapshot.mp4';snapshot.write_bytes(b'media')
        job={'id':'job1','clip_id':'clip1'}
        request=Mock();progress=Mock();progress.progress.return_value=.5
        request.next_chunk.side_effect=[(progress,None),(None,{'id':'abcdefghijk'})]
        service=Mock();service.videos.return_value.insert.return_value=request
        with patch.object(y,'_credentials',return_value=object()),patch.object(y,'_service',return_value=service):
            y._upload(job,snapshot,y.metadata(self.body()),threading.Event())
        self.assertEqual(job['status'],'done');self.assertEqual(job['progress'],100)
        self.assertEqual(job['url'],'https://www.youtube.com/watch?v=abcdefghijk')
        self.assertFalse(snapshot.exists())
        self.assertEqual(request.next_chunk.call_count,2)
        service.close.assert_called_once()

    def test_cancellation_never_starts_network(self):
        snapshot=self.root/'snapshot.mp4';snapshot.write_bytes(b'media')
        event=threading.Event();event.set();job={'id':'job2'}
        with patch.object(y,'_service') as service:y._upload(job,snapshot,{},event)
        service.assert_not_called();self.assertEqual(job['status'],'cancelled')
        self.assertFalse(snapshot.exists())

    def test_restart_does_not_auto_republish(self):
        y._write(self.root/'uploads'/'job1.json',{'id':'job1','status':'uploading'})
        y._write(self.root/'uploads'/'job2.json',{'id':'job2','status':'done','video_id':'abc'})
        y.recover()
        self.assertEqual(y._read(self.root/'uploads'/'job1.json')['status'],'interrupted')
        self.assertEqual(y._read(self.root/'uploads'/'job2.json')['status'],'done')

    def test_status_does_not_return_credentials(self):
        status=y.status()
        self.assertTrue(status['connected'])
        self.assertNotIn('test-token',json.dumps(status))
