import json
import re
from pathlib import Path

BASE = Path("data/rag_seed")
OUTPUT = BASE / "chunks.jsonl"
MAX_CHARS = 2400

DOCS = {
    "cap_yandal": {
        "title": "Çift Anadal ve Yan Dal Programları Yönergesi",
        "url": "https://oidb.bakircay.edu.tr/Yuklenenler/%C3%87ift_Anadal_ve_Yan_dal_Programla.2025-%2834-01%29%20senato%20karar%C4%B1.pdf",
    },
    "diploma": {
        "title": "Diploma, Diploma Eki ve Diğer Belgelerin Düzenlenmesine İlişkin Yönerge",
        "url": "https://oidb.bakircay.edu.tr/Yuklenenler/Diploma_Diploma_Eki_ve_Di%C4%9Fer_26_.2025%2834-03%29.pdf",
    },
    "katki_payi_2026_2027": {
        "title": "2026-2027 Eğitim-Öğretim Yılı Dönemlik Katkı Payı Ücretleri",
        "url": "https://oidb.bakircay.edu.tr/upload/sayfa/1713/2026-2027_katki_paylari_pdf.pdf",
    },
}

BOUNDARY = re.compile(
    r"(?im)^(?="
    r"(?:BİRİNCİ|İKİNCİ|ÜÇÜNCÜ|DÖRDÜNCÜ|BEŞİNCİ)\s+BÖLÜM\b"
    r"|MADDE\s+\d+\s*[–-]"
    r"|Madde\s+\d+\s*[–-]"
    r"|Amaç ve Kapsam|Amaç|Kapsam|Dayanak|Tanımlar|Genel İlkeler"
    r"|Yürürlük|Yürütme|Hüküm Bulunmayan Haller"
    r")"
)

def split_sections(text):
    text = re.sub(r"\[Sayfa\s+\d+\]", "\n", text)
    # Kaynak dosyası başındaki envanter metaverisini kaldır.
    text = re.sub(
        r"(?s)^.*?(?=\n\s*(?:T\.C\.|İZMİR BAKIRÇAY ÜNİVERSİTESİ))",
        "",
        text,
        count=1,
    )
    matches = list(BOUNDARY.finditer(text))
    if not matches:
        return [text.strip()] if text.strip() else []

    sections = []
    if text[:matches[0].start()].strip():
        sections.append(text[:matches[0].start()].strip())

    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        section = text[match.start():end].strip()
        if section:
            sections.append(section)

    # Çok kısa bölüm başlıklarını bir sonraki bölümle birleştir.
    merged = []
    i = 0
    while i < len(sections):
        current = sections[i]
        is_heading_only = (
            len(current) < 80
            and re.search(r"(?i)\bBÖLÜM\b", current)
            and not re.search(r"(?i)\bMADDE\s+\d+", current)
        )
        if is_heading_only and i + 1 < len(sections):
            merged.append(current + "\n\n" + sections[i + 1])
            i += 2
        else:
            merged.append(current)
            i += 1

    return merged

def split_long_section(section):
    if len(section) <= MAX_CHARS:
        return [section]

    paragraphs = re.split(r"\n\s*\n", section)
    result = []
    current = ""

    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        if len(paragraph) > MAX_CHARS:
            if current:
                result.append(current.strip())
                current = ""
            # Çok uzun tek paragrafı cümle sınırlarına göre böl.
            sentences = re.split(r"(?<=[.!?])\s+", paragraph)
            for sentence in sentences:
                if current and len(current) + len(sentence) + 1 > MAX_CHARS:
                    result.append(current.strip())
                    current = sentence
                else:
                    current = (current + " " + sentence).strip()
            continue

        if current and len(current) + len(paragraph) + 2 > MAX_CHARS:
            result.append(current.strip())
            current = paragraph
        else:
            current = (current + "\n\n" + paragraph).strip()

    if current:
        result.append(current.strip())

    return result

records = []

for source_id, meta in DOCS.items():
    path = BASE / f"{source_id}.txt"
    if not path.exists():
        raise SystemExit(f"Kaynak bulunamadı: {path}")

    text = path.read_text(encoding="utf-8", errors="replace")
    sections = split_sections(text)
    chunks = []

    for section in sections:
        chunks.extend(split_long_section(section))

    for index, chunk in enumerate(chunks, start=1):
        records.append({
            "chunk_id": f"{source_id}_{index:04d}",
            "source_id": source_id,
            "title": meta["title"],
            "source_url": meta["url"],
            "chunk_index": index,
            "text": chunk,
            "rag_status": "pilot_candidate_pending_final_verification",
        })


# Kısa başlık parçalarını sonraki içerikle birleştir.
# Kaynak metni değiştirmez; yalnızca oluşturulan chunk kayıtlarını düzenler.
merged_records = []

for source_id in DOCS:
    source_records = [r for r in records if r["source_id"] == source_id]
    pending = None

    for record in source_records:
        text = record["text"].strip()
        is_short_heading = (
            len(text) < 100
            and (
                "BÖLÜM" in text.upper()
                or text.casefold() in {
                    "amaç", "kapsam", "dayanak", "tanımlar",
                    "genel ilkeler", "amaç ve kapsam",
                    "yürürlük", "yürütme",
                    "hüküm bulunmayan haller"
                }
            )
        )

        if is_short_heading:
            if pending:
                pending["text"] = (pending["text"].rstrip() + "\n\n" + text).strip()
            else:
                pending = dict(record)
            continue

        if pending:
            record = dict(record)
            record["text"] = (pending["text"].rstrip() + "\n\n" + text).strip()
            pending = None

        merged_records.append(record)

    if pending:
        merged_records.append(pending)

# Parça kimliklerini yeniden sırala ve kayıtları deterministik tut.
# ÇAP yönergesinde "Genel İlkeler" başlığını Madde 5 ile birleştir.
for i in range(len(merged_records) - 1):
    current = merged_records[i]
    following = merged_records[i + 1]
    if (
        current["source_id"] == "cap_yandal"
        and current["text"].strip().casefold() == "genel ilkeler"
        and following["source_id"] == "cap_yandal"
        and "Madde 5" in following["text"]
    ):
        following["text"] = current["text"].strip() + "\n\n" + following["text"].strip()
        merged_records.pop(i)
        break

records = []
for source_id in DOCS:
    source_records = [r for r in merged_records if r["source_id"] == source_id]
    for index, record in enumerate(source_records, start=1):
        record = dict(record)
        record["chunk_id"] = f"{source_id}_{index:04d}"
        record["chunk_index"] = index
        records.append(record)


with OUTPUT.open("w", encoding="utf-8") as f:
    for record in records:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

print("Yeni parçalama tamamlandı.")
print("Toplam parça:", len(records))
for source_id in DOCS:
    rows = [r for r in records if r["source_id"] == source_id]
    print(f"{source_id}: {len(rows)} parça")
    print("  En kısa parça:", min(len(r["text"]) for r in rows), "karakter")
    print("  En uzun parça:", max(len(r["text"]) for r in rows), "karakter")

print("Çıktı:", OUTPUT)
