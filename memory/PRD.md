# Travelio PRD - Voice-First Travel Booking App

## Original Problem Statement
Build a voice-first travel booking web app called Travelio for West African users. User speaks one sentence about travel plans and the app handles: AI intent parsing, flight search, selection, payment, and ticket delivery.

## Architecture
- **Frontend**: React with Tailwind CSS, Shadcn UI components
- **Backend**: FastAPI with MongoDB
- **AI**: Claude Sonnet 4.5 via emergentintegrations (intent parsing)
- **Integrations**: All mocked (MTN MoMo, Google Pay, Apple Pay, WhatsApp, AviationStack)

## User Personas
1. **Frequent Traveler (Amadou)**: Business traveler in Dakar who needs quick booking in French
2. **Diaspora Visitor (Marie)**: English-speaking user visiting family in West Africa
3. **First-time User (Oumar)**: Low-tech comfort, needs simple voice interface

## Core Requirements (Static)
- Voice input via Web Speech API
- Bilingual UI (French default, English)
- AI intent parsing for travel details
- 3 flight options (ECO/FAST/PREMIUM)
- Payment via MTN MoMo (primary), Google Pay, Apple Pay
- PDF ticket with QR code
- WhatsApp ticket delivery
- User profile (manual + JSON upload)
- Booking history
- Mobile-first responsive design

## What's Been Implemented
### January 2026
- [x] Full-stack app setup (React + FastAPI + MongoDB)
- [x] Voice input with Web Speech API
- [x] Bilingual UI (FR/EN) with language toggle
- [x] AI intent parsing with Claude Sonnet 4.5
- [x] Intent badges (only show when values assigned)
- [x] Mock flight search with 3 tiers
- [x] Payment modal with MoMo/GPay/APay
- [x] Booking confirmation with QR code
- [x] WhatsApp ticket delivery (simulated)
- [x] User profile page with JSON upload
- [x] Booking history page
- [x] Bottom navigation (mobile-first)
- [x] Premium dark theme with glassmorphism

## P0 Features (Critical)
- [x] Voice/text travel intent input
- [x] AI-powered intent parsing
- [x] Flight search and display
- [x] Payment processing
- [x] Booking confirmation

## P1 Features (High Priority)
- [x] Bilingual support
- [x] User profiles
- [x] Booking history
- [ ] Real flight API integration (AviationStack)
- [ ] Real MTN MoMo integration

## P2 Features (Nice to Have)
- [ ] Real WhatsApp Cloud API integration
- [ ] PDF ticket generation with actual QR code
- [ ] Push notifications
- [ ] Offline mode
- [ ] Multi-passenger booking

## Prioritized Backlog
1. Real AviationStack API integration
2. Real MTN MoMo Sandbox integration
3. Real WhatsApp Cloud API integration
4. Actual PDF generation with QR code
5. Email ticket delivery option
6. Calendar integration for trip reminders

## Next Tasks List
1. Integrate real flight APIs when keys provided
2. Connect MTN MoMo Sandbox when credentials available
3. Add actual PDF generation library (jsPDF)
4. Implement real WhatsApp messaging
5. Add trip notifications/reminders
