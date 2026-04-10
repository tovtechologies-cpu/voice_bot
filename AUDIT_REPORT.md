# TRAVELIO v7.0 — COMPLETE TECHNICAL & FUNCTIONAL AUDIT REPORT

**Report Date:** February 2026
**Auditor:** Automated Technical Audit (Exhaustive)
**Codebase:** `/app/backend/` (20+ modules), `/app/frontend/` (React dashboard)
**Last Test Run:** iteration_7.json — 100% pass rate

---

## 1. APPLICATION OVERVIEW

### Current Version
**v7.0** — Modular Architecture (February 2026)

### Architecture Summary
Travelio is a **voice-first WhatsApp conversational travel booking agent** targeting Benin / West Africa. The system is built as a **FastAPI monolith (now modularized)** that acts as a WhatsApp Cloud API webhook. Users interact exclusively via WhatsApp; there is no user-facing web application. The React frontend is a **status dashboard** for administrators only.

**Architecture pattern:** Event-driven state machine. Each incoming WhatsApp message triggers a handler that reads the user's current `ConversationState` from MongoDB, processes the message, updates the state, and sends a response back via WhatsApp Cloud API.

```
WhatsApp User --> Meta Cloud API --> POST /api/webhook --> handler.py (state machine)
                                                            |
                              MongoDB <--- session/state ---+--- services/* (AI, flights, payments, etc.)
                                                            |
                              WhatsApp <--- response -------+
```

**File structure (85-line server.py entrypoint):**
```
/app/backend/
  server.py (85 lines)     — FastAPI app, CORS, lifespan, route mounting
  config.py (107 lines)     — All env vars, constants, airport codes dict
  database.py (6 lines)     — Motor async MongoDB client
  models.py (128 lines)     — ConversationState enum, fare profiles, refund calculator
  services/ (11 modules)    — Business logic
  conversation/ (5 modules) — State machine handlers
  routes/ (5 modules)       — API endpoints
  utils/ (2 modules)        — Formatting, helpers
```

### Tech Stack (All Libraries and Versions)

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Runtime** | Python | 3.x | Backend |
| **Framework** | FastAPI | 0.110.1 | HTTP server |
| **ASGI Server** | Uvicorn | 0.25.0 | ASGI runner |
| **Database** | MongoDB via Motor | 3.3.1 (pymongo 4.5.0) | Async document store |
| **AI — Intent Parsing** | Claude Sonnet 4.5 via emergentintegrations | 0.1.0 | Travel intent extraction |
| **AI — Voice** | OpenAI Whisper via emergentintegrations | 0.1.0 | Audio transcription |
| **OCR** | Pytesseract | 0.3.13 | Passport MRZ reading |
| **Image Processing** | Pillow | 12.2.0 | Passport image preprocessing |
| **Audio** | Pydub | 0.25.1 | OGG to MP3 conversion |
| **GDS** | Duffel API (sandbox) | HTTP via httpx 0.28.1 | Flight search & booking |
| **Payments — Stripe** | stripe | 15.0.1 | Google/Apple Pay |
| **Payments — MoMo** | Custom HTTP (httpx) | — | MTN Mobile Money |
| **Payments — Moov** | Custom HTTP (httpx) | — | Moov Money (Flooz) |
| **Encryption** | cryptography (AES-256-GCM) | 46.0.7 | PII at rest |
| **Fuzzy Matching** | RapidFuzz | 3.14.5 | Airport name resolution |
| **Date NLP** | dateparser | 1.4.0 | Natural language date parsing |
| **PDF** | ReportLab | 4.4.10 | Ticket generation |
| **QR Code** | qrcode | 8.2 | Ticket QR codes |
| **Frontend** | React (CRA) | — | Admin status dashboard |
| **HTTP Client** | httpx | 0.28.1 | All outbound API calls |

### Deployment Status

| Aspect | Status |
|--------|--------|
| Backend (FastAPI) | ✅ Running on port 8001 via supervisor |
| Frontend (React) | ✅ Running on port 3000 via supervisor |
| MongoDB | ✅ Connected (localhost:27017, db: `travelio`) |
| Ingress | ✅ `https://voice-travel-booking.preview.emergentagent.com` |
| Hot Reload | ✅ Enabled for both frontend and backend |

### Active Integrations — Live vs Mocked

| Integration | Status | Detail |
|-------------|--------|--------|
| Claude AI (Sonnet 4.5) | ✅ **LIVE** | Intent parsing via Emergent LLM Key (`sk-emergent-...`) |
| OpenAI Whisper | ⚠️ **CONFIGURED but untestable** | Emergent LLM Key present, but requires WhatsApp audio download (WhatsApp not configured) |
| Duffel GDS | ⚠️ **SANDBOX MOCK** | `DUFFEL_API_KEY=duffel_test_placeholder` → `is_duffel_sandbox()=True` → all searches return mock flights |
| WhatsApp Cloud API | ❌ **NOT CONFIGURED** | `WHATSAPP_PHONE_ID=your_phone_id_here`, `WHATSAPP_TOKEN=your_token_here` → all messages are logged only, not sent |
| Stripe | ❌ **NOT CONFIGURED** | `STRIPE_SECRET_KEY=your_stripe_secret_key_here` → simulated payment page |
| MTN MoMo | ❌ **NOT CONFIGURED** | `MOMO_API_USER=your_uuid_here` → all MoMo payments return simulated pending |
| Moov Money | ❌ **NOT CONFIGURED** | `MOOV_API_KEY=your_key_here` → all Moov payments return simulated pending |
| Google Pay | ❌ **NOT CONFIGURED** | Depends on Stripe → simulated |
| Apple Pay | ❌ **NOT CONFIGURED** | Depends on Stripe → simulated |
| Google Vision OCR | ❌ **NOT CONFIGURED** | No `GOOGLE_VISION_API_KEY` → falls back to Pytesseract |
| Celtiis Cash | ❌ **STUBBED** | `raise NotImplementedError("Celtiis Cash -- pending partner agreement.")` |

---

## 2. CONVERSATION FLOW — COMPLETE MAP

### State Machine Overview

The conversation is driven by a `ConversationState` class with **32 distinct states**. Below is the exhaustive map of every state.

---

#### State: `IDLE`
- **Trigger condition:** Default state for all sessions (new or cleared)
- **What the agent sends:** Nothing (waits for user input)
- **Expected user input:** Any text message
- **Next state(s):**
  - If user says `"bonjour"`, `"hello"`, `"hi"`, `"salut"` → calls `start_conversation()` → either `ENROLLMENT_METHOD` (new user) or `ASKING_TRAVEL_PURPOSE` (returning user)
  - If user says `"remboursement"`, `"refund"`, `"annuler reservation"` → `CANCELLATION_IDENTIFY`
  - If user says `"modifier"`, `"changer"`, `"change"`, `"modify"` → `MODIFICATION_REQUESTED`
  - If user has existing passenger profile → `ASKING_TRAVEL_PURPOSE`
  - If user is new → `ENROLLMENT_METHOD`
- **Edge cases handled:** ✅ Session expiry (30 min timeout resets to IDLE with notice), ✅ Rate limiting checked first, ✅ `"start"`, `"aide"`, `"help"`, `"menu"` reset to start
- **Edge cases NOT handled:** ❌ User sending random text when IDLE with no passenger profile — goes to enrollment (good), but no guidance if they type gibberish. ❌ No deep-link or resumption of abandoned bookings.

---

#### State: `NEW`
- **Trigger condition:** Defined in ConversationState but **never set anywhere in the code**
- **What the agent sends:** N/A
- **Expected user input:** N/A
- **Next state(s):** N/A
- **Edge cases handled:** N/A
- **Edge cases NOT handled:** ❌ Dead state — never used. Should be removed or implemented.

---

#### State: `ENROLLMENT_METHOD`
- **Trigger condition:** New user starts conversation, or user presses "2" (start over) during profile confirmation
- **What the agent sends (FR):**
  ```
  Bienvenue sur Travelio !
  Avant de rechercher votre vol, j'ai besoin de votre nom pour le billet.

  Comment souhaitez-vous renseigner vos informations ?

  1 Scanner mon passeport (photo)
  2 Envoyer une photo de mon passeport
  3 Saisie manuelle
  ```
- **Expected user input:** `1`, `2`, or `3`
- **Next state(s):**
  - `1` or `2` → `ENROLLING_SCAN`
  - `3` or `"manuel"` or `"manual"` → `ENROLLING_MANUAL_FN`
- **Edge cases handled:** ✅ Invalid input gets "Repondez 1, 2 ou 3". ✅ `"annuler"` cancels flow.
- **Edge cases NOT handled:** ❌ Options 1 and 2 both lead to the exact same flow (`ENROLLING_SCAN`). There is no functional difference between "scan" and "send a photo" — this is cosmetic duplication.

---

#### State: `ENROLLING_SCAN`
- **Trigger condition:** User chose option 1 or 2 from enrollment
- **What the agent sends (FR):**
  ```
  Envoyez une photo de votre passeport.
  Assurez-vous que la photo est nette et que les deux lignes du bas sont visibles (zone MRZ).
  ```
- **Expected user input:** An image (WhatsApp image message)
- **Next state(s):**
  - Image received → OCR extraction → if successful → `CONFIRMING_PROFILE`
  - Image received → OCR partial → `ENROLLING_MANUAL_FN` or `ENROLLING_MANUAL_LN`
  - Image received → OCR failed → back to `ENROLLMENT_METHOD`
  - Text received (no image) → Prompts to send photo or type `3` for manual
  - Text `3` → handler doesn't handle this; stays in `ENROLLING_SCAN`
- **Edge cases handled:** ✅ OCR failure gracefully falls back to manual. ✅ Partial data (name detected but no passport number) prompts for missing fields.
- **Edge cases NOT handled:** ❌ If user types `3` while in `ENROLLING_SCAN`, the handler only re-prompts "send a photo or type 3" but does NOT route to manual entry. The `handler.py` line 103-106 catches text in `ENROLLING_SCAN` but only says to send a photo. The `enrollment.py` `handle_enrollment_method_selection` handles `3` → manual, but `handler.py` never calls it from `ENROLLING_SCAN`. **BUG: User cannot switch to manual entry from scan state by typing `3`.**

---

#### State: `ENROLLING_MANUAL_FN`
- **Trigger condition:** User chose manual entry (option 3) or OCR missed first name
- **What the agent sends (FR):** `"Quel est votre prenom ? (tel qu'il apparait sur votre passeport)"`
- **Expected user input:** First name (letters, spaces, hyphens, min 2 chars)
- **Next state(s):** Valid name → `ENROLLING_MANUAL_LN`
- **Edge cases handled:** ✅ Name validation with regex `[a-zA-Z\u00C0-\u00FF\s\-']+`, min 2 chars. ✅ Title case normalization for ALL CAPS input.
- **Edge cases NOT handled:** ❌ Very long names (no max length check — sanitize_input truncates at 2000 chars globally, but names could be 2000 chars).

---

#### State: `ENROLLING_MANUAL_LN`
- **Trigger condition:** Valid first name entered
- **What the agent sends (FR):** `"Quel est votre nom de famille ?"`
- **Expected user input:** Last name
- **Next state(s):** Valid name → `ENROLLING_MANUAL_PP`
- **Edge cases handled:** ✅ Same validation as first name.
- **Edge cases NOT handled:** Same as `ENROLLING_MANUAL_FN`.

---

#### State: `ENROLLING_MANUAL_PP`
- **Trigger condition:** Valid last name entered
- **What the agent sends (FR):** `"Quel est votre numero de passeport ? (facultatif -- tapez 'passer' pour ignorer)"`
- **Expected user input:** Passport number (6-9 alphanumeric) OR `"passer"`, `"skip"`, `"ignorer"`, `"-"`, `"non"`, `"no"`
- **Next state(s):** → `CONFIRMING_PROFILE`
- **Edge cases handled:** ✅ Optional field with multiple skip keywords. ✅ Validates 6-9 alphanumeric.
- **Edge cases NOT handled:** ✅ All reasonable edge cases handled.

---

#### State: `CONFIRMING_PROFILE`
- **Trigger condition:** All enrollment fields collected (scan or manual)
- **What the agent sends (FR):**
  ```
  Voici les informations que j'ai relevees :

  Nom : DUPONT Jean
  Passeport : AB1234567
  Nationalite : Non renseignee

  Ces informations sont-elles correctes ?

  1 Oui, continuer
  2 Non, recommencer
  ```
- **Expected user input:** `1` (yes) or `2` (no)
- **Next state(s):**
  - `1` → saves passenger → `ASKING_TRAVEL_PURPOSE` (via `handle_returning_user`)
  - `2` → back to `ENROLLMENT_METHOD`
- **Edge cases handled:** ✅ Accept "oui", "yes", "ok", "correct". ✅ Accept "non", "no".
- **Edge cases NOT handled:** ✅ Reasonable coverage.

---

#### State: `ASKING_TRAVEL_PURPOSE`
- **Trigger condition:** Returning user starts conversation, or new user just completed enrollment
- **What the agent sends (FR):**
  ```
  Rebonjour Jean !
  Reservez-vous ce vol pour vous-meme ou pour quelqu'un d'autre ?

  1 Pour moi (Jean Dupont)
  2 Pour un tiers
  ```
- **Expected user input:** `1` or `2`
- **Next state(s):**
  - `1` → `ASKING_PASSENGER_COUNT`
  - `2` → `SELECTING_THIRD_PARTY`
- **Edge cases handled:** ✅ Accepts "moi", "me", "pour moi", "tiers", "autre", "other". ✅ Global cancel/refund/modify keywords detected here.
- **Edge cases NOT handled:** ✅ Good coverage.

---

#### State: `SELECTING_THIRD_PARTY`
- **Trigger condition:** User chose "for someone else"
- **What the agent sends (FR):** Lists existing saved third-party passengers + option for new person
- **Expected user input:** Number selection or "nouvelle"/"new"
- **Next state(s):**
  - Select existing → `ASKING_PASSENGER_COUNT`
  - New person → `ENROLLING_THIRD_PARTY_METHOD`
- **Edge cases handled:** ✅ Dynamic list based on saved profiles. ✅ Max 5 profiles enforced.
- **Edge cases NOT handled:** ✅ Good coverage.

---

#### State: `ENROLLING_THIRD_PARTY_METHOD`
- **Trigger condition:** User wants to register a new third-party passenger
- **Same flow as `ENROLLMENT_METHOD` but with `is_tp=True`**
- **Next state(s):** → `ENROLLING_TP_SCAN` or `ENROLLING_TP_MANUAL_FN`

#### States: `ENROLLING_TP_SCAN`, `ENROLLING_TP_MANUAL_FN`, `ENROLLING_TP_MANUAL_LN`, `ENROLLING_TP_MANUAL_PP`, `CONFIRMING_TP_PROFILE`
- **Mirror states of self-enrollment but for third-party passengers.** Same logic, same validations.
- **Next state(s):** Confirmed → `SAVE_TP_PROMPT`

---

#### State: `SAVE_TP_PROMPT`
- **Trigger condition:** Third-party passenger profile confirmed
- **What the agent sends (FR):** `"Souhaitez-vous sauvegarder ce profil pour vos prochaines reservations ? 1 Oui 2 Non"`
- **Expected user input:** `1` or `2`
- **Next state(s):** → `ASKING_PASSENGER_COUNT`
- **Edge cases handled:** ✅ If at max (5 profiles), oldest is deleted to make room. ✅ Non-saved profiles are stored with `_temp_` prefix.
- **Edge cases NOT handled:** ❌ No confirmation before deleting the oldest saved profile.

---

#### State: `ASKING_PASSENGER_COUNT`
- **Trigger condition:** Passenger selected (self or third-party)
- **What the agent sends (FR):** `"Combien de passagers voyagent ? (repondez 1 pour continuer -- multi-passagers disponible prochainement)"`
- **Expected user input:** `1` (or any number)
- **Next state(s):** → `AWAITING_DESTINATION`
- **Edge cases handled:** ✅ Multi-passenger politely declined with "coming soon" message.
- **Edge cases NOT handled:** ❌ This is a **stub** — multi-passenger is NOT implemented. Always proceeds as 1 passenger regardless of input.

---

#### State: `AWAITING_DESTINATION`
- **Trigger condition:** Passenger count confirmed
- **What the agent sends (FR):** `'Ou souhaitez-vous aller ? "Je veux un vol pour Paris vendredi prochain"'`
- **Expected user input:** City name, IATA code, or natural language sentence
- **Next state(s):**
  - Destination recognized + date included → search flights → `AWAITING_FLIGHT_SELECTION`
  - Destination recognized, no date → `AWAITING_DATE`
  - Destination not recognized → suggests alternatives (stays in `AWAITING_DESTINATION`)
- **Edge cases handled:** ✅ Claude AI intent parsing. ✅ RapidFuzz fuzzy match (score >= 70). ✅ Contains/substring match. ✅ "Did you mean?" suggestions with top 3 matches.
- **Edge cases NOT handled:** ❌ Multi-city / round-trip not supported. ❌ If Claude returns a destination code that isn't in the local DB, it's used raw (might be a valid IATA code, might not).

---

#### State: `AWAITING_DATE`
- **Trigger condition:** Destination resolved but no date
- **What the agent sends (FR):** `"Quelle est votre date de depart ? (ex: demain, vendredi prochain, 15 mars...)"`
- **Expected user input:** Natural language date or ISO format
- **Next state(s):** Date parsed → search flights → `AWAITING_FLIGHT_SELECTION`
- **Edge cases handled:** ✅ dateparser handles French/English. ✅ Quick French matches: demain, apres-demain, jour de la semaine. ✅ ISO format YYYY-MM-DD passthrough. ✅ Past dates auto-corrected to next year. ✅ Fallback to Claude AI if dateparser fails.
- **Edge cases NOT handled:** ❌ No calendar/interactive list actually sent (the `generate_date_options()` function exists but is never called). ❌ Ambiguous dates like "15" (just a number) may confuse the parser.

---

#### State: `AWAITING_FLIGHT_SELECTION`
- **Trigger condition:** Flights found and displayed
- **What the agent sends (FR):**
  ```
  *Travelio -- 3 options trouvees*
  Cotonou -> Paris | 2026-03-15

  LE PLUS BAS Demo
  Air France | Direct
  Duree : 3h15
  Prix : *210.25EUR* (137,900 XOF)
  Taper *1* pour selectionner

  LE PLUS RAPIDE Demo
  ...

  PREMIUM Demo
  ...

  Repondez 1, 2 ou 3 pour continuer.
  ```
- **Expected user input:** `1`, `2`, or `3` (or French/English variants)
- **Next state(s):** → `AWAITING_PAYMENT_METHOD`
- **Edge cases handled:** ✅ Accepts "un", "one", "premier", "plus bas", "deux", "two", etc. ✅ Flight not found in session → error message.
- **Edge cases NOT handled:** ✅ Good coverage.

---

#### State: `AWAITING_PAYMENT_METHOD`
- **Trigger condition:** Flight selected, booking created in DB
- **What the agent sends (FR):**
  ```
  *Choisissez votre moyen de paiement*
  Montant : *210.25EUR* (137,900 XOF)

  1 MTN MoMo
  2 Moov Money (Flooz)
  3 Google Pay
  4 Apple Pay

  Repondez 1, 2, 3 ou 4
  ```
- **Expected user input:** `1`, `2`, `3`, or `4`
- **Next state(s):** → `AWAITING_PAYMENT_CONFIRM`
- **Edge cases handled:** ✅ Payment velocity check (max 3 attempts/hour). ✅ Accepts operator name variants ("mtn", "momo", "moov", "flooz", etc.).
- **Edge cases NOT handled:** ❌ Celtiis Cash (option 5) is not offered to the user even though `PaymentOperator.CELTIIS_CASH` exists. ❌ No Celtiis Cash option in the menu.

---

#### State: `AWAITING_PAYMENT_CONFIRM`
- **Trigger condition:** Payment method selected
- **What the agent sends (FR):**
  ```
  *Recapitulatif de votre paiement*

  Vol : COO -> CDG
  Depart : 2026-03-15
  Passager : Dupont Jean
  Classe : PLUS_BAS
  Methode : MTN MoMo

  *Conditions du billet :*
  - Remboursable : Non -- aucun remboursement
  - Modifiable : Non -- billet sec
  - Delai : Sans objet

  Montant : *210.25EUR* (137,900 XOF)

  Lisez attentivement avant de confirmer.

  1 Oui, envoyer la notification de paiement
  2 Non, annuler
  3 Voir les conditions completes
  ```
- **Expected user input:** `1`, `2`, or `3`
- **Next state(s):**
  - `1` → execute payment → `AWAITING_MOBILE_PAYMENT` or `AWAITING_CARD_PAYMENT`
  - `2` → clear session → `IDLE`
  - `3` → shows full conditions → re-prompts `1` or `2`
- **Edge cases handled:** ✅ Pre-debit confirmation with fare conditions. ✅ Full conditions viewable. ✅ Clear cancel path.
- **Edge cases NOT handled:** ✅ Comprehensive.

---

#### State: `AWAITING_MOBILE_PAYMENT`
- **Trigger condition:** MoMo or Moov payment initiated
- **What the agent sends (FR):**
  ```
  *Notification envoyee !*

  Montant : *210.25EUR* (137,900 XOF)
  Methode : MTN MoMo

  Ouvrez MTN MoMo et confirmez avec votre PIN / mot de passe.

  Vous avez *30 secondes*...
  ```
- **Expected user input:** None (background polling). If user sends text: "Paiement en cours... Approuvez sur votre telephone."
- **Next state(s):**
  - Payment SUCCESSFUL → generates ticket → `IDLE` (via `clear_session`)
  - Payment FAILED → `retry`
  - Payment TIMEOUT → `retry`
- **Edge cases handled:** ✅ 10 polling attempts x 3 seconds = 30 seconds. ✅ Progress messages at 9s and 18s. ✅ Timeout with retry options.
- **Edge cases NOT handled:** ❌ User might receive WhatsApp messages out of order if they interact during polling.

---

#### State: `AWAITING_CARD_PAYMENT`
- **Trigger condition:** Google Pay or Apple Pay selected
- **What the agent sends (FR):** Payment link URL + instructions
- **Expected user input:** None (Stripe webhook callback). If user messages: "En attente du paiement..."
- **Next state(s):** Stripe webhook → `complete_card_payment()` → ticket → `IDLE`
- **Edge cases handled:** ✅ Simulated fallback when Stripe not configured.
- **Edge cases NOT handled:** ❌ No timeout for card payment. User could be stuck in `AWAITING_CARD_PAYMENT` indefinitely if they never pay and never type "annuler". ❌ No automatic session cleanup for abandoned card payments.

---

#### State: `retry`
- **Trigger condition:** Payment failed or timed out
- **What the agent sends (FR):**
  ```
  Souhaitez-vous reessayer ?

  1 Reessayer avec MTN MoMo
  2 Choisir une autre methode
  3 Annuler la reservation
  ```
- **Expected user input:** `1`, `2`, or `3`
- **Next state(s):**
  - `1` → re-execute same method
  - `2` → `AWAITING_PAYMENT_METHOD`
  - `3` → clear session → `IDLE`
- **Edge cases handled:** ✅ Re-attempt, switch, or cancel.
- **Edge cases NOT handled:** ⚠️ State value is the raw string `"retry"`, not a `ConversationState` enum value. This is inconsistent with the rest of the state machine.

---

#### State: `AWAITING_PAYMENT_CONFIRMATION`
- **Defined in ConversationState but NEVER SET anywhere in the code.**
- ❌ Dead state — unused.

---

#### State: `AWAITING_CONSENT`
- **Defined in ConversationState but NEVER SET anywhere in the code.**
- ❌ Dead state — consent flow is not implemented.

---

#### State: `CANCELLATION_IDENTIFY`
- **Trigger condition:** User asks for refund/cancellation
- **What the agent sends (FR):**
  ```
  Quelle reservation souhaitez-vous annuler ?

  1 TRV-ABC123 -- Paris -- 2026-03-15
  2 TRV-DEF456 -- Dakar -- 2026-04-01

  ou tapez votre numero TRV-XXXXXX
  ```
- **Expected user input:** Number or TRV-XXXXXX reference
- **Next state(s):** → `CANCELLATION_CONFIRM`
- **Edge cases handled:** ✅ Lists up to 5 recent confirmed bookings. ✅ Direct reference entry. ✅ "No bookings to cancel" message.
- **Edge cases NOT handled:** ✅ Good coverage.

---

#### State: `CANCELLATION_CONFIRM`
- **Trigger condition:** Booking identified for cancellation
- **What the agent sends:** Refund breakdown based on fare conditions (4 cases — see Section 6)
- **Expected user input:** `1` (confirm) or `2` (keep) or `3` (contact support, for deadline_passed case)
- **Next state(s):**
  - `1` → `CANCELLATION_PROCESSING` → process refund → `IDLE` (or `REFUND_FAILED`)
  - `2` → `IDLE`
  - `3` → shows support email → `IDLE`
- **Edge cases handled:** ✅ All 4 fare condition cases handled.
- **Edge cases NOT handled:** ✅ Comprehensive.

---

#### State: `CANCELLATION_PROCESSING`
- **Trigger condition:** User confirmed cancellation
- **What the agent sends:** "Remboursement en cours... Veuillez patienter." (if user messages during processing)
- **Expected user input:** None (processing is synchronous despite the state name)
- **Next state(s):** → `IDLE` (success) or `REFUND_FAILED`
- **Edge cases handled:** ✅ Refund failure → queue for manual processing.
- **Edge cases NOT handled:** ❌ Processing is actually synchronous — this state is only relevant if the user sends a message during processing (which is a race condition with the cancellation handler).

---

#### State: `REFUND_FAILED`
- **Trigger condition:** Automatic refund processing failed
- **What the agent sends (FR):** "Votre remboursement est en cours de traitement manuel. Reference : REF-TRV-... Contactez support@travelio.app si besoin."
- **Expected user input:** Any (returns same message + clears session)
- **Next state(s):** → `IDLE`
- **Edge cases handled:** ✅ Manual processing queue in DB. ✅ Reference number provided.
- **Edge cases NOT handled:** ✅ Acceptable.

---

#### State: `MODIFICATION_REQUESTED`
- **Trigger condition:** User asks to modify a booking
- **What the agent sends:** Lists modifiable bookings
- **Expected user input:** Number or TRV-XXXXXX
- **Next state(s):** → `MODIFICATION_CONFIRM`
- **Edge cases handled:** ✅ Lists recent confirmed bookings.
- **Edge cases NOT handled:** ✅ Good.

---

#### State: `MODIFICATION_CONFIRM`
- **Trigger condition:** Booking selected for modification
- **What the agent sends:**
  - If not modifiable: "Billet non modifiable. 1 Voir conditions d'annulation 2 Conserver"
  - If modifiable: "Billet modifiable. Penalite : 50EUR. 1 Date de depart 2 Date de retour 3 Annuler plutot"
- **Expected user input:** `1`, `2`, or `3`
- **Next state(s):**
  - Modifiable + `1` or `2` → `AWAITING_DATE` (re-enters booking flow)
  - `3` or not modifiable + `1` → cancellation flow
  - `2` (keep) → `IDLE`
- **Edge cases handled:** ✅ Redirects to cancellation if non-modifiable. ✅ Shows penalty amount.
- **Edge cases NOT handled:** ❌ After selecting new date and searching flights, the modification does NOT actually modify the existing booking — it creates a new booking entirely. **The original booking is not cancelled.** This is a significant gap.

---

### Summary of Dead / Unused States

| State | Status |
|-------|--------|
| `NEW` | ❌ Defined but never set |
| `AWAITING_PAYMENT_CONFIRMATION` | ❌ Defined but never set |
| `AWAITING_CONSENT` | ❌ Defined but never set |

---

## 3. ENROLLMENT & PASSENGER MANAGEMENT

### Method 1: Passport Photo Scan (Options 1 & 2)

| Aspect | Status |
|--------|--------|
| Implemented? | ⚠️ **Partial** |
| Tested? | ⚠️ **Partial** (tested via simulation, not real WhatsApp images) |
| OCR Engine | Pytesseract (primary), Google Vision (fallback, NOT configured) |
| MRZ Parsing | ✅ Implemented — extracts firstName, lastName, passportNumber, nationality, DOB, expiry |
| Image Preprocessing | ✅ Grayscale conversion, contrast enhancement (2.0x), sharpening |
| Confidence Scoring | ✅ Pytesseract confidence average calculated |
| Partial Data Handling | ✅ If name detected but passport missing → prompts for manual entry of missing fields |
| **Known Bugs/Limitations** | |
| - Options 1 and 2 are identical | ⚠️ Both route to `ENROLLING_SCAN`. No functional difference. |
| - Requires WhatsApp configured | ❌ Cannot download images without `WHATSAPP_TOKEN` configured. In current state, always returns `None` → falls back to manual. |
| - No DOB/expiry collection in manual flow | ⚠️ OCR extracts DOB and expiry, but manual entry does not ask for these fields |
| - Typing `3` while in ENROLLING_SCAN doesn't switch to manual | ❌ **BUG** — handler.py tells user to "type 3 for manual" but the scan state handler just re-prompts for a photo |

**What happens on failure:** If image download fails → prompts manual entry. If OCR fails entirely → prompts manual entry with option 3. If OCR partial → prompts for missing fields specifically.

### Method 2: Manual Entry (Option 3)

| Aspect | Status |
|--------|--------|
| Implemented? | ✅ **Yes — fully** |
| Tested? | ✅ **Yes** (E2E tested with testing agent) |
| Validation | ✅ Name regex `[a-zA-Z\u00C0-\u00FF\s\-']` (supports accented chars), min 2 chars |
| Passport validation | ✅ 6-9 alphanumeric, optional (can skip) |
| Title case normalization | ✅ ALL CAPS names converted to Title Case |
| PII encryption | ✅ passportNumber, dateOfBirth, expiryDate encrypted with AES-256-GCM before storage |
| **Known Limitations** | |
| - No DOB collection | ❌ Manual entry skips date of birth (only collected via OCR) |
| - No expiry collection | ❌ Manual entry skips passport expiry (only collected via OCR) |
| - No nationality collection | ❌ Manual entry skips nationality (only collected via OCR) |

**What happens on failure:** Invalid name → re-prompts with validation message. Invalid passport → re-prompts with format hint.

### Method 3: Third-Party Passenger Management

| Aspect | Status |
|--------|--------|
| Implemented? | ✅ **Yes** |
| Tested? | ✅ **Yes** (E2E tested) |
| Max profiles | ✅ 5 third-party passengers per user |
| Profile listing | ✅ Saved profiles listed for re-selection |
| Save prompt | ✅ Asks whether to save for future use |
| Profile rotation | ✅ Oldest profile deleted when at max capacity |
| Temporary profiles | ✅ Non-saved profiles stored with `_temp_` phone prefix |
| **Known Limitations** | |
| - No warning before deleting oldest profile | ⚠️ Silently replaces oldest saved profile |
| - No profile editing | ❌ Cannot update a saved third-party passenger — must delete and recreate |
| - No profile deletion by user | ❌ No way for user to delete a saved third-party profile via conversation |

**What happens on failure:** Same as self-enrollment — validation errors re-prompt.

---

## 4. FLIGHT SEARCH & GDS

### Active GDS
⚠️ **Duffel — SANDBOX MOCK MODE**

Detection logic in `config.py`:
```python
def is_duffel_sandbox():
    return 'placeholder' in DUFFEL_API_KEY or DUFFEL_ENV == 'sandbox'
```
Current env: `DUFFEL_API_KEY=duffel_test_placeholder`, `DUFFEL_ENV=sandbox` → **always returns mock flights.**

### Flight Search Parameters Supported

| Parameter | Supported | Source |
|-----------|-----------|--------|
| Origin | ✅ | Auto-detected (default: COO for Cotonou) or user-specified |
| Destination | ✅ | Extracted from user text via Claude + RapidFuzz |
| Departure date | ✅ | Parsed from natural language via dateparser |
| Return date | ❌ | Extracted by Claude but **never used** — one-way flights only |
| Passengers | ⚠️ | Extracted but **capped at 1** (multi-passenger stubbed) |
| Cabin class | ❌ | Hardcoded to "economy" in Duffel request |

### Categorization Logic

The `categorize_flights()` function selects **exactly 3 flights** from up to 20 results:

| Category | French Label | Selection Logic |
|----------|-------------|-----------------|
| `PLUS_BAS` | "LE PLUS BAS" | Lowest `final_price` |
| `PLUS_RAPIDE` | "LE PLUS RAPIDE" | Lowest `duration_minutes` (not already used) |
| `PREMIUM` | "PREMIUM" | Highest composite score: 40% price + 40% duration + 20% direct bonus (not already used) |

**Composite score formula:**
```python
score = (price_score * 0.4) + (duration_score * 0.4) + (direct_bonus * 0.2)
# price_score = (max_price - flight_price) / max_price
# duration_score = (max_duration - flight_duration) / max_duration
# direct_bonus = 1.0 if 0 stops, 0.5 if 1 stop, 0.0 if 2+ stops
```

### Pricing Margin Application

```python
def apply_travelio_margin(base_price: float) -> float:
    return round(base_price + 15 + (base_price * 0.05), 2)
```

✅ **15EUR flat fee + 5% margin** — correctly applied.

**XOF conversion:**
```python
def eur_to_xof(eur: float) -> int:
    return int(math.ceil(eur * 655.957 / 5) * 5)  # Rounded up to nearest 5 XOF
```

### Fare Conditions Retrieval

⚠️ **MOCKED** — In sandbox mode, fare conditions are **randomly assigned** from 3 mock profiles:

| Profile | Refundable | Penalty | Changeable | Change Fee |
|---------|-----------|---------|------------|------------|
| Budget | NO | — | No | — |
| Standard | PARTIAL | 80 EUR | Yes | 50 EUR |
| Flex | YES | 0 EUR | Yes | 0 EUR |

```python
profile = random.choice(MOCK_FARE_PROFILES).copy()
```

❌ **In sandbox, the fare profile is random — disconnected from the actual flight selected.** A "Budget" categorized flight could get a "Flex" fare profile. This is misleading.

### What Happens When GDS Is Unavailable

✅ **Triple fallback:**
1. Real Duffel API call
2. If HTTP error → `generate_mock_flights()`
3. If exception → `generate_mock_flights()`

The mock generator always returns 5 flights with realistic attributes.

---

## 5. PAYMENT SYSTEM

### MTN MoMo

| Aspect | Status |
|--------|--------|
| Implementation | ⚠️ **SANDBOX / SIMULATED** |
| Live? | ❌ `MOMO_API_USER=your_uuid_here` → always returns simulated response |
| Full flow | 1. User selects MoMo → 2. Pre-debit confirmation → 3. `request_payment()` → 4. Returns `MOMO-SIM-XXXXXXXX` reference → 5. Poll 10x3s → 6. Simulated always returns `SUCCESSFUL` → 7. Ticket generated |
| Pre-debit confirmation | ✅ Shows full breakdown: flight, passenger, fare conditions, amount EUR+XOF |
| Countdown/timeout | ✅ 30 seconds (10 polls x 3s). Progress messages at 9s and 18s |
| Failure handling | ✅ Timeout → retry options (1. retry, 2. switch method, 3. cancel) |
| Refund capability | ⚠️ **SIMULATED** — `process_refund()` just logs and returns a reference ID. No actual API call. |

**Real API flow (when configured):**
1. POST to MoMo sandbox `/collection/token/` for OAuth token
2. POST to `/collection/v1_0/requesttopay` with amount, phone, booking reference
3. Poll `GET /collection/v1_0/requesttopay/{reference_id}` for status

### Moov Money (Flooz)

| Aspect | Status |
|--------|--------|
| Implementation | ⚠️ **SANDBOX / SIMULATED** |
| Live? | ❌ `MOOV_API_KEY=your_key_here` → always returns simulated response |
| Full flow | Same pattern as MoMo but via Moov API (`/v1/cash-in`) |
| Pre-debit confirmation | ✅ Same as MoMo |
| Countdown/timeout | ✅ Same 30-second polling |
| Failure handling | ✅ Same retry options |
| Refund capability | ⚠️ **SIMULATED** |

### Google Pay

| Aspect | Status |
|--------|--------|
| Implementation | ⚠️ **SANDBOX / SIMULATED** |
| Live? | ❌ Depends on Stripe (`STRIPE_SECRET_KEY=your_stripe_secret_key_here`) |
| Full flow | 1. Creates Stripe PaymentIntent → 2. Returns payment page URL → 3. User pays on web page → 4. Stripe webhook confirms → 5. Ticket generated |
| Pre-debit confirmation | ✅ Full summary shown |
| Timeout handling | ❌ **NO TIMEOUT for card payments.** User can be stuck in `AWAITING_CARD_PAYMENT` forever. |
| Failure handling | ❌ No explicit failure handling for card payments — relies on Stripe webhook |
| Refund capability | ⚠️ **SIMULATED** — no actual Stripe refund API call |
| Payment page | ✅ HTML page with Stripe Elements (`#card-element`), Google Pay button, Apple Pay button |

### Apple Pay

| Aspect | Status |
|--------|--------|
| Implementation | ⚠️ **SANDBOX / SIMULATED** |
| Live? | ❌ Same as Google Pay (shares Stripe backend) |
| Full flow | Identical to Google Pay — calls `_google_pay()` then sets operator to `APPLE_PAY` |
| Timeout/Failure | ❌ Same gap as Google Pay |

### Celtiis Cash

| Aspect | Status |
|--------|--------|
| Implementation | ❌ **STUBBED** |
| Code | `raise NotImplementedError("Celtiis Cash -- pending partner agreement.")` |
| User-facing | Not offered in payment menu |

### Summary Table

| Operator | Status | Real API Implemented | Simulated | Refund |
|----------|--------|---------------------|-----------|--------|
| MTN MoMo | ⚠️ Simulated | ✅ Yes (code exists) | ✅ Yes | ⚠️ Simulated |
| Moov Money | ⚠️ Simulated | ✅ Yes (code exists) | ✅ Yes | ⚠️ Simulated |
| Google Pay | ⚠️ Simulated | ✅ Yes (Stripe) | ✅ Yes | ⚠️ Simulated |
| Apple Pay | ⚠️ Simulated | ✅ Yes (Stripe) | ✅ Yes | ⚠️ Simulated |
| Celtiis Cash | ❌ Stubbed | ❌ No | ❌ No | ❌ No |

---

## 6. REFUND & CANCELLATION

### Cancellation Trigger Detection

✅ **Keywords detected globally:**
- French: `"remboursement"`, `"rembourser"`, `"annuler reservation"`
- English: `"refund"`, `"cancel booking"`

✅ **Detected from multiple states:** IDLE, ASKING_TRAVEL_PURPOSE, AWAITING_DESTINATION, AWAITING_DATE, ASKING_PASSENGER_COUNT.

⚠️ **NOT detected from:** AWAITING_FLIGHT_SELECTION, AWAITING_PAYMENT_METHOD (user must type "annuler" — which triggers the global cancel handler).

### All 4 Fare Condition Cases

#### Case 1: `non_refundable` (NO)
```
*Billet non remboursable*
- Remboursable : Non -- aucun remboursement
- Modifiable : Non -- billet sec
- Delai : Sans objet

Annuler quand meme (sans remboursement) ?
1 Oui  2 Non, conserver
```
- ✅ Booking cancelled, no refund, ticket invalidated.

#### Case 2: `partial_refund` (PARTIAL)
```
*Remboursement avec penalite*

Montant paye : 210EUR
- Penalite compagnie : -80EUR
- Frais Travelio : -15EUR (non remboursables)
---
*Total rembourse : 115EUR* (75,440 XOF)

Methode : mtn_momo (****1234)
Delai : 5 a 10 jours ouvres

1 Oui, annuler et rembourser 115EUR
2 Non, conserver
```
- ✅ Refund formula: `max(0, price - airline_penalty - 15EUR_travelio_fee)`

#### Case 3: `fully_refundable` (YES)
```
*Remboursement integral*

Montant paye : 210EUR
- Frais Travelio : -15EUR (non remboursables)
---
*Total rembourse : 195EUR* (127,910 XOF)

Methode : mtn_momo (****1234)
Delai : 3 a 5 jours ouvres

1 Oui  2 Non
```
- ✅ Refund formula: `price - 15EUR_travelio_fee`

#### Case 4: `deadline_passed` (EXPIRED)
```
*Delai d'annulation depasse*

Remboursement possible jusqu'au 2026-03-13 14:00.
Cette date est depassee.

1 Annuler sans remboursement
2 Conserver
3 Contacter le support
```
- ✅ Deadline computed from `departure_date - refund_deadline_hours_before`.

### Refund Processing Per Operator

| Operator | Real Refund | Current Behavior |
|----------|------------|-----------------|
| MTN MoMo | ❌ | Logs refund, returns `REFUND-MOMO-XXXXXXXX` reference. No actual API call. |
| Moov Money | ❌ | Logs refund, returns `REFUND-MOOV-XXXXXXXX` reference. No actual API call. |
| Stripe (GPay/APay) | ❌ | Logs refund, returns `REFUND-STRIPE-XXXXXXXX` reference. No `stripe.Refund.create()` call. |

⚠️ **All refunds are simulated.** The `process_refund()` function in `cancellation.py` only logs and returns a fake reference.

### Refund Failure Handling
✅ If `process_refund()` returns `success=False`:
1. Booking added to `refund_queue` collection with details
2. Booking `refund_status` set to `FAILED`
3. User receives: "Remboursement automatique echoue. Traitement manuel sous 48h. Reference: REF-TRV-..."
4. User transitions to `REFUND_FAILED` state

✅ Testable with `_test_refund_fail` flag on booking.

### Ticket Invalidation
✅ Booking status set to `"cancelled"` in DB. QR code verification endpoint (`/verify_qr/{booking_ref}`) checks `status == "confirmed"` → cancelled bookings show as invalid.

❌ **The PDF file itself is NOT deleted from the filesystem.** The ticket PDF remains downloadable via `/api/tickets/{filename}` even after cancellation.

### Modification Flow
✅ Implemented but with a significant gap:
- User can select a booking to modify
- If changeable: shows penalty and asks what to change (departure date or return date)
- Then enters `AWAITING_DATE` → searches new flights → creates a **new booking**

❌ **The modification flow does NOT cancel or update the original booking.** It effectively creates a duplicate.

---

## 7. SECURITY

### Rate Limiting

| Limit | Max Requests | Window | Enforcement |
|-------|-------------|--------|-------------|
| Messages | 30 | 60 seconds | ✅ Per phone number |
| Payments | 5 | 300 seconds (5 min) | ✅ Per phone number |
| Enrollment | 10 | 600 seconds (10 min) | ✅ Per phone number |

**Implementation:** MongoDB collection `rate_limits` with TTL index (auto-expire after 1 hour). Each action creates a document. Count is checked before allowing the action.

✅ Rate limit exceeded → "Trop de messages. Veuillez patienter."

### Fraud Detection

| Rule | Implemented | Detail |
|------|------------|--------|
| Payment velocity | ✅ | Max 3 payment attempts per hour per phone |
| Security alerts | ✅ | Velocity violations logged to `security_alerts` collection |
| IP-based limiting | ❌ | Not implemented — only phone-based |
| Amount anomaly detection | ❌ | Not implemented |
| Geographic anomaly | ❌ | Not implemented |

### Input Sanitization

```python
def sanitize_input(text: str) -> str:
    if not text:
        return ""
    sanitized = text.replace("$", "").replace("{", "").replace("}", "")
    return sanitized[:2000]
```

✅ **Covered:** NoSQL injection characters (`$`, `{`, `}`) stripped. Length capped at 2000.
❌ **NOT covered:** HTML/script injection (not relevant for WhatsApp, but stored in DB). No Unicode normalization. No null byte stripping.

### Encryption

| Data | Algorithm | At Rest | In Transit |
|------|-----------|---------|-----------|
| `passportNumber` | AES-256-GCM | ✅ Encrypted in MongoDB | ✅ Decrypted only when needed |
| `dateOfBirth` | AES-256-GCM | ✅ Encrypted in MongoDB | ✅ |
| `expiryDate` | AES-256-GCM | ✅ Encrypted in MongoDB | ✅ |
| `firstName` | None | ❌ Stored in plaintext | — |
| `lastName` | None | ❌ Stored in plaintext | — |
| `whatsapp_phone` | None | ❌ Stored in plaintext | — |
| `booking details` | None | ❌ Stored in plaintext | — |

**Key derivation:**
```python
def _derive_key(key_str: str) -> bytes:
    return hashlib.sha256(key_str.encode()).digest()
```
⚠️ SHA-256 key derivation from a string is functional but not best-practice. Should use PBKDF2, scrypt, or Argon2 with salt.

**Encryption key in .env:** `ENCRYPTION_KEY=travelio_aes256_master_key_2024_prod`
❌ **The encryption key is a human-readable string**, not a proper random key. It's stored in plaintext in `.env`.

### Webhook Verification

```python
if hub_mode == "subscribe" and hub_token == WHATSAPP_VERIFY_TOKEN:
    return Response(content=hub_challenge, media_type="text/plain")
```
✅ WhatsApp webhook verification token check implemented.
❌ **Incoming webhook POST requests are NOT verified.** No `X-Hub-Signature-256` header validation. Any HTTP client can send fake webhook payloads.

### API Key Protection

| Key | Storage | Protection |
|-----|---------|-----------|
| EMERGENT_LLM_KEY | .env | ✅ Not exposed in API responses |
| WHATSAPP_TOKEN | .env | ✅ Not exposed |
| STRIPE_SECRET_KEY | .env | ✅ Not exposed |
| STRIPE_PUBLISHABLE_KEY | .env | ⚠️ Exposed in payment page HTML (expected for Stripe) |
| ENCRYPTION_KEY | .env | ✅ Not exposed |

### Known Security Gaps

1. ❌ **No webhook signature verification** — incoming POST /api/webhook is unauthenticated
2. ❌ **Encryption key is weak** — human-readable string, no salt, SHA-256 derivation
3. ❌ **Names and phone numbers stored in plaintext** — only passport/DOB/expiry encrypted
4. ❌ **No IP-based rate limiting** — only phone-based (bot could use different phone numbers)
5. ❌ **Test simulation endpoint is unauthenticated** — POST /api/test/simulate is publicly accessible
6. ❌ **QR code contains passport number** in plaintext JSON
7. ⚠️ **CORS is `*`** — allows any origin (acceptable for webhook-only backend, but risky if API expands)

---

## 8. LEGAL & COMPLIANCE

### /legal/terms Endpoint
✅ **LIVE** — `GET /api/legal/terms` returns full HTML Terms of Service page.

Content covers: Objet, Inscription, Reservations (mentions Duffel + 15EUR commission), Paiements, Annulations et Remboursements, Responsabilite, Protection des Donnees (mentions AES-256-GCM), Contact.

### /legal/privacy Endpoint
✅ **LIVE** — `GET /api/legal/privacy` returns full HTML Privacy Policy page.

Content covers: Donnees Collectees (lists all data points), Utilisation, Securite (mentions AES-256-GCM), Conservation (30 min sessions, 24 months bookings, 5 years payment data), Partage (airlines + payment providers), Vos Droits (GDPR access/rectification/deletion), Retention et Suppression, Contact DPO.

### Consent Flow
❌ **NOT IMPLEMENTED** — `ConversationState.AWAITING_CONSENT` exists but is never set. There is no explicit consent collection before storing user data. Users are enrolled directly without agreeing to ToS/Privacy Policy.

### Data Retention Automation
✅ **ACTIVE** — Periodic cleanup task in `server.py`:
```python
cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
await db.sessions.delete_many({"last_activity": {"$lt": cutoff}})
```
Runs hourly. Deletes sessions inactive for 30+ days.

⚠️ **Only sessions are auto-purged.** Passengers and bookings are NOT automatically cleaned up according to the 24-month retention stated in the privacy policy.

### GDPR Compliance Gaps

| Requirement | Status |
|-------------|--------|
| Right to access | ❌ No API endpoint for data export |
| Right to rectification | ❌ No way to edit passenger data via conversation |
| Right to deletion | ❌ No "delete my data" command or API |
| Consent collection | ❌ Not implemented (state exists but unused) |
| Data minimization | ⚠️ Phone numbers stored in plaintext |
| Automated session purge | ✅ 30-day cleanup |
| Booking data purge | ❌ Not implemented (privacy policy says 24 months) |
| Payment data retention | ❌ Not implemented (privacy policy says 5 years) |
| DPO contact | ✅ Listed as dpo@travelio.app |

### Missing Legal Items Before Go-Live

1. ❌ **Explicit consent flow** before enrollment
2. ❌ **Data export/deletion** endpoints (GDPR right to access/erasure)
3. ❌ **Automated booking data purge** after 24 months
4. ❌ **Cookie consent** on payment page (Stripe loads external JS)
5. ⚠️ **No explicit age verification** (minors could use the service)
6. ⚠️ **ToS/Privacy Policy not version-controlled** — hardcoded in Python, no changelog

---

## 9. AIRPORT RECOGNITION & DATE PICKER

### airports.json
❌ **No separate `airports.json` file.** Airport codes are defined as a Python dictionary in `config.py`.

**Total entries:** 85 city-to-IATA mappings (with some duplicates like `"dakar": "DSS"` appearing 3 times).

**Geographic coverage:**
- West Africa: COO, DSS, LOS, ACC, ABJ, OUA, BKO, CKY, NIM, LFW, PKO, DLA, LBV
- North Africa: CMN, RAK, TUN, ALG, CAI, TIP
- East Africa: ADD, NBO, DAR, EBB, KGL
- Southern Africa: JNB, LAD, MPM, LUN, HRE, WDH, GBE, TNR
- Europe: CDG, LHR, BRU, IST, FCO, MAD, AMS, LIS, BER, FRA, MUC, VIE, MXP, BCN, GVA, ZRH, MRS, LYS, NCE, TLS, BOD, NTE, SXB, LIL
- Americas: JFK, IAD, LAX, MIA, ORD, ATL, IAH, YUL, YYZ, GRU, GIG, MEX
- Middle East: DXB, DOH, AUH, RUH, JED
- Asia: BKK, SIN, NRT, PEK, PVG, BOM, DEL, HKG
- Oceania: SYD, MEL, AKL

### Fuzzy Matching
✅ **Implemented** with RapidFuzz.

| Aspect | Detail |
|--------|--------|
| Library | RapidFuzz 3.14.5 |
| Scorer | `fuzz.WRatio` (weighted ratio) |
| Threshold | Score >= 70 for automatic match |
| Suggestion threshold | Score >= 50 for "did you mean?" |
| Max suggestions | 5 |

**Resolution pipeline (5 steps):**
1. Exact match in dictionary
2. Direct IATA code (3 uppercase letters)
3. Fuzzy match (score >= 70) — auto-resolves
4. Contains/substring match
5. Return `None` → "did you mean?" suggestions or "I don't recognize this city"

### Whisper Corrections
❌ **NOT IMPLEMENTED.** There is no post-processing or correction dictionary for Whisper transcription results. If Whisper mishears "Cotonou" as "Kotonou", the fuzzy matching may still catch it (depends on score), but there is no dedicated Whisper-to-correct-spelling mapping.

### Calendar Fallback
❌ **NOT IMPLEMENTED.** The `generate_date_options()` function exists in `date_parser.py` and generates a list of tomorrow + next 7 days, but it is **never called** anywhere in the codebase. No WhatsApp interactive list is sent for date selection.

**Current method:** Text-only natural language parsing via dateparser + Claude AI fallback.

### Multi-City Disambiguation
❌ **NOT WORKING.** If a user says "I want to fly from Lagos to Paris", Claude AI may extract both origin and destination. However:
- The `resolve_airport()` function only handles one city at a time
- The conversation handler's `handle_awaiting_destination()` calls `parse_travel_intent()` which returns both origin and destination, and both are resolved
- ✅ Actually, the code does handle two-city parsing: `intent["origin"]` and `intent["destination"]` are set separately from Claude's response

⚠️ **Partial.** Works when Claude correctly extracts both cities. Does not work for complex multi-leg journeys.

### Departure Auto-Detection
✅ **Working.** Default origin is `COO` (Cotonou) when not specified:
```python
origin = resolve_airport(intent.get("origin", "Cotonou")) or "COO"
```

Users from Benin (+229) are assumed to depart from Cotonou. This is hardcoded and not phone-number-based.

---

## 10. PERFORMANCE & RELIABILITY

### Average Webhook Response Time

| Operation | Estimated Time |
|-----------|---------------|
| Rate limit check (MongoDB query) | ~5-10ms |
| Session lookup (MongoDB query) | ~5-10ms |
| Input sanitization | <1ms |
| Claude AI intent parsing | ~500-2000ms (when called) |
| Airport fuzzy matching | <5ms |
| Date parsing (dateparser) | ~10-50ms |
| Total webhook response (text, no AI) | ~20-50ms |
| Total webhook response (with AI) | ~500-2500ms |

⚠️ **Claude AI calls add 500-2000ms** to every destination parsing. This is the primary latency source.

### Duffel API Response Time

| Mode | Time |
|------|------|
| Sandbox mock | <1ms (in-memory generation) |
| Real Duffel (when configured) | ~2-5s (offer request → response) |

### Message Chunking
✅ **Implemented.** `chunk_message()` in `whatsapp.py`:
- Limit: 900 characters per message (`WHATSAPP_MSG_LIMIT`)
- Splits at paragraph boundaries (`\n\n`)
- Falls back to line boundaries if single paragraph exceeds limit

### Background Tasks

| Task | Async? | Detail |
|------|--------|--------|
| Periodic cleanup (rate limits + sessions) | ✅ `asyncio.create_task` | Runs hourly |
| Payment polling (MoMo/Moov) | ✅ `asyncio.create_task` | Runs for 30s after payment initiated |
| Ticket PDF generation | ❌ **Synchronous** | Runs in the event loop — blocks during PDF generation |
| OCR (Pytesseract) | ❌ **Synchronous** | `pytesseract.image_to_string` is blocking |
| Claude AI call | ✅ Async via httpx | |
| Whisper transcription | ⚠️ Partially async | File download is async, but `stt.transcribe()` may block |

### Known Bottlenecks

1. ❌ **PDF generation is synchronous** — ReportLab blocks the event loop. Under concurrent users, this will cause latency spikes.
2. ❌ **OCR is synchronous** — Pytesseract blocks the event loop. Should use `asyncio.to_thread()`.
3. ⚠️ **No connection pooling** for MongoDB — Motor creates new connections per operation (Motor handles this internally, but no explicit pool sizing).
4. ⚠️ **No caching** — Airport resolution, flight results, and AI responses are never cached.
5. ⚠️ **Claude AI called for every destination input** — even simple city names like "Paris" trigger an API call.

### Single Points of Failure

1. ❌ **MongoDB** — Single instance, no replica set. If MongoDB goes down, entire service is down.
2. ❌ **Emergent LLM Key** — If key is exhausted or service is down, intent parsing and voice transcription both fail.
3. ❌ **No circuit breaker** — Failed Duffel/payment API calls are retried without backoff pattern.
4. ✅ **WhatsApp API** — Graceful degradation (messages logged when not configured).

---

## 11. UX & CONVERSATION QUALITY

### normalize_response() Function
❌ **NOT IMPLEMENTED.** There is no `normalize_response()` function in the codebase. The `parse_yes_no()` function in `ai.py` serves a similar purpose for yes/no inputs:

```python
yes_words = ["1", "oui", "yes", "ok", "okay", "d'accord", "daccord", "confirmer", "confirm", 
             "bien sur", "exactement", "tout a fait", "parfait", "c'est bon", "volontiers", 
             "absolument", "ouais", "yep", "yup", "ya", "wi"]
no_words = ["2", "non", "no", "nope", "pas", "annuler", "cancel", "refuser", "jamais", "nan", "nah"]
```

⚠️ **This function exists but is NEVER CALLED** in the conversation handlers. All yes/no checks are done with hardcoded comparisons like `text in ["1", "oui", "yes", "ok", "correct"]` in each handler separately. The centralized `parse_yes_no()` is dead code.

### Languages Supported

| Language | Support Level |
|----------|-------------|
| French (fr) | ✅ **Primary** — all messages bilingual, French first |
| English (en) | ✅ **Secondary** — all messages have English variants |

**Language detection:**
```python
french_words = ["je", "veux", "aller", "pour", "le", "la", "un", "une", "merci", "bonjour", "oui", "non", "vol", "billet"]
```
Simple keyword count. If >= 1 French word found, language = "fr". Detected only at IDLE/NEW state.

⚠️ **Very basic detection.** A single French word in an English sentence will trigger French mode. No way for users to switch language mid-conversation.

### XOF/EUR Display Logic
✅ **Consistently displayed** across all price-showing messages:
- Format: `*210.25EUR* (137,900 XOF)`
- Conversion: `ceil(EUR * 655.957 / 5) * 5` (rounded up to nearest 5 XOF)

❌ **No XOF-first display for Benin users.** The primary price is always EUR, with XOF in parentheses. For West African users, XOF should arguably be primary.

### 24h Reminder
❌ **NOT IMPLEMENTED.** No scheduled reminder system. No cron job or background task to remind users of upcoming flights 24 hours before departure.

### Estimated Average Booking Completion Time

Based on the conversation flow (best case, returning user, text input):

| Step | Messages | Time |
|------|----------|------|
| 1. Hello → Travel purpose | 1 exchange | ~10s |
| 2. "For me" → Passenger count | 1 exchange | ~5s |
| 3. "1" → Destination prompt | 1 exchange | ~5s |
| 4. "Paris demain" → Flight results | 1 exchange | ~5-15s (AI + search) |
| 5. "1" → Payment selection | 1 exchange | ~5s |
| 6. "1" (MoMo) → Pre-debit confirm | 1 exchange | ~5s |
| 7. "1" (confirm) → Payment poll | 1 exchange | ~30s |
| 8. Ticket received | automatic | ~5s |
| **Total** | **~8 messages** | **~1-2 minutes** |

For a new user, add ~3-5 messages for enrollment = **~2-3 minutes total**.

### Friction Points in Current Flow

1. ⚠️ **Passenger count is always asked** even though multi-passenger is not supported — adds an unnecessary step.
2. ⚠️ **Travel purpose question** ("for me or someone else?") — always asked for returning users, even if they just want a quick booking.
3. ⚠️ **No quick rebooking** — cannot say "same flight as last time" or "book Paris again".
4. ❌ **No return to previous step** — if user makes a mistake at payment selection, they must go through retry flow rather than simply going back.
5. ⚠️ **30-second payment timeout** is short for real MoMo/Moov where USSD push can take longer.

### Messages That Are Too Long (>900 chars)

The message chunking handles this, but the following messages are at risk of being chunked (which can confuse users):

1. ⚠️ **Pre-debit confirmation** (`handle_payment_method` in `booking.py`) — includes flight details + fare conditions + amount + 3 options. Can exceed 900 chars with long fare conditions.
2. ⚠️ **Flight results** (`format_flight_options_message`) — 3 flights with airline, stops, duration, price each. Typically 400-600 chars, can approach 900 with long airline names.

### Missing Confirmations or Unclear Prompts

1. ❌ **No booking summary after flight selection** before payment method — user goes directly from choosing flight to payment method selection.
2. ⚠️ **Enrollment options 1 and 2 are identical** — confusing for users.
3. ❌ **No "are you sure?" for cancellation of non-refundable tickets** — the "Annuler quand meme (sans remboursement) ?" is adequate but could be more emphatic.
4. ❌ **No estimated arrival time** shown in flight options.

---

## 12. DESIGN & PREMIUM FEEL

### Message Formatting Quality

✅ **Bold text** used consistently for headers and important values (`*Travelio*`, `*210.25EUR*`).
✅ **Line spacing** used to separate sections within messages.
✅ **Numbered options** (1, 2, 3) used consistently for all choices.
❌ **No emoji usage** in business messages (acceptable for professional tone, but competitors use ✈️, 💰, ✅ to improve readability).

**Example of well-formatted message (flight results):**
```
*Travelio -- 3 options trouvees*
Cotonou -> Paris | 2026-03-15

LE PLUS BAS Demo
Air France | Direct
Duree : 3h15
Prix : *210.25EUR* (137,900 XOF)
Taper *1* pour selectionner

LE PLUS RAPIDE Demo
Ethiopian Airlines | 1 escale
Duree : 5h30
Prix : *245.50EUR* (161,100 XOF)
Taper *2* pour selectionner
...
```

### Consistency of Tone

✅ **Consistent formal-but-friendly French** throughout. Uses "vous" (formal) consistently.
✅ **Error messages are polite** — "Je n'ai pas reconnu cette ville" rather than "Invalid input".
⚠️ **Some messages mix formality levels** — "Rebonjour" (casual) vs. "Veuillez patienter" (formal).

### Premium Positioning in Wording

⚠️ **Mixed.** Some messages have premium feel:
- "Votre billet est pret !" (Your ticket is ready!)
- Pre-debit confirmation with full fare breakdown

❌ **Some messages feel generic:**
- "Recherche de vols Cotonou -> Paris..." — could say "Je recherche les meilleurs tarifs..."
- "Paiement confirme !" — could add personalization like "Merci Jean, votre paiement a ete confirme !"
- "Session expiree. Envoyez un message pour recommencer." — abrupt, no warmth.

### Messages That Feel Generic or Robotic

1. ❌ `"Repondez 1, 2 ou 3"` — repeated everywhere without variation.
2. ❌ `"Annule. Envoyez un message pour recommencer."` — cold.
3. ❌ `"Reservation annulee. Envoyez un message pour recommencer."` — could offer alternatives.
4. ❌ `"Recherche indisponible, reessayez."` — too brief for a premium service.
5. ❌ `"Nom invalide. Utilisez uniquement des lettres..."` — sounds like a system error.

### Missing Personalization Opportunities

1. ❌ **No personalized greeting based on time of day** — "Bonjour" / "Bonsoir" based on GMT+1.
2. ❌ **No usage of passenger's first name** in most messages after enrollment.
3. ❌ **No booking history references** — "Vous avez voyage a Paris la derniere fois. Meme destination ?"
4. ❌ **No personalized recommendations** based on travel patterns.
5. ❌ **No celebration messages** — "C'est votre 3eme reservation avec Travelio ! Merci de votre fidelite."

### Overall Impression: Does It Feel Premium?

⚠️ **5/10 — Functional but not premium.** The conversation is clear and gets the job done, but it lacks the warmth, personalization, and delight that would differentiate it from a basic automated system. The pre-debit confirmation with fare conditions is the strongest UX element. The repetitive "Repondez 1, 2 ou 3" prompts and cold error messages bring the experience down.

---

## 13. TICKET GENERATION

### PDF Layout Quality

✅ **Professional layout using ReportLab:**
- "TRAVELIO" header in purple (#6C63FF)
- "Votre billet electronique" subtitle in gray
- BOARDING PASS table with purple header row
- Clean grid layout with passenger name, passport, route, flight, date, category, price, payment method, reference

⚠️ **No airline logo.** Ticket feels generic without carrier branding.
⚠️ **No barcode** (only QR code). Real boarding passes typically have both.

### QR Code

✅ **Present and scannable.** Generated with `qrcode` library.

**QR data content:**
```json
{
  "ref": "TRV-ABC123",
  "passenger": "Dupont Jean",
  "passport": "AB1234567",
  "route": "COO -> CDG",
  "date": "2026-03-15",
  "price": "210.25EUR"
}
```

❌ **QR contains passport number in plaintext.** This is a privacy/security concern — anyone who scans the QR can see the passport number.

### All Required Fields Present

| Field | Present | Value |
|-------|---------|-------|
| Passenger name | ✅ | From passenger profile |
| Passport number | ✅ | From passenger profile (or N/A) |
| Origin | ✅ | City name + IATA code |
| Destination | ✅ | City name + IATA code |
| Flight number | ✅ | Airline + number |
| Date | ✅ | Departure date |
| Category | ✅ | PLUS_BAS / PLUS_RAPIDE / PREMIUM |
| Price | ✅ | EUR + XOF |
| Payment method | ✅ | Operator name |
| Booking reference | ✅ | TRV-XXXXXX |
| **Missing:** Departure time | ❌ | Not shown on ticket |
| **Missing:** Arrival time | ❌ | Not shown on ticket |
| **Missing:** Duration | ❌ | Not shown on ticket |
| **Missing:** Seat number | ❌ | N/A (not assigned) |
| **Missing:** Gate | ❌ | N/A (not assigned) |
| **Missing:** Booking class | ❌ | Not shown |

### Booking ID Format
✅ `TRV-` + 6 random alphanumeric characters (uppercase + digits). Example: `TRV-ABC123`.
Generated by:
```python
def generate_booking_ref() -> str:
    chars = string.ascii_uppercase + string.digits
    return f"TRV-{''.join(random.choices(chars, k=6))}"
```

⚠️ **No collision check.** Theoretically, two bookings could get the same reference (probability low but non-zero with 36^6 = 2.18 billion combinations).

### WhatsApp Delivery
⚠️ **SIMULATED.** WhatsApp document sending implemented in code:
```python
await send_whatsapp_document(phone, f"{APP_BASE_URL}/api/tickets/{ticket_filename}", ticket_filename, ticket_msg)
```
But since WhatsApp is not configured, the document is logged but not actually sent. The PDF is generated and stored at `/app/backend/tickets/`.

### Ticket Invalidation on Cancellation
⚠️ **Partial.** Booking status is set to `"cancelled"` in MongoDB. QR code verification endpoint returns `"valid": false` for cancelled bookings. However:
- ❌ The PDF file remains on disk and accessible via `/api/tickets/{filename}`
- ❌ No "CANCELLED" watermark on the PDF
- ❌ No notification to airline about cancellation (simulated only)

---

## 14. WHAT IS MISSING

This section lists every feature that was specified or implied in the original requirements but is **NOT yet implemented**.

| # | Feature | Status | Detail |
|---|---------|--------|--------|
| 1 | **Real WhatsApp Business API** | ❌ NOT CONFIGURED | `WHATSAPP_PHONE_ID` and `WHATSAPP_TOKEN` are placeholders. No messages are actually sent. |
| 2 | **Real Duffel GDS** | ❌ SANDBOX MOCK | All flights are randomly generated mock data. No real airline data. |
| 3 | **Real payment processing** | ❌ ALL SIMULATED | MoMo, Moov, Stripe all using placeholder keys. No money moves. |
| 4 | **Real refund processing** | ❌ SIMULATED | `process_refund()` logs and returns fake reference. No actual refund API calls. |
| 5 | **Multi-passenger booking** | ❌ STUBBED | Always processes 1 passenger. User sees "coming soon" message. |
| 6 | **Celtiis Cash payment** | ❌ STUBBED | `raise NotImplementedError()` |
| 7 | **Consent flow** | ❌ DEAD STATE | `AWAITING_CONSENT` defined but never entered. No GDPR consent collection. |
| 8 | **24h flight reminder** | ❌ NOT IMPLEMENTED | No scheduled notification system. |
| 9 | **Calendar/date picker** | ❌ NOT IMPLEMENTED | `generate_date_options()` exists but is never called. |
| 10 | **Webhook signature verification** | ❌ NOT IMPLEMENTED | Incoming webhooks are unauthenticated. |
| 11 | **Data export/deletion (GDPR)** | ❌ NOT IMPLEMENTED | No "delete my data" flow. |
| 12 | **Booking data auto-purge** | ❌ NOT IMPLEMENTED | Privacy policy says 24 months, no automation exists. |
| 13 | **Round-trip flights** | ❌ NOT SUPPORTED | Return date extracted by Claude but never used. |
| 14 | **Cabin class selection** | ❌ HARDCODED | Always "economy". |
| 15 | **Modification actually modifies** | ❌ BROKEN | Creates new booking instead of modifying existing. |
| 16 | **Language switching** | ❌ NOT IMPLEMENTED | Language set once at start, no way to switch. |
| 17 | **Whisper correction dictionary** | ❌ NOT IMPLEMENTED | No post-processing for voice transcription. |
| 18 | **Ticket departure/arrival times** | ❌ MISSING | PDF ticket doesn't show departure/arrival times. |
| 19 | **Ticket cancellation watermark** | ❌ NOT IMPLEMENTED | Cancelled tickets still look valid. |
| 20 | **QR code passport privacy** | ❌ NOT ADDRESSED | QR contains passport in plaintext. |
| 21 | **Profile editing** | ❌ NOT IMPLEMENTED | No way to update passenger data. |
| 22 | **Profile deletion** | ❌ NOT IMPLEMENTED | No way to delete saved passenger profiles. |
| 23 | **Booking history view** | ❌ NOT IMPLEMENTED | No "show my bookings" command. |
| 24 | **XOF primary display** | ❌ NOT IMPLEMENTED | EUR is always primary, XOF in parentheses. |

---

## 15. OVERALL SCORES

| Category | Score | Justification |
|----------|-------|--------------|
| **Conversation flow completeness** | **7/10** | 32 states defined, 29 active, complete happy path works. Gaps: 3 dead states, modification doesn't actually modify, no round-trip, no booking history view. |
| **Enrollment & passenger management** | **7/10** | Manual entry fully working and tested. OCR implemented but untestable without WhatsApp. Third-party management solid with 5-profile limit. Gaps: no DOB/expiry in manual flow, no profile editing/deletion. |
| **Flight search & GDS integration** | **5/10** | Architecture is solid with Duffel code ready for production. Categorization logic is smart. But currently 100% mock — no real flights. Fare conditions randomly assigned (misleading). No round-trip, no cabin class. |
| **Payment system** | **5/10** | All 4 payment flows are coded and tested in simulation. Pre-debit confirmation is excellent. But ALL payments are simulated. No card payment timeout. Celtiis Cash stubbed. |
| **Security** | **6/10** | AES-256-GCM encryption for PII is properly implemented. Rate limiting and velocity checks work. Gaps: no webhook verification, weak encryption key, names/phones in plaintext, unauthenticated test endpoints, QR exposes passport. |
| **Legal compliance** | **4/10** | ToS and Privacy Policy pages exist and are well-written. But no consent collection, no data export/deletion, no booking data auto-purge, no age verification. |
| **UX & premium feel** | **5/10** | Bilingual, clear numbered options, pre-debit confirmation is strong. But messages are often robotic, no personalization, unnecessary steps (passenger count), cold error messages. |
| **Performance & reliability** | **6/10** | Async architecture is sound. Rate limiting works. Background payment polling is good. Gaps: synchronous PDF/OCR blocking, no caching, no circuit breaker, single MongoDB instance. |
| **Overall application score** | **6/10** | A well-architected, modular codebase with a complete conversation flow that works end-to-end in simulation. The code quality is high and testing passed 100%. However, the application is fundamentally a **demo** — no real external service is connected. Going from demo to production requires configuring WhatsApp, Duffel, and at least one payment gateway, plus fixing the security and compliance gaps. |

---

## 16. TOP 10 ISSUES TO FIX BEFORE PRODUCTION LAUNCH

### P0 — Critical (Must Fix)

**1. ❌ WhatsApp Webhook Signature Verification**
- **Issue:** Incoming `POST /api/webhook` accepts any payload without verifying `X-Hub-Signature-256`. Any attacker can forge webhook events and trigger actions on behalf of any phone number.
- **Impact:** Complete system compromise — attacker can enroll fake users, make bookings, trigger refunds.
- **Complexity:** Easy (10-15 lines of code)

**2. ❌ Real WhatsApp Business API Configuration**
- **Issue:** `WHATSAPP_PHONE_ID` and `WHATSAPP_TOKEN` are placeholders. No messages reach users.
- **Impact:** **Application is non-functional** — users cannot interact with the bot.
- **Complexity:** Easy (external configuration in Meta Developer Console + env vars)

**3. ❌ Real GDS Integration (Duffel Production Key)**
- **Issue:** All flights are randomly generated mocks. Prices, airlines, schedules, and fare conditions are fictional.
- **Impact:** Users see fake data — cannot book real flights.
- **Complexity:** Easy (replace `duffel_test_placeholder` with real API key)

**4. ❌ Real Payment Gateway Configuration**
- **Issue:** All payments are simulated. No money is actually collected.
- **Impact:** Zero revenue. Bookings appear confirmed but no payment occurred.
- **Complexity:** Medium (requires MoMo sandbox → production migration, Moov API key, Stripe live key)

### P1 — High (Should Fix Before Launch)

**5. ❌ GDPR Consent Collection**
- **Issue:** Users are enrolled and their data stored without explicit consent. `AWAITING_CONSENT` state exists but is never used.
- **Impact:** Legal liability under GDPR/data protection regulations applicable in Benin.
- **Complexity:** Medium (wire up consent state, add ToS link, require "1" before proceeding)

**6. ❌ Modification Flow Creates Duplicate Booking**
- **Issue:** When user "modifies" a booking, the system creates a new booking without cancelling the original. User ends up with two bookings.
- **Impact:** Double charges, duplicate tickets, confused passengers.
- **Complexity:** Medium (need to cancel original booking after new one is confirmed, handle fare difference)

**7. ❌ QR Code Contains Passport Number in Plaintext**
- **Issue:** The QR code on the PDF ticket contains a JSON object with `"passport": "AB1234567"`. Anyone scanning the QR sees the passport number.
- **Impact:** Privacy violation, potential identity theft.
- **Complexity:** Easy (remove or hash passport in QR data, use booking reference only)

**8. ⚠️ Encryption Key Weakness**
- **Issue:** `ENCRYPTION_KEY=travelio_aes256_master_key_2024_prod` is a human-readable string. Key derivation uses simple SHA-256 without salt.
- **Impact:** Predictable key. If `.env` is compromised, all encrypted PII is exposed with minimal effort.
- **Complexity:** Easy (generate random 32-byte key, use PBKDF2 or scrypt)

### P2 — Medium (Fix After Launch)

**9. ❌ Card Payment Has No Timeout**
- **Issue:** If a user selects Google Pay or Apple Pay and never completes the payment, the session stays in `AWAITING_CARD_PAYMENT` indefinitely. The booking stays in "awaiting_payment" forever.
- **Impact:** Ghost bookings accumulate in the database. User must type "annuler" to escape — but they may not know this.
- **Complexity:** Medium (add a background task with 15-minute timeout for card payments)

**10. ❌ Unauthenticated Test/Simulation Endpoints**
- **Issue:** `POST /api/test/simulate`, `GET /api/test/session/{phone}`, `DELETE /api/test/session/{phone}`, `GET /api/test/bookings/{phone}` are all publicly accessible with no authentication.
- **Impact:** Attacker can read any user's session, delete sessions, view booking history, and trigger arbitrary message handling.
- **Complexity:** Easy (add API key check, or disable in production via environment variable)

---

*End of Audit Report*
*Generated: February 2026*
*Codebase version: Travelio v7.0*
*Total files audited: 25 backend modules + 1 frontend module*
*Test status: iteration_7.json — 100% pass rate*
