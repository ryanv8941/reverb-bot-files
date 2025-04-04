from playwright.sync_api import sync_playwright
import time
import requests
import asyncio
import os
import time
import discord
from discord.ext import commands
from discord import app_commands

WOW_AUDIT_TOKEN = os.getenv('WOW_AUDIT_TOKEN')
WOW_AUDIT_URL = 'https://wowaudit.com/v1/characters'
WOW_AUDIT_UPLOAD_URL = 'https://wowaudit.com/v1/wishlists'
EMAIL = os.getenv('RAIDBOTS_EMAIL')
PASSWORD = os.getenv('RAIDBOTS_PASSWORD')
sim_string = []
headers = {
    'Authorization': f'Bearer {WOW_AUDIT_TOKEN}',  # Only if needed
    'Accept': 'application/json'
}


class WowAuditSims(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="runsims", description="runs sims for every team member and uploads to wowaudit wishlist")  # Use app_commands
    @app_commands.checks.has_permissions(administrator=True)  # Check for admin permissions
    async def run_sims(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return
        
        response = requests.get(WOW_AUDIT_URL, headers=headers)
        # Handle the response
        if response.status_code == 200:
            characters = response.json()
            #print(f'JSON HERE ----> {characters}')
        else:
            print(f"Failed to retrieve data. Status code: {response.status_code}")
            print(response.text)
        # Filter out characters with role 'healer'
        filtered_characters = [char for char in characters if char.get("role") != "Heal"]
        print(f'JSON HERE ----> {filtered_characters}')


        log_channel = interaction.channel

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.start_process, filtered_characters, log_channel)

    
    def start_process(self, char_list, log_channel):
        def send_log(msg):
            asyncio.run_coroutine_threadsafe(log_channel.send(msg), self.bot.loop)
        
        asyncio.run_coroutine_threadsafe(
            self.bot.change_presence(activity=discord.Game("Running Sims")),
            self.bot.loop
        )

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page()

            page.goto("https://www.raidbots.com/auth")
            page.wait_for_selector("input[name='email']", state="visible")
            page.fill("input[name='email']", EMAIL)
            page.fill("input[name='password']", PASSWORD)
            page.click("button:has-text('Login')")
            page.wait_for_url("https://www.raidbots.com/simbot", timeout=15000)
            send_log("✅ Logged in and ready to run simulations!")

            # Loop through characters and simulate
            for char in char_list:
                #send_log(f"Starting sim for {char['name']}")
                result = self.run_droptimizer(page, char["realm"], char["name"], char["id"], send_log)
                sim_string.append(result)
                #send_log(f"✅ Sim complete for {char['name']} - Report ID: {result['report_id']}")

            browser.close()
        
        asyncio.run_coroutine_threadsafe(
            self.bot.change_presence(activity=discord.Game("Managing Trials")),
            self.bot.loop
        )

    def run_droptimizer(self, page, realm, name, id, send_log):
        page.goto("https://www.raidbots.com/simbot/droptimizer")
        page.wait_for_load_state("load")

        page.wait_for_selector("div#ArmoryInput-armoryRealm:visible", timeout=10000)
        page.click("div#ArmoryInput-armoryRealm input")  # Click the input inside the div

        page.keyboard.type(realm)
        page.keyboard.press("Enter")
        page.fill("input#ArmoryInput-armorySearch", name)

        time.sleep(5)

        element = page.locator("text=Liberation of Undermine").first
        element.scroll_into_view_if_needed()
        element.click()

        dropdowns = page.locator("div[class*='css-1d8n9bt']")
        second_dropdown = dropdowns.nth(1)

        # Click to open the second dropdown
        second_dropdown.click()

        # Wait for the options to appear
        page.wait_for_selector("div[id^='react-select'][id$='-listbox'] div", timeout=5000)

        # Click the second option
        page.locator("div[id^='react-select'][id$='-listbox'] div").nth(2).click()

        #time.sleep(10)
        page.click("button:has-text('Run Droptimizer')")

        #page.wait_for_selector("text=Job Status: Processing", timeout=15000)
        send_log(f"✅ {name} simulation queued...")

        page.wait_for_selector("text=Boss Summary", timeout=300000)  # Wait up to 5 minutes
        rep_id = page.url.split("/")[-1]
        send_log(f"✅ Sim finished for {name} - Report ID: {rep_id}")
        print("Result URL:", page.url)
        print()

        

        body = {
            "report_id": rep_id,
            "character_id": id,
            "character_name": name,
            "configuration_name": "Single Target",
            "replace_manual_edits": True,
            "clear_conduits": True
        }

        response2 = requests.post(WOW_AUDIT_UPLOAD_URL, headers=headers, json=body)
        # Handle the response
        if response2.status_code == 200 or response2.status_code == 201:
            send_log(f"✅ Successfully updated WowAudit for {body['character_name']}")
        else:
            send_log(f"Failed to retrieve data. Status code: {response2.status_code}")
            send_log(response2.text)

async def setup(bot):
    await bot.add_cog(WowAuditSims(bot))
    