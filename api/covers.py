import httpx
import os

class Cover():
    def __init__(self, url, volume) -> None:
        self.url = url
        self.volume = volume

    def download(self, check_exist=True):
        if not os.path.exists(f"../cdn/vol{self.volume}.jpg") or check_exist is False:
            req = httpx.get(self.url)
            if req.status_code == 200:
                f = open(f"../cdn/vol{self.volume}.jpg", 'wb')
                f.write(req.content)
                f.close()
                return True
        return False

def fetch_all_covers() -> list[Cover]:
    r = httpx.get("https://api.mangadex.org/cover?order[volume]=asc&manga[]=a96676e5-8ae2-425e-b549-7f15dd34a6d8&limit=100&offset=0")
    data = r.json()['data']
    
    results = []
    for result in data:
        if result['type'] == 'cover_art':
            results.append(
                Cover(
                    f"https://mangadex.org/covers/a96676e5-8ae2-425e-b549-7f15dd34a6d8/{result['attributes']['fileName']}",
                    result['attributes']['volume']
                )
            )
    
    return results

if __name__ == '__main__':
    for lol in fetch_all_covers():
        print(lol.url)
        lol.download()