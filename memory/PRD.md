# Travelio PRD - WhatsApp Travel Booking Agent v6.0

## Problem Statement
Travelio is a WhatsApp-only conversational agent for booking flights.
No web frontend — only a status page. Entire journey happens inside WhatsApp.

## Architecture
- **Backend**: FastAPI webhook (server.py)
- **AI**: Claude Sonnet 4.5 (intent parsing), OpenAI Whisper (voice)
- **Flights**: Amadeus Flight Offers Search API
- **Payment**: MTN MoMo, Moov Money, Google Pay, Apple Pay (Stripe)
- **OCR**: pytesseract (default) / Google Vision API (optional)
- **Frontend**: React status dashboard only

## Travelio Fee Policy
- 15€ flat fee: NON-REFUNDABLE in all cases
- 5% margin: included in final price

## Fare Condition Profiles (Sandbox)
| Profile | Refundable | Penalty | Changeable | Change Fee | Deadline |
|---------|-----------|---------|------------|------------|----------|
| Budget | NO | N/A | NO | N/A | N/A |
| Standard | PARTIAL | 80€ | YES | 50€ | 48h before |
| Flex | YES | 0€ | YES | 0€ | 2h before |

## Conversation States (Complete)
### Enrollment
- IDLE, ENROLLMENT_METHOD, ENROLLING_SCAN, ENROLLING_MANUAL_FN/LN/PP
- CONFIRMING_PROFILE, ASKING_TRAVEL_PURPOSE, SELECTING_THIRD_PARTY
- ENROLLING_THIRD_PARTY_METHOD, ENROLLING_TP_SCAN/MANUAL_FN/LN/PP
- CONFIRMING_TP_PROFILE, SAVE_TP_PROMPT, ASKING_PASSENGER_COUNT

### Booking
- AWAITING_DESTINATION, AWAITING_DATE, AWAITING_FLIGHT_SELECTION
- AWAITING_PAYMENT_METHOD, AWAITING_PAYMENT_CONFIRM (pre-debit)
- AWAITING_MOBILE_PAYMENT, AWAITING_CARD_PAYMENT

### Post-booking
- CANCELLATION_IDENTIFY, CANCELLATION_CONFIRM, CANCELLATION_PROCESSING
- REFUND_FAILED, MODIFICATION_REQUESTED, MODIFICATION_CONFIRM

## What's Implemented (v6.0 — April 2026)
- [x] WhatsApp webhook (text, audio, image)
- [x] Claude AI intent parsing + Whisper voice transcription
- [x] Amadeus flight search + categorization (3 categories)
- [x] Travelio pricing margin + EUR/XOF display
- [x] Passenger enrollment (manual + OCR)
- [x] Profile detection (new vs returning user)
- [x] Third-party booking with saved passengers (max 5)
- [x] Multi-passenger stub
- [x] Session timeout (30 min)
- [x] Pre-debit confirmation with fare conditions display
- [x] Payment method selection (4 operators)
- [x] Payment countdown messages (10s, 20s, 30s timeout)
- [x] Rich payment confirmed message (masked phone, GMT+1 timestamp)
- [x] Fare conditions (3 mock profiles, Claude summarization ready)
- [x] Cancellation flow (4 cases: non-refundable, partial, full, deadline)
- [x] Refund processing (simulated MoMo/Moov/Stripe)
- [x] Refund failure → manual escalation queue
- [x] Ticket invalidation (cancelled_bookings + QR verification)
- [x] Modification flow (allowed/not-allowed detection)
- [x] QR verification endpoint (VALID/INVALID/UNKNOWN)
- [x] Frontend status dashboard with per-operator health

## API Endpoints
- `GET/POST /api/webhook` - WhatsApp messages
- `GET /api/verify/{booking_ref}` - QR ticket verification
- `GET /api/pay/{booking_ref}` - Stripe payment page
- `GET /api/health` - Health + operator status
- `GET /api/tickets/{filename}` - PDF download
- `POST /api/momo/callback` - MoMo callback
- `POST /api/moov/callback` - Moov callback
- `POST /api/stripe/webhook` - Stripe callback
- `POST /api/test/message` - Test simulation
- `POST /api/test/transcribe` - Test audio

## Database Collections
- `sessions` - Conversation state per phone
- `passengers` - Passenger profiles
- `bookings` - Flight bookings with fare conditions
- `cancelled_bookings` - Invalidated ticket references
- `refund_queue` - Failed refunds for manual processing

## Backlog
1. Configure WhatsApp Business API (External)
2. Stripe Domain Verification for Apple Pay
3. Production Amadeus/MoMo/Moov/Stripe credentials
4. Celtiis Cash payment
5. Return flight booking
6. Full multi-passenger support
7. Real Amadeus fare condition retrieval
