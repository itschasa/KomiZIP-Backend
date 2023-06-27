from PIL import Image
from io import BytesIO
import json
import flask
import re
import os

def get_latest_chapter(data) -> str:
    "Find latest chapter from a dict, and return it's key."
    latest = None
    for num in data.keys():
        if latest is None or float(num) > float(latest):
            latest = num
    return latest

def load_chapters_json() -> dict:
    f = open('chapters.json', 'r')
    data = json.loads(f.read())
    f.close()
    return data

def save_chapters_json(data) -> None:
    f = open('chapters.json', 'w')
    f.write(json.dumps(data, indent=4))
    f.close()

def create_chapters_response(chapter_data, new_release_data) -> flask.Response:
    return flask.Response(
        response = json.dumps({
            "error": False,
            "new_release": new_release_data,
            "chapters": chapter_data,
            "order": list(chapter_data.keys())
        }),
        status   = 200,
        headers  = {
            "Content-Type": "application/json"
        }
    )

def extract_admin_data(input_data):
    data = {}
    pattern = re.compile(r'([A-Za-z]+)="((?:[^\\"]|\\\\|\\")*)"|([A-Za-z]+)=([0-9]+)')
    
    for line in input_data.replace('\r', '').split('\n'):
        if '=' in line:
            matches = pattern.findall(line)
            identifier = line.split(' ', 1)[0]
            data[identifier] = {}
            for match in matches:
                starting_point = 0
                for group in match:
                    if group == '':
                        starting_point += 1
                    else: break
                data[identifier][match[starting_point]] = match[starting_point+1].replace('\\"', '"')
    
    return data

def validate_admin_data(input_dict):
    for key, value in input_dict.items():
        if '-' in key:
            chapter1, chapter2 = key.split('-')
            if float(chapter1) > float(chapter2):
                return False, 'chapter1 > chapter2 (where "chapter1-chapter2 ...")'
        
        for ke, val in value.items():
            if ke not in ['title', 'volume']:
                return False, f'arg not allowed ({ke})'
            elif ke == 'volume':
                try:
                    int(val)
                except:
                    return False, f'volume arg not int ({val})'
    return True, ''

def edit_chapter(chapter, args, chapters_json, cover_exist_cache):
    edited = []
    if args.get('title') is not None:
        chapters_json[chapter]['metadata']['title'] = args['title']
        edited.append('title')

    if args.get('volume') is not None:
        chapters_json[chapter]['metadata']['volume'] = args['volume']
        edited.append('volume')
        if args['volume'] in cover_exist_cache or os.path.exists(f'../cdn/vol{args["volume"]}.jpg'):
            cover_exist_cache.append(args['volume'])
            chapters_json[chapter]['metadata']['volume_cover'] = True
            edited.append('volume_cover')
    
    return chapters_json, edited

def has_only_white_pixels(image_data):
    img = Image.open(BytesIO(image_data))
    img = img.convert('RGB')

    width, height = img.size
    for x in range(width):
        for y in range(height):
            r, g, b = img.getpixel((x, y))
            if r != 255 or g != 255 or b != 255:
                return False

    return True