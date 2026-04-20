# Overpass QL Sorgulari

Bu projede her il icin ayri Overpass QL sorgusu kullanilir.

## Istanbul

```overpass
[out:json][timeout:180];
area["boundary"="administrative"]["admin_level"="4"]["name"="İstanbul"]->.searchArea;
(
  node["tourism"="attraction"](area.searchArea);
  way["tourism"="attraction"](area.searchArea);
  relation["tourism"="attraction"](area.searchArea);

  node["tourism"="museum"](area.searchArea);
  way["tourism"="museum"](area.searchArea);
  relation["tourism"="museum"](area.searchArea);

  node["tourism"="viewpoint"](area.searchArea);
  way["tourism"="viewpoint"](area.searchArea);
  relation["tourism"="viewpoint"](area.searchArea);

  node["historic"](area.searchArea);
  way["historic"](area.searchArea);
  relation["historic"](area.searchArea);

  node["natural"="peak"](area.searchArea);
  way["natural"="peak"](area.searchArea);
  relation["natural"="peak"](area.searchArea);

  node["leisure"="park"](area.searchArea);
  way["leisure"="park"](area.searchArea);
  relation["leisure"="park"](area.searchArea);
);
out center tags;
```

## Izmir

```overpass
[out:json][timeout:180];
area["boundary"="administrative"]["admin_level"="4"]["name"="İzmir"]->.searchArea;
(
  node["tourism"="attraction"](area.searchArea);
  way["tourism"="attraction"](area.searchArea);
  relation["tourism"="attraction"](area.searchArea);

  node["tourism"="museum"](area.searchArea);
  way["tourism"="museum"](area.searchArea);
  relation["tourism"="museum"](area.searchArea);

  node["tourism"="viewpoint"](area.searchArea);
  way["tourism"="viewpoint"](area.searchArea);
  relation["tourism"="viewpoint"](area.searchArea);

  node["historic"](area.searchArea);
  way["historic"](area.searchArea);
  relation["historic"](area.searchArea);

  node["natural"="peak"](area.searchArea);
  way["natural"="peak"](area.searchArea);
  relation["natural"="peak"](area.searchArea);

  node["leisure"="park"](area.searchArea);
  way["leisure"="park"](area.searchArea);
  relation["leisure"="park"](area.searchArea);
);
out center tags;
```

## Antalya

```overpass
[out:json][timeout:180];
area["boundary"="administrative"]["admin_level"="4"]["name"="Antalya"]->.searchArea;
(
  node["tourism"="attraction"](area.searchArea);
  way["tourism"="attraction"](area.searchArea);
  relation["tourism"="attraction"](area.searchArea);

  node["tourism"="museum"](area.searchArea);
  way["tourism"="museum"](area.searchArea);
  relation["tourism"="museum"](area.searchArea);

  node["tourism"="viewpoint"](area.searchArea);
  way["tourism"="viewpoint"](area.searchArea);
  relation["tourism"="viewpoint"](area.searchArea);

  node["historic"](area.searchArea);
  way["historic"](area.searchArea);
  relation["historic"](area.searchArea);

  node["natural"="peak"](area.searchArea);
  way["natural"="peak"](area.searchArea);
  relation["natural"="peak"](area.searchArea);

  node["leisure"="park"](area.searchArea);
  way["leisure"="park"](area.searchArea);
  relation["leisure"="park"](area.searchArea);
);
out center tags;
```
