# Glovebox

Snap a car, let AI identify it, and add it to your collection with specs and Wikipedia-sourced stories. React Native (Expo) + TypeScript app with a Python FastAPI backend, using vision models on Groq and NVIDIA NIM. A learning project in vision AI, structured outputs and grounding.

```
phone (Expo Go)                       your computer                          cloud
┌──────────────────┐   photo (JPEG)   ┌───────────────────────────┐  base64   ┌──────────────┐
│ Scan → Result    │ ───────────────► │ FastAPI  POST /identify   │ ────────► │ Groq         │
│ Collection       │ ◄─────────────── │   resize, strip EXIF      │ ◄──────── │ (fallback:   │
│ Car detail       │   top-3 guesses  │   validate JSON (Pydantic)│   JSON    │  NVIDIA NIM) │
│ SQLite (local)   │                  │          GET /facts ──────┼─────────► │ Wikipedia    │
└──────────────────┘                  └───────────────────────────┘           └──────────────┘
```

API keys live **only** in `backend/.env`. The app only ever talks to the backend.

## Repository layout

```
backend/
  app/
    main.py         FastAPI routes: /identify, /facts, /health
    config.py       settings from .env (pydantic-settings)
    schemas.py      Pydantic models: model output + API responses
    providers.py    VisionProvider: one OpenAI-compatible client per provider
    identify.py     primary → fallback, JSON validation, strict retry
    image_prep.py   resize ≤1024px, JPEG ~80%, strip EXIF, base64
    prompts.py      system / retry prompts
    wikipedia.py    search + summary lookup for /facts
  eval/run_eval.py  accuracy + latency comparison of providers
  tests/            pytest (all providers mocked)
mobile/
  src/app/          screens (Expo Router: every file is a route)
    index.tsx       Scan (camera + gallery)
    result.tsx      top-3 guesses, confirm / "none of these"
    collection.tsx  saved cars
    car/[id].tsx    photo, specs, Wikipedia summary
  src/api/          typed API client; types.ts mirrors backend/app/schemas.py
  src/db/cars.ts    expo-sqlite schema + queries
  src/lib/          photo resize/persist, useRequest hook, formatting
```

## Prerequisites

- Python 3.11+
- Node.js 20+ (LTS)
- [Expo Go](https://expo.dev/go) on your phone, **matching SDK 58**
- API keys: [Groq](https://console.groq.com/keys) and/or [NVIDIA build](https://build.nvidia.com) (one is enough. With both you get fallback.)
- Phone and computer on the **same Wi-Fi network**

## 1. Backend

```bash
cd backend
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env        # then paste your API keys into .env
```

Model IDs and base URLs live in `.env` (see the comments in `.env.example`). The defaults were checked against the provider docs in November 2026:

| Provider | Base URL | Vision model |
|---|---|---|
| Groq | `https://api.groq.com/openai/v1` | `qwen/qwen3.8-27b` (preview) |
| NVIDIA NIM | `https://integrate.api.nvidia.com/v1` | `nvidia/nemotron-3.5-super-vl-120b-a12b` |

> Groq shut down `meta-llama/llama-4-scout-17b-16e-instruct` on 2026-07-17, and the hosted NVIDIA API no longer lists `nvidia/llama-3.1-nemotron-nano-vl-8b-v1`. If a model is retired again, change the ID in `.env`. No code changes needed. To see what NVIDIA currently serves: `curl https://integrate.api.nvidia.com/v1/models`.

`*_EXTRA_BODY` holds provider-specific request options as JSON. The defaults turn off each model's "thinking" mode, so replies are fast and contain only JSON.

**Run it:**

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

`--host 0.0.0.0` is required. Without it the server only accepts connections from your computer itself, and your phone can't reach it.

Check it works:

- http://localhost:8000/health shows the providers that have keys
- http://localhost:8000/docs has interactive API docs. You can upload a photo to `/identify` from here.
- http://localhost:8000/facts?make=Mazda&model=MX-5

**Tests** (no network, no API keys needed; providers and Wikipedia are mocked):

```bash
pytest
```

## 2. Mobile app

### Find your computer's LAN IP

Your phone can't use `localhost`: on the phone, "localhost" means **the phone itself**. Use your computer's address on the Wi-Fi network instead:

- **Windows:** `ipconfig` → "IPv4 Address" under your Wi-Fi adapter (e.g. `192.168.1.20`)
- **macOS:** `ipconfig getifaddr en0`
- **Linux:** `hostname -I`

```bash
cd mobile
npm install
cp .env.example .env
# edit .env:  EXPO_PUBLIC_API_URL=http://<your-LAN-IP>:8000
npx expo start
```

Scan the QR code with the camera app (iOS) or Expo Go (Android). The grey bar at the top of the Scan screen shows whether the app can reach the backend.

If you change `.env`, restart with `npx expo start --clear`. `EXPO_PUBLIC_*` values are baked in at bundle time.

**If the status bar says "Can't reach the backend":**
1. Open `http://<LAN-IP>:8000/health` in your **phone's** browser. If that fails, it's a network problem, not an app problem.
2. **Windows Firewall:** the first time uvicorn runs, Windows may ask to allow Python on networks. Allow it on *Private* networks. If you missed the prompt, allow `python.exe` under *Windows Security → Firewall → Allow an app*.
3. Make sure the Wi-Fi network is set to *Private*, not *Public*, in Windows.
4. Some guest/office networks block device-to-device traffic. A phone hotspot works as a fallback.

Checks: `npm run typecheck` and `npm run lint`.

### Using the app

1. **Scan:** take a photo or pick one from the gallery. It is resized to ≤1024px JPEG on the phone before upload.
2. **Result:** pick one of the top 3 guesses and tap *Save to collection*, or tap *None of these* to discard. Non-car or unclear photos get a "not a car" message instead of guesses.
3. **Collection:** your saved cars, stored on the phone in SQLite. Photos are copied to the app's document folder.
4. **Car detail:** photo, specs, and a Wikipedia summary with a link to the source.

## 3. Evaluating providers

`eval/run_eval.py` runs a labelled photo set through **every** configured provider, with no fallback, so each is measured on its own.

1. Put photos in `backend/eval/images/` (this folder is git-ignored).
2. List them in `backend/eval/labels.csv`:
   ```csv
   filename,make,model
   red_mx5.jpg,Mazda,MX-5
   street_golf.jpg,Volkswagen,Golf
   ```
3. From `backend/` (venv active, `.env` configured):
   ```bash
   python -m eval.run_eval                     # all images, all providers
   python -m eval.run_eval --providers groq    # one provider
   python -m eval.run_eval --limit 5           # quick smoke run
   ```

It prints top-1 accuracy (the first guess is right), top-3 accuracy (any of the three is right), error count and average latency per provider. Per-image rows are saved to `eval/results/results_<timestamp>.csv`. Matching ignores case and punctuation, knows a few aliases (VW = Volkswagen), and accepts trims ("Golf GTI" counts for "Golf"). See `make_matches`/`model_matches`.

Requests run one at a time to stay within free-tier rate limits and keep latency numbers clean.

## How /identify works

1. Upload is size-checked (`MAX_UPLOAD_MB`), then normalised: EXIF rotation applied, converted to RGB, longest side ≤1024px, JPEG q80, **all EXIF removed** (including GPS).
2. The primary provider gets a system prompt describing the exact JSON shape.
3. The reply is parsed (tolerating code fences and `<think>` blocks) and validated with Pydantic: up to 3 candidates, confidence 0–1, sorted by confidence, no candidates if `is_car` is false.
4. Invalid JSON → **one** retry with a stricter prompt that names the problem.
5. Provider error (network after one retry, auth, rate limit, ...) or invalid JSON twice → fallback provider.
6. Both fail → `502` with `{"code": "...", "message": "..."}`. "Not a car" is a valid answer, not a failure, so it never triggers the fallback.
7. Every call logs `provider`, `model` and `latency_ms`. The response's `latency_ms` is the time spent with the provider that answered.

## Known limitations / next steps

- `/facts` returns the Wikipedia summary as-is. Grounding AI-written facts on it comes later.
- Photos are stored by absolute `file://` URI. On iOS the app container path can change after an app update or reinstall, so storing a relative filename would be sturdier.
- Expo Go allows plain `http://` to your LAN IP. A standalone/development build on Android needs cleartext traffic enabled (or HTTPS) to do the same.
- `mobile/src/api/types.ts` is kept in sync with `backend/app/schemas.py` by hand. Generating it from `/openapi.json` would remove that chore.
