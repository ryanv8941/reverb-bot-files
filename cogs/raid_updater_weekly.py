import discord
from discord.ext import commands, tasks
import os
import json
import requests
import asyncio
from datetime import datetime, timezone

RAIDER_IO_BASE_URL = "https://raider.io/api/v1/raiding/static-data"
BOT_DATA_FILE = "bot_data.json"


class WeeklyRaidUpdater(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.update_raids_weekly.start()

    def get_expansion_id(self):
        """Retrieve the current expansion_id from bot_data.json."""
        try:
            with open(BOT_DATA_FILE, "r") as file:
                data = json.load(file)
                return data.get("expansion_id")
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    @tasks.loop(hours=24)
    async def update_raids_weekly(self):
        """Runs every 24 hours, but only proceeds if it's Sunday."""
        now = datetime.now(timezone.utc)
        if now.weekday() != 6:  # 6 = Sunday
            return

        expansion_id = self.get_expansion_id()
        if not expansion_id:
            print("No expansion_id found in bot_data.json.")
            return
        
        guild_id = 1291413329444737096
        guild = self.bot.get_guild(guild_id)
        mod_logs_channel_id = 1291413331717914712
        mod_logs = self.bot.get_channel(mod_logs_channel_id)

        if not guild:
            print("Guild not found.")
            return

        category = discord.utils.get(guild.categories, name="Raid Strats")
        if not category:
            print("Category 'Raid Strats' not found.")
            return
        

        # Construct the URL with the provided expansion_id
        url = f"{RAIDER_IO_BASE_URL}?expansion_id={expansion_id}"
        response = requests.get(url)
        print(f"Raider.io API Response: {response.status_code}")  # Debugging
        
        if response.status_code != 200:
            await mod_logs.send(
                "Failed to fetch data from Raider.io API.", ephemeral=True
            )
            return
        raid_data = response.json()
        print("Raid data fetched successfully")  # Debugging

        # --- STEP 1: Extract the raid data ---
        raids = raid_data.get("raids", [])
        if not raids:
            await mod_logs.send(
                "No raids found for this expansion.", ephemeral=True
            )
            return
        
        for new_raid in raids:
                raid_name = new_raid.get("name")
                formatted_raid_name = raid_name.lower().replace(" ", "-")
                bosses = new_raid.get("encounters", [])
                print(f"Processing raid: {raid_name}")  # Debugging

                if not raid_name:
                    await mod_logs.send(
                        "Raid name not found in the API response.", ephemeral=True
                    )
                    return

                
                existing_channel = discord.utils.get(category.text_channels, name=formatted_raid_name)
                if existing_channel:
                    await mod_logs.send(
                        f"A channel for raid '{raid_name}' already exists.", ephemeral=True
                    )
                    continue

                new_channel = await guild.create_text_channel(raid_name, category=category)
                print(f"Created new channel: {new_channel.name}")  # Debugging

                # --- STEP 4: Create threads for each boss ---
                boss_threads = []
                for boss in bosses:
                    boss_name = boss.get("name")
                    if not boss_name:
                        continue  # Skip if no boss name

                    # Create a thread for the boss
                    try:
                        thread = await new_channel.create_thread(
                            name=boss_name,
                            type=discord.ChannelType.public_thread
                        )

                        await asyncio.sleep(2) #wait for discord to properly register thread url

                        await thread.send(f"# [Back to {new_channel.name}](https://discord.com/channels/{guild_id}/{new_channel.id})")

                        boss_threads.append((boss_name, thread.id))
                        print(f"Created thread for boss: {boss_name}")  # Debugging
                    except discord.errors.HTTPException as e:
                        # Handle rate limiting (429 error) and retry after delay
                        if e.status == 429:
                            retry_after = e.retry_after  # Time to wait before retrying
                            await asyncio.sleep(retry_after)  # Wait the required amount of time
                            # Retry creating the thread after waiting
                            thread = await new_channel.create_thread(
                                name=boss_name,
                                type=discord.ChannelType.public_thread
                            )

                            await asyncio.sleep(2) #wait for discord to properly register thread url

                            await thread.send(f"[# Back to {new_channel.name}](https://discord.com/channels/{guild_id}/{new_channel.id})")

                            boss_threads.append((boss_name, thread.jump_url))
                            print(f"Retried thread creation for boss: {boss_name}")  # Debugging
                    await asyncio.sleep(1)

                async for message in new_channel.history(limit=100):
                    await message.delete()
                    print(f"Deleted message: {message.content}")  # Debugging

                # --- STEP 5: Create a message with links to each boss thread ---

                links_message = "\n".join(
                    [f"# [{boss_name}](https://discord.com/channels/{guild_id}/{thread_url}) \n" 
                    for boss_name, thread_url in boss_threads]
                )

                await new_channel.send(links_message)
                print(f"Sent links for raid '{raid_name}'")  # Debugging

    @update_raids_weekly.before_loop
    async def before_update_raids_weekly(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(WeeklyRaidUpdater(bot))
