const DATASET_PATH = "dataset/places_tr_merged.json";
const PLACEHOLDER_IMAGE = "images/placeholder.svg";
let placesCachePromise = null;

function toText(value) {
  return String(value ?? "").trim();
}

function normalizeTr(value) {
  return toText(value)
    .toLocaleLowerCase("tr-TR")
    // Handle both proper Turkish chars and common mojibake forms.
    .replace(/(?:\u0131|\u00C4\u00B1)/g, "i")
    .replace(/(?:\u015F|\u00C5\u0178)/g, "s")
    .replace(/(?:\u011F|\u00C4\u0178)/g, "g")
    .replace(/(?:\u00E7|\u00C3\u00A7)/g, "c")
    .replace(/(?:\u00F6|\u00C3\u00B6)/g, "o")
    .replace(/(?:\u00FC|\u00C3\u00BC)/g, "u")
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
      if (!Array.isArray(payload)) throw new Error(`${DATASET_PATH} geÃ§ersiz JSON formatÄ±`);
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
    // CanlÄ± Modda fotoÄŸraflar asenkron yÃ¼klenir, valid check yapÄ±lamaz:
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
      ? `${name}, ${city} gezi planÄ±nda kÃ¼ltÃ¼rel derinlik kazandÄ±ran bir mÃ¼ze deneyimi sunar. BÃ¶lgenin hikayesini yerinde gÃ¶rmek iÃ§in gÃ¼Ã§lÃ¼ bir duraktÄ±r.`
      : "MÃ¼ze koleksiyonu ve yerel hikayesiyle rotana deÄŸer katar.";
  }
  if (theme === "historic") {
    return detailMode
      ? `${name}, tarihi dokusu ve mimari detaylarÄ±yla Ã¶ne Ã§Ä±kar. ${city} gezisinde geÃ§miÅŸe dokunmak iÃ§in ziyaret edilebilir.`
      : "Tarihi atmosferiyle yÃ¼rÃ¼yÃ¼ÅŸ ve fotoÄŸraf iÃ§in gÃ¼Ã§lÃ¼ bir durak.";
  }
  if (theme === "nature") {
    return detailMode
      ? `${name}, doÄŸa odaklÄ± bir mola arayanlar iÃ§in manzara ve aÃ§Ä±k hava deneyimi sunar. ${city} iÃ§inde sakin bir kaÃ§Ä±ÅŸ noktasÄ±dÄ±r.`
      : "DoÄŸa ve manzara odaklÄ± keyifli bir keÅŸif noktasÄ±.";
  }
  if (theme === "viewpoint") {
    return detailMode
      ? `${name}, ÅŸehir siluetini farklÄ± aÃ§Ä±dan izleyebileceÄŸin etkileyici bir manzara noktasÄ±dÄ±r. GÃ¼n batÄ±mÄ± iÃ§in idealdir.`
      : "Åehri farklÄ± aÃ§Ä±dan gÃ¶rebileceÄŸin etkileyici bir manzara noktasÄ±.";
  }
  if (theme === "worship") {
    return detailMode
      ? `${name}, mimarisi ve atmosferiyle dikkat Ã§eken bir ziyaret noktasÄ±dÄ±r. KÃ¼ltÃ¼rel rota iÃ§inde sakin bir durak olarak Ã¶ne Ã§Ä±kar.`
      : "Mimari detaylarÄ± ve sakin atmosferiyle gÃ¶rÃ¼lmeye deÄŸer.";
  }
  return detailMode
    ? `${name}, ${city} gezi planÄ±nda keÅŸfetmeye deÄŸer bir noktadÄ±r. Konum Ã§evresindeki detaylarla birlikte deneyimi zenginleÅŸtirebilirsin.`
    : "KeÅŸif rotana ekleyebileceÄŸin gÃ¼Ã§lÃ¼ bir gezi noktasÄ±.";
}

function generateDescription(item, detailMode = false) {
  const tags = item?.tags || {};
  const city = toText(item?.il) || "bu ÅŸehir";
  const name = toText(item?.ad) || "Bu yer";
  const rawDesc = firstNonEmpty(tags, ["description:tr", "description"]);
  if (rawDesc) return truncateText(rawDesc, detailMode ? 260 : 140);

  const theme = detectTheme(tags, item?.kategori);
  return truncateText(fallbackDescription(theme, city, name, detailMode), detailMode ? 260 : 140);
}


