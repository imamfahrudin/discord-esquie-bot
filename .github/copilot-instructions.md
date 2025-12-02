# Discord Esquie Bot - AI Coding Guidelines

## ⚠️ IMPORTANT: Read These Instructions First

**This file contains critical patterns for working with the Discord Esquie Bot codebase. Always reference these patterns when making changes.**

## Project Overview
AI-powered Discord bot built with discord.py that responds to mentions with intelligent AI-generated responses using Pollinations.AI API. Features conversation context tracking, reaction-based message deletion, and personalized multilingual responses.

## Architecture
- **Package Structure**: Core logic in `esquie_bot/` package; `bot.py` is thin compatibility wrapper
- **Event-Driven**: discord.py event handlers for message processing and reactions
- **AI Integration**: RESTful API calls to Pollinations.AI with conversation history
- **Docker Logging**: Custom `log()` function with immediate flush for container visibility

## Critical Patterns - ALWAYS USE THESE

### Message Response Flow - REQUIRED PATTERN
```python
# 1. Check for mentions or replies to bot messages
is_mention = bot.user.mentioned_in(message)
is_reply_to_bot = message.reference and referenced_msg.author == bot.user

# 2. Build conversation context by following reply chains
conversation_history = await build_conversation_history(message)

# 3. Send thinking message, then edit with AI response
thinking_msg = await message.reply("🤔 Thinking...")
ai_response = await get_ai_response(personalized_content, conversation_history)
await thinking_msg.edit(content=ai_response)
```

### Conversation Context Building
```python
# Follow Discord reply chains to reconstruct conversation history
async def build_conversation_history(message, max_depth=10):
    history = []
    current_msg = message
    while current_msg and len(history) < max_depth:
        if current_msg.author == bot.user or bot.user.mentioned_in(current_msg):
            role = "assistant" if current_msg.author == bot.user else "user"
            history.insert(0, {"role": role, "content": current_msg.content})
        # Move up the reply chain
        current_msg = await get_referenced_message(current_msg)
    return history
```

### Reaction-Based Deletion
```python
@bot.event
async def on_reaction_add(reaction, user):
    # Allow original user to delete bot responses with X reactions
    if (str(reaction.emoji) in ['❌', '✖️', '❎', 'x', 'X'] and
        reaction.message.author == bot.user and
        reaction.message.reference):
        original_msg = await reaction.message.channel.fetch_message(
            reaction.message.reference.message_id)
        if original_msg.author == user:
            await reaction.message.delete()
```

### Docker-Compatible Logging
```python
def log(message: str) -> None:
    """Log with immediate flush for Docker container visibility"""
    print(message)
    sys.stdout.flush()
```

## Development Workflow

### Local Development
```bash
pip install -r requirements.txt
cp .env.example .env  # Add Discord bot token
python bot.py  # Or: python -c "from esquie_bot import run; run()"
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
3. Invite with "Send Messages", "Read Message History", "Add Reactions" permissions

## Key Conventions

- **Error Handling**: Multiple fallback strategies (edit → reply → channel send)
- **Mention Processing**: Parse `<@user_id>` patterns, include context in AI prompts
- **Context Enrichment**: Add user display names, mention maps, referenced content
- **API Integration**: Pollinations.AI with system prompt + conversation history
- **Short Message Handling**: Expand prompts < 3 chars with contextual defaults

## Essential Files
- `esquie_bot/main.py` - Core event handlers and AI integration
- `bot.py` - Compatibility entrypoint wrapper
- `requirements.txt` - discord.py==2.3.2, python-dotenv, requests
- `docker-compose.yml` - Container orchestration with logging