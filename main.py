"""Strange Past autopilot: script -> voice -> images -> reel -> Instagram + TikTok."""
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile

from reel import images, publish_ig, publish_tiktok, render, script_gen, tts

ROOT = os.path.dirname(os.path.abspath(__file__))
USED = os.path.join(ROOT, "data", "used_topics.json")
LOG = os.path.join(ROOT, "data", "log.jsonl")
OUT = os.path.join(ROOT, "out")
REPO = os.environ.get("GITHUB_REPOSITORY", "")
DRY_RUN = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")


def sh(*cmd, check=True, **kw):
    return subprocess.run(cmd, check=check, text=True, capture_output=True, **kw)


def set_secret(name, value):
    """Store a rotated token back into the repo secrets (needs GH_PAT)."""
    if not os.environ.get("GH_PAT"):
        print(f"[secrets] GH_PAT missing, cannot save new {name}")
        return
    env = dict(os.environ, GH_TOKEN=os.environ["GH_PAT"])
    r = sh("gh", "secret", "set", name, "--repo", REPO, "--body", value, check=False, env=env)
    print(f"[secrets] {name} updated" if r.returncode == 0 else f"[secrets] failed: {r.stderr}")


def host_video(path):
    """Push the mp4 to the orphan 'media' branch and return its public raw URL."""
    name = os.path.basename(path)
    tmp = tempfile.mkdtemp()
    url = f"https://x-access-token:{os.environ['GITHUB_TOKEN']}@github.com/{REPO}.git"
    sh("git", "init", "-q", tmp)
    sh("cp", path, os.path.join(tmp, name))
    for c in (["checkout", "-q", "--orphan", "media"], ["add", name],
              ["-c", "user.name=strangepast-bot", "-c", "user.email=bot@users.noreply.github.com",
               "commit", "-q", "-m", f"media {name}"],
              ["push", "-q", "-f", url, "media"]):
        sh("git", "-C", tmp, *c)
    return f"https://raw.githubusercontent.com/{REPO}/media/{name}"


def build_caption(s):
    tags = [t.strip("#").replace(" ", "") for t in s.get("hashtags", [])]
    tags = list(dict.fromkeys(["history", "historyfacts"] + tags))[:5]
    return f"{s['caption']}\n\nNarrated with an AI voice.\n\n" + " ".join("#" + t for t in tags)


QUEUE = os.path.join(ROOT, "data", "queue.json")


def next_script(used):
    """Take the next hand-written script from data/queue.json, else ask Gemini."""
    queue = json.load(open(QUEUE)) if os.path.exists(QUEUE) else []
    used_l = {t.lower() for t in used}
    while queue:
        s = queue.pop(0)
        if not DRY_RUN:
            json.dump(queue, open(QUEUE, "w"), indent=1, ensure_ascii=False)
        if s["topic"].lower() in used_l:
            continue
        try:
            if not script_gen.wikipedia_exists(s["wikipedia_title"]):
                print(f"[queue] skipped, no Wikipedia article: {s['wikipedia_title']}")
                continue
        except Exception as e:
            print(f"[queue] wiki check unavailable ({e}), using script anyway")
        print(f"[queue] {len(queue)} scripts left")
        return s
    return script_gen.generate(used)


def make_reel():
    used = json.load(open(USED))
    s = next_script(used)
    print(f"[script] {s['topic']}  (wiki: {s['wikipedia_title']})")
    work = tempfile.mkdtemp()
    scenes = []
    for i, sc in enumerate(s["scenes"]):
        audio = os.path.join(work, f"a{i}.mp3")
        dur, words = tts.speak(sc["narration"], audio)
        img = os.path.join(work, f"i{i}.jpg")
        src = images.make(sc, img, wiki_title=s["wikipedia_title"])
        print(f"[scene {i}] {dur:.1f}s image={src}")
        scenes.append({"image": img, "audio": audio, "duration": dur, "words": words})
    os.makedirs(OUT, exist_ok=True)
    stamp = dt.datetime.utcnow().strftime("%Y%m%d-%H%M")
    out = os.path.join(OUT, f"reel-{stamp}.mp4")
    music = os.path.join(ROOT, "assets", "music.mp3")
    total = render.build(scenes, s.get("on_screen_title", ""), work, out, music=music)
    print(f"[render] {out} ({total:.1f}s)")
    json.dump(s, open(out.replace(".mp4", ".json"), "w"), indent=2)
    return s, out


def main():
    s, path = make_reel()
    caption = build_caption(s)
    result = {"time": dt.datetime.utcnow().isoformat(), "topic": s["topic"], "file": os.path.basename(path)}
    with open(os.path.join(OUT, "caption.txt"), "w") as f:
        f.write(caption)

    if DRY_RUN:
        print("[dry-run] not publishing")
    else:
        errors = []
        if os.environ.get("IG_ACCESS_TOKEN"):
            try:
                url = host_video(path)
                result["instagram"] = publish_ig.publish_reel(os.environ["IG_ACCESS_TOKEN"], url, caption)
            except Exception as e:
                errors.append(f"instagram: {e}")
        if os.environ.get("TIKTOK_REFRESH_TOKEN"):
            try:
                access, new_refresh = publish_tiktok.refresh(
                    os.environ["TIKTOK_CLIENT_KEY"], os.environ["TIKTOK_CLIENT_SECRET"], os.environ["TIKTOK_REFRESH_TOKEN"])
                if new_refresh != os.environ["TIKTOK_REFRESH_TOKEN"]:
                    set_secret("TIKTOK_REFRESH_TOKEN", new_refresh)
                mode = os.environ.get("TIKTOK_MODE", "inbox")
                result["tiktok"] = publish_tiktok.upload(access, path, caption, mode=mode)
                result["tiktok_mode"] = mode
                if mode == "inbox":
                    open(os.path.join(OUT, "tiktok_inbox"), "w").write(s["topic"])
            except Exception as e:
                errors.append(f"tiktok: {e}")
        if errors:
            result["errors"] = errors
            print("\n".join(errors))

    if DRY_RUN:
        return
    json.dump(json.load(open(USED)) + [s["topic"]], open(USED, "w"), indent=1)
    with open(LOG, "a") as f:
        f.write(json.dumps(result) + "\n")
    if result.get("errors") and not (result.get("instagram") or result.get("tiktok")):
        sys.exit(1)


def refresh_ig():
    new = publish_ig.refresh_token(os.environ["IG_ACCESS_TOKEN"])
    set_secret("IG_ACCESS_TOKEN", new)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "refresh-ig":
        refresh_ig()
    else:
        main()
