import json
import os

from flask import Flask, redirect, request
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

redis = Redis(
    url=env["REDIS_URL"],
    token=env["REDIS_TOKEN"],
)
app = Flask(__name__)
CORS(
    app,
    resources={
        r"/*": {"origins": ["https://www.kothavade.com", "http://localhost:5000"]}
    },
)


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
    print(last_played)
    return json.dumps(
        {
            "videoId": last_played["videoId"],
            "title": last_played["title"],
            "artist": ", ".join([artist["name"] for artist in last_played["artists"]]),
            "album": last_played["album"]["name"] if last_played["album"] else None,
            "thumbnail": last_played["thumbnails"][-1]["url"],
        }
    )


@app.route("/last-played")
def api():
    force_check = request.args.get("force", "false").lower() == "true"
    cached = redis.get("last_played")
    if cached is None or force_check:
        print("Fetching last played from YTMusic")
        last_played = get_ytmusic_last_played()
        redis.set("last_played", last_played, ex=120)
        return last_played
    print("Using cached last played")
    return cached


@app.route("/discord")
def discord():
    pipe = redis.pipeline()
    pipe.get("discord:code")
    pipe.get("discord:uses")
    pipe.get("discord:max_uses")
    invite_code, uses, max_uses = pipe.exec()

    uses = int(uses) if uses else 0
    max_uses = int(max_uses) if max_uses else 0

    if invite_code is None or uses >= max_uses:
        from datetime import datetime

        import httpx
        import pytz

        print("Generating new invite")

        with httpx.Client() as client:
            resp = client.post(
                "https://discord.com/api/v9/users/@me/invites",
                data="{}",
                headers={
                    "authorization": env["DISCORD_TOKEN"],
                    "content-type": "application/json",
                },
            )
            if resp.status_code != 200:
                raise Exception(resp.json())

            response_data = resp.json()
            invite_code = response_data["code"]
            max_uses = response_data["max_uses"]

            expires = response_data["expires_at"]
            expires_dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
            current_dt = datetime.now(pytz.timezone("UTC"))
            ttl = int((expires_dt - current_dt).total_seconds())

            pipe = redis.pipeline()
            pipe.set("discord:code", invite_code, ex=ttl)
            pipe.set("discord:max_uses", str(max_uses), ex=ttl)
            pipe.set("discord:uses", "1", ex=ttl)
            pipe.exec()
    else:
        print("Using existing invite")
        redis.incr("discord:uses")

    if isinstance(invite_code, bytes):
        invite_code = invite_code.decode("utf-8")

    return redirect(
        f"https://discord.com/invite/{invite_code}",
        code=302,
    )


if not vercel:
    app.run()
