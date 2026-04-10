# Travelio PRD - WhatsApp Travel Booking Agent v5.0

## Problem Statement
Build Travelio as a WhatsApp-only conversational agent for booking flights.
No web frontend. Entire journey happens inside WhatsApp.

## Architecture
- **Backend**: FastAPI webhook receiver (server.py)
- **AI**: Claude Sonnet 4.5 (intent parsing via Emergent LLM Key)
- **Flights**: Amadeus Flight Offers Search API
- **Pricing**: Travelio margin on all Amadeus prices
- **Payment**: MTN MoMo, Moov Money, Google Pay, Apple Pay (via Stripe)
- **Voice**: OpenAI Whisper (via Emergent LLM Key) with .ogg→.mp3 conversion
- **Delivery**: PDF ticket + QR code via WhatsApp
- **Frontend**: React status dashboard only (no consumer UX)

## Travelio Pricing Rule
```
final_price = amadeus_price + 15 + (amadeus_price * 0.05)
```
Display in EUR and XOF (1 EUR = 655.957 XOF fixed rate)

## Autonomous Flight Categorization
| Category | Logic | Label |
|----------|-------|-------|
| PLUS_BAS | Lowest final_price | LE PLUS BAS |
| PLUS_RAPIDE | Shortest duration | LE PLUS RAPIDE |
| PREMIUM | Highest score | PREMIUM |

**PREMIUM Score Formula:**
```
score = (1/price * 0.4) + (1/duration * 0.4) + (direct_bonus * 0.2)
direct_bonus = 1.0 if direct, 0.5 if 1 stop, 0 if 2+ stops
```

## Conversation States
1. `idle` → Travel request
2. `awaiting_destination` → Missing destination
3. `awaiting_date` → Missing date
4. `awaiting_flight_selection` → Show 3 options
5. `awaiting_payment_method` → Show 4 payment options
6. `awaiting_mobile_payment` → MoMo/Moov polling
7. `awaiting_card_payment` → Stripe payment link sent
8. `retry` → Payment failed, retry/change/cancel

## Payment Methods
1. MTN MoMo - Mobile money (XOF)
2. Moov Money (Flooz) - Mobile money (XOF)
3. Google Pay - via Stripe PaymentIntent
4. Apple Pay - via Stripe PaymentIntent

## What's Implemented (April 2026)
- [x] WhatsApp webhook receiver (GET verify + POST messages)
- [x] Claude Sonnet 4.5 intent parsing
- [x] Amadeus Flight Offers API integration
- [x] Autonomous flight categorization (3 categories)
- [x] Travelio pricing margin
- [x] EUR/XOF dual currency display
- [x] MTN MoMo payment flow with polling
- [x] Moov Money payment flow with polling
- [x] Google Pay via Stripe PaymentIntent
- [x] Apple Pay via Stripe PaymentIntent
- [x] PaymentService abstraction (unified 4-operator handler)
- [x] Payment retry/change/cancel flow
- [x] PDF ticket generation with QR code
- [x] Whisper voice transcription (.ogg → .mp3 auto-conversion)
- [x] French/English language detection
- [x] Frontend status dashboard with per-operator health indicators
- [x] Bilingual WhatsApp message templates
- [x] Session state management (MongoDB)
- [x] Graceful fallbacks for all APIs

## API Endpoints
- `GET /api/webhook` - WhatsApp verification
- `POST /api/webhook` - WhatsApp incoming messages
- `POST /api/momo/callback` - MoMo payment callback
- `POST /api/moov/callback` - Moov payment callback
- `POST /api/stripe/webhook` - Stripe payment webhook
- `GET /api/pay/{booking_ref}` - Stripe payment page
- `GET /api/health` - Detailed health with per-operator status
- `GET /api/tickets/{filename}` - PDF ticket download
- `POST /api/test/message` - Test message simulation
- `POST /api/test/transcribe` - Test audio transcription
- `GET /api/test/flights` - Test flight search

## Environment Variables
```
EMERGENT_LLM_KEY=         # Claude + Whisper
AMADEUS_API_KEY=          # Amadeus API
AMADEUS_API_SECRET=       # Amadeus Secret
MOMO_SUBSCRIPTION_KEY=    # MoMo payments
MOMO_API_USER=            # MoMo user
MOMO_API_KEY=             # MoMo key
MOOV_API_KEY=             # Moov payments
STRIPE_SECRET_KEY=        # Stripe (Google/Apple Pay)
STRIPE_PUBLISHABLE_KEY=   # Stripe frontend
STRIPE_WEBHOOK_SECRET=    # Stripe webhooks
WHATSAPP_PHONE_ID=        # WhatsApp Cloud API
WHATSAPP_TOKEN=           # WhatsApp token
```

## Next Steps (Backlog)
1. Configure WhatsApp Business API in Meta Developer Console (External)
2. Stripe Domain Verification for Apple Pay (External)
3. Implement Celtiis Cash payment (pending partner agreement)
4. Return flight booking
5. Passenger name collection
6. Get Amadeus production credentials
7. Set up MTN MoMo/Moov Money production credentials
