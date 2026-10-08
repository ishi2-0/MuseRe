"""Reel link/video -> B-flat trumpet notes + MusicXML."""
import os
import re
import tempfile

MAX_SECONDS = 60  # only transcribe the first minute

# Written trumpet range (Bb trumpet, written pitch): F#3 (54) to C6 (84)
LOW, HIGH = 54, 84

# Valve fingerings by written MIDI note. "open" = no valves.
FINGERINGS = {
    54: "1-2-3", 55: "1-3", 56: "2-3", 57: "1-2", 58: "1", 59: "2",
    60: "open", 61: "1-2-3", 62: "1-3", 63: "2-3", 64: "1-2", 65: "1",
    66: "2", 67: "open", 68: "2-3", 69: "1-2", 70: "1", 71: "2",
    72: "open", 73: "1-2", 74: "1", 75: "2", 76: "open", 77: "1",
    78: "2", 79: "open", 80: "2-3", 81: "1-2", 82: "1", 83: "2", 84: "open",
}

NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def midi_name(m: int) -> str:
    return f"{NAMES[m % 12]}{m // 12 - 1}"


def download_audio(url: str, out_dir: str) -> str:
    """Download audio of a public Instagram reel with yt-dlp, return wav path."""
    import yt_dlp

    opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(out_dir, "reel.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "wav"}
        ],
    }
    cookies = os.environ.get("IG_COOKIES_FILE")
    if cookies and os.path.exists(cookies):
        opts["cookiefile"] = cookies
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
    path = os.path.join(out_dir, "reel.wav")
    if not os.path.exists(path):
        raise RuntimeError("Could not download audio from that link.")
    return path


def extract_audio_from_video(video_path: str, out_dir: str) -> str:
    """Pull audio out of an uploaded video/audio file with ffmpeg."""
    import subprocess

    out = os.path.join(out_dir, "upload.wav")
    subprocess.run(
        ["ffmpeg", "-y", "-i", video_path, "-vn", "-ac", "1", out],
        check=True, capture_output=True,
    )
    return out


def trim_audio(path: str, out_dir: str) -> str:
    import subprocess

    out = os.path.join(out_dir, "trimmed.wav")
    subprocess.run(
        ["ffmpeg", "-y", "-i", path, "-t", str(MAX_SECONDS), "-ac", "1",
         "-ar", "22050", out],
        check=True, capture_output=True,
    )
    return out


def transcribe(audio_path: str):
    """Audio -> (note events, tempo). Uses Basic Pitch."""
    from basic_pitch.inference import predict

    _, midi_data, note_events = predict(audio_path)
    try:
        tempo = float(midi_data.estimate_tempo())
    except Exception:
        tempo = 120.0
    # Basic Pitch's tempo guess can be off by 2x; keep it in a singable range.
    while tempo > 160:
        tempo /= 2
    while tempo < 60:
        tempo *= 2
    # note_events: (start, end, pitch, amplitude, pitch_bends)
    notes = [(float(s), float(e), int(p), float(a))
             for s, e, p, a, *_ in note_events]
    return notes, tempo


def extract_melody(notes, min_amp=0.25, min_dur=0.08):
    """Reduce polyphonic notes to one line (highest sounding note wins)."""
    notes = [n for n in notes if n[3] >= min_amp and (n[1] - n[0]) >= min_dur]
    notes.sort(key=lambda n: (n[0], -n[2]))
    melody = []
    for s, e, p, a in notes:
        if melody:
            ps, pe, pp, pa = melody[-1]
            if s < pe:  # overlaps previous note
                if p > pp and s - ps > 0.05:
                    melody[-1] = (ps, s, pp, pa)  # cut previous short
                    melody.append((s, e, p, a))
                # otherwise drop the lower/overlapping note
                continue
        melody.append((s, e, p, a))
    return [m for m in melody if m[1] - m[0] >= min_dur]


def estimate_tempo_from_onsets(melody, fallback=110.0):
    """Pick the BPM (70-160) at which note starts line up best with an
    eighth-note grid. Much steadier than a generic tempo guess for a melody."""
    if len(melody) < 4:
        return fallback
    t0 = melody[0][0]
    onsets = [m[0] - t0 for m in melody]
    best_bpm, best_score = fallback, None
    for bpm in range(70, 161):
        grid = 60.0 / bpm / 2  # one eighth note in seconds
        err = 0.0
        for o in onsets:
            x = o / grid
            err += abs(x - round(x))
        err /= len(onsets)
        score = err + abs(bpm - 110) * 0.0004  # gentle pull toward mid-range
        if best_score is None or score < best_score:
            best_bpm, best_score = bpm, score
    return float(best_bpm)


def fit_to_trumpet(melody):
    """Convert concert pitch -> written Bb trumpet pitch, fitted to range."""
    written = [(s, e, p + 2, a) for s, e, p, a in melody]  # up a major 2nd
    if not written:
        return written
    pitches = sorted(p for _, _, p, _ in written)
    median = pitches[len(pitches) // 2]
    target = (LOW + HIGH) / 2
    shift = round((target - median) / 12) * 12  # whole-octave shift
    out = []
    for s, e, p, a in written:
        p += shift
        while p < LOW:
            p += 12
        while p > HIGH:
            p -= 12
        out.append((s, e, p, a))
    return out


def build_musicxml(written, tempo, concert_key_name):
    """Quantize to a 16th grid and write MusicXML for the trumpet part."""
    from music21 import stream, note, tempo as m21tempo, instrument, meter, key

    spb = 60.0 / tempo  # seconds per beat
    t0 = written[0][0] if written else 0.0  # start the music at the first note
    written = [(s - t0, e - t0, p, a) for s, e, p, a in written]
    part = stream.Part()
    part.insert(0, instrument.Trumpet())
    part.insert(0, m21tempo.MetronomeMark(number=round(tempo)))
    part.insert(0, meter.TimeSignature("4/4"))

    last_end = 0.0
    for s, e, p, _ in written:
        start = max(round(s / spb * 4) / 4, last_end)  # in quarter-note beats
        end = round(e / spb * 4) / 4
        dur = end - start
        if dur < 0.25:
            dur = 0.25
        n = note.Note(p)
        n.quarterLength = dur
        part.insert(start, n)
        last_end = start + dur
    score = stream.Score()
    score.insert(0, part)
    score = score.makeNotation(inPlace=False) if hasattr(score, "makeNotation") else score
    return score


def score_to_xml(score) -> str:
    import music21

    with tempfile.TemporaryDirectory() as d:
        path = score.write("musicxml", fp=os.path.join(d, "out.musicxml"))
        with open(path, "r", encoding="utf-8") as f:
            return f.read()


def detect_key(melody):
    from music21 import stream, note

    s = stream.Stream()
    for _, _, p, _ in melody[:200]:
        s.append(note.Note(p))
    try:
        k = s.analyze("key")
        return f"{k.tonic.name} {k.mode}"
    except Exception:
        return "unknown"


def process_audio(audio_path: str, work_dir: str) -> dict:
    trimmed = trim_audio(audio_path, work_dir)
    notes, tempo = transcribe(trimmed)
    melody = extract_melody(notes)
    if len(melody) < 3:
        raise RuntimeError(
            "Couldn't find a clear melody. Try a reel with a clearer tune."
        )
    tempo = estimate_tempo_from_onsets(melody, fallback=tempo)
    key_name = detect_key(melody)
    written = fit_to_trumpet(melody)
    score = build_musicxml(written, tempo, key_name)
    xml = score_to_xml(score)
    notes_out = [
        {
            "name": midi_name(p),
            "fingering": FINGERINGS.get(p, "?"),
            "start": round(s, 2),
            "length": round(e - s, 2),
        }
        for s, e, p, _ in written
    ]
    return {
        "tempo": round(tempo),
        "concert_key": key_name,
        "note_count": len(notes_out),
        "notes": notes_out,
        "musicxml": xml,
    }


def process_url(url: str, work_dir: str) -> dict:
    return process_audio(download_audio(url, work_dir), work_dir)


def process_upload(path: str, work_dir: str) -> dict:
    return process_audio(extract_audio_from_video(path, work_dir), work_dir)


INSTAGRAM_RE = re.compile(
    r"https?://(?:www\.)?instagram\.com/(?:reel|reels|p|tv)/[\w\-]+[^\s]*",
    re.I,
)


def find_instagram_url(text: str):
    m = INSTAGRAM_RE.search(text or "")
    return m.group(0) if m else None
