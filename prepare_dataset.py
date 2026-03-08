# prepare_dataset.py
# Aşama 27: Export edilen *.messages.jsonl dosyalarını birleştirir, tekrarları siler,
# train/validation olarak böler ve dataset/ klasörüne yazar.
#
# Kullanım:
#   1) Bu dosyayı proje köküne koy (telegram_bot.py ile aynı klasör)
#   2) Export JSONL dosyalarını proje kökündeki exports/ klasörüne koy
#   3) CMD:
#        cd /d "C:\Users\PC\Desktop\python temelleri"
#        python prepare_dataset.py
#
import json
import random
from pathlib import Path

EXPORT_DIR = Path("exports")
OUTPUT_DIR = Path("dataset")
OUTPUT_DIR.mkdir(exist_ok=True)

# Ayarlar (istersen değiştir)
TRAIN_RATIO = 0.90  # %90 train, %10 validation
SEED = 42  # aynı bölünmeyi tekrar üretmek için


def _iter_jsonl(path: Path):
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception as e:
                raise RuntimeError(f"JSONL parse hatası: {path.name} satır {i}: {e}")


def main():
    if not EXPORT_DIR.exists():
        raise RuntimeError(
            "exports/ klasörü bulunamadı. Proje kökünde exports/ oluşturup export dosyalarını içine koy."
        )

    message_files = sorted(EXPORT_DIR.glob("*.messages.jsonl"))
    if not message_files:
        raise RuntimeError(
            "exports/ içinde *.messages.jsonl bulunamadı. /egitim_export ile üretilen messages.jsonl dosyasını exports/ içine koy."
        )

    print("Bulunan messages dosyaları:")
    for p in message_files:
        print(" -", p.as_posix())

    # Birleştir + tekrar sil (aynı içerikse)
    seen = set()
    all_rows = []
    for p in message_files:
        for row in _iter_jsonl(p):
            key = json.dumps(row, ensure_ascii=False, sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            all_rows.append(row)

    print("Toplam benzersiz kayıt:", len(all_rows))
    if not all_rows:
        raise RuntimeError("Hiç kayıt bulunamadı (dosyalar boş olabilir).")

    random.seed(SEED)
    random.shuffle(all_rows)

    if len(all_rows) == 1:
        train = all_rows
        val = []
    else:
        split = int(len(all_rows) * TRAIN_RATIO)
        split = max(1, min(split, len(all_rows) - 1))
        train = all_rows[:split]
        val = all_rows[split:]

    train_path = OUTPUT_DIR / "train.jsonl"
    val_path = OUTPUT_DIR / "validation.jsonl"

    with open(train_path, "w", encoding="utf-8") as f:
        for r in train:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    with open(val_path, "w", encoding="utf-8") as f:
        for r in val:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print("Train:", len(train))
    print("Validation:", len(val))
    print("Hazır. dataset/ klasörüne yazıldı.")


if __name__ == "__main__":
    main()
