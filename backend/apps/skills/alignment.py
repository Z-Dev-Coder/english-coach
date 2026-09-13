"""Real word timings for real recordings, so the read-along follows the voice.

Estimating where the speaker is from how far through the audio we are drifts
badly with real programmes: VOA stories open with an introduction and music
that aren't in the transcript, so the highlight ran ahead of the voice. Here a
small local speech model (faster-whisper tiny.en, free, CPU) listens to the
recording once, and its words are matched to the transcript's words. Each
matched word keeps its start time.

Stored as [[word_index, seconds]], where word_index counts whitespace-separated
words in the text. Word indexes survive whitespace changes, so they can be turned
into character offsets for whatever form of the text a page shows.

Optional: without faster-whisper installed, nothing is aligned and pages fall back
to the estimate.
"""
from __future__ import annotations

import difflib
import os
import re
import tempfile
import threading
import urllib.request

_WORD = re.compile(r"\S+")
_model = None
_model_lock = threading.Lock()
_run_lock = threading.Lock()


def _norm(word: str) -> str:
    return re.sub(r"[^a-z0-9']", "", word.lower().replace("’", "'"))


def match(text: str, heard: list[tuple[str, float]]) -> list[list]:
    """Pair the text's words with heard (word, start) pairs. Returns [[word_index, start]]."""
    words = [_norm(token.group()) for token in _WORD.finditer(text)]
    heard = [(_norm(word), start) for word, start in heard if _norm(word)]
    indexed = [(i, w) for i, w in enumerate(words) if w]
    matcher = difflib.SequenceMatcher(None, [w for _, w in indexed], [w for w, _ in heard], autojunk=False)
    timings = []
    for block in matcher.get_matching_blocks():
        for k in range(block.size):
            timings.append([indexed[block.a + k][0], round(heard[block.b + k][1], 2)])
    # Keep time moving forward, in case a repeated phrase matched out of order.
    ordered, last = [], -1.0
    for index, start in sorted(timings):
        if start >= last:
            ordered.append([index, start])
            last = start
    return ordered


def char_timings(text: str, word_timings: list) -> list[list]:
    """[[char_offset, seconds]] for this text, from stored [[word_index, seconds]]."""
    if not word_timings:
        return []
    offsets = [token.start() for token in _WORD.finditer(text)]
    return [[offsets[i], start] for i, start in word_timings if i < len(offsets)]


def _get_model():
    global _model
    with _model_lock:
        if _model is None:
            from faster_whisper import WhisperModel

            _model = WhisperModel("tiny.en", device="cpu", compute_type="int8")
        return _model


def transcribe(url: str) -> list[tuple[str, float]] | None:
    """Words heard in the recording with start times; None if unavailable."""
    try:
        model = _get_model()
    except ImportError:
        return None
    fd, path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 english-coach"})
        with urllib.request.urlopen(request, timeout=60) as response, open(path, "wb") as out:
            out.write(response.read())
        segments, _ = model.transcribe(path, word_timestamps=True, beam_size=1)
        return [(w.word, w.start) for segment in segments for w in segment.words]
    finally:
        os.remove(path)


def timings_for(url: str, text: str) -> list[list]:
    heard = transcribe(url)
    if not heard:
        return []
    timings = match(text, heard)
    # Too few matches means the recording isn't this text; better no timings than wrong ones.
    words = len(_WORD.findall(text))
    return timings if words and len(timings) >= 0.5 * words else []


def scene_text(scene) -> str:
    return " ".join(line["text"] for line in scene.lines)


def align_passage(passage) -> bool:
    if not passage.audio_url:
        return False
    with _run_lock:  # one transcription at a time; they are CPU-heavy
        timings = timings_for(passage.audio_url, passage.text)
    if timings:
        passage.word_timings = timings
        passage.save(update_fields=["word_timings"])
    return bool(timings)


def align_scene(scene) -> bool:
    if not scene.audio_url:
        return False
    with _run_lock:
        timings = timings_for(scene.audio_url, scene_text(scene))
    if timings:
        scene.word_timings = timings
        scene.save(update_fields=["word_timings"])
    return bool(timings)


def align_in_background(obj) -> None:
    """Align a passage or scene in a thread, unless live fetching is off (tests)."""
    from django.conf import settings
    from django.db import close_old_connections

    if not getattr(settings, "LIVE_CONTENT_FETCH", True) or not getattr(obj, "audio_url", ""):
        return

    def work():
        try:
            (align_scene if hasattr(obj, "lines") else align_passage)(obj)
        except Exception:
            pass  # timings are an improvement; the estimate still works without them
        finally:
            close_old_connections()

    threading.Thread(target=work, daemon=True).start()
