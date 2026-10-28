# Dịch video Trung → Việt — bản đầu

Ứng dụng desktop Python chạy Windows / Ubuntu. Nhận file video hoặc URL do yt-dlp hỗ trợ, nhận diện tiếng Trung, dịch sang Việt, tạo giọng Việt, xuất MP4 + SRT. Có CLI để dùng qua terminal hoặc script.

**Không cần API key trả phí. Không phải hoàn toàn offline:** Whisper chạy trên máy (cần tải model lần đầu); Google Translate qua deep-translator và Microsoft Edge TTS cần Internet. Nội dung lời nói được gửi đến dịch vụ dịch / giọng đọc. Dịch vụ miễn phí có thể giới hạn, thay đổi hoặc ngừng hoạt động; không bảo đảm tốc độ hay tính sẵn sàng.

## 1. Cài Windows 10/11

Cài **Python 3.11 hoặc 3.12 64-bit** từ https://www.python.org/downloads/windows/ và chọn Add Python to PATH, giữ thành phần Tcl/Tk.

Cài FFmpeg trong PowerShell (nếu máy có winget):

```powershell
winget install --id Gyan.FFmpeg -e
```

Đóng rồi mở terminal để cập nhật PATH. Giải nén bộ mã vào thư mục, mở PowerShell tại thư mục có `app.py`, chạy:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
ffmpeg -version
ffprobe -version
.\.venv\Scripts\python.exe app.py
```

Nếu dùng Python 3.11, thay `py -3.12` bằng `py -3.11`. Lần sau mở `start-windows.bat`. Không cần bật PowerShell ExecutionPolicy hay activate môi trường.

## 2. Cài Ubuntu 22.04 / 24.04

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-tk ffmpeg fonts-dejavu-core
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

Chạy các lệnh Python bên trong thư mục bộ mã. Lần sau: `bash start-ubuntu.sh`. Giao diện cần Ubuntu Desktop; máy chủ không có màn hình dùng CLI. Python 3.10 trên Ubuntu 22.04 có thể không còn tương thích yt-dlp mới: dùng Python 3.11/3.12 và gói venv/tk tương ứng nếu pip báo không đáp ứng phiên bản. Khuyến nghị Ubuntu 24.04 + Python 3.12.

## 3. Sử dụng

1. Chọn video trên máy **hoặc** dán URL đầy đủ của một video, không dán cả văn bản chia sẻ.
2. Chọn thư mục kết quả riêng cho mỗi video. Không chọn thư mục chứa video gốc.
3. Chọn model `small` để thử. `medium` / `large-v3` thường phù hợp khi cần tăng chất lượng nhưng tốn RAM và chạy CPU chậm hơn. Nên thử clip 30–60 giây trước.
4. Chọn HoaiMy (nữ) hoặc NamMinh (nam).
5. Mặc định bỏ tiếng gốc. Kéo thanh âm lượng nếu muốn giữ âm thanh gốc nhỏ phía dưới giọng đọc; phần này **vẫn chứa lời Trung**, chưa tách riêng nhạc.
6. Có thể chọn ghi phụ đề lên hình; nếu không, MP4 có track phụ đề bật mặc định, dùng VLC để bật/tắt. Một số trình phát không hiển thị track này.
7. Bấm bắt đầu. Chờ log hoàn tất trước khi đóng ứng dụng. Bản này chưa có nút hủy và chỉ xử lý một video mỗi lần.

Kết quả:

- `translated.mp4`: video lồng tiếng Việt, có track phụ đề Việt; nếu chọn ghi lên hình thì có cả phụ đề cố định.
- `vi.srt`, `zh.srt`: phụ đề Việt và Trung.
- `segments.json`: thời gian, lời Trung và bản dịch, có thể sửa thủ công.
- `dub.wav`: giọng Việt đã đặt lên timeline.
- `warnings.txt`: câu nào phải tăng tốc quá 1.5x để vừa thời gian.
- Các file giọng từng câu và file công việc phục vụ chạy tiếp.

Nếu lỗi mạng, chạy lại **cùng nguồn, model, giọng và thư mục kết quả**. Tool dùng lại nhận diện, những câu đã dịch và file giọng đã tạo thành công. Muốn đổi model/giọng hoặc thay video gốc thì chọn thư mục mới. Không ghi đè nội dung video gốc giữa hai lần chạy.

Để sửa bản dịch: đợi tool dừng/hoàn tất, sao lưu rồi sửa các trường `vi` trong `segments.json` bằng trình soạn thảo UTF-8, giữ nguyên cấu trúc JSON và mốc thời gian; chạy lại. Giọng có nội dung sửa được tạo lại tự động. Nếu muốn nhận diện lại, dùng thư mục mới. Không sửa file giữa lúc đang xử lý.

## 4. Link YouTube, TikTok, Douyin và trang Trung Quốc

Bộ tải dựa vào yt-dlp, **không cam kết tải được mọi trang hoặc mọi video**. Khả năng tải từng URL thay đổi theo trang, khu vực, đăng nhập, CAPTCHA và chống bot. Video DRM không được xử lý. Dùng file trên máy khi URL không tải được.

- Cập nhật bộ tải trong đúng môi trường:

```bash
# Ubuntu
.venv/bin/python -m pip install --upgrade "yt-dlp[default]"
```

```powershell
# Windows
.\.venv\Scripts\python.exe -m pip install --upgrade "yt-dlp[default]"
```

- **Tự động nhận diện Cookie từ trình duyệt**: Nếu bạn không chọn file cookie `.txt`, tool sẽ tự động đọc cookies từ trình duyệt có sẵn trên máy (Chrome, Firefox, Edge, Brave...) để tải video từ các trang yêu cầu đăng nhập.
- **Tự động trích xuất link URL**: Bạn có thể dán nguyên văn đoạn chia sẻ từ Douyin/TikTok (có lẫn tiêu đề hoặc chữ tiếng Trung), tool sẽ tự động lọc lấy link sạch.
- **Lưu ý về Douyin và chống bot**: Một số trang như Douyin có cơ chế bảo vệ chống bot nghiêm ngặt (thuật toán chữ ký `a_bogus` / kiểm tra CAPTCHA). Kể cả khi có cookies trình duyệt, yt-dlp vẫn có thể bị chặn tải (lỗi `403 Forbidden` / `Fresh cookies are needed`). Khi gặp trường hợp này, hãy dùng trang web tải video Douyin (như SnapDouyin, TikWM,...) tải file `.mp4` về máy rồi chọn file trực tiếp vào tool.
- Chỉ tải và xử lý nội dung bạn có quyền sử dụng.

## 5. CLI

Ubuntu:

```bash
.venv/bin/python cli.py "/home/user/Videos/phim.mp4" --output "outputs/phim-01"
.venv/bin/python cli.py "https://www.youtube.com/watch?v=VIDEO_ID" --output "outputs/link-01" --cookies "/home/user/cookies.txt" --burn
```

Windows:

```powershell
.\.venv\Scripts\python.exe cli.py "D:\Videos\phim.mp4" --output "D:\KetQua\phim-01" --voice vi-VN-NamMinhNeural
```

Tham số: `--model small`, `--voice vi-VN-HoaiMyNeural`, `--cookies FILE`, `--burn`, `--original-volume 0.1`. Mỗi lần gọi xử lý một nguồn; có thể dùng vòng lặp script để xử lý nhiều file với thư mục đầu ra khác nhau.

## 6. Giới hạn và lỗi thường gặp

- Phụ đề dựa trên **âm thanh**. Không OCR chữ Trung đã in sẵn trên hình, không xóa phụ đề gốc trên hình.
- Nhận diện mặc định ngôn ngữ `zh`; không bảo đảm chất lượng cho tiếng địa phương/Quảng Đông, nhạc, nói chồng, âm thanh nhỏ.
- Dịch từng đoạn nên có thể sai tên riêng, cách xưng hô hoặc ngữ cảnh phim; nên rà soát `vi.srt` / `segments.json` trước khi xuất bản.
- Một giọng cho toàn bộ video, chưa phân vai, không nhân bản giọng và không khớp khẩu hình.
- Mỗi câu đặt tại mốc bắt đầu; khi dài hơn khoảng còn lại đến câu kế tiếp, giọng được tăng tốc để không chồng câu. Câu rất dài có thể khó nghe; xem warnings.txt và rút gọn bản dịch. Không có xử lý trộn lời nhiều người đồng thời.
- Không tách nhạc nền. Muốn giữ nhạc riêng cần thêm bước như Demucs ở phiên bản sau.
- CPU mặc định, không đòi GPU. Video dài có thể mất nhiều thời gian; cần dung lượng trống cho video, model và file âm thanh trung gian.
- Lỗi thiếu FFmpeg: thêm `ffmpeg` và `ffprobe` vào PATH rồi mở lại terminal.
- Lỗi `subtitles`/libass: dùng FFmpeg có libass hoặc bỏ chọn ghi phụ đề lên hình; MP4 vẫn có track phụ đề rời.
- Lỗi 403/429 từ dịch hoặc TTS: đợi rồi chạy lại. Không có bảo đảm mức dùng miễn phí lâu dài.
- Bản đầu là mã nguồn, chưa đóng gói EXE. Chưa có kiểm thử trực tiếp trên Windows trong môi trường tạo bộ mã.

## 7. Kiểm thử và phụ thuộc

```bash
python -m unittest -v
```

Test dùng FFmpeg thật để tạo video tổng hợp, xuất MP4 có audio/subtitle, kiểm tra thời lượng, chế độ ghi phụ đề lên hình, trộn âm gốc, đường dẫn Unicode/có dấu cách và chạy lại. ML, dịch và TTS được giả lập trong test để không gọi mạng. Chưa kiểm chứng end-to-end với video tiếng Trung thật, tải link thật hoặc dịch vụ dịch/TTS trong môi trường tạo mã. Các giới hạn phiên bản trong requirements không phải lockfile đã kiểm thử trên cả hai OS.

Nguồn tài liệu chính:

- https://github.com/SYSTRAN/faster-whisper
- https://github.com/nidhaloff/deep-translator
- https://github.com/rany2/edge-tts
- https://github.com/yt-dlp/yt-dlp
- https://ffmpeg.org/ffmpeg-filters.html
