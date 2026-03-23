# ORACLE QUANT v8 — GOD MODE 🔮

**Self-Learning · 2-Hour $5→$30 Mission · 24/7 · Live Polymarket AI · 99% Accuracy Protocol**

> **🟢 LIVE URL:** `https://kapoorkundan25-byte.github.io/oracleengine/`
>
> Auto-deploys from `main` via GitHub Actions every time code is pushed.

A single-page AI-powered prediction intelligence platform that:
- Connects to Polymarket live markets (Gamma + CLOB APIs)
- Analyzes real trade flow and whale activity
- Uses the paid Claude API (Sonnet/Opus) for deep Bayesian analysis
- Automatically self-learns by updating signal weights via Brier-score every 10 trades
- Runs a compound-Kelly bot targeting $5→$30 in 2 hours

---

## ⚡ Quick Start — Activate Live Deployment

This repository includes a GitHub Actions workflow (`.github/workflows/deploy.yml`) that publishes the app to GitHub Pages automatically.

**One-time setup (do this once after the PR is merged):**

1. Go to **[github.com/kapoorkundan25-byte/oracleengine/settings/pages](https://github.com/kapoorkundan25-byte/oracleengine/settings/pages)**
2. Under **Source**, select **GitHub Actions** (not "Deploy from a branch")
3. Click **Save**
4. The next push to `main` triggers the workflow and the app goes live at:
   ```
   https://kapoorkundan25-byte.github.io/oracleengine/
   ```
5. You can also trigger it manually: **Actions → Deploy Oracle Quant v8 → Run workflow**

**After that it's fully automatic** — every commit to `main` redeploys within ~1 minute.

---

## 🚀 Deploy Live (24/7 Free Hosting)

### Option 1 — Netlify (Connect GitHub — Auto-Deploys on Every Push) ⭐ Recommended

This repo ships a `netlify.toml` that pre-configures all settings automatically.
Just connect the repo and hit Deploy — no field values to enter.

**If Netlify still asks you for fields, use these exact values:**

| Netlify field | Value |
|---|---|
| **Base directory** | *(leave blank)* |
| **Build command** | *(leave blank)* |
| **Publish directory** | `.` ← a single dot |
| **Functions directory** | *(leave blank)* |

**Steps:**
1. Go to **[app.netlify.com](https://app.netlify.com)** → **Add new site → Import an existing project**
2. Choose **GitHub** → authorise → select **kapoorkundan25-byte/oracleengine**
3. Leave all build fields blank (or as shown above) → click **Deploy site**
4. You get a URL like `oracle-abc123.netlify.app` in ~30 seconds
5. **For privacy**: Site Settings → Access Control → Password → set a password only you know
6. Your Claude API key is stored in **your browser only** — never sent to Netlify

> **Netlify Drop (no GitHub account needed):**
> Go to **[app.netlify.com/drop](https://app.netlify.com/drop)** and drag-and-drop `index.html` directly.

### Option 2 — GitHub Pages (Auto-deploys via GitHub Actions — already set up)

This repo already includes `.github/workflows/deploy.yml`.

1. Push / merge to **`main`**
2. Go to **Settings → Pages → Source: GitHub Actions → Save** (one-time)
3. App goes live at `https://kapoorkundan25-byte.github.io/oracleengine/`
4. *Note: GitHub Pages on private repos requires GitHub Pro ($4/mo). Use Netlify for 100% free.*

### Option 3 — Vercel

1. Go to **[vercel.com](https://vercel.com)** → sign up free
2. New Project → Upload → select `index.html` → Deploy
3. Get URL like `oracle.vercel.app`

**In-app deploy guide**: Click the **📡 DEPLOY** button in the app toolbar for a step-by-step modal.

---

## 🔑 Claude API Key Setup (One-Time)

1. Go to **[console.anthropic.com](https://console.anthropic.com)** → sign up / log in
2. Go to **API Keys** → **Create Key** → copy the `sk-ant-...` key
3. In Oracle Quant: paste it in the **API KEY** field at the top
4. It saves in your browser's localStorage — enter it once per browser/device
5. **The key never leaves your browser** — it goes directly from your browser to Anthropic

**Models used:**
- Standard/Deep: `claude-sonnet-4-20250514`
- Ultra GOD MODE: `claude-opus-4-20250514` (most powerful, highest cost)

---

## ✨ v8 Features

| Feature | Description |
|---|---|
| **Live Polymarket Markets** | Gamma API: top 25 markets by volume |
| **CLOB Trade Flow** | Real-time buyer/seller pressure from last 50 trades |
| **Whale Detection** | Identifies accumulation/distribution by large traders (>$200) |
| **99% Accuracy Protocol** | GOLD/SILVER/BRONZE signal tiers — only enter when 3+ signals align |
| **🆕 2-Hour Mission** | Bot timer extended from 1 hour (v7) to 2 hours for $5→$30 compound growth |
| **🆕 Self-Learning AI** | Brier-score weight auto-update every 10 trades — gets smarter over time |
| **🆕 24/7 Mode** | `∞ 24/7` toggle: scanner restarts automatically after each cycle |
| **🆕 Deploy Guide** | In-app modal with step-by-step free hosting + privacy instructions |
| **Compound Kelly Sizing** | Position size grows with account balance — exponential growth |
| **Claude Opus ULTRA** | Most powerful model for ultra depth analysis |
| **Signal Weight Learning** | Brier-score calibration that improves with each prediction |
| **5 Bot Strategies** | Momentum, Reversal, Breakout, Scalp, AI Deep |

---

## 🧠 Self-Learning Engine

Every **10 trades** (bot + polymarket analyses combined), Oracle v8 automatically:

1. Calculates per-signal accuracy from all recorded trade outcomes
2. Runs Brier-score blending to update signal weights
3. Boosts weights for signals with accuracy > 55%
4. Reduces weights for signals with accuracy < 45%
5. Persists updated weights to localStorage (survives page reloads)
6. Displays learning cycle count and weight version in the header

Over time, the system self-calibrates to your specific markets and conditions — like a neural network that gets smarter with every prediction.

---

## 🤖 2-Hour $5→$30 Bot Usage

1. Click **🤖 AI BOT** in the top-right corner
2. Set **CAP$** = `5` and **TGT$** = `30`  
3. Enter your Claude API key for AI-confirmed trades
4. Click **▶ START** — the 2-hour countdown begins
5. The bot uses compound Kelly sizing + streak bonuses to target 6x in 2 hours

**Compound Kelly sizing:**
- Base position: 22% of current balance
- With AI Kelly signal: AI-provided fraction (half-Kelly, capped 40%)
- Streak bonus: +5% size per consecutive win ≥3 (max +15%)
- As balance grows, absolute position size grows automatically (compounding)

**2-hour strategy:**
- 4-second scan cycles = 1,800 cycles in 2 hours
- Target: ~20-30 profitable trades at 3-5% each = 6x compound growth
- AI confirmation every 2 cycles prevents bad trades
- Self-learning weights improve win rate as the session progresses

---

## 📊 Polymarket APIs Used

| API | Purpose |
|---|---|
| `gamma-api.polymarket.com/markets` | Market list, metadata, volume |
| `clob.polymarket.com/book` | Live order book depth |
| `clob.polymarket.com/price` | Best bid/ask prices |
| `clob.polymarket.com/trades` | Recent trade flow (last 50 trades) |
| `api.coingecko.com` | Live crypto prices for context |

---

## 🔒 Privacy & Security

| Data | Where it's stored | Who can see it |
|---|---|---|
| Claude API key | Your browser localStorage | **You only** |
| Trade history | Your browser localStorage | **You only** |
| Signal weights | Your browser localStorage | **You only** |
| Source code | GitHub repo | **Private if repo is private** |
| App URL | Netlify/Vercel | **Password-protected if you set it** |

**No server, no database** — everything runs in your browser. Your data never leaves your device except API calls directly to Anthropic and Polymarket.

---

## ⚠️ Disclaimer

This tool is for educational and entertainment purposes. Polymarket involves real financial risk. Never invest more than you can afford to lose. The bot uses simulated paper trading — "balance" is not real money unless you manually place the same trades on Polymarket.
