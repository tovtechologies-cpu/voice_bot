# Travelioo — Product Requirements Document

## Overview
Travelioo is a WhatsApp-based travel booking chatbot for the African market (primarily Benin). Users interact via WhatsApp (and soon Telegram) to search flights, enroll passengers, pay via local mobile money, and receive e-tickets.

## Tech Stack
- **Backend**: FastAPI + MongoDB + Motor (async)
- **AI**: Claude Sonnet 4.5 (via Emergent LLM Key), OpenAI Whisper (voice)
- **GDS**: Duffel API (sandbox)
- **Messaging**: Meta WhatsApp Cloud API
- **Payments**: Modular driver architecture (Celtiis Cash, MTN MoMo, Moov Money, Stripe)
- **Security**: AES-256-GCM encryption, webhook signature verification

## Architecture
```
/app/backend/
  server.py           — FastAPI app, lifespan, route mounting
  config.py           — Environment variables, constants
  models.py           — ConversationState, pricing, fare conditions
  database.py         — MongoDB connection
  payment_drivers/    — Modular payment driver architecture
    __init__.py       — BasePaymentDriver, PaymentResult
    router.py         — Geographic routing, menu builder
    celtiis_driver.py — Celtiis Cash (Benin priority)
    mtn_momo_driver.py— MTN MoMo (UEMOA)
    moov_driver.py    — Moov Money/Flooz
    stripe_driver.py  — Cards / Google Pay / Apple Pay
  services/           — Business logic services
    shadow_profile.py — Cross-channel user profiles
    whatsapp.py       — Meta WhatsApp Cloud API
    flight.py         — Duffel GDS integration
    security.py       — AES-256-GCM, rate limiting
    payment.py        — Legacy payment service (deprecated)
    ai.py, whisper.py, passport.py, ticket.py, etc.
  conversation/       — State machine handlers
    handler.py        — Main dispatcher
    booking.py        — Flight search, payment flow
    enrollment.py     — Passenger registration, OCR, consent
    cancellation.py   — Cancellation & refund
    modification.py   — Booking modification
  routes/             — API endpoints
    webhook.py, test.py, health.py, payments.py, legal.py
```

## Completed Features

### Foundation (v7.1)
- [x] WhatsApp conversation state machine (20+ states)
- [x] Manual + OCR passport enrollment
- [x] Flight search via Duffel GDS (sandbox)
- [x] E-ticket PDF generation
- [x] AES-256-GCM PII encryption
- [x] Rate limiting + payment velocity checks
- [x] Third-party passenger booking
- [x] Cancellation + refund with fare conditions
- [x] Booking modification flow

### Security & Compliance
- [x] Webhook signature verification (X-Hub-Signature-256)
- [x] GDPR/APDP consent flow
- [x] Data deletion (SUPPRIMER MES DONNEES)
- [x] Environment mode detection (production/sandbox/mock)
- [x] Input sanitization

### Meta WhatsApp Cloud API
- [x] Official webhook verification (GET /api/webhook)
- [x] Message normalization (text, audio, image)
- [x] Send text, document, and template messages
- [x] Error handling for token/auth failures

### Phase A Enterprise Grade (Completed 2026-04-15)
- [x] **Shadow Profiles**: Cross-channel user profiles created on consent, updated with travel_history and payment_methods after each booking
- [x] **Dynamic Pricing**: Tiered Travelioo fee grid (<200 EUR = 10 EUR flat, 200-500 EUR = 8%, >500 EUR = 6%). Fee is non-refundable.
- [x] **Payment Drivers**: Modular architecture with geographic routing. Celtiis Cash is default for Benin (BJ). Drivers: Celtiis, MTN MoMo, Moov Money, Stripe. All currently in MOCK mode.
- [x] **Interactive OCR Rebound**: When passport scan is partial, missing fields are presented for interactive correction instead of hard fallback to manual entry.
- [x] Old dead payment polling code removed
- [x] Force-fail test mechanism works with new driver architecture

### Phase B Step 1 — Returning User Fast-Track (Completed 2026-04-15)
- [x] **Fast-Track Payment**: Returning users with prior payment history get a fast-track option instead of full payment menu
- [x] Accept (1) skips method selection, Decline (2) shows full menu
- [x] New state: `PAYMENT_FASTTRACK` in ConversationState

## Pending / Upcoming

### Phase B (P1) — Remaining
- [ ] **DUAL CHANNEL**: Telegram Bot API support (telegram_handler.py, /telegram/webhook)
- [ ] **MULTI-NUMBER SPLIT PAYMENT**: Payment split between 2+ numbers with 1,300 XOF reconciliation fee

### Phase C (P2)
- [ ] **MULTILINGUAL SUPPORT + HUMAN-IN-THE-LOOP**: African language translation, HITL trigger on low confidence
- [ ] **PROACTIVE SAV**: Flight disruption notifications (delay, cancellation, gate change)

## Known Issues
- WhatsApp Cloud API token is invalid (user to provide correct token from Meta Developer Console)
- All payment drivers are in MOCK mode (no real API keys configured)
- Duffel is in SANDBOX mode (test flight data)

## Testing
- Test via: POST /api/test/simulate with {phone, message}
- Health: GET /api/health
- Session: GET /api/test/session/{phone}
- Bookings: GET /api/test/bookings/{phone}
- Force-fail: POST /api/test/force_fail with {phone}
- Latest test report: /app/test_reports/iteration_10.json (23/23 passed)
