# Travelioo — Deployment Checklist

## Required Environment Variables

Fill ALL variables below before deploying. Copy this to your `.env` file.

```env
# ═══════════════════════════════════════════════════════
# DATABASE (pre-configured, do not change)
# ═══════════════════════════════════════════════════════
MONGO_URL=<your_mongodb_connection_string>
DB_NAME=travelioo

# ═══════════════════════════════════════════════════════
# APP
# ═══════════════════════════════════════════════════════
APP_BASE_URL=https://your-production-domain.com
CORS_ORIGINS=https://your-production-domain.com

# ═══════════════════════════════════════════════════════
# WHATSAPP CLOUD API (Meta Business)
# Get from: developers.facebook.com → Your App → WhatsApp → API Setup
# ═══════════════════════════════════════════════════════
WHATSAPP_PHONE_ID=<Phone Number ID from API Setup page>
WHATSAPP_TOKEN=<Permanent System User token with whatsapp_business_messaging permission>
WHATSAPP_VERIFY_TOKEN=travelioo_verify_2024
WHATSAPP_WEBHOOK_SECRET=<App Secret from App Settings → Basic>
WHATSAPP_API_VERSION=v18.0
WHATSAPP_BASE_URL=https://graph.facebook.com
WHATSAPP_BUSINESS_PHONE=<Your WhatsApp business phone number without +>
WHATSAPP_COUNTRY=BJ
WHATSAPP_COUNTRY_CODE=229

# ═══════════════════════════════════════════════════════
# TELEGRAM BOT
# Get from: @BotFather on Telegram → /newbot
# ═══════════════════════════════════════════════════════
TELEGRAM_BOT_TOKEN=<Bot token from BotFather>
TELEGRAM_WEBHOOK_SECRET=<Optional: custom secret for webhook verification>

# ═══════════════════════════════════════════════════════
# CELTIIS CASH (Benin mobile money — priority partner)
# Get from: Celtiis partner dashboard
# ═══════════════════════════════════════════════════════
CELTIIS_API_KEY=<Celtiis production API key>
CELTIIS_API_URL=https://api.celtiis.bj

# ═══════════════════════════════════════════════════════
# MTN MOMO (UEMOA mobile money)
# Get from: momodeveloper.mtn.com → Create API User
# ═══════════════════════════════════════════════════════
MOMO_SUBSCRIPTION_KEY=<Primary subscription key>
MOMO_API_USER=<API User UUID>
MOMO_API_KEY=<API Key for the user>
MOMO_BASE_URL=https://proxy.momoapi.mtn.com
MOMO_ENVIRONMENT=production
MOMO_CURRENCY=XOF

# ═══════════════════════════════════════════════════════
# MOOV MONEY (Flooz — UEMOA)
# Get from: Moov Africa partner dashboard
# ═══════════════════════════════════════════════════════
MOOV_API_KEY=<Moov production API key>
MOOV_BASE_URL=https://api.moov-africa.bj

# ═══════════════════════════════════════════════════════
# STRIPE (International cards / Google Pay / Apple Pay)
# Get from: dashboard.stripe.com → Developers → API keys
# ═══════════════════════════════════════════════════════
STRIPE_SECRET_KEY=sk_live_<your_live_key>
STRIPE_PUBLISHABLE_KEY=pk_live_<your_live_key>
STRIPE_WEBHOOK_SECRET=whsec_<your_webhook_secret>

# ═══════════════════════════════════════════════════════
# DUFFEL GDS (Flight search)
# Get from: app.duffel.com → Organization → API tokens
# ═══════════════════════════════════════════════════════
DUFFEL_API_KEY=duffel_live_<your_production_key>
DUFFEL_ENV=production

# ═══════════════════════════════════════════════════════
# AI / LLM (Claude + Whisper via Emergent)
# Already configured — do not change
# ═══════════════════════════════════════════════════════
EMERGENT_LLM_KEY=<already_set>

# ═══════════════════════════════════════════════════════
# SECURITY
# ═══════════════════════════════════════════════════════
ENCRYPTION_KEY=<random 32+ char string for AES-256-GCM>

# ═══════════════════════════════════════════════════════
# HUMAN-IN-THE-LOOP
# Set to a webhook URL (Slack, Discord, or custom)
# Receives JSON POST when HITL review is triggered
# ═══════════════════════════════════════════════════════
HUMAN_REVIEW_WEBHOOK=<your_slack_or_discord_webhook_url>

# ═══════════════════════════════════════════════════════
# IP GEOLOCATION (optional — for payment routing)
# Get from: ipinfo.io/account
# ═══════════════════════════════════════════════════════
IPINFO_API_KEY=<optional_ipinfo_token>

# ═══════════════════════════════════════════════════════
# GOOGLE PAY / APPLE PAY (optional — via Stripe)
# ═══════════════════════════════════════════════════════
GOOGLE_PAY_MERCHANT_ID=<optional>
GOOGLE_PAY_ENVIRONMENT=PRODUCTION
APPLE_PAY_DOMAIN=<optional>
```

## Post-Deploy Steps

### 1. Set WhatsApp Webhook
In Meta Developer Console → Your App → WhatsApp → Configuration:
- Callback URL: `https://your-domain.com/api/webhook`
- Verify Token: `travelioo_verify_2024`
- Subscribe to: `messages`, `message_deliveries`

### 2. Set Telegram Webhook
```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-domain.com/api/telegram/webhook", "secret_token": "<TELEGRAM_WEBHOOK_SECRET>"}'
```

### 3. Verify Health
```bash
curl https://your-domain.com/api/health
```
All services should show as configured/live.

### 4. Test E2E
Send a WhatsApp message to your business number. The bot should respond with the consent prompt.

## Feature Summary (All implemented)

| Feature | Status | Dependencies |
|---------|--------|-------------|
| WhatsApp Bot | Ready | WHATSAPP_* vars |
| Telegram Bot | Ready | TELEGRAM_BOT_TOKEN |
| Shadow Profiles | Ready | MONGO_URL |
| Dynamic Pricing | Ready | None |
| Payment Drivers | Ready | Payment API keys |
| OCR Rebound | Ready | EMERGENT_LLM_KEY |
| Fast-Track | Ready | None |
| Split Payment | Ready | Payment API keys |
| Multilingual (7 langs) | Ready | EMERGENT_LLM_KEY |
| HITL Reviews | Ready | HUMAN_REVIEW_WEBHOOK |
| Proactive SAV | Ready | DUFFEL_API_KEY (live) |
| Predictive Fare Alerts | Ready | DUFFEL_API_KEY (live) |
| AES-256 Encryption | Ready | ENCRYPTION_KEY |
| GDPR Consent + Deletion | Ready | None |
