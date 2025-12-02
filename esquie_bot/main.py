import discord
import os
import re
import requests
import sys
import json
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional


def log(message: str) -> None:
    """Log message with immediate flush (useful in Docker)."""
    print(message)
    sys.stdout.flush()


# Create bot intents and client instance. Event handlers are registered below.
intents = discord.Intents.default()
# Note: message_content intent is privileged and requires approval from Discord.
bot = discord.Client(intents=intents)


def parse_discord_mentions(message: discord.Message) -> Dict[str, str]:
    """Parse Discord mentions in a message and return a mapping of usernames to user IDs."""
    mention_map = {}
    
    # Find all Discord mention patterns: <@id> or <@!id>
    import re
    mention_pattern = r'<@!?(\d+)>'
    mentions = re.findall(mention_pattern, message.content)
    
    for user_id in mentions:
        try:
            # Get the member object to access display name
            member = message.guild.get_member(int(user_id))
            if member:
                # Map display name to user ID for AI context
                mention_map[member.display_name] = user_id
                # Also map username as fallback
                if member.display_name != member.name:
                    mention_map[member.name] = user_id
        except Exception as e:
            log(f"[MENTION] Failed to resolve user ID {user_id}: {e}")
    
    return mention_map


async def get_ai_response(user_message: str, conversation_history: Optional[List[Dict[str, str]]] = None) -> str:
    """Get response from Pollinations.AI API with full conversation context."""
    try:
        url = "https://text.pollinations.ai/openai"

        messages = [
            {"role": "system", "content": f"You are Esquie, a helpful AI assistant that responds naturally to user messages in multiple languages including English, Spanish, French, German, Italian, Portuguese, Indonesian, and others. Match the user's language when possible. Current date and time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}. Try to respond in a single paragraph and avoid complex formatting. When users mention other Discord users in their messages, use Discord mention format <@user_id> in your responses instead of plain usernames."}
        ]

        # Limit conversation history to prevent API token limits (keep last 10 messages)
        if conversation_history:
            limited_history = conversation_history[-10:] if len(conversation_history) > 10 else conversation_history
            messages.extend(limited_history)
            log(f"[CONTEXT] Added {len(limited_history)} messages from conversation history (limited from {len(conversation_history)})")

        messages.append({"role": "user", "content": user_message})

        data = {"model": "openai", "messages": messages, "seed": 42}

        log(f"[API REQUEST] POST to {url} with {len(messages)} total messages")
        # Run HTTP request in thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: requests.post(url, headers={"Content-Type": "application/json"}, data=json.dumps(data), timeout=60))
        response.raise_for_status()

        result = response.json()['choices'][0]['message']['content'].strip()

        # Clean response artifacts (keep minimal cleaning)
        if '---' in result:
            log("  > '---' character found. Cleaning response...")
            result = result.split('---')[0].strip()

        log(f"[API SUCCESS] Got response ({len(result)} characters)")
        return result
    except requests.Timeout:
        log("[API ERROR] Request timed out")
        return "Sorry, the AI is taking too long to respond. Please try again!"
    except requests.RequestException as e:
        log(f"[API ERROR] Request failed: {e}")
        return "Sorry, I'm having trouble connecting to my AI brain right now. Please try again later!"
    except (KeyError, ValueError) as e:
        log(f"[API ERROR] Failed to parse response: {e}")
        return "Oops! I got a response but couldn't understand it. Please try again!"
    except Exception as e:
        log(f"[API ERROR] Unexpected error: {e}")
        return "Oops! Something went wrong. Please try again!"


async def build_conversation_history(message: discord.Message, max_depth: int = 10) -> List[Dict[str, str]]:
    """Build conversation history by following reply chain, only including bot-related messages."""
    history = []
    current_msg = message
    depth = 0

    log(f"[HISTORY] Building conversation history starting from: '{message.content[:50]}...'")

    while current_msg and depth < max_depth:
        # Skip the current message (it's the new user input)
        if current_msg.id == message.id:
            if current_msg.reference and current_msg.reference.message_id:
                try:
                    current_msg = await current_msg.channel.fetch_message(current_msg.reference.message_id)
                    depth += 1
                    continue
                except discord.NotFound:
                    log("[HISTORY] Referenced message not found while skipping current message")
                    break
                except Exception as e:
                    log(f"[HISTORY] Error fetching referenced message while skipping current: {e}")
                    break
            else:
                break

        # Only include messages that are part of the bot conversation
        is_bot_message = current_msg.author == bot.user
        mentions_bot = bot.user.mentioned_in(current_msg)

        if is_bot_message or mentions_bot:
            role = "assistant" if is_bot_message else "user"
            content = current_msg.content

            # Clean mentions from user messages for better context
            if not is_bot_message and mentions_bot:
                content = re.sub(r'<@!?{}>'.format(bot.user.id), '', content).strip()

            history.insert(0, {"role": role, "content": content})
            log(f"[HISTORY] Added {role} message: '{content[:30]}...'")
        else:
            log(f"[HISTORY] Skipping unrelated message from {current_msg.author.name}")

        # Move to the next message in the reply chain
        if current_msg.reference and current_msg.reference.message_id:
            try:
                current_msg = await current_msg.channel.fetch_message(current_msg.reference.message_id)
            except discord.NotFound:
                log(f"[HISTORY] Referenced message not found at depth {depth}")
                break
            except Exception as e:
                log(f"[HISTORY] Error fetching message at depth {depth}: {e}")
                break
        else:
            break

        depth += 1

    log(f"[HISTORY] Built conversation history with {len(history)} messages")
    return history


@bot.event
async def on_ready():
    """Called when the bot is ready and connected to Discord."""
    log(f"[STARTUP] Bot is ready! Logged in as {bot.user}")
    log(f"[STARTUP] Bot ID: {bot.user.id}")
    log(f"[STARTUP] Connected to {len(bot.guilds)} servers")
    
    # Set bot status
    await bot.change_presence(activity=discord.Game(name="Losing A Rock Is Better Than Never Having A Rock!"))
    log("[STARTUP] Bot status updated")


@bot.event
async def on_message(message):
    """Called whenever a message is sent in a channel the bot can see."""
    # Prevent responding to own messages
    if message.author == bot.user:
        return

    # Skip messages without content (embeds, files, etc.)
    if not message.content and not message.reference:
        return

    is_mention = bot.user.mentioned_in(message)
    is_reply_to_bot = False
    conversation_history = []
    referenced_content = ""
    
    # Check if this is a reply to one of our messages
    if message.reference and message.reference.message_id:
        try:
            referenced_msg = await message.channel.fetch_message(message.reference.message_id)
            if referenced_msg.author == bot.user:
                is_reply_to_bot = True
                log(f"[REPLY] User {message.author.name} replied to bot message: '{referenced_msg.content[:50]}...'")
                conversation_history = await build_conversation_history(message)
            else:
                # If mentioning bot in reply to another user's message, include that message for context
                if is_mention:
                    referenced_content = referenced_msg.content
                    log(f"[REPLY] User {message.author.name} replied to {referenced_msg.author.name}'s message with bot mention: '{referenced_msg.content[:50]}...'")
        except discord.NotFound:
            log("[REPLY] Referenced message not found - might have been deleted")
        except discord.Forbidden:
            log("[REPLY] Cannot access referenced message - permission issue")
        except Exception as e:
            log(f"[REPLY] Error fetching referenced message: {e}")

    # Only respond to mentions or replies to bot messages
    if not (is_mention or is_reply_to_bot):
        return

    log(f"[INTERACTION] User {message.author.name} - Mention: {is_mention}, Reply: {is_reply_to_bot}")

    content = message.content

    # Clean up the content
    if is_mention:
        content = re.sub(r'<@!?{}>'.format(bot.user.id), '', content).strip()
        log(f"[CONTENT] Extracted content after mention removal: '{content}'")

    # Handle empty or very short content
    if not content:
        if is_reply_to_bot:
            content = "Please continue our conversation."
        else:
            content = "Hello! Can you introduce yourself?"
        log(f"[DEFAULT] Using default prompt: '{content}'")
    elif len(content.strip()) < 3:
        if is_reply_to_bot:
            content = f"Continuing our conversation: '{content.strip()}'"
        else:
            content = f"Hello! Someone said '{content.strip()}'. Can you respond to that?"
        log(f"[SHORT] Expanded short prompt to: '{content}'")

    # Get AI response
    log(f"[API] Calling Pollinations.AI API with prompt: '{content}'")
    if conversation_history:
        log(f"[CONTEXT] Including {len(conversation_history)} messages from conversation history")

    # Include user's display name (nickname) in the prompt for personalization
    user_display_name = message.author.display_name
    
    # Parse Discord mentions and create context
    mention_map = parse_discord_mentions(message)
    mention_context = ""
    if mention_map:
        mention_list = [f"{name}({user_id})" for name, user_id in mention_map.items()]
        mention_context = f" [Mentioned users: {', '.join(mention_list)}]"
        log(f"[MENTION] Found mentions: {mention_context}")
    
    # Include referenced message content if replying to another user's message with bot mention
    reference_context = ""
    if referenced_content:
        reference_context = f" [Replying to: {referenced_content}]"
        log(f"[CONTEXT] Including referenced message: '{referenced_content[:50]}...'")
    
    personalized_content = f"[{user_display_name}]: {content}{mention_context}{reference_context}"

    ai_response = await get_ai_response(personalized_content, conversation_history)

    if not ai_response:
        log("[ERROR] Got empty response from AI")
        ai_response = "I apologize, but I couldn't generate a response right now. Please try again!"

    log(f"[RESPONSE] AI response: '{ai_response[:100]}...'")

    # Try to reply, with fallback to channel send
    try:
        await message.reply(ai_response)
        log(f"[REPLY] Sent reply to {message.author.name}")
    except discord.Forbidden:
        log("[REPLY] Cannot reply - missing permissions")
        try:
            await message.channel.send(f"{message.author.mention} {ai_response}")
            log(f"[REPLY] Sent fallback channel message to {message.author.name}")
        except discord.Forbidden:
            log("[REPLY] Cannot send messages in this channel")
        except Exception as e2:
            log(f"[REPLY] Fallback send failed: {e2}")
    except Exception as e:
        log(f"[REPLY] Reply failed: {e}")
        try:
            await message.channel.send(f"{message.author.mention} {ai_response}")
            log(f"[REPLY] Sent fallback channel message to {message.author.name}")
        except Exception as e2:
            log(f"[REPLY] Fallback send failed: {e2}")


def run(token: Optional[str] = None) -> None:
    """Run the Discord bot. If token is None, read from DISCORD_BOT_TOKEN env var (after loading .env)."""
    load_dotenv()
    if token is None:
        token = os.getenv('DISCORD_BOT_TOKEN')

    if not token:
        log("Error: DISCORD_BOT_TOKEN not found in environment variables")
        log("Please create a .env file with your bot token or pass the token to run()")
        sys.exit(1)

    if not token.strip():
        log("Error: DISCORD_BOT_TOKEN is empty")
        sys.exit(1)

    log("Starting bot...")
    try:
        bot.run(token)
    except discord.LoginFailure:
        log("Error: Invalid bot token")
        sys.exit(1)
    except Exception as e:
        log(f"Error starting bot: {e}")
        sys.exit(1)
