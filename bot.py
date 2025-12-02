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

def get_ai_response(user_message, previous_bot_message=None):
    """Get response from Pollinations.AI API"""
    try:
        # Use the OpenAI-compatible endpoint
        url = "https://text.pollinations.ai/openai"
        
        # Build messages array with system and user messages
        messages = [
            {"role": "system", "content": "You are a helpful AI assistant that responds naturally to user messages."}
        ]
        
        # Add previous bot message as assistant role if available
        if previous_bot_message:
            messages.append({"role": "assistant", "content": previous_bot_message})
            log(f"[CONTEXT] Added previous bot message to conversation")
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        
        # Use seed for consistent responses
        data = {"model": "openai", "messages": messages, "seed": 42}

        log(f"[API REQUEST] POST to {url}")
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
    previous_bot_message = None

    # Check if this is a reply to one of our messages
    if message.reference and message.reference.message_id:
        try:
            # Fetch the referenced message
            referenced_msg = await message.channel.fetch_message(message.reference.message_id)
            # Check if the referenced message is from the bot
            if referenced_msg.author == bot.user:
                is_reply_to_bot = True
                previous_bot_message = referenced_msg.content
                log(f"[REPLY] User {message.author.name} replied to bot message: '{previous_bot_message[:50]}...'")
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

    # Get AI response with conversation context
    log(f"[API] Calling Pollinations.AI API with prompt: '{content}'")
    if previous_bot_message:
        log(f"[CONTEXT] Including previous bot message in conversation")
    ai_response = get_ai_response(content, previous_bot_message)

    log(f"[RESPONSE] AI response: '{ai_response[:100]}...'")

    # Send the AI response
    await message.reply(ai_response)
    log(f"[REPLY] Sent reply to {message.author.name}")

# Run the bot
bot.run(TOKEN)