import urllib.request
import re

try:
    req = urllib.request.Request('https://pixabay.com/videos/search/cat/', headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'})
    html = urllib.request.urlopen(req).read().decode('utf-8')
    links = re.findall(r'https://cdn\.pixabay\.com/video/[^\"]+\.mp4', html)
    print("Found links:", len(links))
    if links:
        print(links[:3])
except Exception as e:
    print("Error:", e)
