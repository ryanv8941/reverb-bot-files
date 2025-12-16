from re import L
import discord
from discord.ext import commands
import os
import json
import db
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")





# Set up intents. We need members intent to get role updates.
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)


@bot.event
async def on_ready():
    await bot.change_presence(status=discord.Status.online, activity=discord.Game("Managing trials"))
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')

    database = db.Database()
    await database.connect()

    try:
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py") and filename != "gold_gamba.py" and filename != "trial_management.py" and filename != "raid_updater.py" and filename != "raid_updater_weekly.py" and filename != "upgrade_sheet_sync.py":
                await bot.load_extension(f"cogs.{filename[:-3]}")
    except Exception as l:
        print(f'RYAN EXCEPTON NO FILE: {l}')

    try:
        from cogs.trial_management import TrialManagement
        await bot.add_cog(TrialManagement(bot, database))
        print("Loaded TrialManagement cog with database.")
    except Exception as e:
        print(f"Error loading TrialManagement cog: {e}")

    try:
        from cogs.raid_updater import RaidUpdater
        await bot.add_cog(RaidUpdater(bot, database))
        print("Loaded RaidUpdater cog with database.")
    except Exception as e:
        print(f"Error loading RaidUpdater cog: {e}")

    try:
        from cogs.raid_updater_weekly import WeeklyRaidUpdater
        await bot.add_cog(WeeklyRaidUpdater(bot, database))
        print("Loaded RaidUpdaterWeekly cog with database.")
    except Exception as e:
        print(f"Error loading RaidUpdaterWeekly cog: {e}")
# Load UpgradeSheetSync cog after WeeklyRaidUpdater
    try:
        from cogs.upgrade_sheet_sync import UpgradeSheetSync
        await bot.add_cog(UpgradeSheetSync(bot))
        print("Loaded UpgradeSheetSync cog.")
    except Exception as e:
        print(f"Error loading UpgradeSheetSync cog: {e}")

    try:
        from cogs.gold_gamba import GoldGamba
        await bot.add_cog(GoldGamba(bot, database))
        print("Loaded GoldGamba cog with database.")
    except Exception as e:
        print(f"Error loading GoldGamba cog: {e}")

    try:
        from cogs.lottery_task import Lottery
        await bot.add_cog(Lottery(bot, database))
        print("Loaded Lottery cog with database.")
    except Exception as e:
        print(f"Error loading Lottery cog: {e}")

    try:
        await bot.tree.sync()  # Force sync application commands
        print("Slash commands synced successfully.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

bot.run(TOKEN)