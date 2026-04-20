#!/usr/bin/env python3
import argparse
import json
import time
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = ROOT / "dataset" / "places_tr.json"
IMAGES_DIR = ROOT / "images" / "places"
CATEGORY_DIR = ROOT / "images" / "categories"
PLACEHOLDER = "images/placeholder.svg"

REQUEST_INTERVAL_SECONDS = 0.05
REQUEST_TIMEOUT = 15
REQUEST_RETRIES = 2

HEADERS = {
    "User-Agent": "nereye-gidilir-image-fetcher/1.0 (contact: dilmacoguz33@gmail.com)",
}

CATEGORY_REPRESENTATIVES = {
    "nature": "images/categories/nature.jpg",
    "history": "images/categories/history.jpg",
    "museum": "images/categories/museum.jpg",
    "park": "images/categories/park.jpg",
    "viewpoint": "images/categories/viewpoint.jpg",
    "other": "images/categories/other.jpg",
}


class HttpClient:
    def __init__(self, interval: float = REQUEST_INTERVAL_SECONDS) -> None:
        self.interval = interval
        self.last_request_ts = 0.0

    def _throttle(self) -> None:
        now = time.time()
        wait = self.interval - (now - self.last_request_ts)
        if wait > 0:
            time.sleep(wait)

    def get_json(self, url: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        for attempt in range(1, REQUEST_RETRIES + 1):
            try:
                self._throttle()
                resp = requests.get(url, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
                self.last_request_ts = time.time()
                if resp.status_code in (429, 500, 502, 503, 504):
                    if attempt < REQUEST_RETRIES:
                        time.sleep(attempt * 0.8)
                        continue
                    return None
                resp.raise_for_status()
                payload = resp.json()
                return payload if isinstance(payload, dict) else None
            except Exception:
                if attempt < REQUEST_RETRIES:
                    time.sleep(attempt * 0.8)
                    continue
                return None
        return None

    def download_binary(self, url: str, out_path: Path) -> bool:
        for attempt in range(1, REQUEST_RETRIES + 1):
            try:
                self._throttle()
                resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
                self.last_request_ts = time.time()
                if resp.status_code in (429, 500, 502, 503, 504):
                    if attempt < REQUEST_RETRIES:
                        time.sleep(attempt * 0.8)
                        continue
                    return False
                resp.raise_for_status()
                out_path.write_bytes(resp.content)
                return True
            except Exception:
                if attempt < REQUEST_RETRIES:
                    time.sleep(attempt * 0.8)
                    continue
                return False
        return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch local images for places_tr dataset.")
    parser.add_argument("--limit", type=int, default=0, help="Only process first N records (0 = all).")
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="Only process records where image_url is empty/placeholder.",
    )
    parser.add_argument(
        "--prefer-representative",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Assign representative category image when real image cannot be found (default: on).",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DATASET_PATH,
        help="Dataset path (default: dataset/places_tr.json).",
    )
    return parser.parse_args()


def is_missing_image(value: str) -> bool:
    v = (value or "").strip().lower()
    return (not v) or ("placeholder" in v)


def normalize_wikipedia_tag(value: str) -> Tuple[str, str]:
    raw = (value or "").strip()
    if ":" in raw and not raw.startswith("http"):
        lang, title = raw.split(":", 1)
        return lang.strip() or "tr", title.strip()
    return "tr", raw


def p18_to_filepath_url(p18_value: str) -> Optional[str]:
    name = (p18_value or "").strip()
    if not name:
        return None
    name = name.removeprefix("File:")
    return f"https://commons.wikimedia.org/wiki/Special:FilePath/{quote(name)}"


def p18_from_entity_data(client: HttpClient, wikidata_id: str) -> Optional[str]:
    wd = (wikidata_id or "").strip()
    if not wd:
        return None
    payload = client.get_json(f"https://www.wikidata.org/wiki/Special:EntityData/{wd}.json")
    if not payload:
        return None
    claims = (((payload.get("entities") or {}).get(wd) or {}).get("claims") or {})
    p18 = claims.get("P18") or []
    if not p18:
        return None
    mainsnak = (p18[0] or {}).get("mainsnak") or {}
    datavalue = mainsnak.get("datavalue") or {}
    filename = datavalue.get("value")
    return filename if isinstance(filename, str) else None


def wikidata_id_from_wikipedia(client: HttpClient, wikipedia_tag: str) -> Optional[str]:
    lang, title = normalize_wikipedia_tag(wikipedia_tag)
    if not title:
        return None
    payload = client.get_json(
        f"https://{lang}.wikipedia.org/w/api.php",
        params={
            "action": "query",
            "format": "json",
            "prop": "pageprops",
            "titles": title,
        },
    )
    if not payload:
        return None
    pages = ((payload.get("query") or {}).get("pages") or {})
    for _, page in pages.items():
        qid = ((page.get("pageprops") or {}).get("wikibase_item") or "").strip()
        if qid:
            return qid
    return None


def sanitize_filename_from_id(place_id: str) -> str:
    safe = (place_id or "unknown").replace(":", "_")
    return "".join(ch for ch in safe if ch.isalnum() or ch in ("_", "-", "."))


def representative_key_from_category(category: str) -> str:
    c = (category or "").lower()
    if c.startswith("natural:"):
        return "nature"
    if c.startswith("historic:"):
        return "history"
    if c == "tourism:museum":
        return "museum"
    if c in ("leisure:park", "leisure:nature_reserve"):
        return "park"
    if c == "tourism:viewpoint":
        return "viewpoint"
    return "other"


def assign_representative(item: Dict[str, Any]) -> str:
    key = representative_key_from_category(str(item.get("kategori", "")))
    url = CATEGORY_REPRESENTATIVES[key]
    item["image_url"] = url
    return url


def ensure_category_images() -> None:
    CATEGORY_DIR.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        # If PIL is unavailable, rely on existing files in repo.
        return

    palette = {
        "nature": ((34, 139, 110), (112, 193, 129), "NATURE"),
        "history": ((111, 78, 55), (194, 146, 102), "HISTORY"),
        "museum": ((57, 73, 171), (123, 159, 255), "MUSEUM"),
        "park": ((51, 105, 30), (139, 195, 74), "PARK"),
        "viewpoint": ((2, 119, 189), (79, 195, 247), "VIEW"),
        "other": ((55, 71, 79), (144, 164, 174), "DISCOVER"),
    }

    for key, rel_path in CATEGORY_REPRESENTATIVES.items():
        out_path = ROOT / rel_path
        if out_path.exists():
            continue
        c1, c2, text = palette[key]
        w, h = 1200, 800
        img = Image.new("RGB", (w, h), c1)
        draw = ImageDraw.Draw(img)
        for y in range(h):
            t = y / (h - 1)
            r = int(c1[0] * (1 - t) + c2[0] * t)
            g = int(c1[1] * (1 - t) + c2[1] * t)
            b = int(c1[2] * (1 - t) + c2[2] * t)
            draw.line([(0, y), (w, y)], fill=(r, g, b))
        try:
            font = ImageFont.truetype("arial.ttf", 84)
        except Exception:
            font = ImageFont.load_default()
        tw, th = draw.textbbox((0, 0), text, font=font)[2:]
        draw.text(((w - tw) / 2, (h - th) / 2), text, fill=(255, 255, 255), font=font)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(out_path, format="JPEG", quality=88)


def wikipedia_thumbnail_from_title(client: HttpClient, lang: str, title: str) -> Optional[str]:
    if not title:
        return None
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote(title)}"
    payload = client.get_json(url)
    if payload:
        thumbnail = payload.get("thumbnail")
        if isinstance(thumbnail, dict):
            source = thumbnail.get("source")
            if isinstance(source, str) and source.startswith("http"):
                return source
    return None


def commons_search_image(client: HttpClient, query: str) -> Optional[str]:
    if not query:
        return None
    url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": f"filetype:bitmap {query}",
        "gsrlimit": 1,
        "prop": "imageinfo",
        "iiprop": "url"
    }
    payload = client.get_json(url, params=params)
    if payload:
        pages = (payload.get("query") or {}).get("pages") or {}
        for page in pages.values():
            imageinfo = page.get("imageinfo") or []
            if imageinfo and isinstance(imageinfo, list):
                candidate = (imageinfo[0] or {}).get("url")
                if isinstance(candidate, str) and candidate.startswith("http"):
                    return candidate
    return None


def resolve_real_image(client: HttpClient, item: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    tags = item.get("tags") if isinstance(item.get("tags"), dict) else {}
    wikidata_id = str(tags.get("wikidata", "")).strip()
    wikipedia_tag = str(tags.get("wikipedia", "")).strip()

    qid = wikidata_id or None
    if not qid and wikipedia_tag:
        qid = wikidata_id_from_wikipedia(client, wikipedia_tag)
        
    thumbnail_url = None
    if wikipedia_tag:
        lang, title = normalize_wikipedia_tag(wikipedia_tag)
        thumbnail_url = wikipedia_thumbnail_from_title(client, lang, title)

    # First try Wikipedia Thumbnail, it's often better quality for place header
    if thumbnail_url:
        return qid, thumbnail_url

    p18_filename = None
    if qid:
        p18_filename = p18_from_entity_data(client, qid)
        
    if p18_filename:
        return qid, p18_to_filepath_url(p18_filename)

    # Fallback to Wikimedia Commons textual search
    place_name = str(item.get("ad", "")).strip()
    city_name = str(item.get("il", "")).strip()
    if place_name:
        search_query = f"{place_name} {city_name}".strip()
        search_img = commons_search_image(client, search_query)
        if search_img:
            return qid, search_img

    return qid, None



def process_single_item(item: Dict[str, Any], client: HttpClient, args: argparse.Namespace) -> Tuple[Optional[Dict[str, Any]], str]:
    place_id = str(item.get("id", "")).strip()
    place_name = str(item.get("ad", "")).strip() or place_id

    if not place_id:
        return None, "silindi"

    filename = sanitize_filename_from_id(place_id) + ".jpg"
    out_path = IMAGES_DIR / filename
    local_url = f"images/places/{filename}"

    if out_path.exists():
        item["image_url"] = local_url
        print(f"[VAR] {place_name} -> Lokalden yüklendi.")
        return item, "reused"

    qid, remote_url = resolve_real_image(client, item)
    if remote_url:
        ok = client.download_binary(remote_url, out_path)
        if ok:
            item["image_url"] = local_url
            print(f"[İNDİ] {place_name} -> Yeni resim başarıyla çekildi.")
            return item, "downloaded"

    # Resim bulunamazsa item silinmek üzere işaretlenir
    print(f"[YOK] {place_name} -> Gerçek resim bulunamadı, REDDEDİLDİ.")
    return None, "silindi"


def main() -> None:
    args = parse_args()
    dataset_path = args.dataset.resolve()
    if not dataset_path.exists():
        raise SystemExit(f"Dataset not found: {dataset_path}")

    # Artık category resimlerine ihtiyaç yok
    # ensure_category_images()

    try:
        records = json.loads(dataset_path.read_text(encoding="utf-8"))
        if not isinstance(records, list):
            raise ValueError("Dataset must be a JSON array.")
    except Exception as exc:
        raise SystemExit(f"Dataset read error: {exc}") from exc

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    
    targets: List[Dict[str, Any]] = []
    for item in records:
        image_url = str(item.get("image_url", "")).strip()
        if args.only_missing and not is_missing_image(image_url):
            continue
        targets.append(item)

    if args.limit and args.limit > 0:
        targets = targets[: args.limit]

    downloaded_success = 0
    failed = 0
    reused_local = 0
    total_targets = len(targets)

    print(f"Toplam {total_targets} mekan için Thread-Pool çoklu taraması başlıyor...")

    # Client HTTP request
    base_client = HttpClient()

    valid_places = []
    
    with ThreadPoolExecutor(max_workers=15) as executor:
        future_to_item = {executor.submit(process_single_item, item, base_client, args): item for item in targets}
        for future in concurrent.futures.as_completed(future_to_item):
            res_item, status = future.result()
            if status == "downloaded":
                downloaded_success += 1
                valid_places.append(res_item)
            elif status == "reused":
                reused_local += 1
                valid_places.append(res_item)
            else:
                failed += 1

    # Silinmeyen (yani resmi olan) orjinal record setin yeni hali
    # Yalnızca valid_places içerisine giren ve zaten eski resmi olanları tutacağız
    final_dataset = []
    valid_ids = {str(vp.get('id')) for vp in valid_places if vp and vp.get('id')}
    
    for r in records:
        r_id = str(r.get('id'))
        url = str(r.get('image_url', '')).strip()
        # Eğer bu sefer tarandıysa ve asıl resmi bulunduysa
        if r_id in valid_ids:
            final_dataset.append(r)
        # Taramaya dahil olmadı ama önceden indirilmiş resmi var ise
        elif "images/places" in url and not is_missing_image(url):
            final_dataset.append(r)

    dataset_path.write_text(json.dumps(final_dataset, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"\n[BİTTİ] Toplam Kalan ve Resimli Mekan: {len(final_dataset)}, İndirilen Yeni Resim: {downloaded_success}, "
        f"Lokalden Korunan: {reused_local}, Acımasızca Silinen Resimsiz Mekan: {failed}\nDataset Güncellendi: {dataset_path}"
    )


if __name__ == "__main__":
    main()
