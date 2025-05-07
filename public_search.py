import requests
from bs4 import BeautifulSoup

def search_ru_music(query, max_results=2):
    url = f"https://ru-music.com/search/{query.replace(' ', '%20')}"
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(r.text, "html.parser")
    tracks = []
    for a in soup.select("a.download-button")[:max_results]:
        link = a.get("href")
        title = a.get("title") or a.text
        if link and link.endswith(".mp3"):
            tracks.append({
                "title": title,
                "url": link,
            })
    return tracks