import argparse
from core import process

p = argparse.ArgumentParser(description='Dịch và lồng tiếng video Trung → Việt')
p.add_argument('source', help='File video hoặc URL')
p.add_argument('--output', required=True, help='Thư mục riêng cho video này')
p.add_argument('--model', default='small', choices=['tiny', 'base', 'small', 'medium', 'large-v3'])
p.add_argument('--voice', default='vi-VN-HoaiMyNeural', choices=['vi-VN-HoaiMyNeural', 'vi-VN-NamMinhNeural'])
p.add_argument('--cookies', default='', help='File cookies định dạng Netscape')
p.add_argument('--burn', action='store_true', help='Ghi phụ đề lên hình')
p.add_argument('--original-volume', type=float, default=0, choices=None)
if __name__ == '__main__':
    a = p.parse_args()
    if not 0 <= a.original_volume <= 1:
        p.error('--original-volume phải từ 0 đến 1')
    try:
        process(a.source, a.output, a.model, a.voice, a.cookies, a.burn, a.original_volume)
    except Exception as exc:
        p.exit(1, f'Lỗi: {exc}\n')
