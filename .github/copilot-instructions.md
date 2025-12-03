# Discord Esquie Bot - AI Coding Guidelines

## ⚠️ IMPORTANT: Read These Instructions First

**This file contains critical patterns for working with the Discord Esquie Bot codebase. Always reference these patterns when making changes.**

## Project Overview
AI-powered Discord bot built with discord.py that responds to mentions with intelligent AI-generated responses using Pollinations.AI API. Features conversation context tracking, reaction-based message deletion, image processing, and personalized multilingual responses.

## Architecture
- **Package Structure**: Core logic in `esquie_bot/` package; `bot.py` is thin compatibility wrapper
- **Event-Driven**: discord.py event handlers for message processing, reactions, and slash commands
- **AI Integration**: RESTful API calls to Pollinations.AI with conversation history and vision capabilities
- **Docker Logging**: Custom `log()` function with immediate flush for container visibility
- **Async Processing**: Thread pool executors for non-blocking HTTP requests

## Critical Patterns - ALWAYS USE THESE

### Message Response Flow - REQUIRED PATTERN
```python
# 1. Check for mentions or replies to bot messages
is_mention = bot.user.mentioned_in(message)
is_reply_to_bot = message.reference and referenced_msg.author == bot.user

# 2. Build conversation context by following reply chains
conversation_history = await build_conversation_history(message)

# 3. Process images if present
image_descriptions = await get_image_descriptions(message)

# 4. Send thinking message, then edit with AI response
thinking_msg = await message.reply("🤔 Thinking...")
ai_response = await get_ai_response(personalized_content, conversation_history, image_descriptions)
await thinking_msg.edit(content=ai_response)
```

### Conversation Context Building
```python
# Follow Discord reply chains to reconstruct conversation history
async def build_conversation_history(message, max_depth=10):
    history = []
    current_msg = message
    while current_msg and len(history) < max_depth:
        # Only include bot-related messages (mentions or bot responses)
        is_bot_message = current_msg.author == bot.user
        mentions_bot = bot.user.mentioned_in(current_msg)

        if is_bot_message or mentions_bot:
            role = "assistant" if is_bot_message else "user"
            # Clean mentions from user messages for better context
            content = re.sub(r'<@!?{}>'.format(bot.user.id), '', current_msg.content).strip()
            history.insert(0, {"role": role, "content": content})
        # Move up the reply chain
        current_msg = await get_referenced_message(current_msg)
    return history
```

### Image Processing Pipeline
```python
# Process Discord attachments and embeds for AI vision analysis
async def process_image_attachment(attachment):
    if not attachment.content_type.startswith('image/'):
        return None

    # Download and base64 encode image
    image_data = await attachment.read()
    base64_image = base64.b64encode(image_data).decode('utf-8')

    # Call Pollinations.AI vision API
    messages = [
        {"role": "user", "content": [
            {"type": "text", "text": "Describe this image in detail..."},
            {"type": "image_url", "image_url": {
                "url": f"data:{attachment.content_type};base64,{base64_image}"
            }}
        ]}
    ]
    # Return formatted description for AI context
```

### Mention Parsing and Context Enrichment
```python
# Parse Discord mentions and create user mapping for AI context
def parse_discord_mentions(message):
    mention_map = {}
    mention_pattern = r'<@!?(\d+)>'
    for user_id in re.findall(mention_pattern, message.content):
        member = message.guild.get_member(int(user_id))
        if member:
            mention_map[member.display_name] = user_id
    return mention_map

# Enrich prompt with user context
personalized_content = f"[{user_display_name}]: {content}{mention_context}{reference_context}"
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

### Slash Command Pattern
```python
@tree.command(name="image", description="Generate an AI image from a text prompt")
@discord.app_commands.describe(prompt="Describe the image you want to generate")
async def image_command(interaction, prompt: str):
    await interaction.response.defer()  # Defer for long-running operations

    # Use thread pool for HTTP requests
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, lambda: requests.get(url, params=params))

    # Send file attachment with embed
    file = discord.File(image_data, filename=filename)
    embed = discord.Embed(title="🎨 AI Generated Image", description=f"**Prompt:** {prompt}")
    embed.set_image(url=f"attachment://{filename}")
    await interaction.followup.send(embed=embed, file=file)
```

### Docker-Compatible Logging
```python
def log(message: str) -> None:
    """Log with immediate flush for Docker container visibility"""
    print(message)
    sys.stdout.flush()
```

### Error Handling with Multiple Fallbacks
```python
# Try edit first, then reply, then channel send
try:
    await thinking_message.edit(content=ai_response)
except discord.Forbidden:
    try:
        await message.reply(ai_response)
    except discord.Forbidden:
        await message.channel.send(f"{message.author.mention} {ai_response}")
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
3. Invite with "Send Messages", "Read Message History", "Add Reactions", "Use Slash Commands" permissions

## Key Conventions

- **Async HTTP Requests**: Use `asyncio.get_event_loop().run_in_executor()` for non-blocking API calls
- **Message Content Cleaning**: Strip bot mentions with `re.sub(r'<@!?{}>'.format(bot.user.id), '', content)`
- **Context Limits**: Restrict conversation history to last 10 messages to prevent token limits
- **Image Processing**: Handle both attachments and embeds, return formatted descriptions
- **Personalization**: Include user display names and parsed mentions in AI prompts
- **Error Handling**: Multiple fallback strategies (edit → reply → channel send)
- **Mention Processing**: Parse `<@user_id>` patterns, include context in AI prompts
- **Short Message Handling**: Expand prompts < 3 chars with contextual defaults
- **Thread Pool Usage**: Execute synchronous HTTP requests in thread pools to avoid blocking event loop

## Essential Files
- `esquie_bot/main.py` - Core event handlers, AI integration, image processing (437 lines)
- `bot.py` - Compatibility entrypoint wrapper
- `requirements.txt` - discord.py==2.3.2, python-dotenv, requests
- `docker-compose.yml` - Container orchestration with logging
- `Dockerfile` - Python 3.11 slim with proper logging setup