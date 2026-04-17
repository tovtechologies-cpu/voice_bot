# Travelioo — Railway Deployment Guide

## Prerequisites
- Railway account (https://railway.app)
- GitHub repository with the code pushed
- MongoDB Atlas account (free tier works) OR use Railway's MongoDB plugin

---

## Step 1 — Push Code to GitHub

In the Emergent chat input, click **"Save to GitHub"** to push the current codebase.
Make sure these files are at the **root** of the repo:
```
/Dockerfile
/railway.toml
/railway.json
/.dockerignore
/backend/           ← all Python code
```

---

## Step 2 — Create MongoDB

### Option A: Railway MongoDB Plugin (simplest)
1. Go to Railway dashboard → your project
2. Click **"+ New"** → **"Database"** → **"MongoDB"**
3. Once created, click on it → **"Variables"** tab
4. Copy the `MONGO_URL` value (starts with `mongodb://...`)

### Option B: MongoDB Atlas (recommended for production)
1. Go to https://cloud.mongodb.com
2. Create a free M0 cluster
3. Set Network Access → **Allow from anywhere** (0.0.0.0/0)
4. Create a database user
5. Get connection string: `mongodb+srv://user:password@cluster.xxxxx.mongodb.net/travelioo`

---

## Step 3 — Create Railway Service

1. Go to https://railway.app/dashboard
2. Click **"New Project"**
3. Choose **"Deploy from GitHub Repo"**
4. Select your Travelioo repository
5. Railway detects the `Dockerfile` automatically

---

## Step 4 — Set Environment Variables

In Railway dashboard → your service → **"Variables"** tab.

Click **"RAW Editor"** and paste ALL of these (replace values in `<...>`):

```env
MONGO_URL=<your_mongodb_url_from_step_2>
DB_NAME=travelioo
PORT=8001
APP_BASE_URL=https://<your-railway-domain>.up.railway.app
CORS_ORIGINS=*
WHATSAPP_PHONE_ID=1126308040556330
WHATSAPP_TOKEN=EAALX0stsp4ABRNZA3WdlCSqHHOviWAA2AYhnYSWTYuYTSCoD7NG5PwvKvcadmOBWWZCJZB97i3sDZCMlzpikrB5yyukZBt9W1CsIFTUAVD7yZCqidxdqAcAsXQFAOLLJFZBRGOC8vbXr9AFXQGyHrjnyIjGTutop05lFx0CEII9Nv4wXbpgjZATEdBPuHLqs0smLgwZDZD
WHATSAPP_VERIFY_TOKEN=travelioo_verify_2024
WHATSAPP_WEBHOOK_SECRET=GhxlKRYg9vORjr3lynK0pDSbfTRwp2Vc67E29DDMKgY
WHATSAPP_API_VERSION=v18.0
WHATSAPP_BASE_URL=https://graph.facebook.com
WHATSAPP_BUSINESS_PHONE=22901298883
WHATSAPP_COUNTRY=BJ
WHATSAPP_COUNTRY_CODE=229
TELEGRAM_BOT_TOKEN=8456557658:AAEWs9ODl9ZwPk88l9RjWE3DJcuuR4701QI
TELEGRAM_WEBHOOK_SECRET=AAEWs9ODl9ZwPk88l9RjWE3DJcuuR4701QI
CELTIIS_API_KEY=
CELTIIS_API_URL=https://api.celtiis.bj
MOMO_SUBSCRIPTION_KEY=
MOMO_API_USER=
MOMO_API_KEY=
MOMO_BASE_URL=https://sandbox.momodeveloper.mtn.com
MOMO_ENVIRONMENT=sandbox
MOMO_CURRENCY=XOF
MOOV_API_KEY=
MOOV_BASE_URL=https://api.moov-africa.bj
STRIPE_SECRET_KEY=
STRIPE_PUBLISHABLE_KEY=
STRIPE_WEBHOOK_SECRET=
DUFFEL_API_KEY=duffel_test_placeholder
DUFFEL_ENV=sandbox
EMERGENT_LLM_KEY=<your_emergent_llm_key>
ENCRYPTION_KEY=travelioo_aes256_prod_key_change_me
HUMAN_REVIEW_WEBHOOK=
IPINFO_API_KEY=
GOOGLE_PAY_MERCHANT_ID=
GOOGLE_PAY_ENVIRONMENT=TEST
APPLE_PAY_DOMAIN=
```

**IMPORTANT**: After deploy, update `APP_BASE_URL` with your actual Railway URL.

---

## Step 5 — Deploy

1. Railway auto-deploys when you push to GitHub
2. Or click **"Deploy"** manually in the dashboard
3. Wait for build to complete (~2-3 minutes)
4. Click **"Settings"** → **"Networking"** → **"Generate Domain"** to get your public URL

---

## Step 6 — Update APP_BASE_URL

Once you have your Railway domain (e.g., `travelioo-production.up.railway.app`):
1. Go to **Variables** tab
2. Update: `APP_BASE_URL=https://travelioo-production.up.railway.app`
3. Railway auto-redeploys

---

## Step 7 — Set Webhooks

### WhatsApp Webhook
1. Go to https://developers.facebook.com → Your App → WhatsApp → **Configuration**
2. Set:
   - **Callback URL**: `https://<your-railway-domain>.up.railway.app/api/webhook`
   - **Verify Token**: `travelioo_verify_2024`
3. Click **"Verify and Save"**
4. Subscribe to: **messages**

### Telegram Webhook
Run this command (replace `<DOMAIN>`):
```bash
curl -X POST "https://api.telegram.org/bot8456557658:AAEWs9ODl9ZwPk88l9RjWE3DJcuuR4701QI/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://<DOMAIN>.up.railway.app/api/telegram/webhook", "secret_token": "AAEWs9ODl9ZwPk88l9RjWE3DJcuuR4701QI"}'
```

---

## Step 8 — Verify

```bash
# Health check
curl https://<DOMAIN>.up.railway.app/api/health

# Test simulate
curl -X POST https://<DOMAIN>.up.railway.app/api/test/simulate \
  -H "Content-Type: application/json" \
  -d '{"phone": "+22990000001", "message": "bonjour"}'
```

Expected health response:
```json
{
  "status": "healthy",
  "services": {
    "mongodb": "connected",
    "whatsapp": "live",
    "telegram": "configured",
    "claude_ai": "configured"
  }
}
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Build fails on `emergentintegrations` | Dockerfile uses `--extra-index-url` for Emergent's private PyPI — check it's in the pip install line |
| MongoDB connection error | Check `MONGO_URL` is correct and network access allows Railway IPs (use 0.0.0.0/0 for Atlas) |
| WhatsApp webhook verify fails | Ensure `WHATSAPP_VERIFY_TOKEN` matches what you set in Meta console |
| Telegram 403 error | Bot can't message users who haven't started a conversation with it first |
| Port binding error | Railway injects `PORT` env var — our Dockerfile uses it |

---

## Railway Costs (estimate)
- **Hobby plan**: $5/month — enough for Travelioo
- **MongoDB Atlas free tier**: 512MB storage, sufficient for thousands of bookings
- **No sleep**: Railway keeps services running 24/7 on paid plans
