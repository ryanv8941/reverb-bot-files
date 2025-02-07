import discord
from discord.ext import commands
import os
import json

#from dotenv import load_dotenv
#load_dotenv()
#TOKEN = os.getenv("DISCORD_TOKEN")

#load_dotenv()
TOKEN = "MTMzNjczODI1NTIxNDczOTQ2Nw.Gy5cmi.HJBvPBDuFxhuF99vanJvKhKy7DjgiQy1bmtlOs"

# Set up intents. We need members intent to get role updates.
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

async def on_ready():

    try:
        await bot.change_presence(status=discord.Status.online, activity=discord.Game("Managing trials"))
        print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    except Exception as p:
        print(f'error ryan here: {p}')

    try:
        await bot.load_extension("cogs.trial_management")  # Manually load cog
        await bot.tree.sync()  # Sync slash commands
        print("Slash commands synced successfully.")
    except Exception as e:
        print(f"Error loading cog: {e}")

bot.run(TOKEN)