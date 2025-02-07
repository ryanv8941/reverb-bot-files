import discord
from discord.ext import commands
import os
import json



class RaidUpdater(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print("Raid updater cog loaded")




async def setup(bot):
    await bot.add_cog(RaidUpdater(bot))