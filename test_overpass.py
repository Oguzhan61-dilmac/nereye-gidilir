import requests
import urllib.parse

query = """
[out:json][timeout:25];
area["boundary"="administrative"]["admin_level"="4"]["name"="Trabzon"]->.searchArea;
(
    node["tourism"="museum"](area.searchArea);
);
out center tags limit 10;
"""

url = "https://overpass-api.de/api/interpreter"
headers = {"Content-Type": "application/x-www-form-urlencoded"}
data = "data=" + urllib.parse.quote(query)

try:
    response = requests.post(url, headers=headers, data=data, timeout=10)
    print("STATUS:", response.status_code)
    print("BODY:", response.text[:500])
except Exception as e:
    print("ERROR:", e)
