# Travelio PRD - WhatsApp Travel Booking Agent v4.0

## Problem Statement
Build Travelio as a WhatsApp-only conversational agent for booking flights.
No web frontend. Entire journey happens inside WhatsApp.

## Architecture
- **Backend**: FastAPI webhook receiver
- **AI**: Claude Sonnet 4.5 (intent parsing)
- **Flights**: Amadeus Flight Offers Search API
- **Pricing**: Travelio margin on all Amadeus prices
- **Payment**: MTN MoMo Sandbox
- **Delivery**: PDF ticket + QR code via WhatsApp

## Travelio Pricing Rule
```
final_price = amadeus_price + 15 + (amadeus_price * 0.05)
```
Display in EUR and XOF (1 EUR = 655.957 XOF fixed rate)

## Autonomous Flight Categorization
| Category | Logic | Label |
|----------|-------|-------|
| PLUS_BAS | Lowest final_price | 💚 LE PLUS BAS |
| PLUS_RAPIDE | Shortest duration | ⚡ LE PLUS RAPIDE |
| PREMIUM | Highest score | 👑 PREMIUM |

**PREMIUM Score Formula:**
```
score = (1/price * 0.4) + (1/duration * 0.4) + (direct_bonus * 0.2)
direct_bonus = 1.0 if direct, 0.5 if 1 stop, 0 if 2+ stops
```

## WhatsApp Message Format
```
✈️ *Travelio — 3 options trouvées*
{origin} → {destination} | {date}

━━━━━━━━━━━━━━━━━━━━
💚 *LE PLUS BAS*
{airline} | {stops}
Durée : {duration}
Prix : *{price}€* ({price_xof} XOF)
Taper *1* pour sélectionner
...
━━━━━━━━━━━━━━━━━━━━
Répondez 1, 2 ou 3 pour continuer.
```

## Conversation States
1. `idle` → Travel request
2. `awaiting_destination` → Missing destination
3. `awaiting_date` → Missing date
4. `awaiting_flight_selection` → Show 3 options
5. `awaiting_payment_confirmation` → Confirm selected flight
6. `awaiting_momo_approval` → Payment polling

## What's Implemented (April 2026)
- [x] WhatsApp webhook receiver (GET verify + POST messages)
- [x] Claude Sonnet 4.5 intent parsing
- [x] Amadeus Flight Offers API integration
- [x] Autonomous flight categorization (3 categories)
- [x] Travelio pricing margin
- [x] EUR/XOF dual currency display
- [x] MTN MoMo payment flow with polling
- [x] PDF ticket generation with QR code
- [x] Bilingual support (FR/EN)
- [x] Graceful fallbacks for all APIs
- [x] Session state management

## Environment Variables
```
EMERGENT_LLM_KEY=         # Claude Sonnet 4.5
AMADEUS_API_KEY=          # Amadeus API
AMADEUS_API_SECRET=       # Amadeus Secret
OPENAI_API_KEY=           # Whisper transcription
MOMO_SUBSCRIPTION_KEY=    # MoMo payments
WHATSAPP_PHONE_ID=        # WhatsApp Cloud API
WHATSAPP_TOKEN=           # WhatsApp token
```

## Next Steps
1. Configure WhatsApp Business API in Meta Developer Console
2. Get Amadeus production API credentials
3. Set up MTN MoMo production credentials
4. Add voice message transcription (Whisper)
5. Implement return flight booking
6. Add passenger name collection
