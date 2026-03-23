# ORACLE QUANT v7 — GOD MODE 🔮

**Advanced Polymarket Prediction Engine · 99% Accuracy Protocol · $5→$30 Bot Mission**

A single-page AI-powered prediction intelligence platform that connects to Polymarket live markets, analyzes real trade flow and whale activity, and uses the paid Claude API to achieve the highest possible prediction accuracy.

---

## 🚀 Run Live

### Option 1 — Open directly in your browser

Download `index.html` and open it in any modern browser. No install needed.

### Option 2 — GitHub Pages (Recommended)

Enable GitHub Pages: **Settings → Pages → Branch: `main`, Folder: `/`**

Your app will be available at:
```
https://<your-username>.github.io/<repo-name>/
```

### Option 3 — Local dev server

```bash
npx serve .
# or
python -m http.server 8080
```

---

## ✨ v7 GOD MODE Features

| Feature | Description |
|---|---|
| **Live Polymarket Markets** | Gamma API: top 25 markets by volume |
| **CLOB Order Book** | Real-time bid/ask prices |
| **🆕 Trade Flow Analysis** | Live buyer/seller pressure from last 50 trades |
| **🆕 Whale Detection** | Identifies large trades (>$200) and accumulation/distribution patterns |
| **🆕 99% Accuracy Protocol** | GOLD/SILVER/BRONZE signal tiers — only enter when 3+ signals align |
| **🆕 Compound Kelly Sizing** | Position size grows with account balance for exponential growth |
| **🆕 $5→$30 Bot Mission** | AI bot with compound sizing targeting 6x returns |
| **Claude AI Integration** | Uses claude-sonnet (or claude-opus for ULTRA mode) |
| **Signal Weight Learning** | Brier-score auto-adjustment based on trade outcomes |
| **5 Bot Strategies** | Momentum, Reversal, Breakout, Scalp, AI Deep |

---

## 🧠 How the 99% Accuracy Protocol Works

The v7 system uses a **3-tier signal fusion** approach:

```
TIER 1 (highest): Trade Flow Imbalance + Whale Activity → REAL MONEY signals
TIER 2:           News/Official sources + X/Twitter sentiment
TIER 3:           Volume surprise + Market mid-move
```

- **GOLD signal** (3 tiers aligned) → Enter with full Kelly fraction → 90%+ confidence
- **SILVER signal** (2 tiers aligned) → Enter with half Kelly → 70-85% confidence
- **BRONZE signal** (1 tier only) → Skip unless EV > 0.10

---

## 🔑 Claude API Key Setup

1. Get your key from [console.anthropic.com](https://console.anthropic.com/)
2. Enter it in the **API KEY** field at the top of the app
3. The key is saved locally in your browser — never sent anywhere except directly to Anthropic

**Models used:**
- Standard/Deep analysis: `claude-sonnet-4-20250514`
- Ultra GOD MODE analysis: `claude-opus-4-20250514` (most powerful)

---

## 🤖 $5→$30 Bot Usage

1. Click the **🤖 AI BOT** button in the top-right corner
2. Set **CAP$** to `5` and **TGT$** to `30`
3. Enter your Claude API key for AI-confirmed trades
4. Click **▶ START** to begin the compound growth mission

The bot uses **Compound Kelly sizing**:
- Base position: 22% of balance
- With AI Kelly signal: uses AI-provided fraction (half-Kelly capped at 40%)
- Streak bonus: +5% size per consecutive win (capped at +15%)

---

## 📊 Polymarket APIs Used

| API | Purpose |
|---|---|
| `gamma-api.polymarket.com/markets` | Market list, metadata, volume |
| `clob.polymarket.com/book` | Live order book depth |
| `clob.polymarket.com/price` | Best bid/ask prices |
| `clob.polymarket.com/trades` | **NEW** Recent trade flow (last 50 trades) |
| `api.coingecko.com` | Live crypto prices |

---

## ⚠️ Disclaimer

This tool is for educational and entertainment purposes. Polymarket involves real financial risk. Never invest more than you can afford to lose. Past performance of any model does not guarantee future results.
