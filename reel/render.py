"""Assemble a 1080x1920 reel: Ken Burns images + voice + karaoke captions."""
import os
import subprocess

FPS = 30
W, H = 1080, 1920
HERE = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(os.path.dirname(HERE), "assets", "fonts")
CAPTION_FONT = os.environ.get("CAPTION_FONT", "Anton")
HANDLE = os.environ.get("HANDLE", "@strangepast.daily")

MOVES = [
    ("min(zoom+0.0009,1.18)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),  # zoom in centre
    ("1.18", "(iw-iw/zoom)*on/{n}", "ih/2-(ih/zoom/2)"),  # pan left->right
    ("max(1.18-0.0009*on,1.0)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),  # zoom out
    ("1.18", "(iw-iw/zoom)*(1-on/{n})", "ih/2-(ih/zoom/2)"),  # pan right->left
    ("min(zoom+0.0009,1.18)", "iw/2-(iw/zoom/2)", "(ih-ih/zoom)*0.25"),  # zoom in upper
]


def run(cmd):
    print("+", " ".join(cmd[:6]), "...")
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def scene_clip(image, seconds, out, idx):
    n = max(1, round(seconds * FPS))
    z, x, y = (s.format(n=n) for s in MOVES[idx % len(MOVES)])
    vf = (
        f"scale={W * 2}:{H * 2},"
        f"zoompan=z='{z}':x='{x}':y='{y}':d={n}:s={W}x{H}:fps={FPS},"
        "eq=brightness=-0.03:saturation=1.08,vignette=PI/5,format=yuv420p"
    )
    run(["ffmpeg", "-y", "-i", image, "-vf", vf, "-frames:v", str(n), "-c:v", "libx264",
         "-preset", "veryfast", "-crf", "18", out])


def _ts(t):
    t = max(0.0, t)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _chunks(words, max_words=3, max_gap=0.35):
    chunk = []
    for w in words:
        if chunk and (len(chunk) >= max_words or w["start"] - chunk[-1]["end"] > max_gap
                      or chunk[-1]["text"][-1:] in ".,!?;:"):
            yield chunk
            chunk = []
        chunk.append(w)
    if chunk:
        yield chunk


def _fit(text, size, max_chars):
    return size if len(text) <= max_chars else max(56, int(size * max_chars / len(text)))


def _clean(t):
    return t.replace("{", "").replace("}", "").replace("\\", "").upper()


def write_ass(words, title, total, path):
    hdr = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{CAPTION_FONT},104,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,1,0,0,0,100,100,1,0,1,7,4,5,60,60,0,1
Style: Title,{CAPTION_FONT},118,&H0000D7FF,&H00FFFFFF,&H00000000,&H96000000,1,0,0,0,100,100,2,0,1,8,5,5,60,60,0,1
Style: Handle,{CAPTION_FONT},40,&H80FFFFFF,&H00FFFFFF,&H80000000,&H00000000,0,0,0,0,100,100,2,0,1,2,0,2,0,0,90,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    if title:
        lines.append(f"Dialogue: 2,{_ts(0)},{_ts(2.6)},Title,,0,0,0,,"
                     f"{{\\pos({W // 2},{int(H * 0.2)})\\fs{_fit(title, 118, 12)}\\fad(0,250)\\t(0,180,\\fscx112\\fscy112)\\t(180,320,\\fscx100\\fscy100)}}{_clean(title)}")
    for chunk in _chunks(words):
        for i, w in enumerate(chunk):
            start = w["start"]
            end = chunk[i + 1]["start"] if i + 1 < len(chunk) else w["end"] + 0.12
            parts = []
            for j, cw in enumerate(chunk):
                txt = _clean(cw["text"])
                parts.append("{\\c&H0000E5FF&}" + txt + "{\\c&H00FFFFFF&}" if j == i else txt)
            pop = "\\t(0,90,\\fscx108\\fscy108)\\t(90,160,\\fscx100\\fscy100)" if i == 0 else ""
            lines.append(f"Dialogue: 1,{_ts(start)},{_ts(end)},Cap,,0,0,0,,"
                         f"{{\\pos({W // 2},{int(H * 0.64)})\\fs{_fit(' '.join(c['text'] for c in chunk), 104, 15)}{pop}}}" + " ".join(parts))
    lines.append(f"Dialogue: 0,{_ts(0)},{_ts(total)},Handle,,0,0,0,,{HANDLE}")
    with open(path, "w", encoding="utf-8") as f:
        f.write(hdr + "\n".join(lines) + "\n")


def build(scenes, title, workdir, out, music=None):
    """scenes: [{'image','audio','duration','words'(relative times)}]"""
    clips, words, t = [], [], 0.0
    lead_out = 0.6  # small pause after the last line
    for i, s in enumerate(scenes):
        dur = s["duration"] + (lead_out if i == len(scenes) - 1 else 0)
        clip = os.path.join(workdir, f"clip{i}.mp4")
        scene_clip(s["image"], dur, clip, i)
        clips.append(clip)
        words += [{**w, "start": w["start"] + t, "end": w["end"] + t} for w in s["words"]]
        t += s["duration"]
    total = t + lead_out

    lst = os.path.join(workdir, "clips.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{os.path.abspath(c)}'\n" for c in clips)
    video = os.path.join(workdir, "video.mp4")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", video])

    alst = os.path.join(workdir, "audio.txt")
    with open(alst, "w") as f:
        f.writelines(f"file '{os.path.abspath(s['audio'])}'\n" for s in scenes)
    voice = os.path.join(workdir, "voice.wav")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", alst, "-ar", "44100", "-ac", "2", voice])

    ass = os.path.join(workdir, "subs.ass")
    write_ass(words, title, total, ass)

    cmd = ["ffmpeg", "-y", "-i", video, "-i", voice]
    if music and os.path.exists(music):
        cmd += ["-stream_loop", "-1", "-i", music]
        afilter = "[2:a]volume=0.10[m];[1:a][m]amix=inputs=2:duration=first:normalize=0,apad[a]"
    else:
        afilter = "[1:a]apad[a]"
    fonts = f":fontsdir={FONTS_DIR}" if os.path.isdir(FONTS_DIR) else ""
    cmd += ["-filter_complex", f"[0:v]ass={ass}{fonts}[v];{afilter}",
            "-map", "[v]", "-map", "[a]", "-t", f"{total:.2f}",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-profile:v", "high",
            "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-movflags", "+faststart", out]
    run(cmd)
    return total
