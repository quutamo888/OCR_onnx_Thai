'''OneOCR example — อ่านข้อความ (รวมไทย) จากรูป

usage:
    python example.py <path รูป>          # พิมพ์ข้อความออกจอ
    python example.py <path รูป> -o out.txt
'''
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'oneocr'))
from PIL import Image  # noqa: E402
import oneocr  # noqa: E402


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    image_path = sys.argv[1]
    out_path = sys.argv[sys.argv.index('-o') + 1] if '-o' in sys.argv else None

    engine = oneocr.OcrEngine()  # โหลดโมเดล ~0.8 วิ (ครั้งเดียวต่อโปรแกรม)
    result = engine.recognize_pil(Image.open(image_path))

    if 'error' in result:
        print(f'ERROR: {result["error"]}')
        sys.exit(1)

    if out_path:
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(result['text'])
        print(f'saved: {out_path} ({len(result["lines"])} lines)')
    else:
        print(result['text'])


if __name__ == '__main__':
    main()
