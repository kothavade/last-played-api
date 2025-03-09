import json
import os

from flask import Flask, request
from flask_cors import CORS
from upstash_redis import Redis

vercel = "VERCEL" in os.environ
if not vercel:
    from dotenv import load_dotenv

    load_dotenv()

env = os.environ

OAUTH_JSON = f"""{{
"scope": "https://www.googleapis.com/auth/youtube",
"token_type": "Bearer",
"access_token": "{env["OAUTH_ACCESS_TOKEN"]}",
"refresh_token": "{env["OAUTH_REFRESH_TOKEN"]}",
"expires_at": 1741474523,
"expires_in": 3599
}}"""
LAST_PLAYED_KEY = "last_played"

redis = Redis(
    url=env["REDIS_URL"],
    token=env["REDIS_TOKEN"],
)
app = Flask(__name__)
CORS(app)


def get_ytmusic_last_played():
    from ytmusicapi import OAuthCredentials, YTMusic

    ytmusic = YTMusic(
        OAUTH_JSON,
        oauth_credentials=OAuthCredentials(
            client_id=env["OAUTH_CLIENT_ID"],
            client_secret=env["OAUTH_CLIENT_SECRET"],
        ),
    )
    history = ytmusic.get_history()
    last_played = history[0]
    return json.dumps(
        {
            "videoId": last_played["videoId"],
            "title": last_played["title"],
            "artist": ", ".join([artist["name"] for artist in last_played["artists"]]),
            "album": last_played["album"]["name"],
            "thumbnail": last_played["thumbnails"][-1]["url"],
        }
    )


@app.route("/")
def api():
    force_check = request.args.get("force", "false").lower() == "true"
    cached = redis.get(LAST_PLAYED_KEY)
    if cached is None or force_check:
        if force_check:
            print("Force fetching last played from YTMusic")
        else:
            print("Fetching last played from YTMusic")
        last_played = get_ytmusic_last_played()
        redis.set(LAST_PLAYED_KEY, last_played, ex=120)
        return last_played
    print("Using cached last played")
    return cached


if not vercel:
    app.run()
