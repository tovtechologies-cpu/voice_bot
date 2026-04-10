# Travelio PRD - WhatsApp Travel Booking Agent

## Original Problem Statement
A WhatsApp conversational travel booking agent for Benin/West Africa. Users interact via WhatsApp to search flights, enroll passengers, book tickets, pay (MoMo/Moov/Stripe), and manage cancellations/refunds.

## Architecture (v7.0 - Modular)
```
/app/backend/
├── server.py (85 lines - slim FastAPI entry point)
├── config.py (All env vars, constants, airport codes)
├── database.py (MongoDB connection)
├── models.py (ConversationState, fare profiles)
├── services/
│   ├── security.py (AES-256-GCM encryption, rate limiting, velocity checks)
│   ├── flight.py (Duffel GDS + sandbox mock)
│   ├── airport.py (Fuzzy airport recognition with rapidfuzz)
│   ├── date_parser.py (Natural language date parsing with dateparser)
│   ├── payment.py (MTN MoMo, Moov, Stripe)
│   ├── ai.py (Claude intent parsing)
│   ├── whatsapp.py (WhatsApp messaging + chunking)
│   ├── passport.py (OCR via pytesseract)
│   ├── whisper.py (Audio transcription)
│   ├── ticket.py (PDF generation with QR)
│   └── session.py (Session + passenger CRUD)
├── conversation/
│   ├── handler.py (Main message dispatcher)
│   ├── enrollment.py (User enrollment flows)
│   ├── booking.py (Destination, date, flight, payment)
│   ├── cancellation.py (Cancel/refund)
│   └── modification.py (Modify booking)
├── routes/
│   ├── webhook.py (WhatsApp webhook)
│   ├── payments.py (Payment callbacks + page)
│   ├── legal.py (Terms of Service, Privacy Policy)
│   ├── health.py (Health + root)
│   └── test.py (Test simulation)
└── utils/
    ├── formatting.py (Message formatting)
    └── helpers.py (Booking ref, phone masking)
```

## What's Been Implemented

### v7.0 (Feb 2026) - Major Refactoring + New Features
- Refactored monolithic server.py (3632 lines) into 20+ modular files (85 lines)
- Migrated GDS from Amadeus to Duffel (sandbox mock with auto-detection)
- AES-256-GCM encryption for passenger PII (passport, DOB, expiry) at rest and in transit
- Rate limiting (30 msg/min, 5 payments/5min, 10 enrollments/10min)
- Payment velocity checks (max 3/hour)
- Fuzzy airport recognition with rapidfuzz (handles misspellings)
- Natural language date parsing with dateparser (French + English)
- Legal endpoints: GET /api/legal/terms, GET /api/legal/privacy
- Message chunking for >900 char WhatsApp messages
- Data retention cron (auto-purge old sessions)
- Frontend updated: Amadeus → Duffel GDS

### v6.0 - Refund & Cancellation
- Full cancellation flow with fare condition verification
- Pre-debit confirmation showing refund breakdown
- Automated refund processing with fallback queue
- Refund failed -> manual processing workflow

### v5.0 - Passenger Enrollment
- Passport OCR (pytesseract + Google Vision)
- Manual entry with validation
- Third-party passenger management (max 5)
- Profile confirmation flow

### v4.0 - Multi-Gateway Payment
- MTN MoMo, Moov Money, Google Pay, Apple Pay
- Payment polling with timeout
- Retry and method-switch flows
- PDF ticket generation with QR

### v3.0 - Core
- WhatsApp webhook integration
- Claude AI intent parsing
- OpenAI Whisper voice transcription
- Flight search and categorization (3 options)
- MongoDB session state machine

## API Endpoints
- POST /api/webhook (WhatsApp incoming)
- GET /api/webhook (WhatsApp verification)
- POST /api/test/simulate (Test simulation)
- GET /api/health (Health check)
- GET /api/ (Root info)
- GET /api/legal/terms (Terms of Service)
- GET /api/legal/privacy (Privacy Policy)
- POST /api/momo/callback, /api/moov/callback, /api/stripe/webhook
- GET /api/pay/{booking_id} (Payment page)
- GET /api/tickets/{filename} (PDF download)
- GET /api/verify_qr/{booking_ref} (QR verification)

## Prioritized Backlog
### P0 (Done)
- ✅ Duffel GDS Migration (sandbox)
- ✅ Security & Encryption (AES-256-GCM)
- ✅ Airport Recognition (rapidfuzz)
- ✅ Date Picker (dateparser)
- ✅ Legal Endpoints (ToS, Privacy)
- ✅ UX (chunking, rate limiting)
- ✅ Refactoring (modular architecture)

### P1 (Remaining)
- Natural language yes/no parsing improvements
- Background message queue for heavy operations
- XOF currency priority for Benin +229

### P2 (Future)
- Configure real WhatsApp Business API in Meta Developer Console
- Implement Celtiis Cash payment
- Full multi-passenger booking
- Production Duffel API key
- Production MoMo/Moov/Stripe credentials
- Replace Duffel sandbox mock with real API when key provided
