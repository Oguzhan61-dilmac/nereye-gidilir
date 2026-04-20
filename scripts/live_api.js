// Canlı Harita (Overpass) ve Vikipedi Arama (Real-Time API) Motoru

/**
 * Kullanıcının Seçtiği İlin Canlı Overpass verilerini çeker.
 * @param {string} cityName - Seçilen Şehir (Örn: "Antalya")
 */
async function fetchLiveOverpassData(cityName) {
    let bbox = "";
    
    // 1. En güvenilir ve hızlı yöntem: Lokal GeoJSON'dan ilin sınır kutusunu (Bounding Box) bul.
    try {
        const geoRes = await fetch("./assets/geo/tr_provinces_simplified.geojson");
        if (geoRes.ok) {
            const geoData = await geoRes.json();
            const feature = geoData.features.find(f => {
                const name = f.properties.name_tr || f.properties.name;
                return name.toLowerCase() === cityName.toLowerCase();
            });
            
            if (feature) {
                let minLat = 90, maxLat = -90, minLon = 180, maxLon = -180;
                const extractCoords = (coords) => {
                    for (const item of coords) {
                        if (typeof item[0] === 'number') {
                            if (item[1] < minLat) minLat = item[1];
                            if (item[1] > maxLat) maxLat = item[1];
                            if (item[0] < minLon) minLon = item[0];
                            if (item[0] > maxLon) maxLon = item[0];
                        } else if (Array.isArray(item)) {
                            extractCoords(item);
                        }
                    }
                };
                extractCoords(feature.geometry.coordinates);
                if (minLat < 90) {
                    bbox = `[bbox:${minLat},${minLon},${maxLat},${maxLon}]`;
                }
            }
        }
    } catch(err) {
        console.warn("Lokal BBOX hesaplanamadı", err);
    }

    let areaDef = "";
    let suffix = "";
    if (!bbox) {
        areaDef = `area["boundary"="administrative"]["admin_level"="4"]["name"="${cityName}"]->.searchArea;`;
        suffix = "(area.searchArea)";
    }

    const query = `
        [out:json][timeout:25]${bbox};
        ${areaDef}
        (
            node["tourism"="museum"]${suffix};
            node["tourism"="attraction"]${suffix};
            node["tourism"="theme_park"]${suffix};
            node["tourism"="viewpoint"]${suffix};
            node["historic"="monument"]${suffix};
            node["historic"="castle"]${suffix};
            node["historic"="ruins"]${suffix};
            node["natural"="waterfall"]${suffix};
            node["natural"="peak"]${suffix};
            node["leisure"="nature_reserve"]${suffix};
        );
        out center tags;
    `;

    // 2. Overpass sunucusu çökmelerine (504/Too Many Requests) karşı Fallback mekanizması
    const endpoints = [
        "https://overpass-api.de/api/interpreter",
        "https://lz4.overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter"
    ];

    let data = null;
    let lastError = null;

    for (const overpassUrl of endpoints) {
        try {
            const response = await fetch(overpassUrl, {
                method: "POST",
                headers: { "Content-Type": "application/x-www-form-urlencoded" },
                body: "data=" + encodeURIComponent(query)
            });
            
            if (response.ok) {
                data = await response.json();
                break; // Başarılı olursa döngüden çık
            } else {
                throw new Error(`HTTP ${response.status} from ${overpassUrl}`);
            }
        } catch (e) {
            lastError = e;
            console.warn(`Sunucu başarısız oldu: ${overpassUrl} - Atlanıyor...`);
        }
    }

    if (!data || !data.elements) {
        console.error("Tüm Overpass sunucuları yanıt vermedi veya zaman aşımı yaşandı.", lastError);
        return [];
    }
        
    // 3. Gelen veriyi normalize et
        const places = data.elements.map(el => {
            const tags = el.tags || {};
            const name = tags["name:tr"] || tags.name;
            if (!name) return null;

            let cat = "Diğer";
            if (tags.tourism) cat = `Turizm (${tags.tourism})`;
            else if (tags.historic) cat = `Tarihi (${tags.historic})`;
            else if (tags.natural) cat = `Doğa (${tags.natural})`;
            else if (tags.leisure) cat = `Aktivite (${tags.leisure})`;

            return {
                id: `${el.type}:${el.id}`,
                ad: name,
                il: cityName,
                ilce: tags.ilce || tags["addr:district"] || "Merkez",
                lat: el.lat || (el.center && el.center.lat) || 0,
                lon: el.lon || (el.center && el.center.lon) || 0,
                kategori: cat,
                tags: tags,
                image_url: ""
            };
        }).filter(item => item !== null);

        const uniquePlaces = [];
        const seenNames = new Set();
        places.forEach(p => {
            const norm = p.ad.toLowerCase();
            if (!seenNames.has(norm)) {
                seenNames.add(norm);
                uniquePlaces.push(p);
            }
        });

        uniquePlaces.sort((a,b) => Object.keys(b.tags).length - Object.keys(a.tags).length);

        return uniquePlaces;
}

/**
 * Wikipedia API üzerinden isimle hızlı küçük resim (Thumbnail) çeker.
 */
async function fetchWikipediaImage(placeName) {
    if (!placeName) return null;
    try {
        const response = await fetch(`https://tr.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(placeName)}`);
        if (response.ok) {
            const data = await response.json();
            if (data.thumbnail && data.thumbnail.source) {
                return data.thumbnail.source;
            }
        }
        
        const engRes = await fetch(`https://en.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(placeName)}`);
        if (engRes.ok) {
            const engData = await engRes.json();
            if (engData.thumbnail && engData.thumbnail.source) {
                return engData.thumbnail.source;
            }
        }

    } catch (err) {
        console.warn("Wiki Image Hatası:", err);
    }
    return null;
}

/**
 * Tek bir mekanın detaylarını Overpass API'den id ile çeker.
 */
async function fetchSinglePlace(fullId) {
    if (!fullId) return null;
    const parts = fullId.split(":");
    if (parts.length !== 2) return null;
    
    const type = parts[0];
    const id = parts[1];
    
    const query = `
        [out:json][timeout:15];
        ${type}(${id});
        out center tags;
    `;

    try {
        const response = await fetch("https://overpass-api.de/api/interpreter", {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: "data=" + encodeURIComponent(query)
        });
        
        if (!response.ok) return null;
        const data = await response.json();
        if (!data.elements || data.elements.length === 0) return null;
        
        const el = data.elements[0];
        const tags = el.tags || {};
        
        let cat = "Diğer";
        if (tags.tourism) cat = `Turizm (${tags.tourism})`;
        else if (tags.historic) cat = `Tarihi (${tags.historic})`;
        else if (tags.natural) cat = `Doğa (${tags.natural})`;
        else if (tags.leisure) cat = `Aktivite (${tags.leisure})`;

        return {
            id: fullId,
            ad: tags["name:tr"] || tags.name || "Bilinmeyen Yer",
            il: tags.il || tags["addr:province"] || "Bilinmeyen İl",
            ilce: tags.ilce || tags["addr:district"] || "Bilinmeyen İlçe",
            lat: el.lat || (el.center && el.center.lat) || 0,
            lon: el.lon || (el.center && el.center.lon) || 0,
            kategori: cat,
            tags: tags,
            image_url: "" 
        };
    } catch (err) {
        console.error("Single Place Fetch Error:", err);
        return null;
    }
}
