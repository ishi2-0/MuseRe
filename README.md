# Reel to Trumpet

Share an Instagram reel to this app and get the melody as B♭ trumpet sheet music, note names, and valve fingerings.

## How it works

1. `yt-dlp` downloads the reel's audio from the shared link
2. Basic Pitch turns the audio into notes
3. The melody is extracted, the tempo is estimated, and the notes are moved to written B♭ trumpet pitch (up a major 2nd) and fitted to the trumpet range
4. music21 writes MusicXML; the page draws it with OpenSheetMusicDisplay

## Run it on your computer (needs Python 3.11 and ffmpeg)

    python3.11 -m venv venv && source venv/bin/activate
    pip install -r requirements.txt
    uvicorn main:app --port 8000

Open http://localhost:8000. Basic Pitch downloads nothing extra; the first job is just slower.

## Put it online (needed for the phone Share button)

The Share button only works for an installed web app, and installing requires HTTPS, so the app must be hosted.

1. Put this folder in a GitHub repo.
2. Deploy it as a Docker web service (the `Dockerfile` is ready). `render.yaml` is set up for Render.
3. Memory: Basic Pitch uses TensorFlow, which needs more than Render's free 512 MB. Use a paid instance (about $7/month) or a host with more free memory (for example a Hugging Face Space using Docker).

## Install on your Samsung

1. Open your hosted link in **Chrome**.
2. Menu (three dots) → **Install app** / **Add to Home screen**.
3. In Instagram: reel → paper-airplane Share → **Share to…** → pick **Reel to Trumpet**.

## Notes

- Works on public reels. Private reels need Instagram login cookies; set `IG_COOKIES_FILE` to a cookies.txt path to try.
- Instagram changes often; if downloads stop working, run `pip install -U yt-dlp`.
- Cloud servers get blocked by Instagram more than home connections do. The upload button (screen recording) always works as a backup.
- Transcription is imperfect on busy songs. It works best on clear single-line melodies.
- Jobs are kept in memory, so they disappear when the server restarts.
