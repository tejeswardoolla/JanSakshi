import urllib.request

for url in ['http://127.0.0.1:8000/api/health', 'http://localhost:5173/']:
    try:
        with urllib.request.urlopen(url, timeout=3) as res:
            print(f"{url} -> HTTP {res.getcode()}")
    except Exception as e:
        print(f"{url} -> Error: {e}")

