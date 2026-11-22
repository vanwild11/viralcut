"""Optional game split screen, interruption ad and watermark for rendered clips."""
from __future__ import annotations
import re
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from .config import DATA_DIR, ffmpeg
from . import utils

ASSETS = DATA_DIR / 'composition'

def asset(asset_id: str) -> Path:
    if not re.fullmatch(r'[a-f0-9]{32}\.(png|mp4)', asset_id):
        raise ValueError('Неверный файл композиции')
    path = ASSETS / asset_id
    if not path.is_file():
        raise ValueError('Файл композиции удалён. Загрузите его повторно.')
    return path


def validate(conf: dict) -> dict:
    out = {}
    for key in ('game', 'logo', 'ad'):
        if conf.get(key):
            path = asset(str(conf[key]))
            if path.suffix != ('.png' if key == 'logo' else '.mp4'):
                raise ValueError('Неверный тип файла')
            out[key] = path.name
    out['game_position'] = conf.get('game_position', 'bottom')
    out['logo_position'] = conf.get('logo_position', 'top-right')
    if out['game_position'] not in ('top', 'bottom') or out['logo_position'] not in ('top-left','top-right','bottom-left','bottom-right'):
        raise ValueError('Неверное положение')
    out['logo_size'] = max(5, min(30, int(conf.get('logo_size', 9))))
    out['logo_remove_background'] = bool(conf.get('logo_remove_background', False))
    out['game_variety'] = bool(conf.get('game_variety', True))
    out['game_start'] = max(0., float(conf['game_start'])) if conf.get('game_start') is not None else None
    return out


def encode(args: list[str], output: Path):
    r = utils.run([ffmpeg(), '-y', '-v', 'error', *args,
                   '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21',
                   '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-ar', '48000', '-ac', '2',
                   '-movflags', '+faststart', str(output)], timeout=1800)
    if r.returncode:
        raise utils.MediaError('Не удалось собрать композицию: ' + (r.stderr or '')[-700:])


def ad_point(path: Path, duration: float) -> tuple[float, str]:
    r = utils.run([ffmpeg(), '-v', 'info', '-i', str(path), '-af',
                   'silencedetect=noise=-32dB:d=0.25', '-f', 'null', '-'], timeout=120)
    pauses = [float(v) for v in re.findall(r'silence_end: ([0-9.]+)', r.stderr or '')]
    pauses = [v for v in pauses if duration * .25 <= v <= duration * .75]
    if pauses:
        return min(pauses, key=lambda v: abs(v-duration/2)), 'Пауза в речи'
    return duration/2, 'Пауза не найдена: середина клипа'


def apply(path: Path, raw: dict, canvas: tuple[int, int] | None = None,
          main_prepared: bool = False, variation: int = 0) -> dict:
    conf = validate(raw)
    if not any(conf.get(k) for k in ('game','logo','ad')):
        return {}
    report = {}
    info = utils.probe(path)
    w, h = canvas or (info['width'], info['height'])
    duration = info['duration']
    with TemporaryDirectory(prefix='vc-compose-', dir=str(path.parent)) as tmp:
        work = Path(tmp)
        current = path
        if conf.get('game'):
            half = info['height'] if main_prepared else int(h*.60)//2*2
            main = f'[0:v]scale={w}:{half}:force_original_aspect_ratio=increase,crop={w}:{half},setsar=1,fps=30[m]'
            game_path=asset(conf['game'])
            auto_start,auto_length=gameplay_window(game_path)
            start=conf['game_start'] if conf['game_start'] is not None else auto_start
            game_duration=utils.probe(game_path)['duration']
            start=min(start,max(0,game_duration-1))
            length=max(.5,min(auto_length if conf['game_start'] is None else game_duration-start,game_duration-start))
            start,length=choose_game_segment(start,length,duration,variation,conf['game_variety'])
            loop_path=work/'loop.mp4'
            encode(['-ss',str(start),'-i',str(game_path),'-t',str(length),'-an'],loop_path)
            report['game_start']=start
            game = f'[1:v]crop=iw:trunc(ih*0.92/2)*2:0:trunc(ih*0.02/2)*2,scale={w}:{h-half}:force_original_aspect_ratio=increase,crop={w}:{h-half},setsar=1,fps=30[g]'
            order = '[g][m]' if conf['game_position']=='top' else '[m][g]'
            target = work/'game.mp4'
            encode(['-i',str(current),'-stream_loop','-1','-i',str(loop_path),
                    '-filter_complex',f'{main};{game};{order}vstack=inputs=2[v]',
                    '-map','[v]','-map','0:a?','-t',str(duration)],target)
            current = target
        if conf.get('ad'):
            ad = asset(conf['ad']); ad_info = utils.probe(ad)
            point, reason = ad_point(path, duration)
            report.update({'ad_at': round(point, 2), 'ad_reason': reason, 'ad_duration': ad_info['duration']})
            ad_audio = '[1:a]aresample=48000,aformat=channel_layouts=stereo,asetpts=PTS-STARTPTS[aa]' if ad_info['has_audio'] else f'anullsrc=r=48000:cl=stereo,atrim=duration={ad_info["duration"]}[aa]'
            main_audio = '[0:a]aresample=48000,aformat=channel_layouts=stereo,asplit=2[a1][a2]' if info['has_audio'] else f'anullsrc=r=48000:cl=stereo,atrim=duration={duration},asplit=2[a1][a2]'
            filters = f'[0:v]split=2[v1][v2];[v1]trim=end={point},setpts=PTS-STARTPTS,fps=30,setsar=1[vb];[v2]trim=start={point},setpts=PTS-STARTPTS,fps=30,setsar=1[ve];{main_audio};[a1]atrim=end={point},asetpts=PTS-STARTPTS[ab];[a2]atrim=start={point},asetpts=PTS-STARTPTS[ae];[1:v]scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,setpts=PTS-STARTPTS[va];{ad_audio};[vb][ab][va][aa][ve][ae]concat=n=3:v=1:a=1[v][a]'
            target = work/'ad.mp4'
            encode(['-i',str(current),'-i',str(ad),'-filter_complex',filters,'-map','[v]','-map','[a]'],target)
            current = target
        if conf.get('logo'):
            prepared_logo=work/'watermark.png'
            prepare_logo(asset(conf['logo']),prepared_logo,conf['logo_remove_background'])
            size = max(2, int(w * conf['logo_size']/100)//2*2)
            pos = conf['logo_position']; x = '24' if pos.endswith('left') else 'W-w-24'; y = '24' if pos.startswith('top') else 'H-h-24'
            target = work/'logo.mp4'
            encode(['-i',str(current),'-i',str(prepared_logo),'-filter_complex',f'[1:v]scale={size}:-1[l];[0:v][l]overlay={x}:{y}:format=auto[v]', '-map','[v]','-map','0:a?'],target)
            current = target
        current.replace(path)
    return report


def gameplay_window(path: Path) -> tuple[float, float]:
    """Find the longest region with spatially distributed motion, skipping static menus.

    This is a motion heuristic; the selected region is exposed for preview/override.
    """
    import cv2
    import numpy as np
    import json
    cache = path.with_suffix('.motion.json')
    try:
        saved = json.loads(cache.read_text())
        if saved.get('version') == 2 and saved['size'] == path.stat().st_size:
            return saved['start'], saved['length']
    except (OSError, ValueError, KeyError):
        pass
    cap = cv2.VideoCapture(str(path))
    duration = cap.get(cv2.CAP_PROP_FRAME_COUNT) / max(1, cap.get(cv2.CAP_PROP_FPS))
    active = []
    try:
        for sec in range(0, int(duration-1), max(2,int(duration/90))):
            frames = []
            for t in (sec, sec+.4):
                cap.set(cv2.CAP_PROP_POS_MSEC,t*1000)
                ok, frame = cap.read()
                if not ok: break
                frame=cv2.resize(frame,(256,144))
                frames.append(cv2.cvtColor(frame[12:130,20:236],cv2.COLOR_BGR2GRAY))
            if len(frames)!=2: continue
            flow=cv2.calcOpticalFlowFarneback(frames[0],frames[1],None,.5,2,15,2,5,1.2,0)
            magnitude=np.linalg.norm(flow,axis=2)
            # Broad motion in multiple regions, rather than a single blinking button.
            blocks=[magnitude[y:y+39,x:x+72] for y in (0,39,78) for x in (0,72,144)]
            coverage=sum(float((b>1.5).mean())>.25 for b in blocks)
            active.append((sec,coverage>=5))
    finally:
        cap.release()
    runs=[]; begin=None
    for sec,on in active+[(int(duration),False)]:
        if on and begin is None:begin=sec
        if not on and begin is not None:
            runs.append((begin,sec-begin));begin=None
    best=max(runs,key=lambda v:v[1],default=(0,duration))
    start,length=best
    margin=min(12.,max(1.,length*.18)) if runs else 0
    start=min(start+margin,max(0,duration-1)) if runs else 0
    length=max(.5,min(length-margin,duration-start))
    try: cache.write_text(json.dumps({'version':2,'size':path.stat().st_size,'start':start,'length':length}))
    except OSError: pass
    return float(start),float(length)


def prepare_logo(path: Path, output: Path, remove_background: bool) -> None:
    """Trim transparent padding; optionally remove a uniform background connected to borders."""
    import numpy as np
    import cv2
    from PIL import Image
    with Image.open(path) as image:
        pixels=np.array(image.convert('RGBA'))
    if remove_background and pixels[:,:,3].min() == 255:
        rgb=pixels[:,:,:3].astype(float)
        corners=np.array([rgb[0,0],rgb[0,-1],rgb[-1,0],rgb[-1,-1]])
        if float(corners.std(axis=0).max())<12:
            background=np.median(corners,axis=0)
            candidate=(np.max(np.abs(rgb-background),axis=2)<35).astype('uint8')
            _,labels=cv2.connectedComponents(candidate)
            border=np.unique(np.concatenate([labels[0],labels[-1],labels[:,0],labels[:,-1]]))
            pixels[np.isin(labels,border[border!=0]),3]=0
    image=Image.fromarray(pixels)
    box=image.getbbox()
    if box: image=image.crop(box)
    image.save(output)


def choose_game_segment(start: float, length: float, clip_duration: float, index: int,
                        varied: bool = True) -> tuple[float, float]:
    """Stable, spread-out starts; first clip starts in the middle of available slack."""
    slack=max(0.,length-min(length,clip_duration))
    if varied and slack>0:
        offset=slack*((.5+index*.618033988749895)%1)
        return start+offset,min(clip_duration,length-offset)
    if varied and length>2:
        # Short background: rotate its loop so even long clips don't share an opening.
        offset=(length*.75)*((.5+index*.618033988749895)%1)
        return start+offset,length-offset
    return start,length
