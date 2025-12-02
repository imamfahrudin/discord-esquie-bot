# Discord Esquie Bot

[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)](https://python.org)
[![Discord](https://img.shields.io/badge/Discord-%235865F2.svg?style=for-the-badge&logo=discord&logoColor=white)](https://discord.com)
[![Pollinations.AI](https://img.shields.io/badge/Pollinations.AI-%23FF6B6B.svg?style=for-the-badge&logo=ai&logoColor=white)](https://pollinations.ai)

An AI-powered Discord bot built with Python and discord.py that provides intelligent responses using Pollinations.AI.

## Features

- 🤖 **AI-Powered Responses**: Uses Pollinations.AI API for natural, intelligent conversations
- 💬 **Mention-Based Interaction**: Responds to @mentions with context-aware AI responses
- 🔄 **Chained Conversation Context**: Maintains full conversation history by following reply chains
- � **Docker Deployment**: Easy containerized deployment with Docker Compose
- ⚙️ **Environment Configuration**: Secure token management via environment variables
- 📝 **Smart Message Processing**: Handles short prompts and provides contextual responses
- 📊 **Real-time Logging**: Comprehensive logging visible in Docker containers

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

# Run the bot (compatibility entrypoint)
python bot.py

# Or run the package directly:
python -c "from esquie_bot import run; run()"
```

## Usage

The bot listens for messages that mention it (@YourBotName). When mentioned, it processes the message content and responds with AI-generated replies.

### Examples

**Basic Interaction:**
```
User: @YourBot hello!
Bot: Hello! How are you doing today? I'm here to help with any questions you might have!
```

**Contextual Responses:**
```
User: @YourBot what's the weather like?
Bot: I'd be happy to help with weather information! Could you let me know which city you're interested in? I can provide current conditions and forecasts.
```

**Short Prompts:**
```
User: @YourBot hi
Bot: Hello! Someone said 'hi'. Can you respond to that? Hi there! How can I assist you today?
```

## Conversation Context

The bot now supports natural, chained conversations by following Discord's reply chains. When you reply to a bot message, it reconstructs the entire conversation history to provide coherent, context-aware responses.

### Chained Conversation Example

**Multi-turn Conversation with Full Context:**
```
User: @YourBot tell me about Python
Bot: Python is a high-level programming language known for its simplicity and readability. It's widely used for web development, data science, AI, and automation. What specifically would you like to know about Python?

User: [replying to bot] How do I install it?
Bot: To install Python, you can download it from the official website at python.org. They offer installers for Windows, macOS, and Linux. Make sure to check "Add Python to PATH" during installation on Windows. Would you like me to guide you through the installation process?

User: [replying to bot] Yes, show me Windows installation
Bot: Great! For Windows installation, follow these steps:

1. Go to https://python.org/downloads/
2. Click "Download Python 3.x.x" (latest version)
3. Run the installer
4. **Important**: Check "Add Python to PATH" at the bottom
5. Click "Install Now"

After installation, open Command Prompt and type `python --version` to verify. Let me know if you need help with the next steps!

User: [replying to bot] How do I run my first program?
Bot: Excellent! Now that Python is installed, let's create your first program. Here's how to get started:

1. Open Notepad or any text editor
2. Type: `print("Hello, World!")`
3. Save the file as `hello.py`
4. Open Command Prompt in the same folder
5. Type: `python hello.py`

You should see "Hello, World!" printed on the screen. This is the traditional first program in any programming language. What would you like to learn next about Python?
```

**Context-Aware Responses:**
```
User: @YourBot what's the capital of France?
Bot: The capital of France is Paris, often called the "City of Light." It's home to iconic landmarks like the Eiffel Tower and Louvre Museum.

User: [replying to bot] Tell me more about the Eiffel Tower
Bot: The Eiffel Tower is an iron lattice tower located in Paris, France. It was built in 1889 for the World's Fair and stands at 324 meters tall. It's one of the most visited monuments in the world, receiving over 7 million visitors annually. The tower was originally intended to be temporary but became a permanent symbol of Paris.
```

## Configuration

The bot uses environment variables for configuration:

- `DISCORD_BOT_TOKEN`: Your Discord bot token (required)

## AI Integration

The bot integrates with [Pollinations.AI](https://pollinations.ai), a free AI platform:

- **API Endpoint**: `https://text.pollinations.ai/openai`
- **Model**: OpenAI-compatible with consistent responses (seed=42)
- **Message Format**: System prompt + user message for context
- **Error Handling**: Graceful fallbacks when API is unavailable
- **Rate Limits**: Respects API limitations with appropriate timeouts

## Troubleshooting

### Bot doesn't respond to mentions
- Make sure the bot has been invited to your server with proper permissions
- Check that the bot token in `.env` is correct
- Verify the bot is online: `docker-compose ps`

### AI responses not working
- Check API connectivity: `docker-compose logs discord-bot`
- Verify Pollinations.AI service is available
- Look for API error messages in logs

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

The bot provides detailed logging including:
- `[STARTUP]`: Bot initialization and connection status
- `[MENTION]`: When users mention the bot
- `[CONTENT]`: Extracted message content
- `[API REQUEST/SUCCESS/ERROR]`: AI API interaction details
- `[REPLY]`: Successful message responses

- ## Architecture

- **Package**: Main logic lives in `esquie_bot/main.py`; `bot.py` is a thin entrypoint that calls `esquie_bot.run()` for backward compatibility.
- **Event-Driven**: Uses discord.py's event system
- **AI Integration**: RESTful API calls to Pollinations.AI
- **Docker Optimized**: Logging with immediate flush for container visibility
- **Error Resilient**: Graceful handling of API failures and network issues