"""Scene images: free AI images from Pollinations, with a safe fallback."""
import io
import os
import random
import time
import urllib.parse

import requests
from PIL import Image, ImageDraw, ImageFilter

W, H = 1080, 1920
STYLE = ", cinematic historical scene, dramatic lighting, film still, highly detailed, 35mm, vertical composition"


def _pollinations(prompt, seed):
    url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt + STYLE)
    params = {"width": W, "height": H, "seed": seed, "nologo": "true", "model": os.environ.get("IMAGE_MODEL", "flux")}
    headers = {"User-Agent": "strangepast-bot/1.0"}
    tok = os.environ.get("POLLINATIONS_TOKEN")
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    r = requests.get(url, params=params, headers=headers, timeout=240)
    r.raise_for_status()
    img = Image.open(io.BytesIO(r.content)).convert("RGB")
    if img.width < 500:
        raise ValueError("image too small")
    return img


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


def cover(img):
    """Resize/crop to exactly 1080x1920."""
    scale = max(W / img.width, H / img.height)
    img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    left, top = (img.width - W) // 2, (img.height - H) // 2
    return img.crop((left, top, left + W, top + H))


def make(prompt, path, seed=None):
    seed = seed or random.randint(1, 10**9)
    for attempt in range(3):
        try:
            img = _pollinations(prompt, seed + attempt)
            cover(img).save(path, quality=93)
            return True
        except Exception as e:
            print(f"[image] retry {attempt + 1}: {e}")
            time.sleep(8)
    _fallback(seed).save(path, quality=93)
    return False
