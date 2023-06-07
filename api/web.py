from flask import Flask, request, Response
from waitress import serve
import flask
import time
import werkzeug
import json
import threading
import traceback

import scrape
import statics
import log_setup
import utils

app = Flask(__name__)
app.logger = log_setup.logger

@app.route("/cdn/<path:path>", methods=["HEAD"])
def cdn_head(path):
    # See comment on "cdn_deliver".
    host = request.headers.get("Host")
    if "cdn." not in host:
        flask.abort(404)

    data = Response()
    data.headers['X-Page-Count'] = chapters_json[path.split('-')[0]]['count']
    return data

@app.route("/cdn/<path:path>", methods=["GET"])
def cdn_deliver(path):
    # As both "cdn." and "api." go to this server,
    # we need to stop "api." from accessing this endpoint.
    host = request.headers.get("Host")
    if "cdn." not in host:
        flask.abort(404) # Expected API 404 error.
    
    if path == "__logs_here__":
        return Response(
            response = "you read the github didn't you?",
            status   = 200,
            headers  = {
                'Cache-Control': "public; max-age=14400"
            }
        )

    try:
        data = flask.send_from_directory("../cdn", path)
    except werkzeug.exceptions.NotFound:
        data = flask.Response("404")
        data.headers['Cache-Control'] = 'no-store' # Prevent Cloudflare caching it to allow real-time CDN uploads.
        data.status_code = 404
        return data
    else:
        data.headers['Cache-Control'] = "public; max-age=14400"
        data.headers['X-Page-Count'] = chapters_json[path.split('-')[0]]['count']
        return data

@app.errorhandler(404)
def error_404(error):
    # Less resource intensive to use a string instead of parsing dict -> json string.
    return '{"error": true, "description": "404: Not Found."}', 404

@app.route("/v1/chapters")
def list_chapters():
    # X-Ip-Country is returned by Cloudflare, as well as CORS headers.
    return chapters_json_resp

def scrape_thread():
    global chapters_json, chapters_json_resp
    manga = scrape.Manga("komi-cant-communicate")
    
    while True:
        try:
            chapters = manga.fetch_chapters(force_update=True)

            added_chapter_count = 0
            for chapter_num, chapter in chapters.items():
                if chapters_json.get(chapter_num) is None and chapter.free:
                    app.logger.info(f"new chapter found ({chapter_num})")
                    pages = chapter.fetch_pages()
                    app.logger.info(f"new chapter downloading ({chapter_num}) ({len(pages)} pages)")
                    
                    for page_num, page in pages.items():
                        page_num_cleaned = str(int(page_num) + 1) # page_num starts at 0, but we want to start at 1.
                        page.download_page(f"../cdn/{chapter_num}-{page_num_cleaned if len(page_num_cleaned) == 2 else '0' + page_num_cleaned}.jpg")
                    
                    chapters_json[chapter_num] = {
                        "metadata": {
                            "title": None, # Viz doesn't display the titles' of chapters, so this has to be added manually.
                            "page_count": len(pages)
                        },
                        "links": {
                            "viz": chapter.html_url,
                            "komizip": statics.reader_url_format.format(chapter_num)
                        }
                    }
                    added_chapter_count += 1
                    app.logger.info(f"new chapter downloaded ({chapter_num}) ({len(pages)} pages)")

            chapters_json_resp = utils.create_chapters_response(chapters_json, manga.new_release)
            if added_chapter_count > 0:
                utils.save_chapters_json(chapters_json) # chapters_json has been changed, so we have to save our changes.
        
        except Exception:
            app.logger.error("scrape_thread error; " + traceback.format_exc())

        time.sleep(15)


if __name__ == '__main__':
    chapters_json = utils.load_chapters_json()
    chapters_json_resp = utils.create_chapters_response(chapters_json, "null")
    latest_chapter = utils.get_latest_chapter(chapters_json)
    
    t = threading.Thread(target=scrape_thread, daemon=True)
    t.start()
    
    app.logger.info("bootup")
    serve(app, host="0.0.0.0", port=8491, threads=200, _quiet=True)