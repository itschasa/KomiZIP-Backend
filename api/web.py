from flask import Flask, request, Response
from waitress import serve
import flask
import time
import werkzeug
import json
import threading
import logging

import scrape

app = Flask(__name__)

def get_latest_chapter(data):
    latest = None
    for num in data.keys():
        if latest is None or int(num) > int(latest):
            latest = num
    return latest

def save_chapters_json():
    f = open('chapters.json', 'w')
    f.write(json.dumps(chatpers_json, indent=4))
    f.close()

f = open('chapters.json', 'r')
chatpers_json = json.loads(f.read())
latest_chapter = get_latest_chapter(chatpers_json)
f.close()

@app.route("/cdn/<path:path>", methods=["HEAD"])
def cdn_head(path):
    host = request.headers.get("Host")
    if "cdn." not in host:
        flask.abort(404)

    data = Response()
    data.headers['X-Page-Count'] = chatpers_json[path.split('-')[0]]['count']
    return data

@app.route("/cdn/<path:path>", methods=["GET"])
def cdn_deliver(path):
    host = request.headers.get("Host")
    if "cdn." not in host:
        flask.abort(404)
    
    try:
        data = flask.send_from_directory("../cdn", path)
    except werkzeug.exceptions.NotFound:
        data = flask.Response("404")
        data.headers['Cache-Control'] = 'no-store'
        data.status_code = 404
        return data
    else:
        data.headers['Cache-Control'] = "public; max-age=14400"
        data.headers['X-Page-Count'] = chatpers_json[path.split('-')[0]]['count']
        return data

@app.errorhandler(404)
def error_404(error):
    return '{"error": true, "description": "404: Not Found."}', 404

@app.route("/v1/chapters")
def list_chapters():
    return json.dumps(chatpers_json)

def scrape_thread():
    global chatpers_json
    manga = scrape.Manga("komi-cant-communicate")
    
    while True:
        try:
            chapters = manga.fetch_chapters()
            latest_check = get_latest_chapter(chapters)
            
            if int(latest_check) > int(latest_chapter):
                pages = chapters[latest_check].fetch_pages()
                for pagenum, page in pages.items():
                    if len(str(int(pagenum) + 1)) == 1:
                        page_num_formatted = "0" + str(int(pagenum) + 1)
                    else:
                        page_num_formatted = str(int(pagenum) + 1)
                    page.download_page(f"../cdn/{latest_check}-{page_num_formatted}.jpg")
                chatpers_json[latest_check] = {'count': len(pages)}
                save_chapters_json()
        except Exception as e:
            print(e)

        manga.new_release

        time.sleep(15)

t = threading.Thread(target=scrape_thread)
t.daemon = True
t.start()

logger = logging.getLogger('waitress')
logger.setLevel(logging.DEBUG)
serve(app, host="0.0.0.0", port=8491, threads=200)