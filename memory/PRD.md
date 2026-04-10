# Travelio PRD - WhatsApp Travel Booking Agent v5.1

## Problem Statement
Travelio is a WhatsApp-only conversational agent for booking flights.
No web frontend — only a status page. Entire journey happens inside WhatsApp.

## Architecture
- **Backend**: FastAPI webhook receiver (server.py)
- **AI**: Claude Sonnet 4.5 (intent parsing via Emergent LLM Key)
- **Flights**: Amadeus Flight Offers Search API
- **Payment**: MTN MoMo, Moov Money, Google Pay, Apple Pay (via Stripe)
- **Voice**: OpenAI Whisper (via Emergent LLM Key) with .ogg→.mp3 conversion
- **OCR**: pytesseract (default) / Google Vision API (optional)
- **Delivery**: PDF ticket + QR code via WhatsApp
- **Frontend**: React status dashboard only

## Conversation Flow (Updated)

### New User
1. First message → Welcome + enrollment method selection
2. Enrollment (scan/photo/manual) → 3 steps for manual
3. Profile confirmation + save to DB
4. "Pour vous ou pour un tiers?"
5. Multi-passenger count (stub: 1 only)
6. Travel intent (destination, date)
7. Flight search → 3 options (cheapest, fastest, premium)
8. Flight selection
9. Payment method selection (4 operators)
10. Payment processing
11. Ticket generated with passenger data + sent via WhatsApp

### Returning User
1. Message → profile found → "Pour moi / Pour un tiers"
2. Skip enrollment, go directly to step 5+

## Enrollment Methods
1. **Passport scan/photo**: Image → OCR (pytesseract/Vision) → MRZ parsing
2. **Manual entry**: First name → Last name → Passport # (optional)

## Passenger Schema (MongoDB: passengers)
- id, whatsapp_phone (unique), firstName, lastName
- passportNumber (nullable), nationality, dateOfBirth, expiryDate
- created_by_phone, createdAt, updatedAt

## Third-Party Booking
- Returning users can book for saved third parties (max 5 per phone)
- New third parties go through full enrollment
- Save/discard option after enrollment

## Pricing Rule
final_price = amadeus_price + 15€ + 5%
Display in EUR and XOF (1€ = 655.957 XOF)

## What's Implemented
- [x] WhatsApp webhook (GET verify + POST messages + images)
- [x] Claude Sonnet 4.5 intent parsing
- [x] Amadeus Flight Offers API
- [x] Flight categorization (PLUS_BAS, PLUS_RAPIDE, PREMIUM)
- [x] Travelio pricing margin + EUR/XOF display
- [x] MTN MoMo, Moov Money, Google Pay, Apple Pay payments
- [x] PaymentService abstraction + retry/cancel flow
- [x] PDF ticket with QR code + passenger data
- [x] Whisper voice transcription (.ogg auto-conversion)
- [x] French/English bilingual support
- [x] **Passenger enrollment (manual + OCR)**
- [x] **Profile detection (new vs returning user)**
- [x] **Third-party booking with saved passengers**
- [x] **Multi-passenger stub**
- [x] **Session timeout (30 min)**
- [x] **Input validation (name regex, passport format)**
- [x] Frontend status dashboard with per-operator health

## API Endpoints
- `GET/POST /api/webhook` - WhatsApp
- `POST /api/momo/callback` - MoMo callback
- `POST /api/moov/callback` - Moov callback
- `POST /api/stripe/webhook` - Stripe callback
- `GET /api/pay/{booking_ref}` - Stripe payment page
- `GET /api/health` - Health + operator status
- `GET /api/tickets/{filename}` - PDF download
- `POST /api/test/message` - Test simulation
- `POST /api/test/transcribe` - Test audio

## Backlog
1. Configure WhatsApp Business API (External)
2. Stripe Domain Verification for Apple Pay (External)
3. Celtiis Cash payment (pending)
4. Return flight booking
5. Passenger name collection improvements
6. Production Amadeus/MoMo/Moov credentials
7. Actual multi-passenger support
