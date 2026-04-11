# Travelioo PRD - WhatsApp Travel Booking Agent

## Original Problem Statement
Voice-first WhatsApp conversational agent for travel booking (Travelioo), targeting Benin/West Africa.
Users interact exclusively via WhatsApp to search, book, and pay for flights.

## Architecture
- Backend: FastAPI (Python), modular structure (services/, conversation/, routes/, utils/)
- Database: MongoDB (Motor async driver), database name: `travelioo`
- Frontend: React (admin status dashboard only, not user-facing)
- AI: Claude Sonnet 4.5 (intent parsing), OpenAI Whisper (voice transcription)
- GDS: Duffel API (sandbox/mock mode)
- Payments: MTN MoMo, Moov Money, Stripe (Google Pay/Apple Pay) — all simulated
- Security: AES-256-GCM encryption, rate limiting, webhook signature verification

## What's Been Implemented

### v7.0 (Initial modular release)
- Complete monolith-to-modular refactoring (server.py 3600+ lines → 85 lines)
- Duffel API migration from Amadeus (sandbox fallback)
- AES-256-GCM encryption for PII (passport, DOB, expiry)
- Rate limiting (messages, payments, enrollment)
- Legal endpoints (/legal/terms, /legal/privacy)
- Airport recognition with RapidFuzz fuzzy matching
- Natural language date parsing with dateparser
- Full conversation state machine (32 states)
- 4 payment operators with simulation
- PDF ticket generation with QR code
- Cancellation with 4 fare condition cases
- Third-party passenger management (up to 5 profiles)
- Frontend status dashboard

### v7.1 (Security & compliance update)
- Webhook signature verification (X-Hub-Signature-256 / HMAC-SHA256)
- Duffel environment-aware mode switching (PRODUCTION/SANDBOX/MOCK)
- Payment gateway environment-aware detection
- Enhanced health endpoint with webhook_security and environment_modes
- GDPR consent flow (AWAITING_CONSENT state)
- Modification flow fix (cancels original booking before rebooking)
- QR code passport removal
- Setup documentation: SETUP_WHATSAPP.md, SETUP_PAYMENTS.md, .env.example

### v7.1.1 (Rename — Feb 2026)
- Complete rename from Travelio → Travelioo across all 30+ files
- Database migrated: travelio → travelioo
- 3 test files renamed
- Webhook verify token: travelioo_verify_2024
- Zero regressions confirmed (100% test pass rate)

## Prioritized Backlog

### P0 (Before production)
- Configure real WhatsApp Business API (external Meta Console)
- Replace Duffel sandbox key with real production key
- Configure at least one real payment gateway

### P1
- 24h flight reminder (scheduled notifications)
- Round-trip flight support
- Cabin class selection
- Booking history view ("show my bookings" command)
- Language switching mid-conversation
- Profile editing and deletion

### P2
- Celtiis Cash payment integration
- Multi-passenger booking
- XOF primary currency display for Benin users
- Whisper correction dictionary
- Caching for airport resolution and AI responses
- Circuit breaker for external API calls
