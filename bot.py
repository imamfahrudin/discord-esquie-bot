import discord
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get bot token from environment variable
TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# Check if token is provided
if not TOKEN:
    print("Error: DISCORD_BOT_TOKEN not found in environment variables")
    print("Please create a .env file with your bot token")
    exit(1)

# Create bot instance with intents
intents = discord.Intents.default()
# Note: message_content intent is privileged and requires approval from Discord
# For a simple mention-response bot, we don't need it

bot = discord.Client(intents=intents)

@bot.event
async def on_ready():
    """Called when the bot is ready and connected to Discord"""
    print(f'Bot is ready! Logged in as {bot.user}')

@bot.event
async def on_message(message):
    """Called whenever a message is sent in a channel the bot can see"""
    # Don't respond to our own messages
    if message.author == bot.user:
        return

    # Check if the bot is mentioned in the message
    if bot.user.mentioned_in(message):
        # Get the username (without discriminator if using new username system)
        username = message.author.name
        # Send hello message
        await message.reply(f"Hello {username}!")

# Run the bot
bot.run(TOKEN)