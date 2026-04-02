# Miniclaw

A lightweight personal AI assistant framework that connects Claude AI to messaging platforms (Telegram, WhatsApp, Web) with tool integrations (Gmail, Google Calendar, and more).

## Features

- Multi-channel support: Telegram, WhatsApp, Web chat
- Tool integrations: Gmail, Google Calendar
- Scheduled tasks (cron)
- Memory and workspace per user
- Extensible plugin/skill system

## Quick Start with Docker

```bash
# Download setup files
curl -O https://raw.githubusercontent.com/tringv8/miniclaw/main/docker/Dockerfile
curl -O https://raw.githubusercontent.com/tringv8/miniclaw/main/docker/docker-compose.yml
curl -O https://raw.githubusercontent.com/tringv8/miniclaw/main/docker/.env.example

# Configure
mv .env.example .env
# Edit .env and fill in your API keys

# Run
docker compose up -d --build
```

Open http://localhost:18801 in your browser.

## Configuration

Copy `.env.example` to `.env` and fill in:

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Claude API key (required) |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token (optional) |

## License

MIT
