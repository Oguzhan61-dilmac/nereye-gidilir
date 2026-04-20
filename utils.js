const DATASET_PATH = "dataset/places_tr_merged.json";
const PLACEHOLDER_IMAGE = "images/placeholder.svg";
let placesCachePromise = null;

function toText(value) {
  return String(value ?? "").trim();
}

function normalizeTr(value) {
  return toText(value)
    .toLocaleLowerCase("tr-TR")
    .replace(/ı/g, "i")
    .replace(/İ/g, "i")
    .replace(/ş/g, "s")
    .replace(/ğ/g, "g")
    .replace(/ç/g, "c")
    .replace(/ö/g, "o")
    .replace(/ü/g, "u")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function normalizeText(value) {
  return normalizeTr(value);
}

function escapeHtml(value) {
  return toText(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function hasValidImage(imageUrl) {
  const value = toText(imageUrl).toLowerCase();
  if (!value) return false;
  if (value.includes("placeholder")) return false;
  if (value.includes("categories/")) return false;
  return true;
}

function resolveImageSource(imageUrl) {
  const value = toText(imageUrl);
  if (!hasValidImage(value)) return PLACEHOLDER_IMAGE;
  if (value.startsWith("http://") || value.startsWith("https://")) return value;
  if (value.startsWith("images/")) return value;
  return value;
}

async function fetchJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path} (${response.status})`);
  return response.json();
}

async function loadPlaces() {
  if (!placesCachePromise) {
    placesCachePromise = (async () => {
      const payload = await fetchJson(DATASET_PATH);
      if (!Array.isArray(payload)) throw new Error(`${DATASET_PATH} geçersiz JSON formatı`);
      return payload;
    })();
  }
  return placesCachePromise;
}

async function loadDataset() {
  return loadPlaces();
}

function getFilteredPlaces(places, filters = {}) {
  const q = normalizeTr(filters.q || "");
  const il = toText(filters.il || "");
  const kategori = toText(filters.kategori || "");

  return places.filter((item) => {
    // Canlı Modda fotoğraflar asenkron yüklenir, valid check yapılamaz:
    if (il && toText(item.il) !== il) return false;
    if (kategori && toText(item.kategori) !== kategori) return false;
    if (q && !normalizeTr(item.ad).includes(q)) return false;
    return true;
  });
}

function haversine(a, b) {
  const toRad = (deg) => (deg * Math.PI) / 180;
  const lat1 = Number(a.lat);
  const lon1 = Number(a.lon);
  const lat2 = Number(b.lat);
  const lon2 = Number(b.lon);
  const R = 6371e3;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const p1 = toRad(lat1);
  const p2 = toRad(lat2);
  const x = Math.sin(dLat / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.atan2(Math.sqrt(x), Math.sqrt(1 - x));
}

function mapLink(lat, lon) {
  return `https://www.google.com/maps?q=${encodeURIComponent(`${lat},${lon}`)}`;
}

function osmLink(type, id) {
  const osmType = toText(type).toLowerCase();
  const osmId = toText(id);
  if (!osmType || !osmId) return "";
  if (!["node", "way", "relation"].includes(osmType)) return "";
  return `https://www.openstreetmap.org/${osmType}/${osmId}`;
}

function truncateText(text, maxLen) {
  const value = toText(text);
  if (value.length <= maxLen) return value;
  return `${value.slice(0, maxLen - 1).trim()}...`;
}

function firstNonEmpty(tags, keys) {
  if (!tags || typeof tags !== "object") return "";
  for (const key of keys) {
    const value = tags[key];
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return "";
}

function detectTheme(tags, kategori) {
  const k = toText(kategori).toLowerCase();
  const tourism = toText(tags?.tourism).toLowerCase();
  const amenity = toText(tags?.amenity).toLowerCase();
  if (tourism === "museum" || k.includes("museum") || amenity === "museum") return "museum";
  if (tags?.historic || k.includes("historic")) return "historic";
  if (tags?.natural || k.includes("natural") || toText(tags?.leisure) === "park") return "nature";
  if (amenity === "place_of_worship") return "worship";
  if (tourism === "viewpoint") return "viewpoint";
  return "general";
}

function fallbackDescription(theme, city, name, detailMode) {
  if (theme === "museum") {
    return detailMode
      ? `${name}, ${city} gezi planında kültürel derinlik kazandıran bir müze deneyimi sunar. Bölgenin hikayesini yerinde görmek için güçlü bir duraktır.`
      : "Müze koleksiyonu ve yerel hikayesiyle rotana değer katar.";
  }
  if (theme === "historic") {
    return detailMode
      ? `${name}, tarihi dokusu ve mimari detaylarıyla öne çıkar. ${city} gezisinde geçmişe dokunmak için ziyaret edilebilir.`
      : "Tarihi atmosferiyle yürüyüş ve fotoğraf için güçlü bir durak.";
  }
  if (theme === "nature") {
    return detailMode
      ? `${name}, doğa odaklı bir mola arayanlar için manzara ve açık hava deneyimi sunar. ${city} içinde sakin bir kaçış noktasıdır.`
      : "Doğa ve manzara odaklı keyifli bir keşif noktası.";
  }
  if (theme === "viewpoint") {
    return detailMode
      ? `${name}, şehir siluetini farklı açıdan izleyebileceğin etkileyici bir manzara noktasıdır. Gün batımı için idealdir.`
      : "Şehri farklı açıdan görebileceğin etkileyici bir manzara noktası.";
  }
  if (theme === "worship") {
    return detailMode
      ? `${name}, mimarisi ve atmosferiyle dikkat çeken bir ziyaret noktasıdır. Kültürel rota içinde sakin bir durak olarak öne çıkar.`
      : "Mimari detayları ve sakin atmosferiyle görülmeye değer.";
  }
  return detailMode
    ? `${name}, ${city} gezi planında keşfetmeye değer bir noktadır. Konum çevresindeki detaylarla birlikte deneyimi zenginleştirebilirsin.`
    : "Keşif rotana ekleyebileceğin güçlü bir gezi noktası.";
}

function generateDescription(item, detailMode = false) {
  const tags = item?.tags || {};
  const city = toText(item?.il) || "bu şehir";
  const name = toText(item?.ad) || "Bu yer";
  const rawDesc = firstNonEmpty(tags, ["description:tr", "description"]);
  if (rawDesc) return truncateText(rawDesc, detailMode ? 260 : 140);

  const theme = detectTheme(tags, item?.kategori);
  return truncateText(fallbackDescription(theme, city, name, detailMode), detailMode ? 260 : 140);
}

