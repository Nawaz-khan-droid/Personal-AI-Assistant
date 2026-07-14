---
title: JARVIS Voice Assistant
emoji: 🤖
colorFrom: cyan
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# JARVIS Voice Assistant

A real-time voice AI assistant powered by LiveKit, Groq (Llama 3.3 70B), and Deepgram.

## Required Secrets

Set these in **Settings > Variables and secrets** as Repository Secrets:

| Variable | Description |
|---|---|
| `LIVEKIT_API_KEY` | LiveKit Cloud API key |
| `LIVEKIT_API_SECRET` | LiveKit Cloud API secret |
| `LIVEKIT_URL` | LiveKit Cloud WebSocket URL (wss://...) |
| `GROQ_API_KEY` | Groq API key |
| `DEEPGRAM_API_KEY` | Deepgram API key |
| `JARVIS_UI_PASSWORD` | Password to access the UI |

## Optional Variables

| Variable | Default | Description |
|---|---|---|
| `GROQ_LLM_MODEL` | `llama-3.3-70b-versatile` | Groq LLM model |
| `DEEPGRAM_STT_MODEL` | `nova-2` | Deepgram STT model |
| `DEEPGRAM_TTS_MODEL` | `aura-2-neptune-en` | Default TTS voice |
| `TTS_SAMPLE_RATE` | `24000` | TTS audio sample rate |
| `GOOGLE_CLOUD_API_KEY` | _(optional)_ | Enables YouTube search + fact-check tools |
| `SENDGRID_API_KEY` | _(optional)_ | Enables email dispatch tool |
| `JARVIS_EMAIL_IDENTITY` | _(optional)_ | Sender email address for SendGrid |
