import discord
from discord.ext import commands
import os
import json
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

#load_dotenv()
#TOKEN = "MTMzNjczODI1NTIxNDczOTQ2Nw.Gy5cmi.HJBvPBDuFxhuF99vanJvKhKy7DjgiQy1bmtlOs"

# Set up intents. We need members intent to get role updates.
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Dictionary to track trial threads: mapping user_id -> thread_id.
#trial_threads = {}

# Customize these to match your server’s configuration.
TRIAL_ROLE_NAME = "Trial Raider"
TRIAL_CHANNEL_NAME = "trials"
DATA_FILE = "bot_data.json"

# Load bot data (including welcome message and trial threads)
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {"trial_threads": {}, "welcome_message": "Welcome to your trial thread 1, {mention}!"}
    return {"trial_threads": {}, "welcome_message": "Welcome to your trial thread 2, {mention}!"}

# Save bot data
def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(bot_data, f)

# Load data
bot_data = load_data()
trial_threads = bot_data["trial_threads"]
welcome_message = bot_data["welcome_message"]

@bot.event
async def on_ready():
    await bot.change_presence(status=discord.Status.online, activity=discord.Game("Managing trials"))
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    try:
        await bot.tree.sync()  # Force sync application commands
        print("Slash commands synced successfully.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")


@bot.tree.command(name="updatewelcomemessage", description="Update the welcome message for trial threads.")
async def update_welcome_message(interaction: discord.Interaction, new_message: str):
    """Allows an admin to update the welcome message dynamically."""
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return
    
    global welcome_message
    welcome_message = new_message  # Update the variable
    bot_data["welcome_message"] = new_message  # Update the stored data
    save_data()  # Save changes to file
    
    await interaction.response.send_message(f"Welcome message updated to: `{new_message}`", ephemeral=True)

@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
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
                type=discord.ChannelType.private_thread,
                reason="Creating trial thread for new Trial Raider"
            )
            # Invite the member to the thread.
            await thread.add_user(after)

            # 3. Send a welcome message in the thread.
            #welcome_message = f"# Welcome to your trial thread, {after.mention}!\n- This thread exists as a way to privately chat with <@&1291413329751048243> about any concerns, suggestions, issues, or comments you might have during your trial.\n- This thread will also be used to provide feedback on your trial 😄\n- You can view the overview of requirements and expectations of your trial here: https://discord.com/channels/1291413329444737096/1294140302663225439/1294142408455487522"

            formatted_message = welcome_message.replace("{mention}", after.mention)
            await thread.send(formatted_message)

            # 2. Send a DM to the user with a link to the thread.
            try:
                await after.send(f"Hi {after.display_name}, your trial thread is ready: {thread.jump_url}")
            except discord.Forbidden:
                print(f"Could not DM {after.display_name}. They might have DMs disabled.")

            # Store thread ID persistently
            trial_threads[str(after.id)] = thread.id
            save_data()


        except Exception as e:
            print(f"Error creating trial thread for {after.display_name}: {e}")

    # 4. If the Trial Raider role is removed, delete the thread.
    elif trial_role in before.roles and trial_role not in after.roles:
        print(f"Trial role removed for {after.display_name}")
        thread_id = trial_threads.get(str(after.id))
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
                thread = await bot.fetch_channel(thread_id)
            except Exception as e:
                print(f"Error fetching thread: {e}")
                return
        
        try:
            await thread.delete(reason="Trial Raider role removed")
            print(f"Deleted trial thread for {after.display_name}")
        except Exception as e:
            print(f"Error deleting trial thread for {after.display_name}: {e}")
        
        trial_threads.pop(str(after.id), None)
        save_data()

bot.run(TOKEN)

