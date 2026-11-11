"""Scene images.

1. Public-domain historical art from Wikimedia Commons (free, no key, real history).
2. AI image from Pollinations, only if POLLINATIONS_TOKEN is set.
3. A soft abstract background as a last resort.
Landscape pictures are placed on a blurred copy of themselves to fill 9:16.
"""
import io
import os
import random
import re
import time
import urllib.parse

import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

W, H = 1080, 1920
UA = {"User-Agent": "StrangePastBot/1.0 (https://github.com/; history shorts) python-requests"}
STYLE = ", cinematic historical scene, dramatic lighting, film still, highly detailed, vertical composition"
OK_LICENSES = ("public domain", "pd", "cc0", "no restrictions")
_used = set()


def _get_image(url):
    r = requests.get(url, headers=UA, timeout=120)
    r.raise_for_status()
    return Image.open(io.BytesIO(r.content)).convert("RGB")


def commons_search(query, limit=12):
    params = {
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
        "gsrsearch": f"{query} filetype:bitmap", "gsrlimit": limit,
        "prop": "imageinfo", "iiprop": "url|size|extmetadata|mime", "iiurlwidth": 1600,
    }
    r = requests.get("https://commons.wikimedia.org/w/api.php", params=params, headers=UA, timeout=60)
    pages = sorted(r.json().get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
    out = []
    for p in pages:
        ii = (p.get("imageinfo") or [{}])[0]
        meta = ii.get("extmetadata", {})
        lic = (meta.get("LicenseShortName", {}).get("value", "") + " " + meta.get("License", {}).get("value", "")).lower()
        if not any(k in lic for k in OK_LICENSES):
            continue
        if ii.get("mime") not in ("image/jpeg", "image/png") or ii.get("width", 0) < 700 or ii.get("height", 0) < 500:
            continue
        title = p.get("title", "").lower()
        if re.search(r"logo|icon|flag of|coat of arms|map of .* location|signature|diagram", title):
            continue
        out.append(ii.get("thumburl") or ii["url"])
    return out


def _from_commons(queries):
    for q in queries:
        if not q:
            continue
        try:
            for url in commons_search(q):
                if url in _used:
                    continue
                img = _get_image(url)
                _used.add(url)
                return img
        except Exception as e:
            print(f"[image] commons '{q}': {e}")
    return None


def _pollinations(prompt, seed):
    tok = os.environ.get("POLLINATIONS_TOKEN")
    if not tok:
        return None
    url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt + STYLE)
    r = requests.get(url, params={"width": W, "height": H, "seed": seed, "nologo": "true"},
                     headers={**UA, "Authorization": f"Bearer {tok}"}, timeout=240)
    r.raise_for_status()
    return Image.open(io.BytesIO(r.content)).convert("RGB")


def _fallback(seed):
    rnd = random.Random(seed)
    base = (rnd.randint(30, 70), rnd.randint(20, 50), rnd.randint(10, 35))
    img = Image.new("RGB", (W, H), base)
    d = ImageDraw.Draw(img)
    for _ in range(40):
        x, y, r = rnd.randint(0, W), rnd.randint(0, H), rnd.randint(80, 400)
        c = tuple(min(255, v + rnd.randint(0, 40)) for v in base)
        d.ellipse([x - r, y - r, x + r, y + r], fill=c)
    return img.filter(ImageFilter.GaussianBlur(60))


def cover(img, w=W, h=H):
    scale = max(w / img.width, h / img.height)
    img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    left, top = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((left, top, left + w, top + h))


def compose(img):
    """Fit any picture into 1080x1920."""
    if img.width / img.height <= 0.8:  # already portrait-ish
        return cover(img)
    bg = cover(img).filter(ImageFilter.GaussianBlur(45))
    bg = ImageEnhance.Brightness(bg).enhance(0.45)
    fg_h = 1150
    fg_w = max(W, round(img.width * fg_h / img.height))
    fg = img.resize((fg_w, fg_h), Image.LANCZOS)
    left = (fg_w - W) // 2
    fg = fg.crop((left, 0, left + W, fg_h))
    bg.paste(fg, (0, 300))
    return bg


def make(scene, path, wiki_title=None, seed=None):
    """scene: dict with image_query / image_prompt. Returns source name."""
    seed = seed or random.randint(1, 10**9)
    img = _from_commons([scene.get("image_query"), wiki_title])
    src = "commons"
    if img is None:
        try:
            img, src = _pollinations(scene.get("image_prompt", ""), seed), "ai"
        except Exception as e:
            print(f"[image] pollinations: {e}")
            img = None
    if img is None:
        img, src = _fallback(seed), "fallback"
        img.save(path, quality=93)
        return src
    compose(img).save(path, quality=93)
    time.sleep(1)
    return src
