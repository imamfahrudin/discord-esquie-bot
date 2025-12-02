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
import base64
from urllib.parse import quote
from io import BytesIO


def log(message: str) -> None:
    """Log message with immediate flush (useful in Docker)."""
    print(message)
    sys.stdout.flush()


# Create bot intents and client instance. Event handlers are registered below.
intents = discord.Intents.default()
# Note: message_content intent is privileged and requires approval from Discord.
bot = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(bot)


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


async def process_image_attachment(attachment: discord.Attachment) -> Optional[str]:
    """Process a Discord image attachment and return AI description."""
    try:
        # Check if it's an image
        if not attachment.content_type or not attachment.content_type.startswith('image/'):
            return None
            
        log(f"[IMAGE] Processing image attachment: {attachment.filename} ({attachment.content_type})")
        
        # Download image data
        image_data = await attachment.read()
        
        # Convert to base64
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        # Use Pollinations.AI vision API
        url = "https://text.pollinations.ai/openai"
        
        messages = [
            {
                "role": "user", 
                "content": [
                    {
                        "type": "text",
                        "text": "Describe this image in detail. Be specific about what you see, including any text, objects, people, colors, and context. Keep the description concise but informative."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{attachment.content_type};base64,{base64_image}"
                        }
                    }
                ]
            }
        ]
        
        data = {
            "model": "openai",  # Vision-capable model
            "messages": messages,
            "max_tokens": 300,
            "seed": 42
        }
        
        log(f"[IMAGE API] Sending image to vision API")
        
        # Run HTTP request in thread pool
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: requests.post(
            url, 
            headers={"Content-Type": "application/json"}, 
            data=json.dumps(data), 
            timeout=60
        ))
        response.raise_for_status()
        
        result = response.json()['choices'][0]['message']['content'].strip()
        log(f"[IMAGE API] Got description ({len(result)} characters)")
        
        return f"[Image: {attachment.filename}] {result}"
        
    except Exception as e:
        log(f"[IMAGE ERROR] Failed to process image {attachment.filename}: {e}")
        return f"[Image: {attachment.filename}] (Could not analyze this image)"


async def get_image_descriptions(message: discord.Message) -> List[str]:
    """Extract and describe all images in a message."""
    descriptions = []
    
    if message.attachments:
        for attachment in message.attachments:
            description = await process_image_attachment(attachment)
            if description:
                descriptions.append(description)
    
    # Also check for image embeds (links that Discord auto-embeds)
    if message.embeds:
        for embed in message.embeds:
            if embed.type == 'image' and embed.url:
                log(f"[IMAGE] Found embedded image: {embed.url}")
                descriptions.append(f"[Embedded Image] {embed.url}")
    
    return descriptions


async def get_ai_response(user_message: str, conversation_history: Optional[List[Dict[str, str]]] = None, image_descriptions: Optional[List[str]] = None) -> str:
    """Get response from Pollinations.AI API with full conversation context and image descriptions."""
    try:
        url = "https://text.pollinations.ai/openai"

        messages = [
            {"role": "system", "content": f"You are Esquie, a helpful AI assistant that responds naturally to user messages in multiple languages including English, Spanish, French, German, Italian, Portuguese, Indonesian, and others. Match the user's language when possible. Current date and time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}. Try to respond in a single paragraph and avoid complex formatting. When users mention other Discord users in their messages, use Discord mention format <@user_id> in your responses instead of plain usernames. You can also see and describe images that users share."}
        ]

        # Limit conversation history to prevent API token limits (keep last 10 messages)
        if conversation_history:
            limited_history = conversation_history[-10:] if len(conversation_history) > 10 else conversation_history
            messages.extend(limited_history)
            log(f"[CONTEXT] Added {len(limited_history)} messages from conversation history (limited from {len(conversation_history)})")

        # Build user message with image descriptions
        full_user_message = user_message
        if image_descriptions:
            image_context = "\n\n".join(image_descriptions)
            full_user_message = f"{user_message}\n\n{image_context}"
            log(f"[IMAGES] Added {len(image_descriptions)} image descriptions to prompt")

        messages.append({"role": "user", "content": full_user_message})

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
    
    # Sync slash commands
    try:
        synced = await tree.sync()
        log(f"[STARTUP] Synced {len(synced)} slash commands")
    except Exception as e:
        log(f"[STARTUP] Failed to sync slash commands: {e}")
    
    # Set bot status
    await bot.change_presence(activity=discord.Game(name="Losing A Rock Is Better Than Never Having A Rock!"))
    log("[STARTUP] Bot status updated")


@bot.event
async def on_reaction_add(reaction, user):
    """Called when a reaction is added to a message."""
    # Ignore bot's own reactions
    if user == bot.user:
        return
    
    # Check if reaction is X mark (❌ or :x:)
    if str(reaction.emoji) not in ['❌', '✖️', '❎', 'x', 'X']:
        return
    
    # Check if the message is from the bot
    if reaction.message.author != bot.user:
        return
    
    # Check if the bot message is replying to the reacting user
    if not reaction.message.reference or not reaction.message.reference.message_id:
        log(f"[DELETE] Bot message is not a reply, ignoring X reaction from {user.name}")
        return
    
    try:
        # Get the original message that the bot replied to
        original_message = await reaction.message.channel.fetch_message(reaction.message.reference.message_id)
        
        # Only allow the original user to delete their bot response
        if original_message.author != user:
            log(f"[DELETE] User {user.name} tried to delete bot message but is not the original requester")
            return
            
    except discord.NotFound:
        log("[DELETE] Referenced original message not found")
        return
    except discord.Forbidden:
        log("[DELETE] Cannot access referenced message - permission issue")
        return
    except Exception as e:
        log(f"[DELETE] Error checking original message: {e}")
        return
    
    try:
        await reaction.message.delete()
        log(f"[DELETE] Deleted bot message due to X reaction from original user {user.name}")
    except discord.Forbidden:
        log(f"[DELETE] Cannot delete message - missing permissions for user {user.name}")
    except discord.NotFound:
        log("[DELETE] Message already deleted")
    except Exception as e:
        log(f"[DELETE] Error deleting message: {e}")


@bot.event
async def on_message(message):
    """Called whenever a message is sent in a channel the bot can see."""
    # Prevent responding to own messages
    if message.author == bot.user:
        return

    # Skip messages without content, attachments, or embeds (unless they're replies)
    has_content = message.content or message.attachments or message.embeds
    if not has_content and not message.reference:
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

    # Only respond to mentions or replies to bot messages that contain new images
    has_new_images = bool(message.attachments or message.embeds)
    should_respond = is_mention or (is_reply_to_bot and has_new_images)
    
    if not should_respond:
        log(f"[SKIP] Ignoring reply without mention or new images from {message.author.name}")
        return

    log(f"[INTERACTION] User {message.author.name} - Mention: {is_mention}, Reply: {is_reply_to_bot}")

    content = message.content

    # Clean up the content
    if is_mention:
        content = re.sub(r'<@!?{}>'.format(bot.user.id), '', content).strip()
        log(f"[CONTENT] Extracted content after mention removal: '{content}'")

    # Handle empty or very short content (but allow if there are images)
    has_images = bool(message.attachments or message.embeds)
    if not content:
        if has_images:
            content = "Please describe this image(s)."
            log(f"[IMAGES] Using image description prompt for message with attachments")
        elif is_reply_to_bot:
            content = "Please continue our conversation."
        else:
            content = "Hello! Can you introduce yourself?"
        log(f"[DEFAULT] Using default prompt: '{content}'")
    elif len(content.strip()) < 3 and not has_images:
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

    # Process any images in the message
    image_descriptions = []
    if message.attachments or message.embeds:
        log("[IMAGES] Message contains attachments/embeds, processing images...")
        image_descriptions = await get_image_descriptions(message)
        if image_descriptions:
            log(f"[IMAGES] Processed {len(image_descriptions)} images")

    # Send thinking message first
    thinking_message = await message.reply("🤔 Thinking...")
    log(f"[THINKING] Sent thinking message as reply to user {message.author.name}")

    ai_response = await get_ai_response(personalized_content, conversation_history, image_descriptions)

    if not ai_response:
        log("[ERROR] Got empty response from AI")
        ai_response = "I apologize, but I couldn't generate a response right now. Please try again!"

    log(f"[RESPONSE] AI response: '{ai_response[:100]}...'")

    # Edit the thinking message with the actual response
    try:
        await thinking_message.edit(content=ai_response)
        log(f"[EDIT] Edited thinking message with AI response for {message.author.name}")
    except discord.Forbidden:
        log("[EDIT] Cannot edit message - missing permissions")
        # Fallback to sending a new reply message
        try:
            await message.reply(ai_response)
            log(f"[FALLBACK] Sent reply fallback for {message.author.name}")
        except discord.Forbidden:
            log("[FALLBACK] Cannot reply in this channel")
            try:
                await message.channel.send(f"{message.author.mention} {ai_response}")
                log(f"[FALLBACK] Sent channel message fallback for {message.author.name}")
            except Exception as e:
                log(f"[FALLBACK] Channel send failed: {e}")
        except Exception as e:
            log(f"[FALLBACK] Reply failed: {e}")
            try:
                await message.channel.send(f"{message.author.mention} {ai_response}")
                log(f"[FALLBACK] Sent channel message fallback for {message.author.name}")
            except Exception as e2:
                log(f"[FALLBACK] Channel send failed: {e2}")
    except Exception as e:
        log(f"[EDIT] Edit failed: {e}")
        # Fallback to sending a new reply message
        try:
            await message.reply(ai_response)
            log(f"[FALLBACK] Sent reply fallback for {message.author.name}")
        except Exception as e2:
            log(f"[FALLBACK] Reply failed: {e2}")
            try:
                await message.channel.send(f"{message.author.mention} {ai_response}")
                log(f"[FALLBACK] Sent channel message fallback for {message.author.name}")
            except Exception as e3:
                log(f"[FALLBACK] Channel send failed: {e3}")


@tree.command(name="image", description="Generate an AI image from a text prompt")
@discord.app_commands.describe(prompt="Describe the image you want to generate")
async def image_command(interaction: discord.Interaction, prompt: str):
    """Generate an AI image using Pollinations.AI based on user prompt."""
    try:
        await interaction.response.defer()  # Defer response since image generation takes time
        
        log(f"[IMAGE_CMD] User {interaction.user.name} requested image with prompt: '{prompt}'")
        
        # Encode the prompt to handle spaces and special characters
        encoded_prompt = quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}"
        
        # Customize the image size and model
        params = {
            "width": 1024,
            "height": 1024,
            "model": "flux",
            "seed": 42  # For consistent results
        }
        
        log(f"[IMAGE_CMD] Making request to {url} with params: {params}")
        
        # Make the request in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: requests.get(
            url, 
            params=params, 
            timeout=60
        ))
        response.raise_for_status()
        
        # Create a file-like object from the response content
        image_data = BytesIO(response.content)
        image_data.seek(0)
        
        # Create a Discord file attachment
        filename = f"generated_image_{int(datetime.now().timestamp())}.png"
        file = discord.File(image_data, filename=filename)
        
        # Send the image as an embed with the prompt
        embed = discord.Embed(
            title="🎨 AI Generated Image",
            description=f"**Prompt:** {prompt}",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.set_image(url=f"attachment://{filename}")
        embed.set_footer(text=f"Generated by {interaction.user.display_name}")
        
        await interaction.followup.send(embed=embed, file=file)
        log(f"[IMAGE_CMD] Successfully sent generated image to {interaction.user.name}")
        
    except requests.Timeout:
        log("[IMAGE_CMD] Request timed out")
        await interaction.followup.send("⏰ Sorry, image generation is taking too long. Please try again with a simpler prompt!")
    except requests.RequestException as e:
        log(f"[IMAGE_CMD] Request failed: {e}")
        await interaction.followup.send("❌ Sorry, I'm having trouble generating the image right now. Please try again later!")
    except Exception as e:
        log(f"[IMAGE_CMD] Unexpected error: {e}")
        await interaction.followup.send("💥 Oops! Something went wrong while generating your image. Please try again!")


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
