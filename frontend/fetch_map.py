import urllib.request
import json
import ssl

ssl._create_default_https_context = ssl._create_unverified_context
url = "https://www.geoboundaries.org/api/current/gbOpen/KEN/ADM1/"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        d_url = data['gjDownloadURL']
        print(f"Downloading from {d_url}...")
        req2 = urllib.request.Request(d_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req2) as res2:
            with open("public/counties.geojson", "wb") as f:
                f.write(res2.read())
    print("SUCCESS: Downloaded to public/counties.geojson")
except Exception as e:
    print(f"Error: {e}")
