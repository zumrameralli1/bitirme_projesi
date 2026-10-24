import fitz
import subprocess
from pathlib import Path

pdf_path = Path(
    "data/raw/bakırçay data/bakırçay data-katkı payı/"
    "Katkı_Payı_Nasıl_Ödenir.pdf"
)
out_dir = Path("data/ocr_test")
out_dir.mkdir(parents=True, exist_ok=True)

doc = fitz.open(pdf_path)
all_text = []

for i, page in enumerate(doc, start=1):
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
    image_path = out_dir / f"katki_sayfa_{i}.png"
    pix.save(image_path)

    result = subprocess.run(
        ["tesseract", str(image_path), "stdout", "-l", "tur"],
        capture_output=True,
        text=True,
        check=True,
    )

    text = result.stdout.strip()
    all_text.append(f"--- SAYFA {i} ---\n{text}")
    print(f"Sayfa {i}: {len(text)} karakter")

output_path = out_dir / "katki_ocr.txt"
output_path.write_text("\n\n".join(all_text), encoding="utf-8")
print(f"\nOCR tamamlandı: {output_path}")
