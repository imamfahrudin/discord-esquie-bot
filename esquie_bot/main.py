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


# Load environment variables for bot configuration
load_dotenv()
BOT_NAME = os.getenv('BOT_NAME', 'Esquie')
BOT_STATUS = os.getenv('BOT_STATUS', 'Losing A Rock Is Better Than Never Having A Rock!')


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
        # Handle bot's own mention specially
        if str(user_id) == str(bot.user.id):
            mention_map[BOT_NAME] = "self"
            continue
            
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


async def extract_bot_message_content(message: discord.Message) -> str:
    """Extract comprehensive content from a bot message including embeds, attachments, components, and other rich content."""
    content_parts = []
    log(f"[EXTRACT] Analyzing bot message from {message.author.name} (ID: {message.id})")
    log(f"[EXTRACT] Message type: {message.type}, Channel: {message.channel}, Created: {message.created_at}")

    # Add the main message content if it exists
    if message.content:
        content_parts.append(f"Message: {message.content}")
        log(f"[EXTRACT] Found message content: '{message.content[:100]}...'")
    else:
        log("[EXTRACT] No message content found")

    # Process embeds (common in bot messages)
    if message.embeds:
        log(f"[EXTRACT] Found {len(message.embeds)} embed(s)")
        for i, embed in enumerate(message.embeds, 1):
            embed_info = []
            
            if embed.title:
                embed_info.append(f"Title: {embed.title}")
            if embed.description:
                embed_info.append(f"Description: {embed.description}")
            if embed.fields:
                for field in embed.fields:
                    embed_info.append(f"{field.name}: {field.value}")
            if embed.footer and embed.footer.text:
                embed_info.append(f"Footer: {embed.footer.text}")
            if embed.author and embed.author.name:
                embed_info.append(f"Author: {embed.author.name}")
            if embed.timestamp:
                embed_info.append(f"Timestamp: {embed.timestamp}")
            if embed.url:
                embed_info.append(f"URL: {embed.url}")
            if embed.image and embed.image.url:
                embed_info.append(f"Image: {embed.image.url}")
            if embed.thumbnail and embed.thumbnail.url:
                embed_info.append(f"Thumbnail: {embed.thumbnail.url}")
            
            if embed_info:
                content_parts.append(f"Embed {i}: {' | '.join(embed_info)}")
                log(f"[EXTRACT] Embed {i} info: {embed_info}")
    else:
        log("[EXTRACT] No embeds found")

    # Process attachments (images, files, etc.)
    if message.attachments:
        log(f"[EXTRACT] Found {len(message.attachments)} attachment(s)")
        for i, attachment in enumerate(message.attachments, 1):
            if attachment.content_type and attachment.content_type.startswith('image/'):
                content_parts.append(f"Attachment {i}: Image file ({attachment.filename})")
            else:
                content_parts.append(f"Attachment {i}: {attachment.filename}")
    else:
        log("[EXTRACT] No attachments found")

    # Process components (buttons, select menus, etc.)
    if hasattr(message, 'components') and message.components:
        log(f"[EXTRACT] Found {len(message.components)} component row(s)")
        for i, component_row in enumerate(message.components, 1):
            if hasattr(component_row, 'children'):
                component_info = []
                for component in component_row.children:
                    if hasattr(component, 'label') and component.label:
                        component_info.append(f"Button: {component.label}")
                    elif hasattr(component, 'placeholder') and component.placeholder:
                        component_info.append(f"Select Menu: {component.placeholder}")
                    elif hasattr(component, 'options') and component.options:
                        options_text = [opt.get('label', opt.get('value', 'Unknown')) for opt in component.options]
                        component_info.append(f"Select Options: {', '.join(options_text)}")
                    elif hasattr(component, 'type'):
                        component_info.append(f"Component type {component.type}")
                    else:
                        component_info.append(f"Unknown component: {component}")
                if component_info:
                    content_parts.append(f"Components Row {i}: {' | '.join(component_info)}")
                    log(f"[EXTRACT] Component row {i}: {component_info}")
    else:
        log("[EXTRACT] No components found")

    # Process stickers
    if hasattr(message, 'stickers') and message.stickers:
        sticker_names = [sticker.name for sticker in message.stickers]
        content_parts.append(f"Stickers: {', '.join(sticker_names)}")
        log(f"[EXTRACT] Found stickers: {sticker_names}")

    # Process reactions if any (though usually not on bot messages)
    if message.reactions:
        reaction_info = []
        for reaction in message.reactions:
            if hasattr(reaction.emoji, 'name'):
                reaction_info.append(f"{reaction.emoji.name} ({reaction.count})")
            else:
                reaction_info.append(f"{reaction.emoji} ({reaction.count})")
        content_parts.append(f"Reactions: {', '.join(reaction_info)}")
        log(f"[EXTRACT] Found reactions: {reaction_info}")

    # Check for special message flags
    flags_info = []
    if hasattr(message, 'flags'):
        if message.flags.ephemeral:
            flags_info.append("ephemeral")
        if message.flags.loading:
            flags_info.append("loading")
        if message.flags.suppress_notifications:
            flags_info.append("suppress_notifications")
    if flags_info:
        content_parts.append(f"Flags: {', '.join(flags_info)}")
        log(f"[EXTRACT] Message flags: {flags_info}")

    # Check for interaction metadata (for slash command responses)
    if hasattr(message, 'interaction') and message.interaction:
        interaction_info = f"Interaction: {message.interaction.name}"
        if hasattr(message.interaction, 'user'):
            interaction_info += f" by {message.interaction.user}"
        content_parts.append(interaction_info)
        log(f"[EXTRACT] Interaction metadata: {interaction_info}")

    # Check for application command data
    if hasattr(message, 'application') and message.application:
        content_parts.append(f"Application: {message.application.name}")
        log(f"[EXTRACT] Application: {message.application.name}")

    # Add raw message data for debugging
    raw_data = {
        'content_length': len(message.content) if message.content else 0,
        'embeds_count': len(message.embeds),
        'attachments_count': len(message.attachments),
        'components_count': len(message.components) if hasattr(message, 'components') else 0,
        'reactions_count': len(message.reactions),
        'stickers_count': len(message.stickers) if hasattr(message, 'stickers') else 0,
    }
    log(f"[EXTRACT] Raw message data: {raw_data}")

    # If no content at all, provide a generic description
    if not content_parts:
        log(f"[EXTRACT] No content found in bot message from {message.author.name}")
        return f"Bot message from {message.author.name} (no visible content)"

    result = " | ".join(content_parts)
    log(f"[EXTRACT] Final extracted content: '{result[:200]}...'")
    return result
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
            {"role": "system", "content": f"You are {BOT_NAME}, a helpful AI assistant that responds naturally to user messages in multiple languages including English, Spanish, French, German, Italian, Portuguese, Indonesian, and others. Match the user's language when possible. Current date and time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}. Try to respond in a single paragraph and avoid complex formatting. When users mention other Discord users in their messages, use Discord mention format <@user_id> in your responses instead of plain usernames. You can also see and describe images that users share."}
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


def detect_explanation_request(content: str) -> bool:
    """Detect if the user is asking for an explanation of something."""
    explanation_keywords = [
        'explain', 'what is', 'what\'s', 'what are', 'what does', 'what do',
        'tell me about', 'describe', 'meaning of', 'what does this mean',
        'can you explain', 'please explain', 'explain this', 'explain that',
        'what is it', 'what\'s this', 'what\'s that', 'what is this', 'what is that'
    ]
    
    content_lower = content.lower().strip()
    return any(keyword in content_lower for keyword in explanation_keywords)


async def build_enhanced_reference_context(message: discord.Message, referenced_msg: discord.Message, referenced_content: str) -> str:
    """Build enhanced context for referenced messages, especially for explanation requests."""
    if not referenced_content:
        return ""
    
    # Check if this looks like an explanation request
    is_explanation_request = detect_explanation_request(message.content)
    
    if is_explanation_request and referenced_msg.author.bot:
        # For explanation requests to other bots, provide more detailed context
        context = f" [Please explain this bot message from {referenced_msg.author.name}: {referenced_content}]"
        log(f"[EXPLANATION] Detected explanation request for bot message: '{referenced_content[:50]}...'")
    elif referenced_msg.author.bot:
        # Regular reference to bot message
        context = f" [Referring to bot {referenced_msg.author.name}'s message: {referenced_content}]"
        log(f"[BOT_CONTEXT] Including bot message context: '{referenced_content[:50]}...'")
    else:
        # Regular user message reference
        context = f" [Replying to: {referenced_content}]"
        log(f"[USER_CONTEXT] Including user message context: '{referenced_content[:50]}...'")
    
    return context


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
    await bot.change_presence(activity=discord.Game(name=BOT_STATUS))
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
    
    # Check if this is an AI-generated image embed
    is_image_embed = False
    if reaction.message.embeds:
        for embed in reaction.message.embeds:
            if embed.title and "🎨 AI Generated Image" in embed.title:
                is_image_embed = True
                break
    
    # For image embeds, allow deletion by any user who reacts with X
    if is_image_embed:
        try:
            await reaction.message.delete()
            log(f"[DELETE] Deleted AI-generated image embed due to X reaction from {user.name}")
            return
        except discord.Forbidden:
            log(f"[DELETE] Cannot delete image embed - missing permissions for user {user.name}")
            return
        except discord.NotFound:
            log("[DELETE] Image embed message already deleted")
            return
        except Exception as e:
            log(f"[DELETE] Error deleting image embed: {e}")
            return
    
    # For regular bot messages, check if the bot message is replying to the reacting user
    if not reaction.message.reference or not reaction.message.reference.message_id:
        log(f"[DELETE] Bot message is not a reply and not an image embed, ignoring X reaction from {user.name}")
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
    referenced_msg = None  # Initialize to None
    
    # Check if this is a reply to one of our messages
    if message.reference and message.reference.message_id:
        try:
            referenced_msg = await message.channel.fetch_message(message.reference.message_id)
            if referenced_msg.author == bot.user:
                is_reply_to_bot = True
                log(f"[REPLY] User {message.author.name} replied to bot message: '{referenced_msg.content[:50]}...'")
                conversation_history = await build_conversation_history(message)
            else:
                # If mentioning bot in reply to another user's/bot's message, include that message for context
                if is_mention:
                    # Check if the referenced message is from a bot
                    is_referenced_bot = referenced_msg.author.bot
                    
                    if is_referenced_bot:
                        # Extract comprehensive content from bot message
                        referenced_content = await extract_bot_message_content(referenced_msg)
                        log(f"[BOT_REPLY] User {message.author.name} replied to bot {referenced_msg.author.name}'s message with bot mention")
                    else:
                        # Regular user message
                        referenced_content = referenced_msg.content
                        log(f"[USER_REPLY] User {message.author.name} replied to {referenced_msg.author.name}'s message with bot mention: '{referenced_msg.content[:50]}...'")
        except discord.NotFound:
            log("[REPLY] Referenced message not found - might have been deleted")
        except discord.Forbidden:
            log("[REPLY] Cannot access referenced message - permission issue")
        except Exception as e:
            log(f"[REPLY] Error fetching referenced message: {e}")

    # Only respond to mentions or replies to bot messages that contain new images or explanation requests
    has_new_images = bool(message.attachments or message.embeds)
    is_reply_to_other_bot = bool(referenced_msg and referenced_msg.author.bot and referenced_msg.author != bot.user)
    is_explanation_request = detect_explanation_request(message.content)

    should_respond = is_mention or (is_reply_to_bot and has_new_images) or (is_reply_to_other_bot and is_explanation_request)
    
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
    if referenced_content and referenced_msg:
        # Use enhanced context building for better bot message handling
        reference_context = await build_enhanced_reference_context(message, referenced_msg, referenced_content)
        log(f"[CONTEXT] Including referenced message: '{referenced_content[:50]}...'")
    elif referenced_content:
        # Fallback if referenced_msg is not available
        reference_context = f" [Replying to: {referenced_content}]"
        log(f"[CONTEXT] Using fallback context: '{referenced_content[:50]}...'")
    
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
        # Request options: make images non-deterministic and enable enhancements
        # Use lowercase string 'true' for boolean flags to be compatible with remote APIs
        params = {
            "width": 1024,
            "height": 1024,
            "model": "flux",
            "nologo": "true",
            "enhance": "true",
            "private": "true"
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
