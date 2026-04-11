# WhatsApp Business API Setup Guide

## Prerequisites
- A Meta Business Account (business.facebook.com)
- A Facebook Developer account (developers.facebook.com)
- A phone number that is NOT currently registered with WhatsApp

---

## Step 1: Create a Meta App

1. Go to https://developers.facebook.com/apps/
2. Click "Create App"
3. Choose "Business" type
4. Fill in app name: "Travelioo" (or your preferred name)
5. Select your Meta Business Account
6. Click "Create App"

---

## Step 2: Add WhatsApp Product

1. In your app dashboard, click "Add Product"
2. Find "WhatsApp" and click "Set Up"
3. You'll be redirected to the WhatsApp section

---

## Step 3: Get Your Phone Number ID

1. Go to WhatsApp > Getting Started
2. Under "Send and receive messages", you'll see a test phone number
3. To use your own number:
   a. Go to WhatsApp > Getting Started > "Add phone number"
   b. Enter your business phone number
   c. Verify via SMS or voice call
   d. Your **Phone Number ID** will appear below the number
4. Copy the Phone Number ID

```
WHATSAPP_PHONE_ID=your_phone_number_id_here
```

---

## Step 4: Generate a Permanent System Token

**Temporary tokens expire in 24 hours. For production, create a System User token:**

1. Go to https://business.facebook.com/settings/system-users
2. Click "Add" to create a new system user
3. Name: "Travelioo Bot"
4. Role: Admin
5. Click "Generate Token"
6. Select your app ("Travelioo")
7. Add these permissions:
   - `whatsapp_business_management`
   - `whatsapp_business_messaging`
8. Click "Generate Token"
9. **Copy the token immediately** (it won't be shown again)

```
WHATSAPP_TOKEN=your_permanent_system_token
```

---

## Step 5: Register Webhook in Meta Console

1. Go to your app > WhatsApp > Configuration
2. Under "Webhook", click "Edit"
3. Set:
   - **Callback URL:** `https://your-domain.com/api/webhook`
   - **Verify Token:** `travelioo_verify_2024` (or your custom token from .env)
4. Click "Verify and Save"
5. Meta will send a GET request to your webhook URL with the verify token
6. Your server must respond with the `hub.challenge` value

---

## Step 6: Subscribe to Webhook Fields

After webhook verification:

1. Under "Webhook fields", click "Manage"
2. Subscribe to:
   - **messages** (required — incoming user messages)
   - **message_deliveries** (optional — delivery receipts)
   - **message_reads** (optional — read receipts)
   - **messaging_postbacks** (optional — button callbacks)
3. Click "Done"

---

## Step 7: Set Up Webhook Signature Verification

Generate a webhook secret for signature verification:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Add to your `.env`:
```
WHATSAPP_WEBHOOK_SECRET=your_generated_secret
```

The App Secret is found at:
- Your App > Settings > Basic > App Secret

**Note:** WhatsApp uses your App Secret to sign webhook payloads with `X-Hub-Signature-256`. Set `WHATSAPP_WEBHOOK_SECRET` to your App Secret value.

---

## Step 8: Register Message Templates (Optional)

For proactive messaging (e.g., 24h reminders), register these templates:

### Template 1: Booking Confirmation
- **Name:** `booking_confirmation`
- **Language:** French
- **Category:** Transactional
- **Body:**
  ```
  Votre reservation Travelioo {{1}} est confirmee.
  Vol: {{2}} -> {{3}}
  Date: {{4}}
  Bon voyage !
  ```

### Template 2: Payment Reminder
- **Name:** `payment_reminder`
- **Language:** French
- **Category:** Transactional
- **Body:**
  ```
  Rappel : votre paiement pour le vol {{1}} -> {{2}} est en attente.
  Montant: {{3}}EUR
  Finalisez votre reservation sur Travelioo.
  ```

### Template 3: Flight Reminder (24h)
- **Name:** `flight_reminder_24h`
- **Language:** French
- **Category:** Transactional
- **Body:**
  ```
  Rappel : votre vol {{1}} decolle demain !
  {{2}} -> {{3}}
  Depart: {{4}}
  Reference: {{5}}
  Bon voyage !
  ```

### Template 4: Refund Notification
- **Name:** `refund_notification`
- **Language:** French
- **Category:** Transactional
- **Body:**
  ```
  Votre remboursement de {{1}}EUR a ete traite.
  Reference: {{2}}
  Delai: 3 a 10 jours ouvres.
  ```

Submit templates at: WhatsApp > Message Templates > Create Template

---

## Step 9: Verify End-to-End Setup

### Test webhook verification:
```bash
curl "https://your-domain.com/api/webhook?hub.mode=subscribe&hub.verify_token=travelioo_verify_2024&hub.challenge=test123"
# Expected: test123
```

### Test sending a message (from Meta test console):
1. Go to WhatsApp > Getting Started
2. Select your phone number
3. Add a test recipient phone number
4. Send a test message
5. Check your server logs for the incoming webhook

### Test the full flow:
1. Send "Bonjour" to your WhatsApp business number
2. You should receive the enrollment/consent message
3. Follow the booking flow

---

## Environment Variables Summary

```env
WHATSAPP_PHONE_ID=your_phone_number_id
WHATSAPP_TOKEN=your_permanent_system_token
WHATSAPP_VERIFY_TOKEN=travelioo_verify_2024
WHATSAPP_WEBHOOK_SECRET=your_app_secret
```

---

## Troubleshooting

| Issue | Solution |
|-------|---------|
| Webhook verification fails | Check WHATSAPP_VERIFY_TOKEN matches Meta console |
| Messages not received | Verify "messages" webhook field is subscribed |
| 403 errors on webhook | Check WHATSAPP_WEBHOOK_SECRET matches App Secret |
| Token expired | Use System User token (permanent), not temporary test token |
| Rate limited | WhatsApp Business API: 80 messages/second (Tier 1) |
