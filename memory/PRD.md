# Travelioo — Product Requirements Document

## Original Problem Statement
Travelioo is a premium AI travel booking agent for WhatsApp, Telegram, and Webchat focused on the African market (Benin, Senegal, etc.). All user-facing text is in French.

## Core Features (Implemented)
- Multi-channel: WhatsApp Cloud API, Telegram Bot API, Webchat API
- Duffel GDS integration: one-way & round-trip flights, unified PDF tickets
- Shadow Profiles with AES-256-GCM encryption
- Passport OCR (no strict format validation)
- Multi-lingual auto-detection by phone country code
- Telegram Premium UI (MarkdownV2 + Inline Keyboards)
- Voice IO: OpenAI Whisper STT (with ffmpeg OGG→MP3) + OpenAI TTS replies
- Modular payment drivers: Celtiis, MTN MoMo, Moov Money, Stripe (all MOCK locally)
- CORS-enabled Webchat endpoints `/api/webchat/message` and `/api/webchat/session/{id}`

## Architecture
- FastAPI backend + MongoDB
- /app/backend/{server.py, routes/, services/, conversation/, payment_drivers/}
- Dockerfile installs ffmpeg for audio conversion

## Recent Changes (2026-04-29)
- Pre-demo regression sprint:
  - Fixed `NameError: name 'db' is not defined` in `conversation/handler.py` (added `from database import db`)
  - Installed `ffmpeg` in runtime + confirmed in Dockerfile
  - Added placeholder-value detection to `services/whisper.py` and `services/tts_service.py` (skip `your_*_here` style placeholders, fall back to EMERGENT_LLM_KEY)
  - Added explicit SIG-DEBUG log line in `routes/webhook.py` with `secret_first10`, `sig_received_first10`, `sig_expected_first10`, `secret_len`, `payload_len` to diagnose Meta App Secret mismatches in Railway

## Known Demo-Time Notes
- TTS via direct OpenAI API requires a real `OPENAI_API_KEY`; EMERGENT_LLM_KEY proxy is incompatible with the audio TTS endpoint. Text replies still work.
- Railway `WHATSAPP_WEBHOOK_SECRET` must equal Meta App Secret (32-char hex from App Settings → Basic), NOT the verify token.

## Backlog (P1/P2)
- Refactor `handler.py` post-message hooks into a unified `send_response()` dispatcher (Part 9 of the prior Mega Sprint)
- Optional React frontend that consumes `/api/webchat/message` for a website chat widget
