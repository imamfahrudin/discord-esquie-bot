# Discord Esquie Bot

[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)](https://python.org)
[![Discord](https://img.shields.io/badge/Discord-%235865F2.svg?style=for-the-badge&logo=discord&logoColor=white)](https://discord.com)
[![Pollinations.AI](https://img.shields.io/badge/Pollinations.AI-%23FF6B6B.svg?style=for-the-badge&logo=ai&logoColor=white)](https://pollinations.ai)

An AI-powered Discord bot built with Python and discord.py that provides intelligent, multilingual responses using Pollinations.AI. Features advanced conversation context tracking, reaction-based message management, and personalized interactions.

## Features

- 🤖 **AI-Powered Responses**: Uses Pollinations.AI API for natural, intelligent conversations with consistent responses (seeded)
- 💬 **Mention-Based Interaction**: Responds to @mentions with context-aware AI responses
- 🔄 **Chained Conversation Context**: Maintains full conversation history by following Discord reply chains (up to 10 messages)
- 🌍 **Multilingual Support**: Responds in multiple languages including English, Spanish, French, German, Italian, Portuguese, Indonesian, and others
- 🗑️ **Reaction-Based Deletion**: Users can delete bot responses by reacting with X (❌, ✖️, ❎, x, X) emojis
- 👤 **Personalized Interactions**: Uses user display names and properly handles Discord mentions in responses
- 📅 **Time-Aware Responses**: Includes current date and time in AI context for temporal awareness
- 🐳 **Docker Deployment**: Easy containerized deployment with Docker Compose
- ⚙️ **Environment Configuration**: Secure token management via environment variables
- 📝 **Smart Message Processing**: Handles short prompts with contextual expansion
- 📊 **Real-time Logging**: Comprehensive logging visible in Docker containers with immediate flush
- 🔄 **Fallback Error Handling**: Multiple fallback strategies for message delivery (edit → reply → channel send)

## Prerequisites

- Docker and Docker Compose installed
- One or more Discord bot tokens (from Discord Developer Portal)
- Git (for cloning the repository)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/imamfahrudin/discord-esquie-bot.git
cd discord-esquie-bot
```

### 2. Create Discord Bots

For each bot instance you want to run:

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Go to the "Bot" section
4. Click "Add Bot" and confirm
5. Under "Token", click "Copy" to get your bot token

### 3. Configure Environment

Create environment files for each bot instance. The project supports multiple independent bots:

```bash
# Copy the example file for your first bot
cp .env.example .env1

# Edit .env1 and replace 'your_bot_token_here' with your actual bot token
```

For additional bots, create more env files:

```bash
cp .env1 .env2  # Copy settings from first bot
# Edit .env2 with a different bot token and customize other settings if needed
```

Or manually create the `.env` files:

```env
# .env1
DISCORD_BOT_TOKEN=your_first_bot_token_here
BOT_NAME=Esquie-1
BOT_STATUS=First bot instance!

# .env2
DISCORD_BOT_TOKEN=your_second_bot_token_here
BOT_NAME=Esquie-2
BOT_STATUS=Second bot instance!
```

### 4. Set Bot Permissions

In the Discord Developer Portal, ensure each bot has these permissions:
- Send Messages
- Read Message History
- Add Reactions
- Use Slash Commands (optional)

**Note**: This bot uses only basic intents and doesn't require privileged gateway intents.

## Deployment

### Using Docker Compose (Recommended)

The project supports running multiple independent bot instances. Each instance uses its own environment file and runs in a separate container.

```bash
# Build and start all active bot instances
docker-compose up -d

# Start a specific bot instance
docker-compose up -d discord-bot-1

# Start multiple specific instances
docker-compose up -d discord-bot-1 discord-bot-2

# View logs for all bots
docker-compose logs -f

# View logs for a specific bot
docker-compose logs -f discord-bot-1

# Stop all bots
docker-compose down

# Stop a specific bot
docker-compose down discord-bot-1
```

### Adding More Bot Instances

1. Create a new environment file (e.g., `.env3`)
2. Add a new service block in `docker-compose.yml`:

```yaml
discord-bot-3:
  build: .
  container_name: discord-esquie-bot-3
  env_file:
    - .env3
  restart: unless-stopped
  logging:
    driver: "json-file"
    options:
      max-size: "10m"
      max-file: "3"
```

3. Start the new instance: `docker-compose up -d discord-bot-3`

### Local Development

For development with a single instance:

```bash
# Install dependencies
pip install -r requirements.txt

# Run the bot (compatibility entrypoint)
python bot.py

# Or run the package directly:
python -c "from esquie_bot import run; run()"
```

For multiple local instances, run them in separate terminals with different environment variables.

## Usage

The bot listens for messages that mention it (@YourBotName) or replies to its messages. When triggered, it processes the message content and responds with AI-generated replies that maintain conversation context.

### Multiple Bot Instances

You can run multiple bot instances simultaneously, each with different personalities or serving different servers:

- Each bot instance has its own Discord token and can be invited to different servers
- Bots can have different names and status messages for easy identification
- All instances share the same codebase but run in separate containers
- Use different bot names (e.g., "Esquie-1", "Esquie-2") to distinguish them in conversations

### Examples

**Basic Interaction:**
```
User: @YourBot hello!
Bot: Hello! How are you doing today? I'm here to help with any questions you might have!
```

**Multilingual Responses:**
```
User: @YourBot ¿Cómo estás?
Bot: ¡Hola! Estoy muy bien, gracias por preguntar. ¿En qué puedo ayudarte hoy?
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

**Mention Handling:**
```
User: @YourBot tell @John about the meeting
Bot: <@123456789> Hey John! There's a meeting scheduled for tomorrow at 3 PM. Please let me know if you can attend.
```

## Conversation Context

The bot supports natural, chained conversations by following Discord's reply chains and maintaining conversation history. It reconstructs the entire conversation context to provide coherent, context-aware responses.

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

## Reaction-Based Message Management

Users can delete bot responses by reacting to them with X emojis:
- ❌ (cross mark)
- ✖️ (heavy multiplication x)
- ❎ (negative squared cross mark)
- x or X (letter x)

**Only the original user who triggered the bot response can delete it.**

**Example:**
```
User: @YourBot tell me a joke
Bot: Why don't scientists trust atoms? Because they make up everything! 🤣

User: [reacts with ❌ to bot's message]
[Bot's message gets deleted]
```

## Configuration

The bot uses environment variables for configuration. You can create multiple `.env` files for different bot instances (`.env1`, `.env2`, etc.).

### Environment Variables

- `DISCORD_BOT_TOKEN`: Your Discord bot token (required) - Must be unique for each bot instance
- `BOT_NAME`: The name the bot will use in its AI responses (default: "Esquie")
- `BOT_STATUS`: The status message shown in Discord (default: "Losing A Rock Is Better Than Never Having A Rock!")

### Example Configuration Files

```env
# .env1 - First bot instance
DISCORD_BOT_TOKEN=your_first_bot_token_here
BOT_NAME=Esquie-1
BOT_STATUS=First bot instance!

# .env2 - Second bot instance
DISCORD_BOT_TOKEN=your_second_bot_token_here
BOT_NAME=Esquie-2
BOT_STATUS=Second bot instance!
```

### Docker Compose Service Configuration

Each bot instance is defined as a separate service in `docker-compose.yml`:

```yaml
services:
  discord-bot-1:
    build: .
    container_name: discord-esquie-bot-1
    env_file:
      - .env1
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  # discord-bot-2:  # Uncomment to enable second bot
  #   build: .
  #   container_name: discord-esquie-bot-2
  #   env_file:
  #     - .env2
  #   restart: unless-stopped
  #   logging:
  #     driver: "json-file"
  #     options:
  #       max-size: "10m"
  #       max-file: "3"
```

## AI Integration

The bot integrates with [Pollinations.AI](https://pollinations.ai), a free AI platform:

- **API Endpoint**: `https://text.pollinations.ai/openai`
- **Model**: OpenAI-compatible with consistent responses (seed=42)
- **Message Format**: System prompt + user message + conversation history
- **Context Window**: Limited to last 10 messages to prevent token limits
- **Multilingual**: System prompt includes support for multiple languages
- **Temporal Awareness**: Current date/time included in system context
- **Error Handling**: Graceful fallbacks when API is unavailable
- **Rate Limits**: Respects API limitations with 60-second timeouts

## Architecture

- **Package Structure**: Main logic lives in `esquie_bot/main.py`; `bot.py` is a thin entrypoint that calls `esquie_bot.run()` for backward compatibility
- **Event-Driven**: Uses discord.py's event system for message processing and reactions
- **AI Integration**: RESTful API calls to Pollinations.AI with conversation history
- **Multi-Bot Support**: Docker Compose configuration supports multiple independent bot instances, each with its own environment file and container
- **Docker Optimized**: Logging with immediate flush for container visibility
- **Error Resilient**: Multiple fallback strategies (edit → reply → channel send) for message delivery
- **Async Processing**: Non-blocking HTTP requests using thread pools

## Dependencies

- `discord.py==2.3.2` - Discord API wrapper
- `python-dotenv==1.0.0` - Environment variable management
- `requests==2.31.0` - HTTP client for AI API calls

## Troubleshooting

### Bot doesn't respond to mentions
- Make sure the bot has been invited to your server with proper permissions
- Check that the bot token in your `.env` file is correct
- Verify the bot is online: `docker-compose ps`
- For multiple bots, ensure you're mentioning the correct bot instance

### AI responses not working
- Check API connectivity: `docker-compose logs discord-bot-1` (replace with your service name)
- Verify Pollinations.AI service is available
- Look for API error messages in logs

### Permission errors
- Ensure the bot has "Send Messages" permission in your server
- The bot needs "Read Message History" to see mentions and build conversation context
- "Add Reactions" permission is required for reaction-based deletion

### Privileged Intents Error
If you see `PrivilegedIntentsRequired` error:
- The bot code has been updated to avoid requiring privileged intents
- Restart the bot with `docker-compose restart`
- If the error persists, check that you're using the latest bot code

### Reaction deletion not working
- Ensure the bot has "Add Reactions" permission
- Only the original user who triggered the response can delete it
- The bot message must be a reply to the user's message

### Multiple Bot Issues
- Each bot instance needs a unique Discord token
- Make sure container names don't conflict (check `docker-compose ps`)
- Use different bot names/statuses to distinguish instances
- Check logs for each service individually: `docker-compose logs -f discord-bot-1`

### Logs
Check the logs for any errors:
```bash
# All bots
docker-compose logs

# Specific bot instance
docker-compose logs discord-bot-1
```

The bot provides detailed logging including:
- `[STARTUP]`: Bot initialization and connection status
- `[MENTION]`: When users mention the bot
- `[CONTENT]`: Extracted message content
- `[HISTORY]`: Conversation context building
- `[API REQUEST/SUCCESS/ERROR]`: AI API interaction details
- `[REPLY]`: Successful message responses
- `[DELETE]`: Reaction-based message deletion
- `[THINKING]`: Thinking message sent
- `[EDIT/FALLBACK]`: Response delivery methods