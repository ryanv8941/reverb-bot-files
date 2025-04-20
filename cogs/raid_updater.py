import discord
from discord.ext import commands
from discord import app_commands
import os
import json
import requests
import asyncio
import traceback

RAIDER_IO_BASE_URL = "https://raider.io/api/v1/raiding/static-data"

class RaidUpdater(commands.Cog):
    def __init__(self, bot, database):
        self.bot = bot
        self.db = database

    @app_commands.command(
        name="updateraids",
        description="Create new raid channels and threads for a given expansion ID."
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def update_raids(self, interaction: discord.Interaction, expansion_id: int):
        """
        Slash command that updates raids by fetching data from Raider.io using a given expansion_id.
        """
        try:
            # Defer the response to avoid timeout
            await interaction.response.defer()
            print("Response deferred successfully")  # Debugging

            # Construct the URL with the provided expansion_id
            url = f"{RAIDER_IO_BASE_URL}?expansion_id={expansion_id}"
            response = requests.get(url)
            print(f"Raider.io API Response: {response.status_code}")  # Debugging
            
            if response.status_code != 200:
                await interaction.followup.send(
                    "Failed to fetch data from Raider.io API.", ephemeral=True
                )
                return

            raid_data = response.json()
            print("Raid data fetched successfully")  # Debugging

            # --- STEP 1: Extract the raid data ---
            raids = raid_data.get("raids", [])
            if not raids:
                await interaction.followup.send(
                    "No raids found for this expansion.", ephemeral=True
                )
                return

            # --- STEP 2: Get the raid and its bosses ---
            for new_raid in raids:
                raid_name = new_raid.get("name")
                formatted_raid_name = raid_name.lower().replace(" ", "-")
                bosses = new_raid.get("encounters", [])
                print(f"Processing raid: {raid_name}")  # Debugging

                if not raid_name:
                    await interaction.followup.send(
                        "Raid name not found in the API response.", ephemeral=True
                    )
                    return

                # --- STEP 3: Create a new channel for the raid ---
                guild = interaction.guild
                guild_id = guild.id
                category = discord.utils.get(guild.categories, name="Raid Strats")
                if not category:
                    await interaction.followup.send(
                        "Category 'Raid Strats' not found.", ephemeral=True
                    )
                    return
                
                existing_channel = discord.utils.get(category.text_channels, name=formatted_raid_name)
                if existing_channel:
                    await interaction.followup.send(
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

            # Finally, send the confirmation message to the user
            await interaction.followup.send(
                "Raid channels and threads created successfully!", ephemeral=True
            )


            await self.db.set_expansion_id(expansion_id)
            await interaction.followup.send(
                f"Raid channels and threads created successfully! Expansion ID {expansion_id} has been saved.", ephemeral=True
            )

            print("Final confirmation sent")  # Debugging

        except Exception as e:
            # Log the full error for debugging
            traceback.print_exc()  # This prints a full traceback to help debug the error
            await interaction.followup.send(
                "An error occurred while processing the raid updates.", ephemeral=True
            )

async def setup(bot):
    from db import Database
    db = Database()
    await db.connect()
    await bot.add_cog(RaidUpdater(bot))
