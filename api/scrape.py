from __future__ import annotations
import httpx
import regex
import deobf
import tls_client
import time

session = httpx.Client(timeout=3)
real_session = tls_client.Session(client_identifier="chrome_113")

# https://www.viz.com/search/series_titles.js
# contains all titles viz has [{"title": str, "subtitle": str}]
# seems like all non alphanumeric characters are replaced with "-"


# login, (remember token lasts ages)
# POST https://www.viz.com/account/try_login
# form data: login=itschasa&pass=***&rem_user=on&uid=0
# resp: {"ok":1, "trust_user_jwt": "eyJ****"}
# set-cookie: remember_token=8xAYmp5rbPEVswLamKncRdhYye9m****; path=/; expires=Fri, 24 May 2024 20:48:10 GMT
# set-cookie: _session_id=44464576beb349bc9aca05d9********; path=/; expires=Wed, 31 May 2023 20:39:57 GMT; HttpOnly
# set-cookie: prev_login=itschasa; path=/; expires=Wed, 31 May 2023 20:39:57 GMT (maybe important idk)

# this may be preferred \/ as it doesnt require csrf-token
# refresh session_id
# GET https://www.viz.com/account/refresh_login_links
# with remember_token on cookie
# Set-Cookie: _session_id=3e5c89cd18ecee25ec26480b074df27b; path=/; expires=Wed, 31 May 2023 20:51:12 GMT; HttpOnly
# Set-Cookie: remember_token=8xAYmp5rbPEVswLamKncRdhYye9m6xnH; path=/; expires=Fri, 24 May 2024 20:51:12 GMT


class Manga():
    def __init__(self, text_id:str) -> None:
        self.text_id = text_id
        
        self._url_regex = regex.compile(self.text_id + r"-chapter-([0-9]{0,3})\/chapter\/([0-9]{0,7})\?action=read")

        self.html_url = f"https://www.viz.com/vizmanga/chapters/{self.text_id}"

        self._new_release_update = 15
        self._new_release_last_update = 0
        self._new_release_last_value = None

    def _get_manga_request(self):
        while True:
            res = real_session.get(self.html_url, headers={
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept-Language': 'en-US,en;q=0.9',
                'Cache-Control': 'max-age=0',
                'Sec-Ch-Ua': '"Google Chrome";v="113", "Chromium";v="113", "Not-A.Brand";v="24"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"Windows"',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'Sec-Fetch-User': '?1',
                'Upgrade-Insecure-Requests': '1',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36'
            })
            if res.status_code != 429:
                return res
            
            time.sleep(5)

    def fetch_chapters(self) -> dict[str, Chapter]:
        "`{'403': <Chapter()>, ...}`"
        
        res = self._get_manga_request()
        matches = self._url_regex.findall(res.text)
        
        chapters = {}
        for match in matches:
            chapters[match[0]] = Chapter(match[1], self)
        
        return chapters
    
    @property
    def new_release(self) -> str:
        "Example: `7 days`, `30 minutes`.\nAuto updates every `self._new_release_update` seconds (Default: 15)."
        if time.time() + self._new_release_update > self._new_release_last_update:
            res = self._get_manga_request()
            self._new_release_last_update = str(res.text).split("New chapter coming in ", 1)[1].split('!', 1)[0]
        
        return self._new_release_last_value


class Chapter():
    def __init__(self, chapter_id:str, manga:Manga) -> None:
        # internal id for each chapter
        self.chapter_id = chapter_id
        
        # string identifier for the manga
        self.manga = manga

        # page count
        self.page_count = None

        # found in page url for the chapter
        self._text_id = f"{self.manga.text_id}-chapter-{self.chapter_id}"

        self.html_url = f"https://www.viz.com/vizmanga/{self._text_id}/chapter/{self.chapter_id}?action=read"

    def fetch_page_count(self, force_update=False) -> int:
        if self.page_count is None or force_update is True:
            res = real_session.get(self.html_url, headers={
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept-Language': 'en-US,en;q=0.9',
                'Cache-Control': 'max-age=0',
                'Sec-Ch-Ua': '"Google Chrome";v="113", "Chromium";v="113", "Not-A.Brand";v="24"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"Windows"',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'Sec-Fetch-User': '?1',
                'Upgrade-Insecure-Requests': '1',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36'
            })

            self.page_count = int(res.text.split("pages        = ", 1)[1].split(';', 1)[0]) + 1 # because of the blank page at the start

        return self.page_count

    def fetch_pages(self, page_count=None) -> dict[str, Page]:
        if page_count is None:
            if self.page_count is None:
                page_count = self.fetch_page_count()
            else:
                page_count = self.page_count
        
        res = real_session.get(f"https://www.viz.com/manga/get_manga_url?device_id=3&manga_id={self.chapter_id}&pages={''.join(f'{x},' for x in range(page_count))[:-1]}", headers={
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': f'https://www.viz.com/vizmanga/{self._text_id}/chapter/{self.chapter_id}?action=read',
            'Sec-Ch-Ua': '"Google Chrome";v="113", "Chromium";v="113", "Not-A.Brand";v="24"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36',
            'X-Client-Login': 'false',
            'X-Requested-With': 'XMLHttpRequest',
        })

        pages = {}
        for page_num, page_url in res.json()['data'].items():
            pages[page_num] = Page(self.manga, self, page_url, page_num)
        
        return pages

class Page():
    def __init__(self, manga:Manga, chapter:Chapter, page_url:str, page_num:str) -> None:
        self.manga = manga
        self.chapter = chapter
        self.page_url = page_url
        self.page_num = page_num

    def download_page(self, file_name:str, deobfuscate=True) -> None:        
        res = session.get(self.page_url, headers={
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'en-US,en;q=0.9',
            #'Host': 'd2vs6ffylckc3p.cloudfront.net', # is in original request, but is not needed lol
            'Origin': 'https://www.viz.com',
            'Referer': 'https://www.viz.com/',
            'Sec-Ch-Ua': '"Google Chrome";v="113", "Chromium";v="113", "Not-A.Brand";v="24"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36'
        })

        f = open(file_name, 'wb')
        f.write(res.content)
        f.close()
        
        if deobfuscate:
            deobf.deobfuscate_image(file_name).save(file_name)
        


if __name__ == '__main__':
    chapter_id_text = "komi-cant-communicate"
    
    manga = Manga(chapter_id_text)
    chapters = manga.fetch_chapters()
    
    for page_id, page in chapters['403'].fetch_pages().items():
        page.download_page(f"komi-403-{page.page_num}.jpg")

