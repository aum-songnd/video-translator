from pathlib import Path
import asyncio
import hashlib
import json
import shutil
import subprocess
import time
import wave
from urllib.parse import urlparse

try:
    import av
    _orig_av_open = av.open
    def _patched_av_open(*args, metadata_errors=None, **kwargs):
        return _orig_av_open(*args, **kwargs)
    av.open = _patched_av_open
except Exception:
    pass


def run(args, cwd=None):
    p = subprocess.run([str(x) for x in args], cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if p.returncode:
        raise RuntimeError(p.stderr[-5000:] or p.stdout[-5000:])
    return p.stdout


def stamp(seconds):
    ms = max(0, round(seconds * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'


def save(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def srt(rows, key, path):
    path.write_text('\n\n'.join(f'{i}\n{stamp(r["start"])} --> {stamp(r["end"])}\n{r[key].strip()}' for i, r in enumerate(rows, 1)) + '\n', encoding='utf-8')


def retry(fn):
    for attempt in range(4):
        try:
            return fn()
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def tempo_chain(rate):
    parts = []
    while rate > 2:
        parts.append('atempo=2')
        rate /= 2
    parts.append(f'atempo={max(0.5, rate):.8f}')
    return ','.join(parts)


def silence(out, frames):
    block = bytes(48000 * 2)
    while frames > 0:
        n = min(frames, 48000)
        out.writeframesraw(block[:n * 2])
        frames -= n


def synthesize_tts(text, voice, target_mp3, log=print):
    temp = target_mp3.with_suffix('.part.mp3')
    if temp.exists():
        try:
            temp.unlink()
        except OSError:
            pass

    import edge_tts
    alt_voice = 'vi-VN-NamMinhNeural' if 'HoaiMy' in voice else 'vi-VN-HoaiMyNeural'

    for cycle in range(5):
        # 1. Primary: edge_tts with requested voice
        try:
            asyncio.run(edge_tts.Communicate(text, voice).save(str(temp)))
            if temp.exists() and temp.stat().st_size > 200:
                temp.replace(target_mp3)
                return
        except Exception:
            if temp.exists():
                try:
                    temp.unlink()
                except OSError:
                    pass

        # 2. Secondary: alternate edge_tts voice
        try:
            asyncio.run(edge_tts.Communicate(text, alt_voice).save(str(temp)))
            if temp.exists() and temp.stat().st_size > 200:
                temp.replace(target_mp3)
                return
        except Exception:
            if temp.exists():
                try:
                    temp.unlink()
                except OSError:
                    pass

        # 3. Tertiary: Google TTS fallback
        try:
            r = requests.get(
                'https://translate.google.com/translate_tts',
                params={'ie': 'UTF-8', 'q': text, 'tl': 'vi', 'client': 'tw-ob'},
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'},
                timeout=10
            )
            if r.status_code == 200 and len(r.content) > 100:
                temp.write_bytes(r.content)
                temp.replace(target_mp3)
                return
        except Exception:
            if temp.exists():
                try:
                    temp.unlink()
                except OSError:
                    pass

        if cycle < 4:
            wait = min(2 * (cycle + 1), 8)
            log(f'Máy chủ giọng đọc bận; đang tự động thử lại sau {wait}s…')
            time.sleep(wait)

    # 4. Fallback: generate silence so process() never crashes
    log(f'Cảnh báo: Không thể tải giọng câu "{text[:30]}", dùng khoảng lặng thay thế.')
    run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=24000:cl=mono', '-t', '1.0', '-q:a', '9', '-acodec', 'libmp3lame', str(target_mp3)])


def build_timeline(rows, folder, duration, log):
    target = folder / 'dub.wav'
    warnings = []
    with wave.open(str(target), 'wb') as out:
        out.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
        cursor = 0
        total = round(duration * 24000)
        for i, row in enumerate(rows):
            log(f'Giọng đọc {i + 1}/{len(rows)}')
            start = max(cursor, round(row['start'] * 24000))
            end_time = min(duration, rows[i + 1]['start'] if i + 1 < len(rows) else duration)
            end = round(end_time * 24000)
            if end <= start or not row['vi'].strip():
                continue
            fingerprint = hashlib.sha256((row['_voice'] + '\0' + row['vi']).encode('utf-8')).hexdigest()[:16]
            mp3 = folder / f'voice_{i:05}_{fingerprint}.mp3'
            if not mp3.exists() or mp3.stat().st_size < 200:
                synthesize_tts(row['vi'], row['_voice'], mp3, log=log)
                time.sleep(0.15)
            natural = float(run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', mp3]).strip())
            available = (end - start) / 24000
            speed = max(1, natural / available)
            if speed > 1.5:
                warnings.append(f'Câu {i+1}: tăng tốc {speed:.2f}x; nên rút gọn bản dịch.')
            clip = folder / 'clip.wav'
            run(['ffmpeg', '-v', 'error', '-y', '-i', mp3, '-af', tempo_chain(speed), '-ar', '24000', '-ac', '1', '-c:a', 'pcm_s16le', clip])
            silence(out, start - cursor)
            cursor = start
            with wave.open(str(clip), 'rb') as src:
                remaining = end - start
                while remaining > 0:
                    data = src.readframes(min(remaining, 24000))
                    if not data:
                        break
                    out.writeframesraw(data)
                    n = len(data) // 2
                    remaining -= n
                    cursor += n
        silence(out, total - cursor)
    (folder / 'warnings.txt').write_text('\n'.join(warnings) or 'Không có cảnh báo đồng bộ.', encoding='utf-8')
    return target


import re


def extract_source_url(source):
    source = (source or '').strip()
    if Path(source).is_file():
        return source
    match = re.search(r'https?://[^\s]+', source)
    if match:
        return match.group(0).rstrip('!?,.;"\'，。！？')
    return source


def get_browser_cookies(log=print):
    for b in ['chrome', 'firefox', 'chromium', 'brave', 'edge']:
        try:
            import yt_dlp
            with yt_dlp.YoutubeDL({'cookiesfrombrowser': (b, None, None, None), 'quiet': True}) as ydl:
                if ydl.cookiejar and len(ydl.cookiejar) > 0:
                    log(f'Tự động lấy cookies từ trình duyệt {b}…')
                    return (b, None, None, None)
        except Exception:
            continue
    return None


import base64
import requests


def download_douyin(url, target_path, log=print):
    log('Đang kết nối cổng tải Douyin tự động…')
    s = requests.Session()
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
        'Referer': 'https://snapdouyin.app/'
    })
    s.get('https://snapdouyin.app/', timeout=10)
    salt = 'aio-dl'
    hash_val = base64.b64encode(url.encode()).decode() + str(len(url) + 1000) + base64.b64encode(salt.encode()).decode()
    payload = {'url': url, 'token': '', 'hash': hash_val}
    resp = s.post('https://snapdouyin.app/wp-json/mx-downloader/video-data/', data=payload, timeout=15)
    data = resp.json()
    medias = [m for m in data.get('medias', []) if m.get('videoAvailable') and m.get('extension') == 'mp4']
    if not medias:
        raise RuntimeError('Không tìm thấy link video Douyin từ dịch vụ tải.')
    
    candidates = []
    if len(medias) > 1:
        candidates.append(medias[1])
    candidates.append(medias[0])
    for m in medias[2:]:
        candidates.append(m)

    temp_path = target_path.with_suffix('.download.part')
    last_err = None

    for idx, media in enumerate(candidates):
        dl_url = media['url']
        sz = media.get('formattedSize', '')
        q = media.get('quality', '')
        log(f'Bắt đầu tải video Douyin ({sz} - {q})…')
        try:
            r_file = s.get(dl_url, stream=True, timeout=30)
            if r_file.status_code != 200:
                continue
            downloaded = 0
            t0 = time.time()
            with open(temp_path, 'wb') as f:
                for chunk in r_file.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if time.time() - t0 > 1.2:
                            mb = downloaded / (1024 * 1024)
                            log(f'Đã tải {mb:.1f} MB…')
                            t0 = time.time()
            if downloaded > 10240:
                temp_path.replace(target_path)
                log(f'Tải video Douyin hoàn tất ({downloaded / (1024 * 1024):.1f} MB).')
                return target_path
            else:
                if temp_path.exists():
                    temp_path.unlink()
        except Exception as e:
            last_err = e
            if temp_path.exists():
                temp_path.unlink()
            continue

    raise RuntimeError(f'Tải video Douyin thất bại: {last_err or "Dữ liệu trả về rỗng"}')


def translate_text_single(text, source='zh-CN', target='vi', session=None):
    if not text or not text.strip():
        return ''
    text = text.strip()

    # 1. Google Translate via client=dict-chrome-ex (bypasses 429 on translate.google.com/m)
    try:
        s = session or requests.Session()
        r = s.get(
            'https://translate.googleapis.com/translate_a/single',
            params={'client': 'dict-chrome-ex', 'sl': source, 'tl': target, 'dt': 't', 'q': text},
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'},
            timeout=8
        )
        if r.status_code == 200:
            data = r.json()
            if data and data[0]:
                res = ''.join(part[0] for part in data[0] if part and part[0]).strip()
                if res:
                    return res
    except Exception:
        pass

    # 2. MyMemory API fallback
    try:
        s = session or requests.Session()
        langpair = f'{source}|vi-VN' if target == 'vi' else f'{source}|{target}'
        r = s.get(
            'https://api.mymemory.translated.net/get',
            params={'q': text, 'langpair': langpair},
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'},
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            res = data.get('responseData', {}).get('translatedText', '').strip()
            if res and not res.upper().startswith('MYMEMORY WARNING'):
                return res
    except Exception:
        pass

    # 3. deep_translator GoogleTranslator fallback
    try:
        from deep_translator import GoogleTranslator
        res = GoogleTranslator(source=source, target=target).translate(text)
        if res and res.strip():
            return res.strip()
    except Exception:
        pass

    # 4. deep_translator MyMemory fallback
    try:
        from deep_translator import MyMemoryTranslator
        res = MyMemoryTranslator(source=source, target='vi-VN' if target == 'vi' else target).translate(text)
        if res and res.strip():
            return res.strip()
    except Exception:
        pass

    raise RuntimeError(f'Dịch thất bại cho đoạn văn: "{text[:40]}"')


def translate_rows(rows, transcript_path, source='zh-CN', target='vi', log=print):
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })

    untranslated_indices = [i for i, r in enumerate(rows) if not r.get('vi', '').strip()]
    if not untranslated_indices:
        return

    batch_size = 15
    for b_start in range(0, len(untranslated_indices), batch_size):
        batch_indices = untranslated_indices[b_start : b_start + batch_size]
        start_idx = batch_indices[0] + 1
        end_idx = batch_indices[-1] + 1
        log(f'Dịch {start_idx}–{end_idx}/{len(rows)}')

        batch_texts = [rows[i]['zh'].replace('\r', ' ').replace('\n', ' ').strip() for i in batch_indices]
        combined = '\n'.join(batch_texts)
        batch_ok = False

        try:
            r = session.get(
                'https://translate.googleapis.com/translate_a/single',
                params={'client': 'dict-chrome-ex', 'sl': source, 'tl': target, 'dt': 't', 'q': combined},
                timeout=12
            )
            if r.status_code == 200:
                data = r.json()
                if data and data[0]:
                    full_translated = ''.join(part[0] for part in data[0] if part and part[0])
                    lines = [l.strip() for l in full_translated.split('\n')]
                    if len(lines) == len(batch_indices):
                        for idx, trans_line in zip(batch_indices, lines):
                            rows[idx]['vi'] = trans_line or rows[idx]['zh']
                        save(transcript_path, rows)
                        batch_ok = True
        except Exception:
            pass

        if not batch_ok:
            for idx in batch_indices:
                zh_text = rows[idx]['zh']
                trans = retry(lambda: translate_text_single(zh_text, source=source, target=target, session=session))
                rows[idx]['vi'] = trans or zh_text
                save(transcript_path, rows)
                time.sleep(0.05)

        time.sleep(0.05)


def process(source, output, model='small', voice='vi-VN-HoaiMyNeural', cookies='', burn=False, original_volume=0.0, log=print):
    source = extract_source_url(source)
    for tool in ['ffmpeg', 'ffprobe']:
        if not shutil.which(tool):
            raise RuntimeError(f'Chưa cài {tool}, hoặc chưa thêm vào PATH. Xem README.md.')
    folder = Path(output).expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)
    marker = folder / 'job.json'
    identity = {'source': source, 'model': model, 'voice': voice}
    if marker.exists() and json.loads(marker.read_text(encoding='utf-8')) != identity:
        raise ValueError('Thư mục đã chứa công việc khác. Hãy chọn thư mục kết quả mới.')
    save(marker, identity)
    if urlparse(source).scheme in ('http', 'https'):
        video = folder / 'source.mkv'
        if video.exists() and video.stat().st_size == 0:
            video.unlink()
        if not video.exists():
            is_douyin = any(d in source.lower() for d in ['douyin.com', 'iesdouyin.com'])
            downloaded_ok = False
            if is_douyin:
                try:
                    download_douyin(source, video, log=log)
                    downloaded_ok = True
                except Exception as e_dy:
                    log(f'Cổng tải Douyin tự động gặp sự cố ({e_dy}), đang chuyển sang thử yt-dlp…')
            if not downloaded_ok:
                log('Đang tải video bằng yt-dlp…')
                import yt_dlp
                opts = {'outtmpl': str(folder / 'download.%(ext)s'), 'noplaylist': True, 'format': 'bv*+ba/b', 'merge_output_format': 'mkv', 'quiet': True}
                if cookies:
                    opts['cookiefile'] = str(Path(cookies).resolve())
                else:
                    browser_cookies = get_browser_cookies(log)
                    if browser_cookies:
                        opts['cookiesfrombrowser'] = browser_cookies
                try:
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        info = ydl.extract_info(source, download=True)
                        candidates = [Path(ydl.prepare_filename(info)).with_suffix('.mkv'), Path(ydl.prepare_filename(info))]
                    downloaded = next((p for p in candidates if p.is_file()), None)
                    if downloaded is None:
                        raise RuntimeError('Không tìm thấy file sau khi tải. Xem thư mục kết quả.')
                    downloaded.replace(video)
                except Exception as exc:
                    if not is_douyin and any(d in str(exc).lower() for d in ['douyin', '403']):
                        log('yt-dlp bị chặn, đang chuyển sang cổng tải Douyin tự động…')
                        download_douyin(source, video, log=log)
                    else:
                        raise
    else:
        video = Path(source).expanduser().resolve()
        if not video.is_file():
            raise ValueError('Không tìm thấy file video.')
    probe = json.loads(run(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', video]))
    if not any(s['codec_type'] == 'video' for s in probe['streams']):
        raise ValueError('Nguồn không có hình ảnh video.')
    duration = float(probe['format']['duration'])
    if not any(s['codec_type'] == 'audio' for s in probe['streams']):
        raise ValueError('Video không có âm thanh để nhận diện.')
    transcript = folder / 'segments.json'
    if transcript.exists():
        rows = json.loads(transcript.read_text(encoding='utf-8'))
    else:
        log('Đang nhận diện tiếng Trung; lần đầu cần tải mô hình Whisper…')
        from faster_whisper import WhisperModel
        engine = WhisperModel(model, device='cpu', compute_type='int8')
        segments, _ = engine.transcribe(str(video), language='zh', task='transcribe', vad_filter=True, beam_size=5)
        rows = []
        for s in segments:
            if s.text.strip() and s.end > s.start:
                rows.append({'start': max(0, s.start), 'end': min(duration, s.end), 'zh': s.text.strip(), 'vi': ''})
                log(f'Nhận diện: {s.end:.0f}/{duration:.0f} giây')
        save(transcript, rows)
    if not rows:
        raise ValueError('Không nhận diện được lời nói. Thử model medium/large-v3 hoặc kiểm tra âm thanh.')
    translate_rows(rows, transcript, source='zh-CN', target='vi', log=log)
    srt(rows, 'zh', folder / 'zh.srt')
    srt(rows, 'vi', folder / 'vi.srt')
    audio = build_timeline([dict(r, _voice=voice) for r in rows], folder, duration, log)
    log('Đang ghép video…')
    args = ['ffmpeg', '-v', 'error', '-y', '-i', video, '-i', audio, '-i', folder / 'vi.srt']
    if original_volume > 0:
        args += ['-filter_complex', f'[0:a:0]volume={original_volume}[bg];[bg][1:a:0]amix=inputs=2:duration=longest:normalize=0[a]', '-map', '0:v:0', '-map', '[a]']
    else:
        args += ['-map', '0:v:0', '-map', '1:a:0']
    args += ['-map', '2:0', '-c:v', 'libx264', '-preset', 'fast', '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-c:s', 'mov_text', '-metadata:s:s:0', 'language=vie', '-disposition:s:0', 'default', '-t', str(duration), '-movflags', '+faststart']
    if burn:
        args += ['-vf', "subtitles=vi.srt:force_style='FontName=DejaVu Sans,FontSize=24,PrimaryColour=&H00FFFFFF,BackColour=&H00000000,BorderStyle=3,Outline=4,MarginV=12'"]
    args += [folder / 'translated.mp4']
    run(args, cwd=folder)
    log(f'Hoàn tất: {folder / "translated.mp4"}')
    return folder
