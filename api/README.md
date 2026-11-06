# api: the classroom camera server

The backend of Techpreneure Cam, in Python. It finds the faces in the camera, names the students it knows, and
takes a photo when someone says **"cheese"**. FastAPI for the API, OpenCV for the face models, whisper.cpp for
speech, asyncio for the live stream.

## Run it

With Docker, from the repo root: `docker compose up -d --build`, then open <http://localhost:3000>.

On your computer (Python 3.10 or newer):

```bash
cd api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m app
```

The first start downloads the models into `../models` (about 190 MB). Students and photos are saved in `data/`.
Then build the web app (`npm run build` in `web/`) and open <http://localhost:8004>, or run `npm run dev` in `web/`
and open <http://localhost:5173>. The API docs are at <http://localhost:8004/docs>.

## How it works

- **Faces:** the Live page streams camera frames over `/ws`. The server finds the faces (YuNet), follows them from
  frame to frame, turns each into 128 numbers (SFace), and compares them with every student's reference photos.
- **Voice:** the microphone audio is cut into utterances, written down by whisper.cpp, and checked for the keyword.
- **Photos:** on a match, the server asks a Live page to take a full-resolution photo and post it to `/api/photos`.
  `POST /api/capture` does the same for a script, and answers with the photo.

## The code

All in `app/`:

| File | What it does |
| --- | --- |
| `main.py`, `app_state.py` | starts everything; the state shared by every route |
| `config.py`, `settings.py` | the environment variables; the teacher's settings |
| `face_analysis.py`, `face_tracking.py` | finds and recognizes faces; follows them from frame to frame |
| `class_roster.py`, `photo_store.py` | the people and their reference photos; the photos taken |
| `voice_activity.py`, `transcription.py` | cuts the audio into utterances; writes them down with whisper.cpp |
| `keyword_matching.py` | hears the keyword however Whisper spells it |
| `capture_coordinator.py` | asks a Live page to take a photo, and waits for it |
| `websocket_messages.py` | every message sent to the browser over `/ws` |
| `model_downloads.py`, `json_files.py`, `errors.py` | model files; JSON files on disk; API errors |
| `routes/` | `system.py` (health, settings), `people.py`, `photos.py` (photos, capture), `live_stream.py` (`/ws`) |

## Tests

```bash
python -m pytest
```

The face tests need `samples/bus.jpg` in the repo root. Every test uses an empty data folder of its own.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `BIND` | `0.0.0.0:8004` | where the server listens |
| `MODEL_DIR` | `../models` | the face and Whisper model files |
| `DATA_DIR` | `./data` | students and photos |
| `WEB_DIR` | `../web/build` | the built web app, served at `/` when it exists |
| `SPEECH` | `local` | `local` (whisper.cpp), `http` (speech-api at `SPEECH_URL`) or `off` (the browser's own) |
| `SPEECH_URL` | (empty) | the speech-api, for `SPEECH=http` |
| `WHISPER_MODEL` | `ggml-base.en.bin` | the whisper.cpp model in `MODEL_DIR` |
| `WHISPER_THREADS` | `4` | CPU threads whisper.cpp may use |
| `THREADS` | `4` | CPU threads OpenCV may use |

There is no login: anyone who can reach the port can see and delete students and photos.
