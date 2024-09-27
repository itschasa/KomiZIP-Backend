from flask import Flask, request, Response
from waitress import serve
import flask
import os
import time
import werkzeug
import json
import threading
import traceback
from flask_compress import Compress

import scrape
import statics
import log_setup
import utils
from password import check_password
import covers
import wiki


app = Flask(__name__)
app.logger = log_setup.logger

Compress(app)
app.config['COMPRESS_MIMETYPES'] = [
    'application/javascript',
    'application/json',
    'text/css',
    'text/html',
    'text/javascript',
    'text/xml',
    'image/jpeg'
]

def subdomain(area):
    def decorator(route_func):
        def wrapper(*args, **kwargs):
            #if request.headers.get('Host', '').split('.')[0] != area:
                #flask.abort(404)
            
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
    
    if "-" not in path and "vol" not in path:
        data = Response()
        data.headers['Cache-Control'] = "public; max-age=180" # 3 min cache
        data.headers['X-Chapters'] = json.dumps(list(chapters_json.keys()), separators=(",", ':'))
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
            
            if "vol" not in path:
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

@app.route("/v1/admin/edit", endpoint="edit_admin", methods=['POST'])
@subdomain("api")
def edit_admin():
    global chapters_json_resp, chapters_json
    try:
        request_data = {
            "pwd": str(request.json['pwd']),
            "data": str(request.json['data']),
        }
    except:
        return '{"error": true, "description": "400: Bad Request."}', 400
    else:
        if check_password(request_data['pwd']):
            data = utils.extract_admin_data(request_data['data'])
            validated, reason = utils.validate_admin_data(data)
            if validated:
                cover_exist_cache = []
                edited = ''
                for key, args in data.items():
                    if '-' in key:
                        start, end = key.split('-')
                        end_found = False
                        for chapter in chapters_json.copy().keys():
                            if chapter == end:
                                end_found = True

                            if end_found:
                                chapters_json, edited_chapter = utils.edit_chapter(chapter, args, chapters_json, cover_exist_cache)
                                if len(edited_chapter) != 0:
                                    edited += f'{chapter}: {" ".join(edited_chapter)}<br>'

                            if chapter == start:
                                break
                    else:
                        chapters_json, edited_chapter = utils.edit_chapter(key, args, chapters_json, cover_exist_cache)
                        if len(edited_chapter) != 0:
                            edited += f'{key}: {" ".join(edited_chapter)}<br>'
                
                chapters_json_resp = utils.create_chapters_response(chapters_json, manga.new_release)
                utils.save_chapters_json(chapters_json)
                return json.dumps({"error": False, "edited": edited}), 200 
            else:
                return json.dumps({"error": True, "description": reason}), 400
        else:
            return '{"error": true, "description": "401: Unauthorized."}', 401

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
    global chapters_json, chapters_json_resp, manga
    manga = scrape.Manga("komi-cant-communicate")
    
    while True:
        try:
            chapters = manga.fetch_chapters(force_update=True)
            
            for chapter_num, chapter in chapters.items():
                if chapters_json.get(chapter_num) is None and chapter.free:
                    app.logger.info(f"new chapter found ({chapter_num})")
                    pages = chapter.fetch_pages()
                    app.logger.info(f"new chapter downloading ({chapter_num}) ({len(pages)} pages)")
                    
                    page_num_counter = 1
                    for _, page in pages.items():
                        result = page.download_page(f"../cdn/{chapter_num}-{page_num_counter if page_num_counter > 9 else '0' + str(page_num_counter)}.jpg")
                        if result:
                            page_num_counter += 1
                    
                    page_num_counter -= 1
                    
                    chapters_json[chapter_num] = {
                        "metadata": {
                            "title": None, # Viz doesn't display the titles' of chapters, so this has to be added manually.
                            "page_count": page_num_counter,
                            "volume": None,
                            "volume_cover": False
                        },
                        "links": {
                            "viz": chapter.html_url,
                            "komizip": statics.reader_url_format.format(chapter_num)
                        }
                    }
                    app.logger.info(f"new chapter downloaded ({chapter_num}) ({page_num_counter} pages)")
            
            chapters_json = dict(sorted(chapters_json.items(), key=lambda item: float(item[0]), reverse=True))
            chapters_json_resp = utils.create_chapters_response(chapters_json, manga.new_release)
        
        except:
            app.logger.error("scrape_thread error on chapter scrape; " + traceback.format_exc())


        try:
            # fetch all volumes, and add to list the new volumes
            downloaded_covers = []
            for cover in covers.fetch_all_covers():
                downloaded = cover.download()
                if downloaded:
                    app.logger.info(f"new volume cover downloaded ({cover.volume})")
                    downloaded_covers.append(cover.volume)
            
            # iterate through chapters, when theres one with a new volume downloaded, change metadata (saying it has a volume cover it can use)
            for chapter, chapter_data in chapters_json.copy().items():
                if chapter_data['metadata']['volume'] in downloaded_covers:
                    if chapter_data['metadata']['volume_cover'] is False:
                        chapters_json[chapter]['metadata']['volume_cover'] = True
            
        except:
            app.logger.error("scrape_thread error on cover scrape; " + traceback.format_exc())

        
        try:
            # fetch all titles, and add to list the new titles
            for chapter_num, chapter_data in chapters_json.items():
                if chapter_data["metadata"]["title"] is None:
                    new_title = wiki.get_title(chapter_num)
                    if new_title is not None:
                        chapters_json[chapter_num]["metadata"]["title"] = new_title
                        app.logger.info(f"new title for {chapter_num} ({new_title})")
        except:
            app.logger.error("scrape_thread error on title scrape; " + traceback.format_exc())
        

        try:
            # fetch all volumes from wiki, and assign chapters their volume
            vol_id = 0
            while True:
                vol_id += 1
                chapters_in_vol = wiki.get_chapters_in_volume(str(vol_id))
                if chapters_in_vol is None:
                    break
                
                for chapter in chapters_in_vol:
                    if chapters_json.get(chapter) is not None:
                        if chapters_json[chapter]["metadata"]["volume"] != str(vol_id):
                            chapters_json[chapter]["metadata"]["volume"] = str(vol_id)
                            app.logger.info(f"new volume for {chapter} ({vol_id})")
                        
                        if os.path.exists(f"../cdn/vol{vol_id}.jpg"):
                            chapters_json[chapter]["metadata"]["volume_cover"] = True
        
        except:
            app.logger.error("scrape_thread error on volume scrape; " + traceback.format_exc())


        try:
            utils.save_chapters_json(chapters_json)
        except:
            app.logger.error("scrape_thread error on saving chapters; " + traceback.format_exc())
            app.logger.debug(chapters_json) # save the chapters_json to the log for debugging

        time.sleep(15)


if __name__ == '__main__':
    chapters_json = utils.load_chapters_json()
    chapters_json_resp = utils.create_chapters_response(chapters_json, "null")
    latest_chapter = utils.get_latest_chapter(chapters_json)
    
    t = threading.Thread(target=scrape_thread, daemon=True)
    t.start()
    
    app.logger.info("bootup")
    #app.run(host="0.0.0.0", port=8491)
    serve(app, host="0.0.0.0", port=8491, threads=500, _quiet=True)