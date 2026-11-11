"""Publish a Reel through the Instagram API with Instagram Login."""
import os
import time

import requests

API = "https://graph.instagram.com/v23.0"


def _check(r):
    if r.status_code >= 400:
        raise RuntimeError(f"Instagram API {r.status_code}: {r.text[:500]}")
    return r.json()


def refresh_token(token):
    r = requests.get(f"{API.rsplit('/', 1)[0]}/refresh_access_token",
                     params={"grant_type": "ig_refresh_token", "access_token": token}, timeout=60)
    return _check(r)["access_token"]


def publish_reel(token, video_url, caption, cover_offset_ms=1500):
    me = _check(requests.get(f"{API}/me", params={"fields": "user_id,username", "access_token": token}, timeout=60))
    uid = me["user_id"]
    print(f"[ig] publishing as @{me.get('username')}")
    c = _check(requests.post(f"{API}/{uid}/media", data={
        "media_type": "REELS", "video_url": video_url, "caption": caption,
        "share_to_feed": "true", "thumb_offset": cover_offset_ms, "access_token": token,
    }, timeout=120))
    cid = c["id"]
    for _ in range(60):  # up to ~10 min
        time.sleep(10)
        st = _check(requests.get(f"{API}/{cid}", params={"fields": "status_code,status", "access_token": token}, timeout=60))
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram processing failed: {st}")
    else:
        raise RuntimeError("Instagram processing timed out")
    res = _check(requests.post(f"{API}/{uid}/media_publish", data={"creation_id": cid, "access_token": token}, timeout=120))
    print(f"[ig] published media id {res['id']}")
    return res["id"]


if __name__ == "__main__":  # quick token check: python -m reel.publish_ig
    t = os.environ["IG_ACCESS_TOKEN"]
    print(requests.get(f"{API}/me", params={"fields": "user_id,username,account_type", "access_token": t}).json())
