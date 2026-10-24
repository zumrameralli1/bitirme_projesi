import csv
import subprocess
from pathlib import Path

import fitz

REPORT = Path("data/review_report.csv")
RAW = Path("data/raw")
OUTPUT = Path("data/ocr_output")
OUTPUT.mkdir(parents=True, exist_ok=True)

with REPORT.open("r", encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))

results = []

for row in rows:
    file_type = row.get("file_type", "").lower()
    try:
        chars = int(row.get("extracted_chars") or 0)
    except ValueError:
        chars = 0

    if chars != 0 or file_type not in (".pdf", ".png"):
        continue

    source = RAW / row["filename"]
    if not source.is_file():
        results.append({
            "filename": row["filename"],
            "status": "DOSYA BULUNAMADI",
            "characters": 0,
            "output": ""
        })
        continue

    texts = []
    try:
        if file_type == ".pdf":
            doc = fitz.open(source)
            for page_number, page in enumerate(doc, start=1):
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                image_path = OUTPUT / f"page_{row['document_id']}_{page_number}.png"
                pix.save(image_path)

                run = subprocess.run(
                    ["tesseract", str(image_path), "stdout", "-l", "tur"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                texts.append(f"--- Sayfa {page_number} ---\n{run.stdout.strip()}")
        else:
            run = subprocess.run(
                ["tesseract", str(source), "stdout", "-l", "tur"],
                capture_output=True,
                text=True,
                check=True,
            )
            texts.append(run.stdout.strip())

        text = "\n\n".join(texts).strip()
        text_path = OUTPUT / f"{row['document_id']}.txt"
        text_path.write_text(text, encoding="utf-8")

        results.append({
            "filename": row["filename"],
            "status": "OCR TAMAM" if text else "METİN BULUNAMADI",
            "characters": len(text),
            "output": str(text_path)
        })

    except Exception as e:
        results.append({
            "filename": row["filename"],
            "status": f"HATA: {e}",
            "characters": 0,
            "output": ""
        })

report_path = OUTPUT / "ocr_report.csv"
with report_path.open("w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(
        f, fieldnames=["filename", "status", "characters", "output"]
    )
    writer.writeheader()
    writer.writerows(results)

print(f"İşlenen dosya: {len(results)}")
print(f"OCR tamam: {sum(r['status'] == 'OCR TAMAM' for r in results)}")
print(f"Metin bulunamadı: {sum(r['status'] == 'METİN BULUNAMADI' for r in results)}")
print(f"Hata veya eksik dosya: {sum(r['status'].startswith(('HATA:', 'DOSYA BULUNAMADI')) for r in results)}")
print(f"Rapor: {report_path}")
print("Not: OCR metinleri doğrulanmadan öğrenci bilgi tabanına eklenmemelidir.")
