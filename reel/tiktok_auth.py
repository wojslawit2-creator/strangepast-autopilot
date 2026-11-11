"""Exchange a TikTok authorization code for a refresh token and store it as a repo secret."""
import os
import subprocess
import sys

import requests

REDIRECT = "https://wojslawit2-creator.github.io/strangepast-autopilot/callback.html"

code = sys.argv[1].strip()
r = requests.post("https://open.tiktokapis.com/v2/oauth/token/", data={
    "client_key": os.environ["TIKTOK_CLIENT_KEY"], "client_secret": os.environ["TIKTOK_CLIENT_SECRET"],
    "code": code, "grant_type": "authorization_code", "redirect_uri": REDIRECT,
}, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=60)
j = r.json()
if "refresh_token" not in j:
    sys.exit(f"TikTok refused the code: {j}")
print(f"Connected TikTok open_id ending ...{j.get('open_id', '')[-6:]}, scopes: {j.get('scope')}")
env = dict(os.environ, GH_TOKEN=os.environ["GH_PAT"])
subprocess.run(["gh", "secret", "set", "TIKTOK_REFRESH_TOKEN", "--repo", os.environ["GITHUB_REPOSITORY"],
                "--body", j["refresh_token"]], check=True, env=env)
print("Saved TIKTOK_REFRESH_TOKEN secret.")
