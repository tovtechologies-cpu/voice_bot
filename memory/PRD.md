# Travelio PRD - WhatsApp Travel Booking Agent

## Original Problem Statement
Build Travelio as a **WhatsApp-only conversational agent** for West African travelers.
The entire user journey happens inside WhatsApp - NO browser interface.

## Architecture v3.0
- **Backend**: FastAPI webhook receiver
- **AI**: Claude Sonnet 4.5 via emergentintegrations
- **Flights**: AviationStack API (fallback to mock)
- **Payments**: MTN MoMo Sandbox (fallback to simulation)
- **Tickets**: PDF with QR code via reportlab
- **Interface**: WhatsApp Cloud API (sole interface)

## User Flow (All in WhatsApp)
1. User sends voice/text message to WhatsApp number
2. AI parses travel intent (destination, dates, budget, passengers)
3. Agent replies with 3 flight options (ECO/FAST/PREMIUM)
4. User replies "1", "2", or "3" to select
5. Agent asks for payment confirmation
6. User replies "OUI" / "YES"
7. MoMo payment initiated, user approves on phone
8. Agent sends confirmation + PDF ticket in same chat

## Conversation States
- `idle` - Waiting for travel request
- `awaiting_flight_selection` - Showing flight options
- `awaiting_payment_confirmation` - Asking to confirm booking
- `awaiting_momo_approval` - Waiting for MoMo payment

## What's Been Implemented
### April 2026
- [x] WhatsApp webhook receiver (GET verify + POST messages)
- [x] Session management (MongoDB)
- [x] Claude Sonnet 4.5 intent parsing
- [x] Mock flight search with 3 tiers
- [x] MTN MoMo payment initiation + polling
- [x] PDF ticket generation with QR code
- [x] WhatsApp message sending (text + document)
- [x] Bilingual support (French default, English)
- [x] Graceful fallbacks for all integrations
- [x] Status page showing webhook setup info

## P0 Features (Critical)
- [x] Receive WhatsApp messages via webhook
- [x] AI intent parsing
- [x] Flight search and display
- [x] MoMo payment flow
- [x] PDF ticket generation
- [x] Send ticket via WhatsApp

## P1 Features (Next)
- [ ] Voice message transcription (Whisper API)
- [ ] Real AviationStack integration
- [ ] Real MoMo integration
- [ ] Real WhatsApp Cloud API connection
- [ ] Passenger name collection

## P2 Features (Future)
- [ ] Multi-passenger booking
- [ ] Return flights in same booking
- [ ] Trip reminders
- [ ] Booking modification
- [ ] Refund handling

## Environment Variables
```
EMERGENT_LLM_KEY=      # Claude Sonnet 4.5
AVIATIONSTACK_API_KEY= # Live flight data
MOMO_SUBSCRIPTION_KEY= # MoMo payments
MOMO_API_USER=
MOMO_API_KEY=
WHATSAPP_PHONE_ID=     # WhatsApp Cloud API
WHATSAPP_TOKEN=
WHATSAPP_VERIFY_TOKEN=travelio_verify_2024
```

## Next Steps
1. Configure WhatsApp Cloud API in Meta Developer Console
2. Set webhook URL: https://your-app/api/webhook
3. Get AviationStack API key for live flights
4. Set up MoMo Sandbox for real payments
5. Add voice message transcription support
