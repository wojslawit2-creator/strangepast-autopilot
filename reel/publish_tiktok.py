"""TikTok Content Posting API.

Until the developer app passes TikTok's audit, direct posts can only be
private, so by default the video is sent to the TikTok inbox (drafts) and you
just tap Publish in the app. Set TIKTOK_MODE=direct after the audit.
"""
import os
import time

import requests

API = "https://open.tiktokapis.com/v2"


def _check(r):
    j = r.json() if r.content else {}
    err = (j.get("error") or {}).get("code")
    if r.status_code >= 400 or (err and err != "ok"):
        raise RuntimeError(f"TikTok API {r.status_code}: {r.text[:500]}")
    return j


def refresh(client_key, client_secret, refresh_token):
    r = requests.post(f"{API}/oauth/token/", data={
        "client_key": client_key, "client_secret": client_secret,
        "grant_type": "refresh_token", "refresh_token": refresh_token,
    }, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=60)
    j = r.json()
    if "access_token" not in j:
        raise RuntimeError(f"TikTok token refresh failed: {j}")
    return j["access_token"], j.get("refresh_token", refresh_token)


def upload(access_token, path, caption, mode="inbox"):
    size = os.path.getsize(path)
    source = {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": size, "total_chunk_count": 1}
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; charset=UTF-8"}
    if mode == "direct":
        body = {"post_info": {"title": caption[:2200], "privacy_level": os.environ.get("TIKTOK_PRIVACY", "PUBLIC_TO_EVERYONE"),
                              "disable_comment": False, "is_aigc": True, "video_cover_timestamp_ms": 1500},
                "source_info": source}
        url = f"{API}/post/publish/video/init/"
    else:
        body = {"source_info": source}
        url = f"{API}/post/publish/inbox/video/init/"
    init = _check(requests.post(url, json=body, headers=headers, timeout=60))["data"]
    with open(path, "rb") as f:
        r = requests.put(init["upload_url"], data=f, headers={
            "Content-Type": "video/mp4", "Content-Length": str(size),
            "Content-Range": f"bytes 0-{size - 1}/{size}"}, timeout=600)
    if r.status_code >= 400:
        raise RuntimeError(f"TikTok upload {r.status_code}: {r.text[:300]}")
    pid = init["publish_id"]
    for _ in range(30):
        time.sleep(10)
        st = _check(requests.post(f"{API}/post/publish/status/fetch/", json={"publish_id": pid},
                                  headers=headers, timeout=60))["data"]
        print(f"[tiktok] status {st.get('status')}")
        if st.get("status") in ("SEND_TO_USER_INBOX", "PUBLISH_COMPLETE"):
            return pid
        if st.get("status") == "FAILED":
            raise RuntimeError(f"TikTok failed: {st}")
    return pid
