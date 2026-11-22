"""Actual FFmpeg roundtrip: split layout, silent ad, resumption and watermark."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from PIL import Image
from viralcut import composition as c, utils


class CompositionTests(unittest.TestCase):
    def test_varied_segments_are_stable_and_stay_inside_gameplay(self):
        segments=[c.choose_game_segment(30,180,40,i) for i in range(10)]
        self.assertEqual(len({round(start,3) for start,_ in segments}),10)
        self.assertEqual(segments[0],(100,40))
        self.assertEqual(segments[3],c.choose_game_segment(30,180,40,3))
        for start,length in segments:
            self.assertGreaterEqual(start,30)
            self.assertLessEqual(start+length,210)
        self.assertEqual(c.choose_game_segment(30,180,40,9,False),(30,180))

    def test_youtube_import_uses_middle_of_source(self):
        from viralcut import main, downloader
        with TemporaryDirectory() as tmp, patch.object(c, 'ASSETS', Path(tmp)), \
                patch.object(downloader, 'probe', return_value={'duration': 1200}), \
                patch.object(downloader, 'download_section') as download:
            def fake_download(url, directory, start, end, **kwargs):
                path=directory/'game.mp4';path.write_bytes(b'test');return path
            download.side_effect=fake_download
            result=main.import_game(main.GameImportIn(video_id='abcdefghijk'))
            self.assertEqual(download.call_args.args[2:4],(510.,690.))
            self.assertTrue(c.asset(result['id']).is_file())

    def test_asset_paths_cannot_escape_library(self):
        for name in ('../../private.mp4', '/tmp/file.mp4', 'a.mp4'):
            with self.assertRaises(ValueError):
                c.asset(name)

    def test_combined_render_both_positions(self):
        with TemporaryDirectory() as tmp, patch.object(c, 'ASSETS', Path(tmp)):
            root=Path(tmp)
            game=root/('a'*32+'.mp4'); ad=root/('b'*32+'.mp4'); logo=root/('c'*32+'.png')
            def video(path, color, duration, audio=False):
                args=['-f','lavfi','-i',f'color=c={color}:s=320x568:r=30:d={duration}']
                if audio:
                    args+=['-f','lavfi','-i',f'sine=frequency=440:duration={duration}']
                c.encode(args+['-t',str(duration)],path)
            video(game,'blue',1); video(ad,'green',1)
            Image.new('RGBA',(100,50),(255,0,0,170)).save(logo)
            def pixel(path,t,x,y):
                import subprocess
                data=subprocess.check_output([c.ffmpeg(),'-v','error','-ss',str(t),'-i',str(path),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'])
                i=(y*320+x)*3
                return tuple(data[i:i+3])
            for position in ('top','bottom'):
                out=root/(position+'.mp4');video(out,'black',4,True)
                report=c.apply(out,{'game':game.name,'ad':ad.name,'logo':logo.name,'game_position':position})
                info=utils.probe(out)
                self.assertAlmostEqual(info['duration'],5,delta=.15)
                self.assertTrue(info['has_audio'])
                self.assertEqual(report['ad_at'],2)
                # Green advertisement at the insertion; blue game returns afterwards.
                r,g,b=pixel(out,2.5,160,284)
                self.assertGreater(g,r+40);self.assertGreater(g,b+40)
                y=100 if position=='top' else 450
                r,g,b=pixel(out,4.5,160,y)
                self.assertGreater(b,r+80)
