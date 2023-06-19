from __future__ import annotations
import httpx
import regex
import deobf
import tls_client
import time

session = httpx.Client(timeout=3)
real_session = tls_client.Session(client_identifier="chrome_113")

class Manga():
    def __init__(self, text_id:str, include_blank_page=False) -> None:
        self.text_id = text_id
        
        self._free_url_regex = regex.compile(r'href="/vizmanga/' + self.text_id + r"-chapter-([0-9]{0,4})\/chapter\/([0-9]{0,7})\?action=read")
        self._paid_url_regex = regex.compile(r"targetUrl:'/vizmanga/" + self.text_id + r"-chapter-([0-9]{0,4})\/chapter\/([0-9]{0,7})\?action=read")

        self.html_url = f"https://www.viz.com/vizmanga/chapters/{self.text_id}"

        self._new_release_update = 10
        self._new_release_last_update = 0
        self._new_release_last_value = None

        self.chapters = None

        self.include_blank_page = include_blank_page

    def _get_manga_request(self):
        while True:
            res = real_session.get(self.html_url,
                headers={
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
                }
            )
            if res.status_code != 429:
                return res
            
            time.sleep(5)

    def fetch_chapters(self, force_update=False) -> dict[str, Chapter]:
        "Returns all chapters of the manga found. The dict is replicated to `self.chapters`, and is returned if it's not None, or `force_update` is True."
        if self.chapters is None or force_update is True:
            res = self._get_manga_request()
            
            free_matches = self._free_url_regex.findall(res.text)
            paid_matches = self._paid_url_regex.findall(res.text)
            
            temp_chapters = {}
            
            for match in free_matches:
                temp_chapters[match[0]] = Chapter(match[1], self, True)
            
            for match in paid_matches:
                temp_chapters[match[0]] = Chapter(match[1], self, False)
            
            self.chapters = temp_chapters.copy()

        return self.chapters
    
    @property
    def new_release(self) -> str:
        "Example: `7 days`, `30 minutes`.\nAuto updates every `self._new_release_update` seconds (Default: 10)."
        if time.time() + self._new_release_update > self._new_release_last_update:
            res = self._get_manga_request()
            self._new_release_last_value = str(res.text).split("New chapter coming in ", 1)[1].split('!', 1)[0]
            self._new_release_last_update = time.time()
        
        return self._new_release_last_value


class Chapter():
    def __init__(self, chapter_id:str, manga:Manga, free:bool) -> None:
        # internal id for each chapter
        self.chapter_id = chapter_id

        # whether or not the chapter requires viz (rizz) premium
        self.free = free
        
        # string identifier for the manga
        self.manga = manga

        # page count
        self.page_count = None

        # found in page url for the chapter
        self._text_id = f"{self.manga.text_id}-chapter-{self.chapter_id}"

        self.html_url = f"https://www.viz.com/vizmanga/{self._text_id}/chapter/{self.chapter_id}?action=read"

        self.include_blank_page = manga.include_blank_page

    def fetch_page_count(self, force_update=False) -> int:
        "Returns the number of pages in the chapter. The value is replicated to `self.page_count`, and is returned if it's not None, or `force_update` is True."
        if self.page_count is None or force_update is True:
            res = real_session.get(self.html_url,
                headers={
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
                }
            )

            self.page_count = int(res.text.split("pages        = ", 1)[1].split(';', 1)[0]) # the blank page isnt included
            
            if self.include_blank_page:
                self.page_count += 1

        return self.page_count

    def fetch_pages(self, page_count=None) -> dict[str, Page]:
        "Returns a dict of Page objects, with the key as the page number. If `page_count` is not given, `self.fetch_page_count()` will be called."
        if page_count is None:
            page_count = self.fetch_page_count()
        
        if self.include_blank_page:
            page_str = ''.join(f'{x},' for x in range(page_count))[:-1]
        else:
            page_str = ''.join(f'{x+1},' for x in range(page_count))[:-1]

        res = real_session.get(f"https://www.viz.com/manga/get_manga_url?device_id=3&manga_id={self.chapter_id}&pages={page_str}",
            headers={
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': self.html_url,
                'Sec-Ch-Ua': '"Google Chrome";v="113", "Chromium";v="113", "Not-A.Brand";v="24"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"Windows"',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36',
                'X-Client-Login': 'false',
                'X-Requested-With': 'XMLHttpRequest',
            }
        )

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
        "Downloads, saves, and deobfuscates the page with the given `file_name`."
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
        

# Example usage of downloading 
if __name__ == '__main__':
    chapter_id_text = "komi-cant-communicate"
    
    manga = Manga(chapter_id_text)
    chapters = manga.fetch_chapters()
    
    for page_id, page in chapters['403'].fetch_pages().items():
        page.download_page(f"komi-403-{page.page_num}.jpg")
