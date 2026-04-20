#!/usr/bin/env python3
import json
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = ROOT / "dataset" / "places_tr.json"


def read_dataset(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return [x for x in payload if isinstance(x, dict)]
    except Exception:
        return []
    return []


def is_disallowed_image(image_url: str) -> bool:
    value = (image_url or "").strip().lower()
    if not value:
        return True
    if "categories/" in value:
        return True
    if "placeholder" in value:
        return True
    return False


def main() -> None:
    dataset = read_dataset(DATASET_PATH)
    if not dataset:
        print(f"[WARN] Dataset bos veya okunamadi: {DATASET_PATH}")
        return

    kept: List[Dict[str, Any]] = []
    removed = 0

    for item in dataset:
        image_url = str(item.get("image_url", "") or "")
        if is_disallowed_image(image_url):
            removed += 1
            continue
        kept.append(item)

    DATASET_PATH.write_text(json.dumps(kept, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[DONE] Temizleme tamamlandi: kaldi={len(kept)}, silindi={removed}, toplam={len(dataset)}")
    print(f"[FILE] {DATASET_PATH}")


if __name__ == "__main__":
    main()
