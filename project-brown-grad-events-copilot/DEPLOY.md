# Deploying the Grad Events Copilot

Two pieces: **backend** (FastAPI) → Railway, **frontend** (Next.js) → Vercel. The frontend
calls the backend over its public URL. Both deploy from the GitHub repo
(`keeeeeliu/sparks`), each pointed at a subdirectory.

> The repo root is `creativeApp/`; this project lives in `project-brown-grad-events-copilot/`.
> Setting the correct **Root Directory** on each platform is the main gotcha.

---

## 0. Commit & push the deploy prep

```bash
cd project-brown-grad-events-copilot
git add backend/api.py Procfile DEPLOY.md
git commit -m "Deploy prep: env-based CORS + Procfile + guide"
git push origin main
```

---

## 1. Backend → Railway

1. Go to **railway.app** → **New Project** → **Deploy from GitHub repo** → pick `keeeeeliu/sparks`.
2. Open the service → **Settings**:
   - **Root Directory:** `project-brown-grad-events-copilot`
   - Railway auto-detects Python (`requirements.txt`) and uses the **`Procfile`** start command
     (`uvicorn backend.api:app --host 0.0.0.0 --port $PORT`).
3. **Variables** → add:
   - `OPENAI_API_KEY` = your key *(required)*
   - *(optional)* `LLM_PROVIDER` / `LLM_MODEL` if not using the defaults (`openai` / `gpt-4o-mini`)
   - Leave `ALLOWED_ORIGINS` empty for now — set it in step 3.
4. Deploy. When it's live, copy the public URL (e.g. `https://grad-events-api.up.railway.app`).
5. **Test:** open `https://<your-railway-url>/api/health` → should return `{"status":"ok"}`.

---

## 2. Frontend → Vercel

1. Go to **vercel.com** → **Add New… → Project** → import `keeeeeliu/sparks`.
2. Configure:
   - **Root Directory:** `project-brown-grad-events-copilot/frontend`
   - Framework preset: **Next.js** (auto-detected)
3. **Environment Variables** → add:
   - `NEXT_PUBLIC_API_URL` = your Railway backend URL from step 1 (e.g. `https://grad-events-api.up.railway.app`)
4. Deploy. Copy the Vercel URL (e.g. `https://grad-events.vercel.app`).

---

## 3. Point CORS back at the frontend

The backend must allow the Vercel origin.

1. In **Railway → Variables**, set:
   - `ALLOWED_ORIGINS` = `https://grad-events.vercel.app` *(your exact Vercel URL, no trailing slash)*
2. Railway redeploys. Done.

---

## 4. Verify end-to-end

Open the **Vercel URL**, pick a date range, **Fetch events** → blurbs → Improve. If the fetch
fails with a network/CORS error, re-check that `NEXT_PUBLIC_API_URL` (Vercel) and
`ALLOWED_ORIGINS` (Railway) exactly match the deployed URLs.

---

## Things to know

- **Cost:** every fetch/generate makes real LLM calls (~$0.02–0.05 per fetch). A public URL means
  anyone with the link can trigger spend — fine for a manager preview. Set a **spend limit** on your
  OpenAI account, and if it goes wider, add a simple access gate (password / allowlist) later.
- **In-memory event cache:** the backend keeps fetched events in memory so "generate blurbs" can find
  them. Railway runs a single always-on instance, so a fetch→blurbs session works. If the instance
  restarts between steps, just re-fetch.
- **Secrets:** never commit `OPENAI_API_KEY` — it lives only in Railway's Variables. `.env` is gitignored.
- **Pricing tiers:** Vercel's free tier is plenty. Railway offers trial credit; an always-on service
  may need their paid Hobby plan (a few $/mo).
- **Favicon:** `app/icon.svg` works everywhere modern; a multi-res `.ico` is optional.
