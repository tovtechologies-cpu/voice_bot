# Payment Gateway Setup Guide

Travelio supports 4 payment operators with automatic environment detection.
Each operator runs in one of three modes: **PRODUCTION**, **SANDBOX/TEST**, or **MOCK**.

The mode is auto-detected at startup based on your `.env` configuration.

---

## Environment Detection Logic

### MTN MoMo
```
if MOMO_ENVIRONMENT == "production"
   AND MOMO_BASE_URL == "https://proxy.momoapi.mtn.com"
   AND all 3 keys present (SUBSCRIPTION_KEY, API_USER, API_KEY):
     mode = PRODUCTION

else if all 3 keys present but sandbox URL:
     mode = SANDBOX

else:
     mode = MOCK (simulated responses)
```

### Moov Money
```
if MOOV_API_KEY is set and not placeholder:
     mode = PRODUCTION
else:
     mode = MOCK
```

### Stripe (Google Pay / Apple Pay)
```
if STRIPE_SECRET_KEY starts with "sk_live_":
     mode = LIVE
elif starts with "sk_test_":
     mode = TEST
else:
     mode = MOCK
```

---

## 1. MTN MoMo — Production Setup

### Step 1: Create Developer Account
1. Go to https://momodeveloper.mtn.com/
2. Sign up / Sign in
3. Subscribe to the **Collection** product

### Step 2: Sandbox Testing
1. Create a sandbox user:
   ```bash
   # Generate UUID for API User
   python -c "import uuid; print(uuid.uuid4())"
   ```
2. Register the API user:
   ```bash
   curl -X POST https://sandbox.momodeveloper.mtn.com/v1_0/apiuser \
     -H "X-Reference-Id: YOUR_UUID" \
     -H "Ocp-Apim-Subscription-Key: YOUR_SUBSCRIPTION_KEY" \
     -H "Content-Type: application/json" \
     -d '{"providerCallbackHost": "your-domain.com"}'
   ```
3. Get the API key:
   ```bash
   curl -X POST https://sandbox.momodeveloper.mtn.com/v1_0/apiuser/YOUR_UUID/apikey \
     -H "Ocp-Apim-Subscription-Key: YOUR_SUBSCRIPTION_KEY"
   ```

### Step 3: Sandbox .env
```env
MOMO_SUBSCRIPTION_KEY=your_subscription_key
MOMO_API_USER=your_uuid
MOMO_API_KEY=your_api_key
MOMO_BASE_URL=https://sandbox.momodeveloper.mtn.com
MOMO_ENVIRONMENT=sandbox
MOMO_CURRENCY=XOF
MOMO_CALLBACK_URL=https://your-domain.com/api/momo/callback
```

### Step 4: Production Migration
1. Contact MTN MoMo Partner team for Benin (partnersupport@mtn.com)
2. Complete KYC / business verification
3. Receive production credentials
4. Update .env:
```env
MOMO_SUBSCRIPTION_KEY=production_key
MOMO_API_USER=production_uuid
MOMO_API_KEY=production_api_key
MOMO_BASE_URL=https://proxy.momoapi.mtn.com
MOMO_ENVIRONMENT=production
MOMO_CURRENCY=XOF
```

### Testing MoMo
```bash
# Check mode at startup logs:
# [PAYMENTS] MTN MoMo: PRODUCTION | SANDBOX | MOCK

# Sandbox test numbers (MoMo sandbox):
# 46733123453 — always succeeds
# 46733123454 — always fails
```

---

## 2. Moov Money (Flooz) — Setup

### Contact Process
Moov Money does not have a public developer portal. Integration requires:

1. Contact Moov Africa Benin commercial team
   - Email: commercial@moov-africa.bj
   - Or through your business relationship manager
2. Request API access for "Cash-In" (collection) service
3. Provide:
   - Business registration documents
   - Use case description (flight booking platform)
   - Expected transaction volumes
   - Callback URL: `https://your-domain.com/api/moov/callback`
4. Receive:
   - API key
   - API documentation
   - Sandbox environment (if available)

### .env Configuration
```env
MOOV_API_KEY=your_moov_api_key
MOOV_BASE_URL=https://api.moov-africa.bj
MOOV_CURRENCY=XOF
MOOV_CALLBACK_URL=https://your-domain.com/api/moov/callback
```

---

## 3. Stripe — Live Mode Activation

### Step 1: Create Stripe Account
1. Go to https://dashboard.stripe.com/register
2. Complete business verification
3. Activate your account

### Step 2: Get Test Keys
1. Go to https://dashboard.stripe.com/test/apikeys
2. Copy Publishable key (`pk_test_...`) and Secret key (`sk_test_...`)

### Step 3: Test .env
```env
STRIPE_SECRET_KEY=sk_test_your_test_key
STRIPE_PUBLISHABLE_KEY=pk_test_your_publishable_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret
```

### Step 4: Set Up Webhook
1. Go to https://dashboard.stripe.com/webhooks
2. Click "Add endpoint"
3. URL: `https://your-domain.com/api/stripe/webhook`
4. Events to listen for:
   - `payment_intent.succeeded`
   - `payment_intent.payment_failed`
5. Copy the webhook signing secret

### Step 5: Go Live
1. Complete Stripe account activation
2. Switch to live keys:
```env
STRIPE_SECRET_KEY=sk_live_your_live_key
STRIPE_PUBLISHABLE_KEY=pk_live_your_publishable_key
STRIPE_WEBHOOK_SECRET=whsec_your_live_webhook_secret
```

### Step 6: Apple Pay Domain Verification
1. Go to Stripe Dashboard > Settings > Payment Methods > Apple Pay
2. Download the domain verification file
3. Host it at: `https://your-domain.com/.well-known/apple-developer-merchantid-domain-association`
4. Click "Verify"
5. Set in .env:
```env
APPLE_PAY_DOMAIN=your-domain.com
```

### Step 7: Google Pay Merchant ID
1. Go to https://pay.google.com/business/console/
2. Register as a merchant
3. Get your Merchant ID
4. Set in .env:
```env
GOOGLE_PAY_MERCHANT_ID=your_merchant_id
GOOGLE_PAY_ENVIRONMENT=PRODUCTION
```

---

## 4. Duffel GDS — Production Key

### Step 1: Create Duffel Account
1. Go to https://app.duffel.com/
2. Sign up with business email
3. Complete business verification

### Step 2: Get API Token
1. Go to Developers > Access Tokens
2. Create a new token:
   - For sandbox: prefix will be `duffel_test_...`
   - For production: prefix will be `duffel_live_...`

### Step 3: .env Configuration
```env
# Sandbox (test data, no real bookings)
DUFFEL_API_KEY=duffel_test_your_test_key
DUFFEL_ENV=sandbox

# Production (real flights, real bookings)
DUFFEL_API_KEY=duffel_live_your_live_key
DUFFEL_ENV=production
```

---

## Startup Logs

After configuring, restart the server and check logs:

```
[DUFFEL] Mode: PRODUCTION (real flights)
[PAYMENTS] MTN MoMo: SANDBOX
[PAYMENTS] Moov Money: MOCK
[PAYMENTS] Stripe: TEST
[WHATSAPP] Configured
[WEBHOOK] Signature verification: ACTIVE
```

All modes switch automatically based on .env — no code changes needed.
