from pathlib import Path
import json
import unittest
from analyzer import recognize, detect_red_strikes, red_mask, load_image, render_pdf
from core import reconstruct

ROOT=Path(__file__).resolve().parents[1]
class AnalyzerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.image=(ROOT/'fixtures/demo.png').read_bytes()
        cls.demo=json.loads((ROOT/'fixtures/demo.json').read_text(encoding='utf-8'))
    def test_image(self):
        img=load_image(self.image)
        self.assertGreater(img.width,500)
        self.assertTrue(red_mask(img).any())
    def test_stroke_candidates_are_pending(self):
        p=detect_red_strikes(self.image,self.demo['tokens'])
        found={e['target_id'] for e in p}
        self.assertTrue({'t3','t9'}.issubset(found))
        self.assertTrue(all(e['status']=='proposed' for e in p))
    def test_local_chinese_ocr_real(self):
        from shutil import which
        if not which('tesseract'):self.skipTest('Tesseract unavailable')
        r=recognize(self.image,'tesseract',roi=[40,135,940,228])
        observed=''.join(t['text'] for t in r['tokens'])
        self.assertIn('今天',observed)
        self.assertIn('决定',observed)
    def test_ocr_roi(self):
        from shutil import which
        if not which('tesseract'):self.skipTest('Tesseract unavailable')
        r=recognize(self.image,'tesseract',roi=[40,135,940,228]);self.assertEqual(r['roi'],[40,135,940,228])
        self.assertTrue(all(t['bbox'][1]>=135 for t in r['tokens']))
    def test_pdf(self):
        # Fully self-contained one-page PDF fixture; no proprietary test file.
        objs = [
          b"<< /Type /Catalog /Pages 2 0 R >>",
          b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
          b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 150 80] /Contents 4 0 R >>",
          b"<< /Length 0 >>\nstream\n\nendstream",
        ]
        data=bytearray(b"%PDF-1.4\n")
        offsets=[0]
        for i, obj in enumerate(objs, 1):
            offsets.append(len(data))
            data.extend(f"{i} 0 obj\n".encode()+obj+b"\nendobj\n")
        xref_at=len(data)
        data.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
        for offset in offsets[1:]:
            data.extend(f"{offset:010} 00000 n \n".encode())
        data.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode())
        pages=render_pdf(bytes(data))
        self.assertEqual(len(pages),1)
        self.assertTrue(pages[0]['data'].startswith(b'\x89PNG'))

    def test_pdf_rejects_non_pdf(self):
        from core import ManuscriptError
        with self.assertRaises(ManuscriptError):
            render_pdf(b'not a pdf')

if __name__=='__main__':unittest.main()
