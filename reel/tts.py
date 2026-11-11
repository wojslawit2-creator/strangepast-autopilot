"""Free neural voice-over via edge-tts, with word timings for captions."""
import asyncio
import inspect
import subprocess

import edge_tts

VOICE = "en-US-AndrewMultilingualNeural"
RATE = "+6%"


def duration(path):
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]
    )
    return float(out.strip())


async def _speak(text, path, voice, rate):
    kwargs = {"rate": rate}
    if "boundary" in inspect.signature(edge_tts.Communicate.__init__).parameters:
        kwargs["boundary"] = "WordBoundary"
    comm = edge_tts.Communicate(text, voice, **kwargs)
    words = []
    with open(path, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 1e7
                words.append({"text": chunk["text"], "start": start, "end": start + chunk["duration"] / 1e7})
    return words


def speak(text, path, voice=VOICE, rate=RATE):
    """Returns (duration_seconds, [{'text','start','end'}...])."""
    for attempt in range(3):
        try:
            words = asyncio.run(_speak(text, path, voice, rate))
            return duration(path), words
        except Exception as e:
            print(f"[tts] retry {attempt + 1}: {e}")
    raise RuntimeError("TTS failed")
