#!/usr/bin/env python3

import argparse
import json
import math
import random
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import quote, unquote, urlparse

import requests
from requests.exceptions import RequestException, Timeout

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.nchc.org.tw/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
]
OVERPASS_RETRY_STATUSES = {429, 502, 503, 504}
OVERPASS_RETRIES_PER_ENDPOINT = 3
OVERPASS_TIMEOUT = (10, 90)
OVERPASS_QUERY_TIMEOUT_SECONDS = 130

HTTP_HEADERS = {
    "Content-Type": "text/plain; charset=utf-8",
    "User-Agent": "nereye-gidilir-dataset/1.0 (contact: dilmacoguz33@gmail.com)",
}

WIKI_TIMEOUT = 8
WIKI_RETRIES = 3
WIKI_DELAY_SECONDS = 0.3
WIKI_CACHE_PATH = Path(__file__).resolve().parent / "cache_wiki.json"

ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = ROOT / "dataset"
OUTPUT_PATH = DATASET_DIR / "places_tr.json"
EXTRA_OUTPUT_PATH = DATASET_DIR / "places_tr_top1000_extra.json"
CACHE_TOP_DIR = DATASET_DIR / "cache_top"
CACHE_DIR = DATASET_DIR / "cache"
DEFAULT_DISTRICTS_DIR = ROOT / "assets" / "geo" / "districts"
DEFAULT_DISTRICT_FALLBACK = ROOT / "assets" / "geo" / "tr_districts_simplified.geojson"
DEFAULT_CITIES = ["İstanbul", "İzmir", "Antalya"]
ALL_TR_CITIES = [
    "Adana", "Adıyaman", "Afyonkarahisar", "Ağrı", "Amasya", "Ankara", "Antalya", "Artvin", "Aydın", "Balıkesir",
    "Bilecik", "Bingöl", "Bitlis", "Bolu", "Burdur", "Bursa", "Çanakkale", "Çankırı", "Çorum", "Denizli",
    "Diyarbakır", "Edirne", "Elazığ", "Erzincan", "Erzurum", "Eskişehir", "Gaziantep", "Giresun", "Gümüşhane", "Hakkâri",
    "Hatay", "Isparta", "Mersin", "İstanbul", "İzmir", "Kars", "Kastamonu", "Kayseri", "Kırklareli", "Kırşehir",
    "Kocaeli", "Konya", "Kütahya", "Malatya", "Manisa", "Kahramanmaraş", "Mardin", "Muğla", "Muş", "Nevşehir",
    "Niğde", "Ordu", "Rize", "Sakarya", "Samsun", "Siirt", "Sinop", "Sivas", "Tekirdağ", "Tokat",
    "Trabzon", "Tunceli", "Şanlıurfa", "Uşak", "Van", "Yozgat", "Zonguldak", "Aksaray", "Bayburt", "Karaman",
    "Kırıkkale", "Batman", "Şırnak", "Bartın", "Ardahan", "Iğdır", "Yalova", "Karabük", "Kilis", "Osmaniye", "Düzce",
]

AMENITY_FILTERS = [
    "museum", "place_of_worship", "theatre", "arts_centre", "library", "planetarium", "monastery", "cinema", "zoo",
]
DISTRICT_KEYS = ["addr:district", "is_in:district", "is_in:county", "addr:suburb"]
NATURAL_KEY_FILTERS = ["peak", "valley", "cliff", "beach", "bay", "coastline", "cape"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Nereye Gidilir dataset builder")
    parser.add_argument("--all-tr", action="store_true", help="Tum 81 il icin calistir.")
    parser.add_argument("--images", action="store_true", help="Legacy secenek (kullanilmiyor).")
    parser.add_argument("--no-images", action="store_true", help="Resim toplama kapali.")
    parser.add_argument("--limit-per-city", type=int, default=2500, help="Her il icin maksimum kayit.")
    parser.add_argument("--refresh-cache", action="store_true", help="Sehir cache dosyalarini yok sayip yeniden Overpass cagir.")
    parser.add_argument("--assign-districts", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--districts-dir", type=Path, default=DEFAULT_DISTRICTS_DIR)
    parser.add_argument("--district-fallback-file", type=Path, default=DEFAULT_DISTRICT_FALLBACK)

    parser.add_argument("--extra-top-tr", type=int, nargs="?", const=5000, default=None)
    parser.add_argument("--base", type=Path, default=None)
    parser.add_argument("--with-images", action="store_true")
    parser.add_argument("--no-pageviews", action="store_true")
    parser.add_argument("--merge-out", type=Path, default=None)
    parser.add_argument("--top-tr", type=int, nargs="?", const=500000, default=None)
    parser.add_argument("--target-total", type=int, default=None)
    parser.add_argument("--merge-in", type=Path, default=Path("dataset/places_tr.json"))
    parser.add_argument("--out", type=Path, default=Path("dataset/places_tr_top1000.json"))
    parser.add_argument("--added-out", type=Path, default=Path("dataset/places_tr_top5000_added.json"))
    parser.add_argument("--top-scan-limit", type=int, default=50000)
    return parser.parse_args()


def slugify_cache(value: str) -> str:
    return (
        value.replace("ç", "c").replace("Ç", "c").replace("ğ", "g").replace("Ğ", "g")
        .replace("ı", "i").replace("İ", "i").replace("ö", "o").replace("Ö", "o")
        .replace("ş", "s").replace("Ş", "s").replace("ü", "u").replace("Ü", "u")
        .replace("â", "a").replace("Â", "a").lower().replace(" ", "_").replace("-", "_")
    )


def slugify_file(value: str) -> str:
    return (
        value.replace("ç", "c").replace("Ç", "c").replace("ğ", "g").replace("Ğ", "g")
        .replace("ı", "i").replace("İ", "i").replace("ö", "o").replace("Ö", "o")
        .replace("ş", "s").replace("Ş", "s").replace("ü", "u").replace("Ü", "u")
        .replace("â", "a").replace("Â", "a").lower().replace(" ", "-").replace("_", "-")
    )


def normalize_text(value: str) -> str:
    return (
        str(value).replace("ç", "c").replace("Ç", "c").replace("ğ", "g").replace("Ğ", "g")
        .replace("ı", "i").replace("İ", "i").replace("ö", "o").replace("Ö", "o")
        .replace("ş", "s").replace("Ş", "s").replace("ü", "u").replace("Ü", "u")
        .replace("â", "a").replace("Â", "a").lower().strip()
    )


def cache_file_for_city(city_name: str) -> Path:
    return CACHE_DIR / f"{slugify_cache(city_name)}.json"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def read_json_array(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
    except Exception:
        return []
    return []

def build_query(city_name: str) -> str:
    amenity_parts = "\n".join(
        f'  node["amenity"="{a}"](area.searchArea);\n  way["amenity"="{a}"](area.searchArea);\n  relation["amenity"="{a}"](area.searchArea);'
        for a in AMENITY_FILTERS
    )
    natural_specific = "\n".join(
        f'  node["natural"="{n}"](area.searchArea);\n  way["natural"="{n}"](area.searchArea);\n  relation["natural"="{n}"](area.searchArea);'
        for n in NATURAL_KEY_FILTERS
    )

    return f"""
[out:json][timeout:{OVERPASS_QUERY_TIMEOUT_SECONDS}];
area["boundary"="administrative"]["admin_level"="4"]["name"="{city_name}"]->.searchArea;
(
  node["tourism"](area.searchArea);
  way["tourism"](area.searchArea);
  relation["tourism"](area.searchArea);

  node["historic"](area.searchArea);
  way["historic"](area.searchArea);
  relation["historic"](area.searchArea);

  node["natural"](area.searchArea);
  way["natural"](area.searchArea);
  relation["natural"](area.searchArea);

{natural_specific}

  node["waterway"="waterfall"](area.searchArea);
  way["waterway"="waterfall"](area.searchArea);
  relation["waterway"="waterfall"](area.searchArea);

  node["leisure"="park"](area.searchArea);
  way["leisure"="park"](area.searchArea);
  relation["leisure"="park"](area.searchArea);

  node["leisure"="nature_reserve"](area.searchArea);
  way["leisure"="nature_reserve"](area.searchArea);
  relation["leisure"="nature_reserve"](area.searchArea);

  node["boundary"="protected_area"](area.searchArea);
  way["boundary"="protected_area"](area.searchArea);
  relation["boundary"="protected_area"](area.searchArea);

  node["protected_area"](area.searchArea);
  way["protected_area"](area.searchArea);
  relation["protected_area"](area.searchArea);

  node["geological"](area.searchArea);
  way["geological"](area.searchArea);
  relation["geological"](area.searchArea);

  node["tourism"="attraction"](area.searchArea);
  way["tourism"="attraction"](area.searchArea);
  relation["tourism"="attraction"](area.searchArea);

  node["tourism"="museum"](area.searchArea);
  way["tourism"="museum"](area.searchArea);
  relation["tourism"="museum"](area.searchArea);

  node["tourism"="viewpoint"](area.searchArea);
  way["tourism"="viewpoint"](area.searchArea);
  relation["tourism"="viewpoint"](area.searchArea);

  node["tourism"="theme_park"](area.searchArea);
  way["tourism"="theme_park"](area.searchArea);
  relation["tourism"="theme_park"](area.searchArea);

  node["historic"="castle"](area.searchArea);
  way["historic"="castle"](area.searchArea);
  relation["historic"="castle"](area.searchArea);

  node["historic"="monument"](area.searchArea);
  way["historic"="monument"](area.searchArea);
  relation["historic"="monument"](area.searchArea);

  node["historic"="ruins"](area.searchArea);
  way["historic"="ruins"](area.searchArea);
  relation["historic"="ruins"](area.searchArea);

{amenity_parts}
);
out center tags;
""".strip()


def backoff_sleep(attempt: int) -> None:
    time.sleep((2 ** (attempt - 1)) + random.uniform(0.05, 0.35))


def fetch_from_endpoints(query: str, endpoint_seed: int) -> Optional[Dict[str, Any]]:
    rotated = OVERPASS_ENDPOINTS[endpoint_seed:] + OVERPASS_ENDPOINTS[:endpoint_seed]
    for endpoint in rotated:
        for attempt in range(1, OVERPASS_RETRIES_PER_ENDPOINT + 1):
            try:
                response = requests.post(endpoint, data=query.encode("utf-8"), headers=HTTP_HEADERS, timeout=OVERPASS_TIMEOUT)
                if response.status_code in OVERPASS_RETRY_STATUSES:
                    if attempt < OVERPASS_RETRIES_PER_ENDPOINT:
                        backoff_sleep(attempt)
                        continue
                    break
                response.raise_for_status()
                payload = response.json()
                if isinstance(payload, dict):
                    return payload
                break
            except Timeout:
                if attempt < OVERPASS_RETRIES_PER_ENDPOINT:
                    backoff_sleep(attempt)
                    continue
                break
            except (RequestException, ValueError):
                break
    return None


def fetch_city_elements(city_name: str, refresh_cache: bool, endpoint_seed: int) -> List[Dict[str, Any]]:
    cache_path = cache_file_for_city(city_name)
    if not refresh_cache:
        cached = read_json(cache_path)
        if cached and isinstance(cached.get("elements"), list):
            return cached["elements"]

    payload = fetch_from_endpoints(build_query(city_name), endpoint_seed)
    if payload and isinstance(payload.get("elements"), list):
        write_json(cache_path, payload)
        return payload["elements"]

    if refresh_cache:
        print(f"[WARN] {city_name}: refresh-cache acik, endpointler fail, sehir atlandi.")
        return []

    cached = read_json(cache_path)
    if cached and isinstance(cached.get("elements"), list):
        print(f"[WARN] {city_name}: endpointler fail, cache kullaniliyor.")
        return cached["elements"]

    print(f"[WARN] {city_name}: endpoint ve cache yok, sehir atlandi.")
    return []


def extract_coords(element: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    if "lat" in element and "lon" in element:
        return float(element["lat"]), float(element["lon"])
    center = element.get("center")
    if isinstance(center, dict) and "lat" in center and "lon" in center:
        return float(center["lat"]), float(center["lon"])
    return None


def extract_ilce_from_tags(tags: Dict[str, str]) -> str:
    for key in DISTRICT_KEYS:
        value = tags.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def extract_il_from_tags(tags: Dict[str, str]) -> str:
    for key in ["addr:province", "is_in:province", "addr:city", "is_in:city", "is_in:state", "addr:state"]:
        value = tags.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def derive_category(tags: Dict[str, str]) -> str:
    if "tourism" in tags:
        return f"tourism:{tags.get('tourism')}"
    if "historic" in tags:
        return f"historic:{tags.get('historic')}"
    if "natural" in tags:
        return f"natural:{tags.get('natural')}"
    if tags.get("waterway") == "waterfall":
        return "natural:waterfall"
    if "leisure" in tags:
        return f"leisure:{tags.get('leisure')}"
    if "geological" in tags:
        return f"geological:{tags.get('geological')}"
    if tags.get("boundary") == "protected_area" or "protected_area" in tags:
        return "natural:protected_area"
    if "amenity" in tags:
        return f"amenity:{tags.get('amenity')}"
    return "other"


def base_score(tags: Dict[str, str]) -> int:
    score = 0
    if tags.get("wikidata"):
        score += 50
    if tags.get("wikipedia"):
        score += 30

    tourism = tags.get("tourism", "")
    if tourism == "attraction":
        score += 30
    elif tourism == "museum":
        score += 28
    elif tourism == "viewpoint":
        score += 26
    elif tourism in {"theme_park", "zoo"}:
        score += 22
    elif tourism:
        score += 10

    historic = tags.get("historic", "")
    if historic in {"castle", "monument", "ruins", "archaeological_site"}:
        score += 28
    elif historic:
        score += 20

    natural = tags.get("natural", "")
    if natural in {"peak", "waterfall", "beach", "bay", "valley", "cliff", "coastline"}:
        score += 22
    elif natural:
        score += 14

    if tags.get("waterway") == "waterfall":
        score += 24
    if tags.get("leisure") in {"nature_reserve", "park"}:
        score += 14
    if tags.get("boundary") == "protected_area" or tags.get("protected_area"):
        score += 18
    if tags.get("amenity") in AMENITY_FILTERS:
        score += 10
    if tags.get("name:tr"):
        score += 3
    return score


def to_record(city_name: str, element: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    tags = element.get("tags")
    if not isinstance(tags, dict):
        return None
    name = tags.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    coords = extract_coords(element)
    if not coords:
        return None

    osm_type = str(element.get("type", "")).strip()
    osm_id = element.get("id")
    if osm_type not in {"node", "way", "relation"} or osm_id is None:
        return None

    tags = dict(tags)
    tags["ilce"] = extract_ilce_from_tags(tags)
    lat, lon = coords
    city_value = city_name.strip() if city_name.strip() else extract_il_from_tags(tags)
    return {
        "id": f"{osm_type}:{osm_id}",
        "il": city_value,
        "ad": name.strip(),
        "kategori": derive_category(tags),
        "lat": lat,
        "lon": lon,
        "osm_type": osm_type,
        "osm_id": osm_id,
        "tags": tags,
        "image_url": "",
    }


def unique_by_id(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: Set[str] = set()
    out: List[Dict[str, Any]] = []
    for record in records:
        key = str(record.get("id", ""))
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(record)
    return out

def load_geojson(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def ring_bbox(ring: List[List[float]]) -> Tuple[float, float, float, float]:
    min_x = min(pt[0] for pt in ring)
    min_y = min(pt[1] for pt in ring)
    max_x = max(pt[0] for pt in ring)
    max_y = max(pt[1] for pt in ring)
    return min_x, min_y, max_x, max_y


def point_in_ring(x: float, y: float, ring: List[List[float]]) -> bool:
    inside = False
    n = len(ring)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        intersects = ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi)
        if intersects:
            inside = not inside
        j = i
    return inside


def point_in_polygon_with_holes(x: float, y: float, polygon: List[List[List[float]]]) -> bool:
    if not polygon:
        return False
    outer = polygon[0]
    if not point_in_ring(x, y, outer):
        return False
    for hole in polygon[1:]:
        if point_in_ring(x, y, hole):
            return False
    return True


def prepare_district_shapes(features: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    shapes: List[Dict[str, Any]] = []
    for feature in features:
        props = feature.get("properties") or {}
        district_name = props.get("name_tr") or props.get("name") or props.get("shapeName")
        if not isinstance(district_name, str) or not district_name.strip():
            continue

        geom = feature.get("geometry") or {}
        geom_type = geom.get("type")
        coords = geom.get("coordinates")

        polygons: List[Any] = []
        if geom_type == "Polygon" and isinstance(coords, list):
            polygons = [coords]
        elif geom_type == "MultiPolygon" and isinstance(coords, list):
            polygons = coords

        for polygon in polygons:
            if not polygon or not isinstance(polygon, list):
                continue
            outer = polygon[0] if polygon else None
            if not outer or len(outer) < 4:
                continue
            min_x, min_y, max_x, max_y = ring_bbox(outer)
            shapes.append({"name": district_name.strip(), "polygon": polygon, "bbox": (min_x, min_y, max_x, max_y)})
    return shapes


def load_city_district_shapes(city_name: str, districts_dir: Path, fallback_file: Path) -> List[Dict[str, Any]]:
    city_file = districts_dir / f"{slugify_file(city_name)}.geojson"
    payload = load_geojson(city_file)
    if payload and isinstance(payload.get("features"), list):
        return prepare_district_shapes(payload["features"])

    fallback = load_geojson(fallback_file)
    if not fallback or not isinstance(fallback.get("features"), list):
        return []

    city_norm = normalize_text(city_name)
    filtered: List[Dict[str, Any]] = []
    for feature in fallback["features"]:
        props = feature.get("properties") or {}
        province_name = props.get("province_tr") or props.get("province") or props.get("il") or ""
        if normalize_text(str(province_name)) == city_norm:
            filtered.append(feature)
    return prepare_district_shapes(filtered)


def assign_district_to_record(record: Dict[str, Any], district_shapes: List[Dict[str, Any]]) -> None:
    tags = record.get("tags") if isinstance(record.get("tags"), dict) else {}
    current = str(tags.get("ilce", "")).strip()
    if current:
        record["tags"] = tags
        return

    x = float(record.get("lon", 0.0))
    y = float(record.get("lat", 0.0))
    for shape in district_shapes:
        min_x, min_y, max_x, max_y = shape["bbox"]
        if x < min_x or x > max_x or y < min_y or y > max_y:
            continue
        if point_in_polygon_with_holes(x, y, shape["polygon"]):
            tags["ilce"] = shape["name"]
            record["tags"] = tags
            return

    tags["ilce"] = ""
    record["tags"] = tags


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def dedupe_name_near(records: List[Dict[str, Any]], max_distance_m: float = 75.0) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    output: List[Dict[str, Any]] = []
    for item in records:
        name_key = normalize_text(item.get("ad", ""))
        if not name_key:
            continue
        lat = float(item.get("lat", 0.0))
        lon = float(item.get("lon", 0.0))
        kept = grouped.setdefault(name_key, [])

        duplicate = False
        for prev in kept:
            if haversine_m(lat, lon, float(prev.get("lat", 0.0)), float(prev.get("lon", 0.0))) <= max_distance_m:
                duplicate = True
                break
        if duplicate:
            continue

        kept.append(item)
        output.append(item)
    return output


def parse_wikipedia_tag(raw: str) -> Optional[Tuple[str, str]]:
    if not isinstance(raw, str) or not raw.strip():
        return None

    raw = raw.strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        parsed = urlparse(raw)
        host = parsed.netloc.lower()
        if "wikipedia.org" not in host:
            return None
        lang = host.split(".")[0]
        path = parsed.path or ""
        if "/wiki/" not in path:
            return None
        title = unquote(path.split("/wiki/", 1)[1]).replace(" ", "_")
        return (lang, title) if title else None

    if ":" in raw:
        lang, title = raw.split(":", 1)
        lang = lang.strip().lower()
        title = title.strip().replace(" ", "_")
        if lang and title:
            return (lang, title)
    return None


def throttle_wiki() -> None:
    time.sleep(WIKI_DELAY_SECONDS)

def load_wiki_cache() -> Dict[str, Dict[str, Any]]:
    if not WIKI_CACHE_PATH.exists():
        return {
            "wikidata_p18": {},
            "wikipedia_thumb": {},
            "wikipedia_qid": {},
            "pageviews": {},
            "commons_imageinfo": {},
            "resolved_images": {},
        }
    try:
        payload = json.loads(WIKI_CACHE_PATH.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("cache format")
    except Exception:
        return {
            "wikidata_p18": {},
            "wikipedia_thumb": {},
            "wikipedia_qid": {},
            "pageviews": {},
            "commons_imageinfo": {},
            "resolved_images": {},
        }

    for key in ["wikidata_p18", "wikipedia_thumb", "wikipedia_qid", "pageviews", "commons_imageinfo", "resolved_images"]:
        if not isinstance(payload.get(key), dict):
            payload[key] = {}
    return payload


def save_wiki_cache(cache: Dict[str, Dict[str, Any]]) -> None:
    write_json(WIKI_CACHE_PATH, cache)


def request_json_retry(url: str, headers: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
    hdrs = {"User-Agent": HTTP_HEADERS["User-Agent"]}
    if headers:
        hdrs.update(headers)

    for attempt in range(1, WIKI_RETRIES + 1):
        try:
            throttle_wiki()
            resp = requests.get(url, timeout=WIKI_TIMEOUT, headers=hdrs)
            if resp.status_code in OVERPASS_RETRY_STATUSES:
                if attempt < WIKI_RETRIES:
                    time.sleep((2 ** (attempt - 1)) + random.uniform(0.05, 0.25))
                    continue
                return None
            resp.raise_for_status()
            payload = resp.json()
            return payload if isinstance(payload, dict) else None
        except Exception:
            if attempt < WIKI_RETRIES:
                time.sleep((2 ** (attempt - 1)) + random.uniform(0.05, 0.25))
                continue
            return None
    return None


def get_p18_from_qid(qid: str, cache: Dict[str, Dict[str, Any]]) -> Optional[str]:
    store = cache["wikidata_p18"]
    if qid in store:
        return store[qid] or None

    payload = request_json_retry(f"https://www.wikidata.org/wiki/Special:EntityData/{quote(qid)}.json")
    filename: Optional[str] = None
    if payload:
        entity = (payload.get("entities") or {}).get(qid) or {}
        claims = entity.get("claims") or {}
        p18_values = claims.get("P18") or []
        if p18_values and isinstance(p18_values, list):
            try:
                filename = p18_values[0]["mainsnak"]["datavalue"]["value"]
            except Exception:
                filename = None

    store[qid] = filename or ""
    return filename


def get_wikidata_from_wikipedia(lang: str, title: str, cache: Dict[str, Dict[str, Any]]) -> Optional[str]:
    key = f"{lang}:{title}"
    store = cache["wikipedia_qid"]
    if key in store:
        return store[key] or None

    api = (
        f"https://{lang}.wikipedia.org/w/api.php?format=json&origin=*&action=query&prop=pageprops"
        f"&titles={quote(title)}"
    )
    payload = request_json_retry(api)
    qid: Optional[str] = None
    if payload:
        pages = ((payload.get("query") or {}).get("pages") or {})
        if isinstance(pages, dict):
            for page in pages.values():
                value = ((page.get("pageprops") or {}).get("wikibase_item"))
                if isinstance(value, str) and value.strip():
                    qid = value.strip()
                    break

    store[key] = qid or ""
    return qid


def get_wikipedia_thumbnail(lang: str, title: str, cache: Dict[str, Dict[str, Any]]) -> Optional[str]:
    key = f"{lang}:{title}"
    store = cache["wikipedia_thumb"]
    if key in store:
        return store[key] or None

    payload = request_json_retry(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote(title)}")
    thumb = ((payload.get("thumbnail") or {}).get("source")) if payload else None
    store[key] = thumb or ""
    return thumb


def normalize_commons_name(raw: str) -> str:
    value = str(raw or "").strip()
    if value.lower().startswith("file:"):
        value = value.split(":", 1)[1]
    return value.replace("_", " ").strip()


def commons_imageinfo_url(file_name: str, cache: Dict[str, Dict[str, Any]]) -> Optional[str]:
    normalized = normalize_commons_name(file_name)
    if not normalized:
        return None

    store = cache["commons_imageinfo"]
    if normalized in store:
        return store[normalized] or None

    url = (
        "https://commons.wikimedia.org/w/api.php?action=query&format=json&origin=*"
        f"&prop=imageinfo&iiprop=url&titles=File:{quote(normalized)}"
    )
    payload = request_json_retry(url)
    image_url: Optional[str] = None
    if payload:
        pages = ((payload.get("query") or {}).get("pages") or {})
        if isinstance(pages, dict):
            for page in pages.values():
                imageinfo = page.get("imageinfo") or []
                if isinstance(imageinfo, list) and imageinfo:
                    candidate = (imageinfo[0] or {}).get("url")
                    if isinstance(candidate, str) and candidate.startswith("http"):
                        image_url = candidate
                        break

    store[normalized] = image_url or ""
    return image_url


def get_pageviews_60d(lang: str, title: str, cache: Dict[str, Dict[str, Any]]) -> int:
    key = f"{lang}:{title}".lower()
    store = cache["pageviews"]
    if key in store:
        try:
            return int(store[key])
        except Exception:
            return 0

    end_date = datetime.utcnow().date() - timedelta(days=1)
    start_date = end_date - timedelta(days=59)
    start = start_date.strftime("%Y%m%d")
    end = end_date.strftime("%Y%m%d")
    url = (
        "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
        f"{lang}.wikipedia.org/all-access/user/{quote(title)}/daily/{start}/{end}"
    )
    payload = request_json_retry(url)

    total = 0
    if payload:
        items = payload.get("items") or []
        if isinstance(items, list):
            for itm in items:
                try:
                    total += int((itm or {}).get("views", 0) or 0)
                except Exception:
                    pass

    store[key] = total
    return total


def find_base_dataset(explicit_base: Optional[Path]) -> Path:
    if explicit_base:
        base = explicit_base if explicit_base.is_absolute() else ROOT / explicit_base
        if base.exists():
            return base
        raise FileNotFoundError(f"Baz dataset bulunamadi: {base}")

    for p in [DATASET_DIR / "places_tr.json", DATASET_DIR / "places_tr_top1000.json"]:
        if p.exists():
            return p

    globbed = sorted(DATASET_DIR.glob("places_tr*.json"), key=lambda p: p.stat().st_size if p.exists() else 0, reverse=True)
    if globbed:
        return globbed[0]
    raise FileNotFoundError("Baz dataset bulunamadi (dataset/places_tr*.json)")


def build_base_index(base_records: List[Dict[str, Any]]) -> Dict[str, Set[Any]]:
    idx: Dict[str, Set[Any]] = {"osm": set(), "wikidata": set(), "wikipedia": set(), "name_loc": set()}
    for item in base_records:
        osm_type = str(item.get("osm_type", "")).strip()
        osm_id = str(item.get("osm_id", "")).strip()
        if osm_type and osm_id:
            idx["osm"].add(f"{osm_type}:{osm_id}")

        tags = item.get("tags") if isinstance(item.get("tags"), dict) else {}
        wikidata = str(tags.get("wikidata", "") or "").strip()
        wikipedia = str(tags.get("wikipedia", "") or "").strip().lower()
        if wikidata:
            idx["wikidata"].add(wikidata)
        if wikipedia:
            idx["wikipedia"].add(wikipedia)

        try:
            idx["name_loc"].add((
                normalize_text(item.get("ad", "")),
                normalize_text(item.get("il", "")),
                round(float(item.get("lat", 0.0)), 3),
                round(float(item.get("lon", 0.0)), 3),
            ))
        except Exception:
            pass
    return idx


def candidate_in_base(item: Dict[str, Any], base_idx: Dict[str, Set[Any]]) -> bool:
    if f"{item.get('osm_type', '')}:{item.get('osm_id', '')}" in base_idx["osm"]:
        return True

    tags = item.get("tags") if isinstance(item.get("tags"), dict) else {}
    wikidata = str(tags.get("wikidata", "") or "").strip()
    wikipedia = str(tags.get("wikipedia", "") or "").strip().lower()
    if wikidata and wikidata in base_idx["wikidata"]:
        return True
    if wikipedia and wikipedia in base_idx["wikipedia"]:
        return True

    try:
        key = (
            normalize_text(item.get("ad", "")),
            normalize_text(item.get("il", "")),
            round(float(item.get("lat", 0.0)), 3),
            round(float(item.get("lon", 0.0)), 3),
        )
        if key in base_idx["name_loc"]:
            return True
    except Exception:
        pass

    return False

def resolve_image_url(tags: Dict[str, Any], wiki_cache: Dict[str, Dict[str, Any]]) -> Tuple[Optional[str], Optional[str], str, str]:
    cache_key = "|".join(
        [
            str(tags.get("image", "") or "").strip(),
            str(tags.get("wikimedia_commons", "") or "").strip(),
            str(tags.get("commons", "") or "").strip(),
            str(tags.get("subject:wikidata", "") or "").strip(),
            str(tags.get("wikidata", "") or "").strip(),
            str(tags.get("wikipedia", "") or "").strip(),
        ]
    )
    resolved_store = wiki_cache.get("resolved_images", {})
    if cache_key in resolved_store:
        cached = resolved_store[cache_key]
        if isinstance(cached, dict):
            return (
                cached.get("url") or None,
                cached.get("source") or None,
                cached.get("wikipedia") or "",
                cached.get("wikidata") or "",
            )

    image_tag = str(tags.get("image", "") or "").strip()
    if image_tag.startswith("http://") or image_tag.startswith("https://"):
        result = (image_tag, "osm_image", str(tags.get("wikipedia", "") or "").strip(), str(tags.get("wikidata", "") or "").strip())
        resolved_store[cache_key] = {"url": result[0], "source": result[1], "wikipedia": result[2], "wikidata": result[3]}
        wiki_cache["resolved_images"] = resolved_store
        return result

    commons_raw = str(tags.get("wikimedia_commons", "") or tags.get("commons", "") or "").strip()
    if commons_raw:
        if commons_raw.lower().startswith("file:"):
            commons_url = commons_imageinfo_url(commons_raw, wiki_cache)
            if commons_url:
                result = (commons_url, "commons_file", str(tags.get("wikipedia", "") or "").strip(), str(tags.get("wikidata", "") or "").strip())
                resolved_store[cache_key] = {"url": result[0], "source": result[1], "wikipedia": result[2], "wikidata": result[3]}
                wiki_cache["resolved_images"] = resolved_store
                return result

    wikipedia_raw = str(tags.get("wikipedia", "") or "").strip()
    wikidata = str(tags.get("subject:wikidata", "") or tags.get("wikidata", "") or "").strip()
    wiki_ref = parse_wikipedia_tag(wikipedia_raw) if wikipedia_raw else None

    if not wikidata and wiki_ref:
        resolved = get_wikidata_from_wikipedia(wiki_ref[0], wiki_ref[1], wiki_cache)
        if resolved:
            wikidata = resolved

    if wikidata:
        p18 = get_p18_from_qid(wikidata, wiki_cache)
        if p18:
            commons_url = commons_imageinfo_url(p18, wiki_cache)
            if commons_url:
                result = (commons_url, "wikidata_p18", wikipedia_raw, wikidata)
                resolved_store[cache_key] = {"url": result[0], "source": result[1], "wikipedia": result[2], "wikidata": result[3]}
                wiki_cache["resolved_images"] = resolved_store
                return result

    if wiki_ref:
        thumb = get_wikipedia_thumbnail(wiki_ref[0], wiki_ref[1], wiki_cache)
        if thumb:
            result = (thumb, "wikipedia_thumbnail", wikipedia_raw, wikidata)
            resolved_store[cache_key] = {"url": result[0], "source": result[1], "wikipedia": result[2], "wikidata": result[3]}
            wiki_cache["resolved_images"] = resolved_store
            return result

    resolved_store[cache_key] = {"url": "", "source": "", "wikipedia": wikipedia_raw, "wikidata": wikidata}
    wiki_cache["resolved_images"] = resolved_store
    return None, None, wikipedia_raw, wikidata


def prepare_extra_record(
    record: Dict[str, Any], wiki_cache: Dict[str, Dict[str, Any]], with_images: bool, with_pageviews: bool
) -> Optional[Dict[str, Any]]:
    tags = record.get("tags") if isinstance(record.get("tags"), dict) else {}
    image_url, source, wikipedia_raw, wikidata = resolve_image_url(tags, wiki_cache)
    wiki_ref = parse_wikipedia_tag(wikipedia_raw) if wikipedia_raw else None

    score = base_score(tags)
    if with_pageviews and wiki_ref:
        score += get_pageviews_60d(wiki_ref[0], wiki_ref[1], wiki_cache)
    if with_images and not image_url:
        return None

    return {
        "id": record.get("id"),
        "il": record.get("il"),
        "ad": record.get("ad"),
        "kategori": record.get("kategori"),
        "lat": record.get("lat"),
        "lon": record.get("lon"),
        "osm_type": record.get("osm_type"),
        "osm_id": record.get("osm_id"),
        "tags": tags,
        "score": score,
        "wikipedia": wikipedia_raw,
        "wikidata": wikidata,
        "image_url": image_url if image_url else "",
        "source": source if source else "",
    }


def run_default_mode(args: argparse.Namespace) -> None:
    if args.images:
        print("[INFO] Resim toplama bu asamada kapali.")

    selected_cities = ALL_TR_CITIES if args.all_tr else DEFAULT_CITIES
    all_records: List[Dict[str, Any]] = []
    global_items = 0
    global_ok = 0
    global_empty = 0

    for idx, city in enumerate(selected_cities):
        city_records: List[Dict[str, Any]] = []
        try:
            elements = fetch_city_elements(city, args.refresh_cache, idx % len(OVERPASS_ENDPOINTS))
            for element in elements:
                rec = to_record(city, element)
                if rec:
                    city_records.append(rec)

            city_records = dedupe_name_near(unique_by_id(city_records), max_distance_m=75.0)
            city_records.sort(key=lambda r: (-base_score(r.get("tags", {})), str(r.get("ad", "")).lower(), str(r.get("id", ""))))
            city_records = city_records[: max(0, args.limit_per_city)]

            district_shapes: List[Dict[str, Any]] = []
            if args.assign_districts:
                district_shapes = load_city_district_shapes(city, args.districts_dir, args.district_fallback_file)

            if district_shapes:
                for rec in city_records:
                    assign_district_to_record(rec, district_shapes)
            else:
                for rec in city_records:
                    tags = rec.get("tags") if isinstance(rec.get("tags"), dict) else {}
                    tags["ilce"] = str(tags.get("ilce", "")).strip()
                    rec["tags"] = tags

            city_items = len(city_records)
            city_ok = sum(1 for r in city_records if str((r.get("tags") or {}).get("ilce", "")).strip())
            city_empty = city_items - city_ok

            global_items += city_items
            global_ok += city_ok
            global_empty += city_empty
            all_records.extend(city_records)
            print(f"[CITY] {city}: items={city_items}, district_ok={city_ok}, district_empty={city_empty}")
        except Exception as exc:
            print(f"[WARN] {city}: hata ({exc}), sehir atlandi.")
            print(f"[CITY] {city}: items=0, district_ok=0, district_empty=0")

    all_records.sort(key=lambda r: (str(r.get("il", "")), str(r.get("ad", "")).lower()))
    write_json(OUTPUT_PATH, all_records)

    ratio = (global_ok / global_items * 100.0) if global_items else 0.0
    print(f"[SUMMARY] toplam={global_items}, district_ok={global_ok}, district_empty={global_empty}, district_dolu_orani={ratio:.2f}%")
    print(f"[DONE] Dataset yazildi: {OUTPUT_PATH} (toplam kayit: {len(all_records)})")


def run_extra_mode(args: argparse.Namespace) -> None:
    target_n = max(1, int(args.extra_top_tr or 1000))
    base_path = find_base_dataset(args.base)
    base_records = read_json_array(base_path)
    base_idx = build_base_index(base_records)
    print(f"[BASE] Kullanilan baz dataset: {base_path} (kayit: {len(base_records)})")

    candidates: List[Dict[str, Any]] = []
    skipped_in_base = 0
    for idx, city in enumerate(ALL_TR_CITIES):
        try:
            raw_elements = fetch_city_elements(city, args.refresh_cache, idx % len(OVERPASS_ENDPOINTS))
            city_records: List[Dict[str, Any]] = []
            for element in raw_elements:
                rec = to_record(city, element)
                if not rec:
                    continue
                if candidate_in_base(rec, base_idx):
                    skipped_in_base += 1
                    continue
                city_records.append(rec)

            city_records = dedupe_name_near(unique_by_id(city_records), max_distance_m=75.0)
            city_records.sort(key=lambda r: -base_score(r.get("tags", {})))
            city_records = city_records[: max(0, args.limit_per_city)]
            candidates.extend(city_records)
            print(f"[POOL] {city}: yeni_aday={len(city_records)}, bazda_atlanan(toplam)={skipped_in_base}")
        except Exception as exc:
            print(f"[WARN] {city}: aday havuzu hatasi ({exc}), sehir atlandi.")

    candidates = dedupe_name_near(unique_by_id(candidates), max_distance_m=75.0)
    final_pool = [item for item in candidates if not candidate_in_base(item, base_idx)]
    print(f"[POOL] Toplam benzersiz baz-disi aday: {len(final_pool)}")

    wiki_cache = load_wiki_cache()
    scored: List[Dict[str, Any]] = []
    total = len(final_pool)
    for i, item in enumerate(final_pool, 1):
        try:
            rec = prepare_extra_record(item, wiki_cache, args.with_images, not args.no_pageviews)
            if args.with_images and not rec:
                continue
            if rec:
                scored.append(rec)
            if i % 50 == 0 or i == total:
                print(f"[SCORE] {i}/{total} tamamlandi")
        except Exception as exc:
            print(f"[WARN] score atlandi: {item.get('id')} ({exc})")

    save_wiki_cache(wiki_cache)
    scored.sort(key=lambda r: (-int(r.get("score", 0) or 0), str(r.get("il", "")), str(r.get("ad", "")).lower()))

    extras = scored[:target_n]
    if len(extras) < target_n:
        print(f"[WARN] Hedef {target_n} fakat bulunan baz-disi kayit {len(extras)}")

    write_json(EXTRA_OUTPUT_PATH, extras)
    print(f"[DONE] Extra dataset yazildi: {EXTRA_OUTPUT_PATH} (kayit: {len(extras)})")

    if args.merge_out:
        merge_path = args.merge_out if args.merge_out.is_absolute() else ROOT / args.merge_out
        write_json(merge_path, list(base_records) + extras)
        print(f"[DONE] Merge dataset yazildi: {merge_path} (kayit: {len(base_records) + len(extras)})")


def popularity_score(tags: Dict[str, Any], kategori: str) -> int:
    score = 0
    tourism = str(tags.get("tourism", "")).strip()
    historic = str(tags.get("historic", "")).strip()
    natural = str(tags.get("natural", "")).strip()
    leisure = str(tags.get("leisure", "")).strip()
    man_made = str(tags.get("man_made", "")).strip()

    if tourism in {"attraction", "museum", "theme_park", "zoo"}:
        score += 60
    elif tourism:
        score += 18

    if historic in {"monument", "memorial", "castle", "archaeological_site"}:
        score += 52
    elif historic:
        score += 32

    if natural in {"peak", "beach", "cave", "waterfall"}:
        score += 42
    elif natural:
        score += 18

    if leisure in {"park", "garden", "nature_reserve"}:
        score += 26

    if man_made in {"tower", "bridge"}:
        score += 24

    if tags.get("wikipedia"):
        score += 30
    if tags.get("wikidata"):
        score += 35

    if "museum" in kategori:
        score += 12
    if "historic" in kategori:
        score += 10
    if "natural" in kategori:
        score += 8
    return score


def build_turkey_batch_queries() -> List[str]:
    return [
        """
[out:json][timeout:180];
area["ISO3166-1"="TR"][admin_level=2]->.tr;
(
  nwr(area.tr)["tourism"~"attraction|museum|theme_park|zoo|viewpoint"];
  nwr(area.tr)["historic"];
);
out center tags;
""".strip(),
        """
[out:json][timeout:180];
area["ISO3166-1"="TR"][admin_level=2]->.tr;
(
  nwr(area.tr)["natural"~"peak|beach|cave|waterfall"];
  nwr(area.tr)["leisure"~"park|garden|nature_reserve"];
  nwr(area.tr)["man_made"~"tower|bridge"];
);
out center tags;
""".strip(),
    ]


def fetch_turkey_batch_elements(refresh_cache: bool = False) -> List[Dict[str, Any]]:
    CACHE_TOP_DIR.mkdir(parents=True, exist_ok=True)
    all_elements: List[Dict[str, Any]] = []
    queries = build_turkey_batch_queries()

    for i, query in enumerate(queries, 1):
        cache_path = CACHE_TOP_DIR / f"tr_batch_{i}.json"
        payload: Optional[Dict[str, Any]] = None
        if not refresh_cache:
            payload = read_json(cache_path)

        if not payload:
            payload = fetch_from_endpoints(query, i % len(OVERPASS_ENDPOINTS))
            if payload:
                write_json(cache_path, payload)

        if not payload and cache_path.exists():
            payload = read_json(cache_path)

        if not payload:
            print(f"[WARN] Batch {i}: veri alinamadi")
            continue

        elements = payload.get("elements")
        if isinstance(elements, list):
            all_elements.extend([el for el in elements if isinstance(el, dict)])
            print(f"[BATCH] {i}: element={len(elements)}")
    return all_elements


def merge_keep_existing(base_records: List[Dict[str, Any]], new_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    existing_ids = {str(item.get("id", "")) for item in base_records}
    merged = list(base_records)
    added = 0
    for item in new_records:
        key = str(item.get("id", ""))
        if not key or key in existing_ids:
            continue
        merged.append(item)
        existing_ids.add(key)
        added += 1
    print(f"[MERGE] yeni_eklenen={added}, toplam={len(merged)}")
    return merged


def add_to_base_index(item: Dict[str, Any], base_idx: Dict[str, Set[Any]]) -> None:
    osm_type = str(item.get("osm_type", "")).strip()
    osm_id = str(item.get("osm_id", "")).strip()
    if osm_type and osm_id:
        base_idx["osm"].add(f"{osm_type}:{osm_id}")

    tags = item.get("tags") if isinstance(item.get("tags"), dict) else {}
    wikidata = str(tags.get("wikidata", "") or "").strip()
    wikipedia = str(tags.get("wikipedia", "") or "").strip().lower()
    if wikidata:
        base_idx["wikidata"].add(wikidata)
    if wikipedia:
        base_idx["wikipedia"].add(wikipedia)

    try:
        base_idx["name_loc"].add((
            normalize_text(item.get("ad", "")),
            normalize_text(item.get("il", "")),
            round(float(item.get("lat", 0.0)), 3),
            round(float(item.get("lon", 0.0)), 3),
        ))
    except Exception:
        pass


def build_near_index(records: List[Dict[str, Any]]) -> Dict[Tuple[str, str], List[Tuple[float, float]]]:
    near_idx: Dict[Tuple[str, str], List[Tuple[float, float]]] = {}
    for item in records:
        city_key = normalize_text(item.get("il", ""))
        name_key = normalize_text(item.get("ad", ""))
        if not name_key:
            continue
        try:
            lat = float(item.get("lat", 0.0))
            lon = float(item.get("lon", 0.0))
        except Exception:
            continue
        near_idx.setdefault((city_key, name_key), []).append((lat, lon))
    return near_idx


def is_duplicate_city_name_near(
    item: Dict[str, Any],
    near_idx: Dict[Tuple[str, str], List[Tuple[float, float]]],
    max_distance_m: float = 75.0,
) -> bool:
    city_key = normalize_text(item.get("il", ""))
    name_key = normalize_text(item.get("ad", ""))
    if not name_key:
        return True
    try:
        lat = float(item.get("lat", 0.0))
        lon = float(item.get("lon", 0.0))
    except Exception:
        return True

    key = (city_key, name_key)
    for prev_lat, prev_lon in near_idx.get(key, []):
        if haversine_m(lat, lon, prev_lat, prev_lon) <= max_distance_m:
            return True
    return False


def add_to_near_index(item: Dict[str, Any], near_idx: Dict[Tuple[str, str], List[Tuple[float, float]]]) -> None:
    city_key = normalize_text(item.get("il", ""))
    name_key = normalize_text(item.get("ad", ""))
    if not name_key:
        return
    try:
        lat = float(item.get("lat", 0.0))
        lon = float(item.get("lon", 0.0))
    except Exception:
        return
    near_idx.setdefault((city_key, name_key), []).append((lat, lon))


def fetch_turkey_batch_groups(refresh_cache: bool = False) -> List[Tuple[str, List[Dict[str, Any]]]]:
    CACHE_TOP_DIR.mkdir(parents=True, exist_ok=True)
    groups: List[Tuple[str, List[Dict[str, Any]]]] = []
    queries = build_turkey_batch_queries()

    for i, query in enumerate(queries, 1):
        cache_path = CACHE_TOP_DIR / f"tr_batch_{i}.json"
        payload: Optional[Dict[str, Any]] = None
        if not refresh_cache:
            payload = read_json(cache_path)

        if not payload:
            payload = fetch_from_endpoints(query, i % len(OVERPASS_ENDPOINTS))
            if payload:
                write_json(cache_path, payload)

        if not payload and cache_path.exists():
            payload = read_json(cache_path)

        if not payload:
            print(f"[WARN] TR-BATCH-{i}: veri alinamadi")
            groups.append((f"TR-BATCH-{i}", []))
            continue

        elements = payload.get("elements")
        if isinstance(elements, list):
            rows = [el for el in elements if isinstance(el, dict)]
            print(f"[BATCH] TR-BATCH-{i}: element={len(rows)}")
            groups.append((f"TR-BATCH-{i}", rows))
        else:
            groups.append((f"TR-BATCH-{i}", []))
    return groups


def build_city_priority_order() -> List[str]:
    priority = [
        "İstanbul", "Ankara", "İzmir", "Antalya", "Bursa", "Adana", "Konya", "Gaziantep",
        "Mersin", "Muğla", "Trabzon", "Eskişehir", "Kocaeli", "Kayseri", "Samsun", "Aydın",
        "Balıkesir", "Çanakkale", "Denizli", "Hatay", "Şanlıurfa", "Manisa", "Nevşehir",
    ]
    ordered = []
    seen = set()
    for city in priority + ALL_TR_CITIES:
        if city not in seen:
            ordered.append(city)
            seen.add(city)
    return ordered


def build_final_record_with_image(rec: Dict[str, Any], wiki_cache: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    tags = rec.get("tags") if isinstance(rec.get("tags"), dict) else {}
    image_url, _, _, _ = resolve_image_url(tags, wiki_cache)
    if not image_url:
        return None
    return {
        "id": rec.get("id"),
        "il": rec.get("il", ""),
        "ad": rec.get("ad"),
        "kategori": rec.get("kategori"),
        "lat": rec.get("lat"),
        "lon": rec.get("lon"),
        "osm_type": rec.get("osm_type"),
        "osm_id": rec.get("osm_id"),
        "tags": tags,
        "image_url": image_url,
    }


def run_target_total_mode(args: argparse.Namespace) -> None:
    if not args.with_images:
        print("[WARN] --target-total modunda --with-images zorunlu kabul edilir.")

    target_total = max(1, int(args.target_total or 5000))
    merge_in_path = args.merge_in if args.merge_in.is_absolute() else ROOT / args.merge_in
    out_path = args.out if args.out.is_absolute() else ROOT / args.out
    added_out_path = args.added_out if args.added_out.is_absolute() else ROOT / args.added_out

    base_records = read_json_array(merge_in_path)
    merged_records = list(base_records)
    base_idx = build_base_index(merged_records)
    near_idx = build_near_index(merged_records)
    print(f"[BASE] {merge_in_path} kayit={len(base_records)} hedef={target_total}")

    if len(merged_records) >= target_total:
        write_json(added_out_path, [])
        write_json(out_path, merged_records)
        print(f"DONE toplam={len(merged_records)}, yeni_eklenen=0, image_url_bos=0")
        print(f"[DONE] added_out={added_out_path}")
        print(f"[DONE] merge_out={out_path}")
        return

    wiki_cache = load_wiki_cache()
    added_records: List[Dict[str, Any]] = []

    def process_batch(batch_name: str, records: List[Dict[str, Any]]) -> None:
        nonlocal merged_records, added_records, base_idx, near_idx
        if len(merged_records) >= target_total or not records:
            print(f"[BATCH] {batch_name}: islenen=0, bulunan_gorselli=0, eklenen=0, toplam={len(merged_records)}")
            return

        records = dedupe_name_near(unique_by_id(records), max_distance_m=75.0)
        records.sort(
            key=lambda r: -popularity_score(
                r.get("tags", {}) if isinstance(r.get("tags"), dict) else {},
                str(r.get("kategori", "")),
            )
        )

        processed = 0
        visual_found = 0
        added_in_batch = 0
        for rec in records:
            if len(merged_records) >= target_total:
                break
            processed += 1

            if candidate_in_base(rec, base_idx):
                continue
            if is_duplicate_city_name_near(rec, near_idx, max_distance_m=75.0):
                continue

            final_rec = build_final_record_with_image(rec, wiki_cache)
            if not final_rec:
                continue
            visual_found += 1

            added_records.append(final_rec)
            merged_records.append(final_rec)
            add_to_base_index(final_rec, base_idx)
            add_to_near_index(final_rec, near_idx)
            added_in_batch += 1

        print(
            f"[BATCH] {batch_name}: islenen={processed}, bulunan_gorselli={visual_found}, "
            f"eklenen={added_in_batch}, toplam={len(merged_records)}"
        )

    batch_groups = fetch_turkey_batch_groups(refresh_cache=args.refresh_cache)
    for batch_name, elements in batch_groups:
        batch_records: List[Dict[str, Any]] = []
        for element in elements:
            rec = to_record("", element)
            if rec:
                batch_records.append(rec)
        process_batch(batch_name, batch_records)
        if len(merged_records) >= target_total:
            break

    city_order = build_city_priority_order()
    for idx, city in enumerate(city_order):
        if len(merged_records) >= target_total:
            break
        try:
            elements = fetch_city_elements(city, args.refresh_cache, idx % len(OVERPASS_ENDPOINTS))
            city_records = []
            for element in elements:
                rec = to_record(city, element)
                if rec:
                    city_records.append(rec)

            boost = 2 if city in city_order[:12] else 1
            cap = max(1, args.limit_per_city * boost)
            city_records.sort(
                key=lambda r: -popularity_score(
                    r.get("tags", {}) if isinstance(r.get("tags"), dict) else {},
                    str(r.get("kategori", "")),
                )
            )
            process_batch(f"CITY-{city}", city_records[:cap])
            time.sleep(0.15)
        except Exception as exc:
            print(f"[WARN] CITY-{city}: batch atlandi ({exc})")

    save_wiki_cache(wiki_cache)

    merged_records.sort(key=lambda r: (str(r.get("il", "")), str(r.get("ad", "")).lower(), str(r.get("id", ""))))
    added_records.sort(key=lambda r: (str(r.get("il", "")), str(r.get("ad", "")).lower(), str(r.get("id", ""))))

    write_json(added_out_path, added_records)
    write_json(out_path, merged_records)

    image_empty_count = sum(1 for row in added_records if not str(row.get("image_url", "")).strip())
    if len(merged_records) < target_total:
        print(f"[WARN] hedefe ulasilamadi: hedef={target_total}, toplam={len(merged_records)}")
    print(f"DONE toplam={len(merged_records)}, yeni_eklenen={len(added_records)}, image_url_bos={image_empty_count}")
    print(f"[DONE] added_out={added_out_path}")
    print(f"[DONE] merge_out={out_path}")


def run_top_tr_mode(args: argparse.Namespace) -> None:
    if args.target_total is not None:
        run_target_total_mode(args)
        return

    target_n = max(1, int(args.top_tr or 1000))
    if not args.with_images:
        print("[WARN] --top-tr modunda --with-images zorunlu kabul edilir; gorselsiz kayitlar alinmaz.")

    merge_in_path = args.merge_in if args.merge_in.is_absolute() else ROOT / args.merge_in
    out_path = args.out if args.out.is_absolute() else ROOT / args.out
    merge_out_path = args.merge_out if args.merge_out and args.merge_out.is_absolute() else (ROOT / args.merge_out if args.merge_out else ROOT / "dataset/places_tr_merged.json")

    base_records = read_json_array(merge_in_path)
    base_idx = build_base_index(base_records)
    print(f"[BASE] {merge_in_path} kayit={len(base_records)}")

    raw_elements = fetch_turkey_batch_elements(refresh_cache=args.refresh_cache)
    candidates: List[Dict[str, Any]] = []
    for element in raw_elements:
        rec = to_record("", element)
        if not rec:
            continue
        if candidate_in_base(rec, base_idx):
            continue
        candidates.append(rec)

    candidates = dedupe_name_near(unique_by_id(candidates), max_distance_m=75.0)
    wiki_cache = load_wiki_cache()

    candidates.sort(key=lambda r: -popularity_score(r.get("tags", {}) if isinstance(r.get("tags"), dict) else {}, str(r.get("kategori", ""))))
    scan_limit = max(target_n, int(args.top_scan_limit))
    candidates = candidates[:scan_limit]
    print(f"[TOP-TR] taranacak_aday={len(candidates)}")

    scored: List[Dict[str, Any]] = []
    for idx, rec in enumerate(candidates, 1):
        tags = rec.get("tags") if isinstance(rec.get("tags"), dict) else {}
        image_url, source, wikipedia_raw, wikidata = resolve_image_url(tags, wiki_cache)
        if not image_url:
            continue

        enriched = {
            "id": rec.get("id"),
            "il": rec.get("il", ""),
            "ad": rec.get("ad"),
            "kategori": rec.get("kategori"),
            "lat": rec.get("lat"),
            "lon": rec.get("lon"),
            "osm_type": rec.get("osm_type"),
            "osm_id": rec.get("osm_id"),
            "tags": tags,
            "score": popularity_score(tags, str(rec.get("kategori", ""))),
            "wikipedia": wikipedia_raw,
            "wikidata": wikidata,
            "image_url": image_url,
            "source": source or "",
        }
        scored.append(enriched)
        if idx % 25 == 0:
            print(f"[TOP-TR] islenen={idx}/{len(candidates)} bulunan={len(scored)}")
        if len(scored) >= target_n * 2:
            print(f"[TOP-TR] erken_durdurma: yeterli gorselli aday toplandi ({len(scored)})")
            break

    save_wiki_cache(wiki_cache)
    scored.sort(key=lambda r: (-int(r.get("score", 0) or 0), str(r.get("ad", "")).lower()))
    top_records = scored[:target_n]
    write_json(out_path, top_records)

    merged = merge_keep_existing(base_records, top_records)
    write_json(merge_out_path, merged)

    empty_image_count = sum(1 for row in top_records if not str(row.get("image_url", "")).strip())
    print(f"[VERIFY] toplam_kayit={len(merged)}")
    print(f"[VERIFY] image_url_bos_sayisi={empty_image_count}")
    print(f"[VERIFY] yeni_eklenen_kayit={len(top_records)}")
    print(f"[DONE] top_out={out_path}")
    print(f"[DONE] merge_out={merge_out_path}")


def main() -> None:
    args = parse_args()
    if args.target_total is not None or args.top_tr is not None:
        run_top_tr_mode(args)
    elif args.extra_top_tr is not None:
        run_extra_mode(args)
    else:
        run_default_mode(args)


if __name__ == "__main__":
    main()
