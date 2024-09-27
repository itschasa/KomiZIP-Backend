import httpx
import bs4

def get_title(chapter_id: str):
    try:
        res = httpx.get('https://komisan.fandom.com/wiki/Chapter_' + chapter_id)
        res.raise_for_status()
        return res.text.split('<h2 class="pi-item pi-header pi-secondary-font pi-item-spacing pi-secondary-background">')[1].split('</h2>')[0]
    except:
        return None
    
def get_chapters_in_volume(volume_id: str):
    try:
        res = httpx.get('https://komisan.fandom.com/wiki/Volume_' + volume_id)
        res.raise_for_status()
    except:
        return None
    
    bs = bs4.BeautifulSoup(res.text, 'html.parser')
    chapters = []
    for elm in bs.select('#List_of_Chapters')[0].find_next('ul').find_all('li'):
        try:
            chapters.append(str(elm).split('title="Chapter ')[1].split('"')[0])
        except:
            pass
    
    return chapters if len(chapters) > 0 else None


if __name__ == '__main__':
    print(get_title("400")) # Expected output: "Kawai-san's House."
    print(get_chapters_in_volume("33")) # Expected output: ['429', '430', '431', '432', '433', '434', '435', '436', '437', '438', '439', '440', '441', '442']