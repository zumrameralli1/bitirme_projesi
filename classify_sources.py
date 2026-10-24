import csv
from pathlib import Path

source = Path("data/sources.csv")
output = Path("data/review_report.csv")

with source.open("r", encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)
    rows = list(reader)

review_flags = []
for row in rows:
    flags = (row.get("review_flags") or "").strip()
    flags_lower = flags.lower()
    reasons = []

    if "staff_content_review_before_student_release" in flags_lower:
        reasons.append("Personel içeriği; öğrenciye açılmadan önce incele")

    if "exact_duplicate_of:" in flags_lower:
        reasons.append("Olası kopya; asıl dosyayla karşılaştır")

    if "image_ocr_or_manual_check" in flags_lower:
        reasons.append("Taranmış/görsel belge; metni kontrol et")

    if "legacy_doc_convert_to_docx_or_pdf" in flags_lower:
        reasons.append("Eski DOC formatı; dönüşüm ve içerik kontrolü gerekli")

    if "category_review" in flags_lower:
        reasons.append("Kategori önerisini kontrol et")

    try:
        chars = int(row.get("extracted_chars") or 0)
    except ValueError:
        chars = 0

    if chars == 0:
        reasons.append("Çıkarılmış metin yok veya boş; dosyayı kontrol et")

    if reasons:
        decision = "İNCELEME GEREKİYOR"
    else:
        decision = "ADAY — RESMÎLİK VE GÜNCELLİK DOĞRULANMALI"

    new_row = dict(row)
    new_row["review_decision"] = decision
    new_row["review_reason"] = "; ".join(reasons) if reasons else (
        "Otomatik kontrolde belirgin inceleme bayrağı yok"
    )
    review_flags.append(new_row)

fieldnames = list(rows[0].keys()) + ["review_decision", "review_reason"] if rows else []
with output.open("w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(review_flags)

counts = {}
for row in review_flags:
    decision = row["review_decision"]
    counts[decision] = counts.get(decision, 0) + 1

print(f"Toplam kayıt: {len(rows)}")
for decision, count in counts.items():
    print(f"{decision}: {count}")
print(f"Rapor oluşturuldu: {output}")
print("Not: Bu rapor hukuki güncelliği veya resmîliği doğrulamaz.")
