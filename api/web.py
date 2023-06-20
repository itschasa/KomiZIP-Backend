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
from password import check_password
import covers


app = Flask(__name__)
app.logger = log_setup.logger

def subdomain(area):
    def decorator(route_func):
        def wrapper(*args, **kwargs):
            if request.headers.get('Host', '').split('.')[0] != area:
                flask.abort(404)
            
            return route_func(*args, **kwargs)
        return wrapper
    return decorator

@app.errorhandler(404)
def error_404(error):
    # Less resource intensive to use a string instead of parsing dict -> json string.
    return '{"error": true, "description": "404: Not Found."}', 404

@app.route("/cdn/<path:path>", methods=["GET"], endpoint="cdn_deliver")
@subdomain("cdn")
def cdn_deliver(path):
    if path == "__images_here__":
        return Response(
            response = "you read the github didn't you?",
            status   = 200,
            headers  = {
                'Cache-Control': "public; max-age=86400"
            }
        )
    
    if "-" not in path:
        data = Response()
        data.headers['Cache-Control'] = "public; max-age=180" # 3 min cache
        try: data.headers['X-Metadata'] = json.dumps(chapters_json[path.split('-')[0]], separators=(",", ':'))
        except: pass
        else: return data
    else:
        try:
            data = flask.send_from_directory("../cdn", path)
        except werkzeug.exceptions.NotFound:
            pass
        else:
            data.headers['Cache-Control'] = "public; max-age=86400" # 1 day cache
            data.headers['X-Metadata'] = json.dumps(chapters_json[path.split('-')[0]], separators=(",", ':'))
            app.logger.debug(f"cdn hit ({path})")
            return data
    
    data = flask.Response("404")
    data.headers['Cache-Control'] = 'no-store' # Prevent Cloudflare caching it to allow real-time CDN uploads.
    data.status_code = 404
    return data

@app.route("/v1/chapters", endpoint="list_chapters")
@subdomain("api")
def list_chapters():
    # X-Ip-Country is returned by Cloudflare, as well as CORS headers.
    return chapters_json_resp

@app.route("/v1/admin/title", endpoint="edit_title", methods=['POST'])
@subdomain("api")
def edit_title():
    try:
        request_data = {
            "pwd": str(request.json['pwd']),
            "title": str(request.json['title']),
            "chapter": str(request.data['chapter'])
        }
    except:
        return '{"error": true, "description": "400: Bad Request."}', 400
    else:
        if check_password(request_data['pwd']):
            if chapters_json.get(request_data['chapter'], False):
                
                chapters_json[request_data['chapter']]['metadata']['title'] = request_data['title']
                
                new_release = chapters_json_resp.response.split('"new_release": "', 1)[1].split('"', 1)[0]
                chapters_json_resp = utils.create_chapters_response(chapters_json, new_release)
                
                utils.save_chapters_json(chapters_json) # chapters_json has been changed, so we have to save our changes.
                return '{"error": false}'
            else:
                return '{"error": true, "description": "400: Unknown Chapter."}', 400
        else:
            return '{"error": true, "description": "401: Unauthorized."}', 401
        
# TODO: add an admin route to add volume numbers
# /v1/admin/volumes ?

@app.route("/<path:path1>/<path:path2>", endpoint="i_redirect")
@subdomain("i")
def i_redirect(path1, path2):
    return Response(
        response = "",
        status   = 301,
        headers  = {
            'Cache-Control': "public; max-age=86400",
            "Location": f"https://cdn.komi.zip/cdn/{path1}-{path2 if len(path2) == 2 else '0' + path2}.jpg"
        }
    )

def scrape_thread():
    global chapters_json, chapters_json_resp
    manga = scrape.Manga("komi-cant-communicate")
    
    while True:
        try:
            chapters = manga.fetch_chapters(force_update=True)

            for chapter_num, chapter in chapters.items():
                if chapters_json.get(chapter_num) is None and chapter.free:
                    app.logger.info(f"new chapter found ({chapter_num})")
                    pages = chapter.fetch_pages()
                    app.logger.info(f"new chapter downloading ({chapter_num}) ({len(pages)} pages)")
                    
                    for page_num, page in pages.items():
                        page.download_page(f"../cdn/{chapter_num}-{page_num if len(page_num) == 2 else '0' + page_num}.jpg")
                    
                    chapters_json[chapter_num] = {
                        "metadata": {
                            "title": None, # Viz doesn't display the titles' of chapters, so this has to be added manually.
                            "page_count": len(pages),
                            "volume": None,
                            "volume_cover": False
                        },
                        "links": {
                            "viz": chapter.html_url,
                            "komizip": statics.reader_url_format.format(chapter_num)
                        }
                    }
                    app.logger.info(f"new chapter downloaded ({chapter_num}) ({len(pages)} pages)")
            
            old_keys = chapters_json.keys() 
            chapters_json = dict(sorted(chapters_json.items(), key=lambda item: float(item[0]), reverse=True))
            new_keys = chapters_json.keys()
            chapters_json_resp = utils.create_chapters_response(chapters_json, manga.new_release)
            if old_keys != new_keys:
                utils.save_chapters_json(chapters_json) # chapters_json has been changed, so we have to save our changes.
        
        except:
            app.logger.error("scrape_thread error on chapter scrape; " + traceback.format_exc())


        try:
            # fetch all volumes, and add to list the new volumes
            downloaded_covers = []
            for cover in covers.fetch_all_covers():
                downloaded = cover.download()
                if downloaded:
                    downloaded_covers.append(cover.volume)
            
            # iterate through chapters, when theres one with a new volume downloaded, change metadata (saying it has a volume cover it can use)
            edits_made = False
            for chapter, chapter_data in chapters_json.copy().items():
                if chapter_data['metadata']['volume'] in downloaded_covers:
                    if chapter_data['metadata']['volume_cover'] is False:
                        chapters_json[chapter]['metadata']['volume_cover'] = True
                        edits_made = True
            
            if edits_made:
                utils.save_chapters_json(chapters_json)
            
        except:
            app.logger.error("scrape_thread error on cover scrape; " + traceback.format_exc())

        time.sleep(15)


if __name__ == '__main__':
    chapters_json = utils.load_chapters_json()
    chapters_json_resp = utils.create_chapters_response(chapters_json, "null")
    latest_chapter = utils.get_latest_chapter(chapters_json)
    
    t = threading.Thread(target=scrape_thread, daemon=True)
    t.start()
    
    app.logger.info("bootup")
    serve(app, host="0.0.0.0", port=8491, threads=200, _quiet=True)