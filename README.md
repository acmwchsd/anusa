# Techpreneure Cam

A classroom camera that knows the class. It finds the faces in the camera, names the students it knows, and takes
a photo when someone says **"cheese"**.

## Run it

```bash
docker compose up -d --build
```

Open <http://localhost:3000>, allow the camera, and say "cheese". A script can take a photo too:
`curl -X POST http://localhost:3000/api/capture`. Stop it with `docker compose down`.

There is no login: anyone who can reach port 3000 can see and change the class.

## What's inside

| Folder | What it is |
| --- | --- |
| [`api/`](api) | the backend: FastAPI, face recognition (OpenCV) and speech-to-text (whisper.cpp) |
| [`web/`](web) | the frontend: a SvelteKit app, served by nginx |
| `models/` | the model files: face detector, face recognizer, Whisper |
| `data/faces/` | your students and photos (kept out of git) |

To run it without Docker, or to change the code, see [api/README.md](api/README.md) and [web/README.md](web/README.md).
