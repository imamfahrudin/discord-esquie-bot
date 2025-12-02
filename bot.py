import discord
import os
import re
import requests
import sys
import json
from dotenv import load_dotenv

def log(message):
    """Log message with immediate flush for Docker visibility"""
    print(message)
    sys.stdout.flush()

# Load environment variables from .env file
load_dotenv()

# Get bot token from environment variable
TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# Check if token is provided
if not TOKEN:
    log("Error: DISCORD_BOT_TOKEN not found in environment variables")
    log("Please create a .env file with your bot token")
    exit(1)

# Create bot instance with intents
intents = discord.Intents.default()
# Note: message_content intent is privileged and requires approval from Discord
# For a simple mention-response bot, we don't need it

bot = discord.Client(intents=intents)

def get_ai_response(user_message, conversation_history=None):
    """Get response from Pollinations.AI API with full conversation context"""
    try:
        # Use the OpenAI-compatible endpoint
        url = "https://text.pollinations.ai/openai"
        
        # Build messages array starting with system message
        messages = [
            {"role": "system", "content": "You are a helpful AI assistant that responds naturally to user messages."}
        ]
        
        # Add conversation history if available
        if conversation_history:
            messages.extend(conversation_history)
            log(f"[CONTEXT] Added {len(conversation_history)} messages from conversation history")
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        
        # Use seed for consistent responses
        data = {"model": "openai", "messages": messages, "seed": 42}

        log(f"[API REQUEST] POST to {url} with {len(messages)} total messages")
        response = requests.post(url, headers={"Content-Type": "application/json"}, data=json.dumps(data), timeout=60)
        response.raise_for_status()

        result = response.json()['choices'][0]['message']['content'].strip()
        
        # Clean up response if it contains separators (sometimes AI adds extra content after ---)
        if '---' in result:
            log("  > '---' character found. Cleaning response...")
            result = result.split('---')[0].strip()
        
        log(f"[API SUCCESS] Got response ({len(result)} characters)")
        return result
    except requests.RequestException as e:
        log(f"[API ERROR] Request failed: {e}")
        return "Sorry, I'm having trouble connecting to my AI brain right now. Please try again later!"
    except (KeyError, ValueError) as e:
        log(f"[API ERROR] Failed to parse response: {e}")
        return "Oops! I got a response but couldn't understand it. Please try again!"
    except Exception as e:
        log(f"[API ERROR] Unexpected error: {e}")
        return "Oops! Something went wrong. Please try again!"

async def build_conversation_history(message, max_depth=10):
    """Build conversation history by following reply chain"""
    history = []
    current_msg = message
    depth = 0
    
    log(f"[HISTORY] Building conversation history starting from: '{message.content[:50]}...'")
    
    while current_msg and depth < max_depth:
        # Skip the current message being processed (we'll add it separately)
        if current_msg.id == message.id:
            # Move to the referenced message object (not just its ID).
            # previous code set current_msg to an integer ID which later caused
            # AttributeError when accessing attributes like `author`.
            if current_msg.reference and current_msg.reference.message_id:
                try:
                    # fetch the referenced message object so the loop can continue
                    current_msg = await current_msg.channel.fetch_message(current_msg.reference.message_id)
                except discord.NotFound:
                    # referenced message missing -> stop building history
                    current_msg = None
                except Exception as e:
                    log(f"[HISTORY] Error fetching referenced message while skipping current: {e}")
                    current_msg = None
            else:
                current_msg = None
            depth += 1
            continue
            
        try:
            # Determine role based on author
            if current_msg.author == bot.user:
                role = "assistant"
                log(f"[HISTORY] Added bot message: '{current_msg.content[:30]}...'")
            else:
                role = "user"
                log(f"[HISTORY] Added user message: '{current_msg.content[:30]}...'")
            
            # Add message to history (in reverse chronological order for now)
            history.insert(0, {
                "role": role,
                "content": current_msg.content
            })
            
            # Move to the referenced message
            if current_msg.reference and current_msg.reference.message_id:
                current_msg = await current_msg.channel.fetch_message(current_msg.reference.message_id)
            else:
                break
                
        except discord.NotFound:
            log(f"[HISTORY] Referenced message not found at depth {depth}")
            break
        except Exception as e:
            log(f"[HISTORY] Error fetching message at depth {depth}: {e}")
            break
            
        depth += 1
    
    log(f"[HISTORY] Built conversation history with {len(history)} messages")
    return history

@bot.event
async def on_ready():
    """Called when the bot is ready and connected to Discord"""
    log(f"[STARTUP] Bot is ready! Logged in as {bot.user}")
    log(f"[STARTUP] Bot ID: {bot.user.id}")
    log(f"[STARTUP] Connected to {len(bot.guilds)} servers")

@bot.event
async def on_message(message):
    """Called whenever a message is sent in a channel the bot can see"""
    # Don't respond to our own messages
    if message.author == bot.user:
        return

    # Check if the bot is mentioned in the message OR if it's a reply to the bot
    is_mention = bot.user.mentioned_in(message)
    is_reply_to_bot = False
    conversation_history = []

    # Check if this is a reply to one of our messages
    if message.reference and message.reference.message_id:
        try:
            # Fetch the referenced message
            referenced_msg = await message.channel.fetch_message(message.reference.message_id)
            # Check if the referenced message is from the bot
            if referenced_msg.author == bot.user:
                is_reply_to_bot = True
                log(f"[REPLY] User {message.author.name} replied to bot message: '{referenced_msg.content[:50]}...'")
                
                # Build full conversation history
                conversation_history = await build_conversation_history(message)
        except discord.NotFound:
            log(f"[REPLY] Referenced message not found")
        except Exception as e:
            log(f"[REPLY] Error fetching referenced message: {e}")

    # Only respond if it's a mention or a reply to the bot
    if not (is_mention or is_reply_to_bot):
        return

    log(f"[INTERACTION] User {message.author.name} - Mention: {is_mention}, Reply: {is_reply_to_bot}")

    # Extract message content after removing the mention (if it's a mention)
    content = message.content

    if is_mention:
        # Remove the bot mention from the content
        content = re.sub(r'<@!?{}>'.format(bot.user.id), '', content).strip()
        log(f"[CONTENT] Extracted content after mention removal: '{content}'")

    # If there's no content, use a default prompt
    if not content:
        if is_reply_to_bot:
            content = "Please continue our conversation."
        else:
            content = "Hello! Can you introduce yourself?"
        log(f"[DEFAULT] Using default prompt: '{content}'")
    elif len(content.strip()) < 3:
        # Handle very short prompts by adding context
        if is_reply_to_bot:
            content = f"Continuing our conversation: '{content.strip()}'"
        else:
            content = f"Hello! Someone said '{content.strip()}'. Can you respond to that?"
        log(f"[SHORT] Expanded short prompt to: '{content}'")

    # Get AI response with full conversation context
    log(f"[API] Calling Pollinations.AI API with prompt: '{content}'")
    if conversation_history:
        log(f"[CONTEXT] Including {len(conversation_history)} messages from conversation history")
    ai_response = get_ai_response(content, conversation_history)

    log(f"[RESPONSE] AI response: '{ai_response[:100]}...'")

    # Send the AI response (with fallback and logging on failure)
    try:
        await message.reply(ai_response)
        log(f"[REPLY] Sent reply to {message.author.name}")
    except Exception as e:
        log(f"[REPLY] Failed to send reply: {e}")
        # Try a fallback: mention the user in the channel (may still fail if missing perms)
        try:
            await message.channel.send(f"{message.author.mention} {ai_response}")
            log(f"[REPLY] Sent fallback channel message to {message.author.name}")
        except Exception as e2:
            log(f"[REPLY] Fallback send failed: {e2}")

# Run the bot
bot.run(TOKEN)