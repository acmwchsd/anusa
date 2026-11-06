# web: the Techpreneure Cam frontend

A SvelteKit single-page app: the Live camera page, the class roster, and the photo gallery.

```bash
npm install
npm run dev      # http://localhost:5173, proxies /api and /ws to the backend on :8004 (BACKEND_URL=... to change)
npm run check    # svelte-check and TypeScript
npm run build    # static files in build/
```

With Docker (`docker compose up` in the repo root), nginx serves it on <http://localhost:3000>
([Dockerfile](Dockerfile), [nginx.conf](nginx.conf)).

| Path | What it is |
| --- | --- |
| `src/routes/` | the Live, Students and Photos pages |
| `src/lib/components/` | the dialogs, the photo viewer, and the Live page's panels |
| `src/lib/api-client.ts` | typed client for the REST API |
| `src/lib/live-connection.svelte.ts` | the WebSocket to the backend, with every message it can receive |
| `src/lib/camera-feed.svelte.ts`, `voice-trigger.svelte.ts` | the Live page's camera and voice trigger |
| `src/lib/keyword-matching.ts` | keyword spotting for the browser's own speech recognition |
| `static/pcm-worklet.js` | microphone audio to 16 kHz PCM for Whisper |
