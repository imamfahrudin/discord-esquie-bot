# Discord Esquie Bot - AI Coding Guidelines

## Project Overview
AI-powered Discord bot built with discord.py that responds to mentions with intelligent AI-generated responses using Pollinations.AI API. Single-file architecture with Docker deployment.

## Architecture
- **Single-file design**: All bot logic in `bot.py` using discord.py's event-driven Client architecture
- **AI Integration**: Uses Pollinations.AI API for natural language processing and responses
- **Intent-based permissions**: Uses minimal `discord.Intents.default()` - no privileged intents required
- **Environment configuration**: Token management via python-dotenv and `.env` files
- **Docker logging**: Custom logging function with immediate flush for container visibility

## Core Patterns

### AI-Powered Response Flow with Chained Context
```python
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    # Check for mentions OR replies to bot messages
    is_mention = bot.user.mentioned_in(message)
    is_reply_to_bot = False
    conversation_history = []
    
    # Detect replies to bot messages and build full conversation chain
    if message.reference and message.reference.message_id:
        try:
            referenced_msg = await message.channel.fetch_message(message.reference.message_id)
            if referenced_msg.author == bot.user:
                is_reply_to_bot = True
                # Build complete conversation history by following reply chain
                conversation_history = await build_conversation_history(message)
        except discord.NotFound:
            pass
    
    if not (is_mention or is_reply_to_bot):
        return
    
    # Extract content and get AI response with full conversation context
    content = message.content
    if is_mention:
        content = re.sub(r'<@!?{}>'.format(bot.user.id), '', content).strip()
    
    ai_response = get_ai_response(content, conversation_history)
    await message.reply(ai_response)
```

### Pollinations.AI API Integration with Full Context
```python
def get_ai_response(user_message, conversation_history=None):
    messages = [
        {"role": "system", "content": "You are a helpful AI assistant that responds naturally to user messages."}
    ]
    
    # Add full conversation history
    if conversation_history:
        messages.extend(conversation_history)
    
    messages.append({"role": "user", "content": user_message})
    
    data = {"model": "openai", "messages": messages, "seed": 42}
    
    response = requests.post("https://text.pollinations.ai/openai", 
                           headers={"Content-Type": "application/json"}, 
                           data=json.dumps(data))
    return response.json()['choices'][0]['message']['content']

async def build_conversation_history(message, max_depth=10):
    """Build conversation history by following Discord reply chain"""
    history = []
    current_msg = message
    depth = 0
    
    while current_msg and depth < max_depth:
        # Skip current message, traverse reply chain backwards
        if current_msg.id == message.id:
            current_msg = current_msg.reference.message_id if current_msg.reference else None
            depth += 1
            continue
            
        # Determine role and add to history
        role = "assistant" if current_msg.author == bot.user else "user"
        history.insert(0, {"role": role, "content": current_msg.content})
        
        # Follow reply chain
        if current_msg.reference and current_msg.reference.message_id:
            current_msg = await current_msg.channel.fetch_message(current_msg.reference.message_id)
        else:
            break
            
        depth += 1
    
    return history
```

### Docker-Compatible Logging
```python
def log(message):
    """Log message with immediate flush for Docker visibility"""
    print(message)
    sys.stdout.flush()
```

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
4. Bot responds to @mentions with AI-generated responses

## Key Files
- `bot.py` - Complete bot implementation with AI integration and event handlers
- `requirements.txt` - discord.py==2.3.2, python-dotenv==1.0.0, requests==2.31.0
- `Dockerfile` - Python 3.11 slim base image with PYTHONUNBUFFERED=1
- `docker-compose.yml` - Container orchestration with logging
- `.env.example` - Configuration template

## API Integration Details
- **Provider**: Pollinations.AI (free tier)
- **Endpoint**: `https://text.pollinations.ai/openai`
- **Model**: openai with seed=42 for consistency
- **Message Format**: System + User message structure
- **Error Handling**: Graceful fallbacks for API failures
- **Rate Limiting**: 60-second timeout, respects API limits

## Deployment Notes
- **Privileged intents**: Code avoids requiring message content intent
- **Permissions**: Only needs "Send Messages" and "Read Message History"
- **Logging**: Docker logs configured with size limits (10m, 3 files) and immediate flush
- **Restart policy**: `unless-stopped` for reliability
- **AI Processing**: Handles short prompts by adding context, provides natural responses
- **Chained Conversation Context**: Follows Discord reply chains to maintain full conversation history for coherent multi-turn conversations