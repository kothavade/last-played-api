# website api

simple [flask](https://flask.palletsprojects.com/) api for [kothavade.com](https://kothavade.com):
- gets the last played song from youtube music
- generates discord friend invite links

## tech
- heavy lifting done by [ytmusicapi](https://github.com/sigma67/ytmusicapi)
- deployed with [vercel](https://vercel.com) functions
- redis from [upstash](https://upstash.com)

## run locally
```sh
python3 api/index.py
```
