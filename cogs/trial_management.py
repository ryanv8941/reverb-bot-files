import discord
from discord.ext import commands
from discord import app_commands
import os
import json
import asyncio

# Customize these to match your server’s configuration.
TRIAL_ROLE_NAME = "Trial Raider"
TRIAL_CHANNEL_NAME = "trials"

# OLD USED WHEN WE LOOKED AT JSON FILE welcome_message = bot_data["welcome_message"]

class TrialManagement(commands.Cog):
    def __init__(self, bot, database):
        self.bot = bot
        self.db = database
        self.welcome_message = None
        asyncio.create_task(self.load_welcome_message())

    async def load_welcome_message(self):
        self.welcome_message = await self.db.get_welcome_message()

    print('RYAN BOT WORK')

    @app_commands.command(name="updatewelcomemessage", description="Update the welcome message for trial threads.")  # Use app_commands
    @app_commands.checks.has_permissions(administrator=True)  # Check for admin permissions
    async def update_welcome_message(self, interaction: discord.Interaction, new_message: str):
        """Allows an admin to update the welcome message dynamically."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return
        
        await self.db.set_welcome_message(new_message)
        self.welcome_message = new_message
        await interaction.response.send_message(f"Welcome message updated to: `{new_message}`", ephemeral=True)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        # Look up the Trial Raider role in the guild.
        trial_role = discord.utils.get(after.guild.roles, name=TRIAL_ROLE_NAME)
        if not trial_role:
            print(f"Role '{TRIAL_ROLE_NAME}' not found in guild {after.guild.name}")
            return

        # 1. If the user has just received the Trial Raider role:
        if trial_role not in before.roles and trial_role in after.roles:
            trials_channel = discord.utils.get(after.guild.channels, name=TRIAL_CHANNEL_NAME)
            if not trials_channel:
                print(f"Channel '{TRIAL_CHANNEL_NAME}' not found in guild {after.guild.name}")
                return

            try:
                # Create a private thread in the trials channel.
                thread = await trials_channel.create_thread(
                    name=after.display_name,  # Using the user's display name as the thread name.
                    auto_archive_duration=10080,
                    type=discord.ChannelType.private_thread,
                    reason="Creating trial thread for new Trial Raider"
                )
                # Invite the member to the thread.
                await thread.add_user(after)

                # 3. Send a welcome message in the thread.
                #welcome_message = f"# Welcome to your trial thread, {after.mention}!\n- This thread exists as a way to privately chat with <@&1291413329751048243> about any concerns, suggestions, issues, or comments you might have during your trial.\n- This thread will also be used to provide feedback on your trial 😄\n- You can view the overview of requirements and expectations of your trial here: https://discord.com/channels/1291413329444737096/1294140302663225439/1294142408455487522"

                formatted_message = self.welcome_message.replace("{mention}", after.mention).replace("\\n", "\n")
                await thread.send(formatted_message)

                # 2. Send a DM to the user with a link to the thread.
                try:
                    await after.send(f"Hi {after.display_name}, your trial thread is ready: {thread.jump_url}")
                except discord.Forbidden:
                    print(f"Could not DM {after.display_name}. They might have DMs disabled.")

                # Store thread ID persistently
                await self.db.set_trial_thread(after.id, thread.id)


            except Exception as e:
                print(f"Error creating trial thread for {after.display_name}: {e}")

        # 4. If the Trial Raider role is removed, delete the thread.
        elif trial_role in before.roles and trial_role not in after.roles:
            print(f"Trial role removed for {after.display_name}")
            #thread_id = trial_threads.get(str(after.id))
            thread_id = await self.db.get_trial_thread(after.id)
            if not thread_id:
                print("No thread mapping found for", after.display_name)
                return
            
            print(f"Found thread id {thread_id} for {after.display_name}")
            # Attempt to get the thread from cache
            thread = after.guild.get_channel(thread_id)
            print('RYAN THREAD: ', thread)
            if thread is None:
                print("Thread not found in cache, attempting to fetch...")
                try:
                    thread = await self.bot.fetch_channel(thread_id)
                except Exception as e:
                    print(f"Error fetching thread: {e}")
                    return
            
            try:
                await thread.delete(reason="Trial Raider role removed")
                print(f"Deleted trial thread for {after.display_name}")
            except Exception as e:
                print(f"Error deleting trial thread for {after.display_name}: {e}")
            
           
            await self.db.delete_trial_thread(after.id)

async def setup(bot):
    from db import Database
    database = Database()
    await database.connect()
    await bot.add_cog(TrialManagement(bot))

