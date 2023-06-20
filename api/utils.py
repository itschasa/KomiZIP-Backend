import json
import flask
from web import app

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
    app.logger.debug("chapters.json saved")

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