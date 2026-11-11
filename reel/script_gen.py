"""Generate a reel script (English, weird-history niche) with an LLM.

Uses Google Gemini (free tier) when GEMINI_API_KEY is set, otherwise the
key-less Pollinations text endpoint. Facts are checked against Wikipedia:
the script must name an existing English Wikipedia article.
"""
import json
import os
import random
import re
import time

import requests

UA = {"User-Agent": "strangepast-bot/1.0 (github actions)"}

ANGLES = [
    "a bizarre medieval law or punishment",
    "a strange death of a famous historical figure",
    "a forgotten disaster or mass event",
    "an absurd military blunder",
    "a weird royal habit or court custom",
    "a historical hoax or con artist",
    "a disgusting everyday practice people used to consider normal",
    "a strange ancient invention or technology",
    "an unbelievable survival story",
    "a mysterious unsolved historical event",
    "a crazy historical coincidence",
    "a bizarre medical treatment from the past",
    "an animal that played a strange role in history",
    "a forgotten weird job from the past",
    "a strange war or conflict over something trivial",
]

PROMPT = """You write viral 40-second faceless short videos for the account "Strange Past" (weird, little-known history).

Theme for this video: {angle}.
Do NOT use any of these already-covered topics: {used}.

Hard rules:
- The story must be TRUE, well documented, and have its own English Wikipedia article. Give that article's exact title.
- No myths presented as fact. If historians doubt a detail, say "reportedly".
- Language: simple spoken English, short punchy sentences, present tense storytelling is fine.
- Total narration 95-125 words.
- Scene 1 is the HOOK: max 12 words, a shocking concrete claim with a year or place. No "Did you know".
- 5 or 6 scenes. The last scene ends with a short question that makes people comment.
- image_prompt: a vivid cinematic description of a single historical scene for an AI image generator, period-accurate, dramatic lighting, no text, no letters, no modern objects, no gore.
- on_screen_title: 2-5 words, ALL CAPS, for the first 2 seconds.

Return ONLY JSON:
{{"topic": "...", "wikipedia_title": "...", "on_screen_title": "...",
  "scenes": [{{"narration": "...", "image_prompt": "..."}}],
  "caption": "1-2 sentence caption that teases the story, ending with a question",
  "hashtags": ["history", "..."]}}
"""


def _extract_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1])


def _gemini(prompt):
    key = os.environ["GEMINI_API_KEY"]
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        params={"key": key},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 1.0, "responseMimeType": "application/json"},
        },
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def _pollinations(prompt):
    headers = dict(UA)
    tok = os.environ.get("POLLINATIONS_TOKEN")
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    r = requests.post(
        "https://text.pollinations.ai/openai",
        json={
            "model": "openai",
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "seed": random.randint(1, 10**6),
        },
        headers=headers,
        timeout=180,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def wikipedia_exists(title):
    r = requests.get(
        "https://en.wikipedia.org/w/api.php",
        params={"action": "query", "titles": title, "redirects": 1, "format": "json"},
        headers=UA,
        timeout=30,
    )
    pages = r.json().get("query", {}).get("pages", {})
    return any(int(pid) > 0 for pid in pages)


def _valid(s):
    scenes = s.get("scenes") or []
    words = sum(len(x.get("narration", "").split()) for x in scenes)
    return 4 <= len(scenes) <= 7 and 70 <= words <= 160 and s.get("wikipedia_title")


def generate(used_topics, attempts=4):
    last_err = None
    for i in range(attempts):
        prompt = PROMPT.format(
            angle=random.choice(ANGLES),
            used="; ".join(used_topics[-80:]) or "none",
        )
        try:
            raw = _gemini(prompt) if os.environ.get("GEMINI_API_KEY") else _pollinations(prompt)
            s = _extract_json(raw)
            if not _valid(s):
                raise ValueError("script failed length/shape checks")
            if s["topic"].lower() in (t.lower() for t in used_topics):
                raise ValueError("duplicate topic")
            if not wikipedia_exists(s["wikipedia_title"]):
                raise ValueError(f"no Wikipedia article: {s['wikipedia_title']}")
            return s
        except Exception as e:  # retry with a fresh angle
            last_err = e
            print(f"[script] attempt {i + 1} failed: {e}")
            time.sleep(5)
    raise RuntimeError(f"could not generate script: {last_err}")
