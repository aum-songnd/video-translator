"""Offline media integration: fake only external ML/translation/TTS services."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
from core import process, run, stamp, tempo_chain, extract_source_url, download_douyin


class PipelineTest(unittest.TestCase):
    def test_extract_source_url(self):
        raw = "1.05 GIv:/ J@i.CH 原创《我不吃泡菜》 https://v.douyin.com/e5C_T0shKNE/ 复制此链接，打开Dou音搜索，直接观看视频！"
        self.assertEqual(extract_source_url(raw), "https://v.douyin.com/e5C_T0shKNE/")
        self.assertEqual(extract_source_url("https://www.youtube.com/watch?v=123"), "https://www.youtube.com/watch?v=123")

    @patch('core.requests.Session')
    def test_download_douyin_mock(self, mock_session_cls):
        mock_session = mock_session_cls.return_value
        mock_resp = mock_session.post.return_value
        mock_resp.json.return_value = {
            "medias": [{"url": "http://example.com/video.mp4", "videoAvailable": True, "extension": "mp4", "quality": "hd", "formattedSize": "10MB"}]
        }
        mock_file_resp = mock_session.get.return_value
        mock_file_resp.status_code = 200
        mock_file_resp.iter_content.return_value = [b"a" * 15000]
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "test.mp4"
            download_douyin("https://v.douyin.com/test/", target, log=lambda _: None)
            self.assertTrue(target.exists())
            self.assertEqual(target.read_bytes(), b"a" * 15000)

    def test_timestamps(self):
        self.assertEqual(stamp(3661.9996), '01:01:02,000')
        self.assertEqual(stamp(-1), '00:00:00,000')
        self.assertEqual(tempo_chain(8), 'atempo=2,atempo=2,atempo=2.00000000')

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
    def test_real_media_pipeline_and_resume(self):
        class Whisper:
            def __init__(self, *a, **kw):
                pass
            def transcribe(self, *a, **kw):
                return iter([types.SimpleNamespace(start=.2, end=.7, text='你好'), types.SimpleNamespace(start=1.2, end=1.8, text='谢谢')]), None
        class Translator:
            def __init__(self, **kw):
                pass
            def translate(self, text):
                return {'你好': 'Xin chào', '谢谢': 'Cảm ơn'}[text]
        class Voice:
            def __init__(self, *a):
                pass
            async def save(self, path):
                run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=1.4', path])
        modules = {'faster_whisper': types.SimpleNamespace(WhisperModel=Whisper), 'deep_translator': types.SimpleNamespace(GoogleTranslator=Translator), 'edge_tts': types.SimpleNamespace(Communicate=Voice)}
        with tempfile.TemporaryDirectory(prefix='video test ') as tmp:
            base = Path(tmp)
            src = base / 'nguon 中文.mp4'
            run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=blue:s=320x240:d=2.5', '-f', 'lavfi', '-i', 'sine=frequency=220:duration=2.5', '-c:v', 'libx264', '-c:a', 'aac', src])
            with patch.dict(sys.modules, modules), patch('core.time.sleep'):
                out = process(str(src), base / 'ket qua', log=lambda _: None)
                data = json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', out / 'translated.mp4']))
                self.assertEqual({s['codec_type'] for s in data['streams']}, {'video', 'audio', 'subtitle'})
                self.assertLess(abs(float(data['format']['duration']) - 2.5), .15)
                self.assertIn('xin chào', (out / 'vi.srt').read_text(encoding='utf-8').lower())
                process(str(src), out, burn=True, original_volume=.1, log=lambda _: None)
                with self.assertRaises(ValueError):
                    process(str(src), out, model='base', log=lambda _: None)

    def test_translate_text_single(self):
        from core import translate_text_single
        res = translate_text_single('你好')
        self.assertIn('chào', res.lower())

    def test_translate_rows_batch(self):
        from core import translate_rows
        with tempfile.TemporaryDirectory() as tmp:
            t_path = Path(tmp) / 'segments.json'
            rows = [{'start': 0, 'end': 1, 'zh': '你好', 'vi': ''}, {'start': 1, 'end': 2, 'zh': '谢谢', 'vi': ''}]
            translate_rows(rows, t_path, log=lambda _: None)
            self.assertTrue(t_path.exists())
            self.assertTrue(bool(rows[0]['vi']))
            self.assertTrue(bool(rows[1]['vi']))
            self.assertIn('chào', rows[0]['vi'].lower())


if __name__ == '__main__':
    unittest.main()
