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
LAST_PLAYED_KEY = "last_played"
DISCORD_INVITE_KEY = "discord_invite"

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


@app.route("/discord")
def discord():
    from datetime import datetime, timedelta

    import httpx
    import pytz

    data = {
        "code": "",
        "expires": (
            datetime.now(pytz.timezone("UTC")) + timedelta(seconds=10)
        ).isoformat(),
        "max_uses": 0,
        "logged_uses": 0,
    }

    cached = redis.get(DISCORD_INVITE_KEY)
    if cached is not None:
        data = json.loads(cached)

    if (
        datetime.fromisoformat(data["expires"]) <= datetime.now(pytz.timezone("UTC"))
        or data["logged_uses"] + 1 > data["max_uses"]
    ):
        print("generating new invite")
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
            data["code"] = response_data["code"]
            data["expires"] = response_data["expires_at"]
            data["max_uses"] = response_data["max_uses"]
            data["logged_uses"] = 1
    else:
        data["logged_uses"] += 1

    redis.set(DISCORD_INVITE_KEY, json.dumps(data))
    return redirect(f"https://discord.com/invite/{data['code']}")


if not vercel:
    app.run()
