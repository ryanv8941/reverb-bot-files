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

@bot.event
async def on_ready():
    await bot.change_presence(status=discord.Status.online, activity=discord.Game("Managing trials"))
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    try:
        await bot.tree.sync()  # Force sync application commands
        print("Slash commands synced successfully.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

    try:
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py"):
                await bot.load_extension(f"cogs.{filename[:-3]}")
    except Exception as l:
        print(f'RYAN EXCEPTON NO FILE: {l}')

bot.run(TOKEN)