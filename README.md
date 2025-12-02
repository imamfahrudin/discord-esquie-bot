# Discord Esquie Bot

[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)](https://python.org)
[![Discord](https://img.shields.io/badge/Discord-%235865F2.svg?style=for-the-badge&logo=discord&logoColor=white)](https://discord.com)

A simple and lightweight Discord bot built with Python and discord.py.

## Features

- Responds to mentions with "Hello [username]!"
- Easy deployment with Docker Compose
- Environment-based configuration
- Lightweight and simple

## Prerequisites

- Docker and Docker Compose installed
- A Discord bot token (from Discord Developer Portal)
- Git (for cloning the repository)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/imamfahrudin/discord-esquie-bot.git
cd discord-esquie-bot
```

### 2. Create a Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Go to the "Bot" section
4. Click "Add Bot" and confirm
5. Under "Token", click "Copy" to get your bot token

### 3. Configure Environment

Create a `.env` file in the project root and add your bot token:

```bash
cp .env.example .env
# Edit .env and replace 'your_bot_token_here' with your actual bot token
```

Or manually create the `.env` file:

```env
DISCORD_BOT_TOKEN=your_actual_bot_token_here
```

### 4. Set Bot Permissions

In the Discord Developer Portal, ensure your bot has these permissions:
- Send Messages
- Read Message History
- Use Slash Commands (optional)

**Note**: This bot uses only basic intents and doesn't require privileged gateway intents.

## Deployment

### Using Docker Compose (Recommended)

```bash
# Build and start the bot
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the bot
docker-compose down
```

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the bot
python bot.py
```

## Usage

The bot listens for messages that mention it (@YourBotName). When mentioned, it replies with:

```
Hello [username]!
```

For example, if a user named "John" mentions the bot, it will reply: "Hello John!"

## Configuration

The bot uses environment variables for configuration:

- `DISCORD_BOT_TOKEN`: Your Discord bot token (required)

## Troubleshooting

### Bot doesn't respond to mentions
- Make sure the bot has been invited to your server with proper permissions
- Check that the bot token in `.env` is correct
- Verify the bot is online: `docker-compose ps`

### Permission errors
- Ensure the bot has "Send Messages" permission in your server
- The bot needs "Read Message History" to see mentions

### Privileged Intents Error
If you see `PrivilegedIntentsRequired` error:
- The bot code has been updated to avoid requiring privileged intents
- Restart the bot with `docker-compose restart`
- If the error persists, check that you're using the latest bot code

### Logs
Check the logs for any errors:
```bash
docker-compose logs discord-bot
```