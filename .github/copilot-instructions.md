# Discord Esquie Bot - AI Coding Guidelines

## Project Overview
Simple Discord bot built with discord.py that responds to mentions with personalized greetings. Single-file architecture with Docker deployment.

## Architecture
- **Single-file design**: All bot logic in `bot.py` using discord.py's event-driven Client architecture
- **Intent-based permissions**: Uses minimal `discord.Intents.default()` - no privileged intents required
- **Environment configuration**: Token management via python-dotenv and `.env` files

## Core Patterns

### Event-Driven Bot Structure
```python
bot = discord.Client(intents=intents)

@bot.event
async def on_ready():
    print(f'Bot is ready! Logged in as {bot.user}')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if bot.user.mentioned_in(message):
        await message.reply(f"Hello {message.author.name}!")
```

### Configuration Management
- **Environment variables**: `DISCORD_BOT_TOKEN` loaded via `python-dotenv`
- **Validation**: Bot exits with clear error if token missing
- **Template**: `.env.example` provides configuration structure

## Development Workflow

### Local Development
```bash
pip install -r requirements.txt
cp .env.example .env  # Add your bot token
python bot.py
```

### Docker Deployment
```bash
docker-compose up -d          # Start bot
docker-compose logs -f        # View logs
docker-compose down           # Stop bot
```

### Bot Setup
1. Create bot at https://discord.com/developers/applications
2. Copy token to `.env` file
3. Invite bot with "Send Messages" permission
4. Bot responds to @mentions with "Hello [username]!"

## Key Files
- `bot.py` - Complete bot implementation with event handlers
- `requirements.txt` - discord.py==2.3.2, python-dotenv==1.0.0
- `Dockerfile` - Python 3.11 slim base image
- `docker-compose.yml` - Container orchestration with logging
- `.env.example` - Configuration template

## Deployment Notes
- **Privileged intents**: Code avoids requiring message content intent
- **Permissions**: Only needs "Send Messages" and "Read Message History"
- **Logging**: Docker logs configured with size limits (10m, 3 files)
- **Restart policy**: `unless-stopped` for reliability