import os
from PIL import Image

media_paths = [
    r"C:\Users\TEJESWAR\.gemini\antigravity\brain\bdb56abf-7523-4449-ad64-50ac4e3fcc86\.user_uploaded\media_1794581899166_eb7a9312.png",
    r"C:\Users\TEJESWAR\.gemini\antigravity\brain\bdb56abf-7523-4449-ad64-50ac4e3fcc86\.user_uploaded\media_1794438925550_5ba8d1db.png",
    r"C:\Users\TEJESWAR\.gemini\antigravity\brain\bdb56abf-7523-4449-ad64-50ac4e3fcc86\.user_uploaded\media_1794439168054_0eac6ac2.png",
    r"C:\Users\TEJESWAR\.gemini\antigravity\brain\bdb56abf-7523-4449-ad64-50ac4e3fcc86\.system_generated\logs\media\step_149_media_0.jpg",
    r"C:\Users\TEJESWAR\.gemini\antigravity\brain\bdb56abf-7523-4449-ad64-50ac4e3fcc86\.system_generated\logs\media\step_150_media_0.jpg",
    r"C:\Users\TEJESWAR\.gemini\antigravity\brain\bdb56abf-7523-4449-ad64-50ac4e3fcc86\.system_generated\logs\media\step_154_media_0.jpg",
    r"C:\Users\TEJESWAR\.gemini\antigravity\brain\bdb56abf-7523-4449-ad64-50ac4e3fcc86\.system_generated\logs\media\step_155_media_0.jpg",
    r"C:\Users\TEJESWAR\.gemini\antigravity\brain\bdb56abf-7523-4449-ad64-50ac4e3fcc86\.system_generated\logs\media\step_156_media_0.jpg",
    r"C:\Users\TEJESWAR\.gemini\antigravity\brain\bdb56abf-7523-4449-ad64-50ac4e3fcc86\.system_generated\logs\media\step_7_media_0.jpg",
]

for p in media_paths:
    if os.path.exists(p):
        im = Image.open(p)
        print(f"{os.path.basename(p)}: {im.size}, format={im.format}")
    else:
        print(f"MISSING: {p}")

