import queue
import re
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from datetime import datetime
from core import process


def main():
    root = tk.Tk()
    root.title('Dịch video Trung → Việt')
    root.geometry('860x670')
    panel = ttk.Frame(root, padding=18)
    panel.pack(fill='both', expand=True)
    ttk.Label(panel, text='Dịch video Trung → Việt', font=('', 20, 'bold')).pack(anchor='w')
    ttk.Label(panel, text='File hoặc URL • Phụ đề + giọng Việt • CPU • Cần Internet cho dịch và giọng đọc').pack(anchor='w', pady=8)
    source = tk.StringVar()
    output = tk.StringVar(value=str(Path.cwd() / 'outputs' / datetime.now().strftime('%Y%m%d-%H%M%S')))
    cookies = tk.StringVar()
    model = tk.StringVar(value='small')
    voice = tk.StringVar(value='vi-VN-HoaiMyNeural')
    burn = tk.BooleanVar(value=True)
    volume = tk.DoubleVar(value=0)
    for label, var, action in [
        ('File video hoặc URL (tự động nhận diện link khi dán cả văn bản chia sẻ)', source, lambda: source.set(filedialog.askopenfilename() or source.get())),
        ('Thư mục kết quả (mỗi video một thư mục riêng)', output, lambda: output.set(filedialog.askdirectory() or output.get())),
        ('Cookie Netscape .txt (tùy chọn; tự động lấy từ Chrome/Firefox nếu để trống)', cookies, lambda: cookies.set(filedialog.askopenfilename(filetypes=[('Cookies', '*.txt')]) or cookies.get()))]:
        ttk.Label(panel, text=label).pack(anchor='w', pady=(8, 2))
        row = ttk.Frame(panel)
        row.pack(fill='x')
        ttk.Entry(row, textvariable=var).pack(side='left', fill='x', expand=True)
        ttk.Button(row, text='Chọn…', command=action).pack(side='right', padx=(6, 0))
    options = ttk.Frame(panel)
    options.pack(fill='x', pady=12)
    ttk.Label(options, text='Whisper:').pack(side='left')
    ttk.Combobox(options, textvariable=model, values=['tiny', 'base', 'small', 'medium', 'large-v3'], state='readonly', width=12).pack(side='left', padx=6)
    ttk.Label(options, text='Giọng:').pack(side='left', padx=6)
    ttk.Combobox(options, textvariable=voice, values=['vi-VN-HoaiMyNeural', 'vi-VN-NamMinhNeural'], state='readonly', width=26).pack(side='left')
    ttk.Checkbutton(panel, text='Ghi đè phụ đề tiếng Việt lên video (có khung nền che chữ Trung)', variable=burn).pack(anchor='w')
    ttk.Label(panel, text='Âm lượng gốc: 0 = bỏ tiếng Trung; tăng lên sẽ giữ cả lời gốc và nhạc').pack(anchor='w', pady=(8, 0))
    ttk.Scale(panel, from_=0, to=0.3, variable=volume).pack(fill='x')
    messages = queue.Queue()
    logbox = tk.Text(panel, height=12, state='disabled', wrap='word')
    busy = [False]
    def start():
        raw_source = source.get().strip()
        m = re.search(r'https?://[^\s]+', raw_source)
        if m and not Path(raw_source).is_file():
            clean_url = m.group(0).rstrip('!?,.;"\'，。！？')
            source.set(clean_url)
        if not source.get().strip() or not output.get().strip():
            messagebox.showerror('Thiếu thông tin', 'Chọn file hoặc nhập URL và thư mục kết quả.')
            return
        config = dict(source=source.get().strip(), output=output.get().strip(), model=model.get(), voice=voice.get(), cookies=cookies.get().strip(), burn=burn.get(), original_volume=volume.get())
        busy[0] = True
        button.configure(state='disabled')
        def worker():
            max_auto_retries = 8
            for attempt in range(max_auto_retries):
                try:
                    process(**config, log=lambda text: messages.put(('log', text)))
                    messages.put(('done', config['output']))
                    return
                except Exception as exc:
                    err_msg = str(exc)
                    is_transient = any(k in err_msg.lower() for k in [
                        'audio', 'connect', 'timeout', 'network', 'reset', '429', '503', '502', '504',
                        'websocket', 'http', 'ssl', 'eof', 'broken pipe', 'tải video douyin thất bại',
                        'temporarily unavailable', 'connection closed'
                    ])
                    if attempt < max_auto_retries - 1 and is_transient:
                        wait_sec = min(3 * (attempt + 1), 12)
                        messages.put(('log', f'⚠️ Gián đoạn kết nối ({err_msg[:60]}…)\n🔄 Đang tự động kết nối lại sau {wait_sec}s (lần {attempt + 1}/{max_auto_retries})…'))
                        time.sleep(wait_sec)
                    else:
                        messages.put(('error', err_msg))
                        return
        threading.Thread(target=worker, daemon=True).start()
    button = ttk.Button(panel, text='Bắt đầu dịch và lồng tiếng', command=start)
    button.pack(fill='x', pady=10)
    logbox.pack(fill='both', expand=True)
    def poll():
        try:
            while True:
                kind, text = messages.get_nowait()
                logbox.configure(state='normal')
                logbox.insert('end', text + '\n')
                logbox.see('end')
                logbox.configure(state='disabled')
                if kind in ('done', 'error'):
                    busy[0] = False
                    button.configure(state='normal')
                    if kind == 'error':
                        messagebox.showerror('Xử lý chưa hoàn tất', text)
                    else:
                        messagebox.showinfo('Hoàn tất', 'Kết quả tại:\n' + text)
        except queue.Empty:
            pass
        root.after(150, poll)
    def close():
        if busy[0]:
            messagebox.showinfo('Đang xử lý', 'Hãy đợi công việc hoàn tất trước khi đóng cửa sổ.')
        else:
            root.destroy()
    root.protocol('WM_DELETE_WINDOW', close)
    poll()
    root.mainloop()


if __name__ == '__main__':
    main()
