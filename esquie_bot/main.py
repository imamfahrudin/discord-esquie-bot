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
intents.message_content = True  # Required to read message content for referenced messages
# Note: message_content intent is privileged and requires approval from Discord Developer Portal
bot = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(bot)

# Global state for managing concurrent requests
processing_lock = asyncio.Lock()
current_processing_user = None
waiting_messages = []


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

    # Debug: Log all message attributes
    log(f"[EXTRACT] Message attributes: {dir(message)}")
    # Note: Discord.py Message objects don't have __dict__, use _state instead
    if hasattr(message, '_state'):
        log(f"[EXTRACT] Message has _state attribute")
    else:
        log(f"[EXTRACT] Message does not have _state attribute")

    # Add the main message content if it exists
    if message.content:
        content_parts.append(f"Message: {message.content}")
        log(f"[EXTRACT] Found message content: '{message.content[:100]}...'")
    else:
        log("[EXTRACT] No message content found")

    # Process embeds with detailed debugging
    log(f"[EXTRACT] Checking embeds: hasattr(message, 'embeds')={hasattr(message, 'embeds')}")
    if hasattr(message, 'embeds'):
        log(f"[EXTRACT] message.embeds type: {type(message.embeds)}")
        log(f"[EXTRACT] message.embeds length: {len(message.embeds) if message.embeds else 0}")
        log(f"[EXTRACT] message.embeds is truthy: {bool(message.embeds)}")
        log(f"[EXTRACT] message.embeds repr: {repr(message.embeds)}")

        if message.embeds:
            log(f"[EXTRACT] Found {len(message.embeds)} embed(s)")
            for i, embed in enumerate(message.embeds, 1):
                log(f"[EXTRACT] Processing embed {i}: type={type(embed)}")
                # Try to get embed attributes safely
                try:
                    if hasattr(embed, '__dict__'):
                        log(f"[EXTRACT] Embed {i} __dict__: {embed.__dict__}")
                    else:
                        log(f"[EXTRACT] Embed {i} attributes: {dir(embed)}")
                except Exception as e:
                    log(f"[EXTRACT] Error getting embed {i} attributes: {e}")
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
                    log(f"[EXTRACT] Embed {i} has no extractable content")
        else:
            log("[EXTRACT] No embeds found")
    else:
        log("[EXTRACT] Message object has no embeds attribute")

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

    # Check message type and other properties
    log(f"[EXTRACT] Message type: {message.type}")
    log(f"[EXTRACT] Message flags: {message.flags if hasattr(message, 'flags') else 'No flags'}")
    log(f"[EXTRACT] Message webhook_id: {message.webhook_id if hasattr(message, 'webhook_id') else 'No webhook'}")
    log(f"[EXTRACT] Message application_id: {message.application_id if hasattr(message, 'application_id') else 'No application'}")

    # Check for interaction metadata that might indicate slash command responses
    if hasattr(message, 'interaction') and message.interaction:
        log(f"[EXTRACT] Message has interaction: {message.interaction}")
        content_parts.append(f"Response to slash command: {message.interaction.name if hasattr(message.interaction, 'name') else 'Unknown'}")

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

    # Check for any rich content that might indicate the message has visual elements
    has_rich_content = bool(message.embeds or message.attachments or (hasattr(message, 'components') and message.components) or message.stickers)
    log(f"[EXTRACT] Message has rich content: {has_rich_content}")

    # If no traditional content but has rich content, try to get a summary
    if not content_parts and has_rich_content:
        log(f"[EXTRACT] Message has no text content but has rich content - attempting to summarize")
        if message.attachments:
            content_parts.append(f"Contains {len(message.attachments)} attachment(s)")
        if hasattr(message, 'components') and message.components:
            content_parts.append(f"Contains interactive components")
        if message.stickers:
            content_parts.append(f"Contains {len(message.stickers)} sticker(s)")

    # If still no content, check if this might be a system message or special format
    if not content_parts:
        if message.type != discord.MessageType.default:
            content_parts.append(f"System message type: {message.type}")
            log(f"[EXTRACT] Detected system message type: {message.type}")
        else:
            log(f"[EXTRACT] Message appears to be truly empty or uses unsupported format")

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
            {"role": "system", "content": f"""# {BOT_NAME} - Discord AI Assistant

## Identity & Behavior
You are {BOT_NAME}, a helpful AI assistant that responds naturally to user messages in multiple languages.

## Language Support
- Primary: English
- Additional: Spanish, French, German, Italian, Portuguese, Indonesian, and others
- **Rule**: Match the user's language when possible

## Response Guidelines
- Current date and time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
- Default to single paragraph responses unless the user specifically requests multiple paragraphs, lists, or other formatting
- Adapt response format to user requests - use multiple paragraphs, lists, or formatting when appropriate

## Discord Mention Handling

### When Responding to Mentions
- When users mention other Discord users in their messages, use the Discord mention format `<@user_id>` in your responses instead of plain usernames

### When Asked to Mention Users
- If asked to mention or tell other users something, mention them directly using the Discord mention format `<@user_id>`
- Do NOT explain how to mention users or provide guidance on mentioning

### When Explaining Mentions to Users
- If you need to explain mentioning to users, use the `@name` format instead of revealing the internal `<@user_id>` format

## Additional Capabilities
- You can see and describe images that users share"""}
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
    try:
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
    except Exception as e:
        log(f"[STARTUP ERROR] Critical error in on_ready: {e}")
        import traceback
        log(f"[STARTUP ERROR] Traceback: {traceback.format_exc()}")


@bot.event
async def on_reaction_add(reaction, user):
    """Called when a reaction is added to a message."""
    try:
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
    except Exception as e:
        log(f"[REACTION ERROR] Unhandled exception in on_reaction_add: {e}")
        import traceback
        log(f"[REACTION ERROR] Traceback: {traceback.format_exc()}")


async def process_user_message(message, thinking_message=None):
    """Process a user message and generate AI response."""
    global current_processing_user
    
    # Acquire the lock for processing
    async with processing_lock:
        current_processing_user = message.author.id
        log(f"[LOCK] Acquired processing lock for user {message.author.name} (ID: {message.author.id})")
        try:
            await _process_user_message_impl(message, thinking_message)
        finally:
            current_processing_user = None
            log(f"[LOCK] Released processing lock for user {message.author.name}")


async def _process_user_message_impl(message, thinking_message=None):
    """Internal implementation of message processing."""
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
                # Extract content from referenced message for context (works with or without mention)
                # Check if the referenced message is from a bot
                is_referenced_bot = referenced_msg.author.bot

                if is_referenced_bot:
                    # Extract comprehensive content from bot message
                    referenced_content = await extract_bot_message_content(referenced_msg)
                    log(f"[BOT_REPLY] User {message.author.name} replied to bot {referenced_msg.author.name}'s message")
                else:
                    # Regular user message - clean bot mentions from it
                    original_content = referenced_msg.content
                    log(f"[DEBUG] Referenced message ID: {referenced_msg.id}")
                    log(f"[DEBUG] Referenced message type: {referenced_msg.type}")
                    log(f"[DEBUG] Referenced message author: {referenced_msg.author.name}")
                    log(f"[DEBUG] Referenced message has embeds: {bool(referenced_msg.embeds)}")
                    log(f"[DEBUG] Referenced message has attachments: {bool(referenced_msg.attachments)}")
                    log(f"[DEBUG] Original content: '{original_content}', length: {len(original_content)}")

                    # If content is empty, this might be a message with only embeds/attachments or deleted content
                    # Try to get something meaningful from the message
                    if not original_content:
                        if referenced_msg.embeds:
                            # Try to extract text from embeds
                            embed_texts = []
                            for embed in referenced_msg.embeds:
                                if embed.description:
                                    embed_texts.append(embed.description)
                                if embed.title:
                                    embed_texts.append(embed.title)
                            if embed_texts:
                                original_content = " | ".join(embed_texts)
                                log(f"[DEBUG] Extracted content from embeds: '{original_content[:50]}...'")
                        elif referenced_msg.attachments:
                            # Message has attachments but no text
                            attachment_names = [att.filename for att in referenced_msg.attachments]
                            original_content = f"[Attachments: {', '.join(attachment_names)}]"
                            log(f"[DEBUG] Message has only attachments: {attachment_names}")
                        else:
                            # Truly empty message - might be deleted or edited
                            log(f"[WARNING] Referenced message has no content, embeds, or attachments!")
                            original_content = "[Empty or deleted message]"

                    # Remove bot mentions to avoid confusion in AI context
                    cleaned_content = re.sub(r'<@!?{}>'.format(bot.user.id), '', original_content).strip()
                    log(f"[DEBUG] Cleaned content: '{cleaned_content}', length: {len(cleaned_content)}")
                    # Use cleaned content, but fall back to original if it becomes empty
                    referenced_content = cleaned_content if cleaned_content else original_content
                    log(f"[DEBUG] Final referenced_content: '{referenced_content}', length: {len(referenced_content)}, bool: {bool(referenced_content)}")  
                    # Log the content
                    if cleaned_content:
                        log(f"[USER_REPLY] User {message.author.name} replied to {referenced_msg.author.name}'s message: '{referenced_content[:50]}...'")  
                    else:
                        log(f"[USER_REPLY] User {message.author.name} replied to {referenced_msg.author.name}'s message (was only bot mention): '{referenced_content[:50]}...'")
        except discord.NotFound:
            log("[REPLY] Referenced message not found - might have been deleted")
        except discord.Forbidden:
            log("[REPLY] Cannot access referenced message - permission issue")
        except Exception as e:
            log(f"[REPLY] Error fetching referenced message: {e}")

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
    log(f"[DEBUG] referenced_content exists: {bool(referenced_content)}, referenced_msg exists: {bool(referenced_msg)}")
    if referenced_content and referenced_msg:
        # Use enhanced context building for better bot message handling
        reference_context = await build_enhanced_reference_context(message, referenced_msg, referenced_content)
        log(f"[CONTEXT] Including referenced message: '{referenced_content[:50]}...'")
    elif referenced_content:
        # Fallback if referenced_msg is not available
        reference_context = f" [Replying to: {referenced_content}]"
        log(f"[CONTEXT] Using fallback context: '{referenced_content[:50]}...'")
    else:
        log(f"[DEBUG] No referenced content to include in context")
    
    personalized_content = f"[{user_display_name}]: {content}{mention_context}{reference_context}"

    # Process any images in the message
    image_descriptions = []
    if message.attachments or message.embeds:
        log("[IMAGES] Message contains attachments/embeds, processing images...")
        image_descriptions = await get_image_descriptions(message)
        if image_descriptions:
            log(f"[IMAGES] Processed {len(image_descriptions)} images")

    # Send thinking message first if not provided
    if thinking_message is None:
        thinking_message = await message.reply("🤔 Thinking...")
        log(f"[THINKING] Sent thinking message as reply to user {message.author.name}")

    ai_response = await get_ai_response(personalized_content, conversation_history, image_descriptions)

    if not ai_response:
        log("[ERROR] Got empty response from AI")
        ai_response = "I apologize, but I couldn't generate a response right now. Please try again!"

    log(f"[RESPONSE] AI response: '{ai_response[:100]}...'")

    # Check if response exceeds Discord's 2000 character limit
    if len(ai_response) > 2000:
        # Split long response into chunks
        chunks = []
        remaining = ai_response
        while len(remaining) > 2000:
            # Find a good break point (sentence end or word boundary)
            chunk = remaining[:2000]
            # Try to break at sentence end
            last_sentence = max(chunk.rfind('.'), chunk.rfind('!'), chunk.rfind('?'))
            if last_sentence > 1800:  # If sentence break is reasonable
                chunk = chunk[:last_sentence + 1]
            else:
                # Try to break at word boundary
                last_space = chunk.rfind(' ')
                if last_space > 1800:
                    chunk = chunk[:last_space]
            
            chunks.append(chunk)
            remaining = remaining[len(chunk):].lstrip()
        
        if remaining:  # Add any remaining content
            chunks.append(remaining)
        
        log(f"[LONG_RESPONSE] Split response into {len(chunks)} chunks")
        
        # Edit thinking message to indicate split response
        try:
            await thinking_message.edit(content=f"My response is quite long, sending it in {len(chunks)} parts below...")
            log(f"[LONG_RESPONSE] Edited thinking message to indicate {len(chunks)} parts for {message.author.name}")
        except Exception as e:
            log(f"[LONG_RESPONSE] Failed to edit thinking message: {e}")
        
        # Send chunks as a reply chain
        last_message = message  # Start with the original user message
        for i, chunk in enumerate(chunks, 1):
            try:
                # Send each chunk as a reply to the previous message in the chain
                sent_message = await last_message.reply(chunk)
                last_message = sent_message  # Update for next iteration
                log(f"[LONG_RESPONSE] Sent chunk {i}/{len(chunks)} ({len(chunk)} chars) for {message.author.name}")
            except discord.Forbidden:
                log(f"[LONG_RESPONSE] Cannot reply for chunk {i} - missing permissions")
                try:
                    sent_message = await message.channel.send(f"{message.author.mention} {chunk}")
                    last_message = sent_message
                    log(f"[LONG_RESPONSE] Sent chunk {i} as channel message fallback for {message.author.name}")
                except Exception as e:
                    log(f"[LONG_RESPONSE] Channel send failed for chunk {i}: {e}")
                    break  # Stop sending more chunks if this fails
            except Exception as e:
                log(f"[LONG_RESPONSE] Reply failed for chunk {i}: {e}")
                try:
                    sent_message = await message.channel.send(f"{message.author.mention} {chunk}")
                    last_message = sent_message
                    log(f"[LONG_RESPONSE] Sent chunk {i} as channel message fallback for {message.author.name}")
                except Exception as e2:
                    log(f"[LONG_RESPONSE] Channel send failed for chunk {i}: {e2}")
                    break  # Stop sending more chunks if this fails
    else:
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
                except Exception as e2:
                    log(f"[FALLBACK] Channel send failed: {e2}")
@bot.event
async def on_message(message):
    """Called whenever a message is sent in a channel the bot can see."""
    global current_processing_user, waiting_messages
    
    try:
        # Prevent responding to own messages
        if message.author == bot.user:
            return

        # Skip messages containing @everyone or @here to avoid spam
        if "@everyone" in message.content or "@here" in message.content:
            log(f"[SKIP] Ignoring message with @everyone/@here from {message.author.name}")
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
                    # Extract content from referenced message for context (works with or without mention)
                    # Check if the referenced message is from a bot
                    is_referenced_bot = referenced_msg.author.bot
                    
                    if is_referenced_bot:
                        # Extract comprehensive content from bot message
                        referenced_content = await extract_bot_message_content(referenced_msg)
                        log(f"[BOT_REPLY] User {message.author.name} replied to bot {referenced_msg.author.name}'s message")
                    else:
                        # Regular user message - clean bot mentions from it
                        original_content = referenced_msg.content
                        log(f"[DEBUG] Referenced message ID: {referenced_msg.id}")
                        log(f"[DEBUG] Referenced message type: {referenced_msg.type}")
                        log(f"[DEBUG] Referenced message author: {referenced_msg.author.name}")
                        log(f"[DEBUG] Referenced message has embeds: {bool(referenced_msg.embeds)}")
                        log(f"[DEBUG] Referenced message has attachments: {bool(referenced_msg.attachments)}")
                        log(f"[DEBUG] Original content: '{original_content}', length: {len(original_content)}")
                        
                        # If content is empty, this might be a message with only embeds/attachments or deleted content
                        # Try to get something meaningful from the message
                        if not original_content:
                            if referenced_msg.embeds:
                                # Try to extract text from embeds
                                embed_texts = []
                                for embed in referenced_msg.embeds:
                                    if embed.description:
                                        embed_texts.append(embed.description)
                                    if embed.title:
                                        embed_texts.append(embed.title)
                                if embed_texts:
                                    original_content = " | ".join(embed_texts)
                                    log(f"[DEBUG] Extracted content from embeds: '{original_content[:50]}...'")
                            elif referenced_msg.attachments:
                                # Message has attachments but no text
                                attachment_names = [att.filename for att in referenced_msg.attachments]
                                original_content = f"[Attachments: {', '.join(attachment_names)}]"
                                log(f"[DEBUG] Message has only attachments: {attachment_names}")
                            else:
                                # Truly empty message - might be deleted or edited
                                log(f"[WARNING] Referenced message has no content, embeds, or attachments!")
                                original_content = "[Empty or deleted message]"
                        
                        # Remove bot mentions to avoid confusion in AI context
                        cleaned_content = re.sub(r'<@!?{}>'.format(bot.user.id), '', original_content).strip()
                        log(f"[DEBUG] Cleaned content: '{cleaned_content}', length: {len(cleaned_content)}")
                        # Use cleaned content, but fall back to original if it becomes empty
                        referenced_content = cleaned_content if cleaned_content else original_content
                        log(f"[DEBUG] Final referenced_content: '{referenced_content}', length: {len(referenced_content)}, bool: {bool(referenced_content)}")
                        # Log the content
                        if cleaned_content:
                            log(f"[USER_REPLY] User {message.author.name} replied to {referenced_msg.author.name}'s message: '{referenced_content[:50]}...'")
                        else:
                            log(f"[USER_REPLY] User {message.author.name} replied to {referenced_msg.author.name}'s message (was only bot mention): '{referenced_content[:50]}...'")
            except discord.NotFound:
                log("[REPLY] Referenced message not found - might have been deleted")
            except discord.Forbidden:
                log("[REPLY] Cannot access referenced message - permission issue")
            except Exception as e:
                log(f"[REPLY] Error fetching referenced message: {e}")

        # Only respond to mentions, replies to bot messages with new images, replies to other bots with explanation requests, or replies to any user (including self) with explanation requests
        has_new_images = bool(message.attachments or message.embeds)
        is_reply_to_other_bot = bool(referenced_msg and referenced_msg.author.bot and referenced_msg.author != bot.user)
        is_explanation_request = detect_explanation_request(message.content)
        # Allow explanation requests for any user message (including self-replies)
        is_reply_to_user_with_explanation = bool(referenced_msg and not referenced_msg.author.bot and is_explanation_request and is_mention)

        should_respond = is_mention or (is_reply_to_bot and has_new_images) or (is_reply_to_other_bot and is_explanation_request) or is_reply_to_user_with_explanation
        
        if not should_respond:
            log(f"[SKIP] Ignoring message without mention, new images, or explanation request from {message.author.name}")
            return

        log(f"[INTERACTION] User {message.author.name} - Mention: {is_mention}, Reply: {is_reply_to_bot}")
        
        # Check if bot is currently processing another user's request
        if processing_lock.locked() and current_processing_user != message.author.id:
            log(f"[QUEUE] Bot is busy processing request for user ID {current_processing_user}, queuing request from {message.author.name}")
            waiting_msg = await message.reply(f"⏳ Please wait, I'm currently answering {bot.get_user(current_processing_user).display_name if bot.get_user(current_processing_user) else 'someone'}'s request...")
            waiting_messages.append((message, waiting_msg))
            return
        
        await process_user_message(message)
        
        # Process next waiting message if any
        if waiting_messages:
            next_message, waiting_msg = waiting_messages.pop(0)
            log(f"[QUEUE] Processing next queued message from {next_message.author.name}")
            await process_user_message(next_message, waiting_msg)
            
    except Exception as e:
        log(f"[ERROR] Unhandled exception in on_message: {e}")
        import traceback
        log(f"[ERROR] Traceback: {traceback.format_exc()}")
        # Make sure to release lock on error
        if processing_lock.locked():
            current_processing_user = None
        # Try to notify user about the error
        try:
            await message.reply("Sorry, I encountered an error processing your message. Please try again!")
        except:
            pass


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


@bot.event
async def on_error(event: str, *args, **kwargs) -> None:
    """Global error handler for Discord events."""
    import traceback
    log(f"[DISCORD ERROR] Error in event '{event}'")
    log(f"[DISCORD ERROR] Traceback: {traceback.format_exc()}")
    # Don't crash - let the bot continue running


@bot.event
async def on_disconnect() -> None:
    """Called when the bot disconnects from Discord."""
    log("[CONNECTION] Bot disconnected from Discord")


@bot.event
async def on_resumed() -> None:
    """Called when the bot resumes a session after disconnection."""
    log("[CONNECTION] Bot resumed connection to Discord")


def run(token: Optional[str] = None) -> None:
    """Run the Discord bot. If token is None, read from DISCORD_BOT_TOKEN env var (after loading .env)."""
    load_dotenv()
    if token is None:
        token = os.getenv('DISCORD_BOT_TOKEN')

    if not token:
        log("[FATAL] DISCORD_BOT_TOKEN not found in environment variables")
        log("[FATAL] Please create a .env file with your bot token or pass the token to run()")
        log("[FATAL] Exiting to prevent restart loop...")
        sys.exit(1)

    if not token.strip():
        log("[FATAL] DISCORD_BOT_TOKEN is empty")
        log("[FATAL] Exiting to prevent restart loop...")
        sys.exit(1)

    log("[STARTUP] Starting bot...")
    log(f"[STARTUP] Bot name: {BOT_NAME}")
    log(f"[STARTUP] Bot status: {BOT_STATUS}")
    
    try:
        bot.run(token)
    except discord.LoginFailure:
        log("[FATAL] Invalid bot token - Discord rejected authentication")
        log("[FATAL] Please check your DISCORD_BOT_TOKEN in .env file")
        log("[FATAL] Exiting to prevent restart loop...")
        sys.exit(1)
    except discord.PrivilegedIntentsRequired:
        log("[FATAL] Missing privileged intents - message_content intent is required")
        log("[FATAL] Enable it in Discord Developer Portal -> Bot -> Privileged Gateway Intents")
        log("[FATAL] Exiting to prevent restart loop...")
        sys.exit(1)
    except KeyboardInterrupt:
        log("[SHUTDOWN] Received keyboard interrupt - shutting down gracefully")
        sys.exit(0)
    except Exception as e:
        log(f"[FATAL] Unexpected error starting bot: {e}")
        import traceback
        log(f"[FATAL] Traceback: {traceback.format_exc()}")
        log("[FATAL] Exiting to prevent restart loop...")
        sys.exit(1)
