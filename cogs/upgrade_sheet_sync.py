import os
import requests
from discord.ext import commands
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

WOW_AUDIT_TOKEN = os.getenv('WOW_AUDIT_TOKEN')
GOOGLE_SHEET_ID = os.getenv('GOOGLE_SHEET_ID')
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE')

headers = {
    'Authorization': f'Bearer {WOW_AUDIT_TOKEN}',
    'Accept': 'application/json'
}

class UpgradeSheetSync(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    from discord import app_commands

    @app_commands.command(name="syncupgrades", description="Syncs upgrade %s from WowAudit to Google Sheets, ordered by boss and player upgrade %.")
    async def syncupgrades(self, interaction):
        # Only allow admins to use this command
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You must be an admin to use this command.", ephemeral=True)
            return
        await interaction.response.send_message("Fetching upgrade data from WowAudit...", ephemeral=True)
        boss_upgrades, raid_name = self.fetch_upgrade_data()
        if not boss_upgrades:
            await interaction.followup.send("No upgrade data found or API error.", ephemeral=True)
            return
        await interaction.followup.send("Updating Google Sheet...", ephemeral=True)
        result = self.update_google_sheet(boss_upgrades, raid_name)
        if result:
            await interaction.followup.send("✅ Sheet updated!", ephemeral=True)
        else:
            await interaction.followup.send("❌ Failed to update sheet.", ephemeral=True)

    def fetch_upgrade_data(self):
        # Use /v1/wishlists endpoint
        response = requests.get('https://wowaudit.com/v1/wishlists', headers=headers)
        if response.status_code != 200:
            print("Failed to fetch upgrade data")
            return {}, None
        data = response.json()
        boss_upgrades = {}
        raid_name = None
        # For each character, get only the last instance (most recent raid)
        for char in data.get('characters', []):
            instances = char.get('instances', [])
            if not instances:
                continue
            last_instance = instances[-1]
            if not raid_name:
                raid_name = last_instance.get('name')
            for diff in last_instance.get('difficulties', []):
                # Only process mythic difficulty
                if diff.get('difficulty') != 'mythic':
                    continue
                wishlist = diff.get('wishlist', {})
                encounters = wishlist.get('encounters', [])
                for encounter in encounters:
                    boss_name = encounter.get('name')
                    percent = encounter.get('encounter_percentage', 0)
                    if not boss_name:
                        continue
                    if boss_name not in boss_upgrades:
                        boss_upgrades[boss_name] = []
                    boss_upgrades[boss_name].append({
                        'name': char.get('name'),
                        'realm': char.get('realm'),
                        'upgrade_percent': percent
                    })
        # Sort each boss's list by upgrade % descending
        for boss in boss_upgrades:
            boss_upgrades[boss].sort(key=lambda x: x['upgrade_percent'], reverse=True)
        return boss_upgrades, raid_name

    def update_google_sheet(self, boss_upgrades, raid_name):
        import datetime
        try:
            import tempfile
            import json
            sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
            if sa_json and sa_json.strip().startswith('{'):
                # If the env variable is a JSON string, write to a temp file
                with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.json') as tmp:
                    tmp.write(sa_json)
                    tmp.flush()
                    creds = Credentials.from_service_account_file(tmp.name, scopes=["https://www.googleapis.com/auth/spreadsheets"])
            else:
                creds = Credentials.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/spreadsheets"])
            service = build('sheets', 'v4', credentials=creds)
            sheet = service.spreadsheets()


            bosses = list(boss_upgrades.keys())
            max_rows = max(len(upgrades) for upgrades in boss_upgrades.values())
            now_str = datetime.datetime.now().strftime("Last updated: %Y-%m-%d %H:%M:%S")

            # Row 1: A1 = last updated, rest empty
            header_row_1 = [now_str] + [None]*(2*len(bosses))
            # Row 2: A2 = raid name, B2+ = boss headers
            boss_headers = []
            for boss in bosses:
                boss_headers += [boss, "% UPGRADE"]
            header_row_2 = [raid_name] + boss_headers

            # Prepare data rows, starting from column B
            data_rows = []
            for i in range(max_rows):
                row = [None]  # A column left blank
                for boss in bosses:
                    upgrades = boss_upgrades[boss]
                    if i < len(upgrades):
                        row += [upgrades[i]['name'], upgrades[i]['upgrade_percent']]
                    else:
                        row += ["", ""]
                data_rows.append(row)

            # Combine all rows
            values = [header_row_1, header_row_2] + data_rows
            body = {"values": values}
            sheet.values().update(
                spreadsheetId=GOOGLE_SHEET_ID,
                range="Upgrade % Sheet!A1",
                valueInputOption="RAW",
                body=body
            ).execute()

            # Add basic styling: bold headers, center columns
            # Get the sheetId for 'Upgrade % Sheet'
            spreadsheet = sheet.get(spreadsheetId=GOOGLE_SHEET_ID).execute()
            sheet_id = None
            for s in spreadsheet['sheets']:
                if s['properties']['title'] == 'Upgrade % Sheet':
                    sheet_id = s['properties']['sheetId']
                    break
            if sheet_id is None:
                print("Sheet 'Upgrade % Sheet' not found!")
                return False

            requests_body = {
                "requests": [
                    {
                        "repeatCell": {
                            "range": {
                                "sheetId": sheet_id,
                                "startRowIndex": 0,
                                "endRowIndex": 2
                            },
                            "cell": {
                                "userEnteredFormat": {
                                    "textFormat": {"bold": True},
                                    "horizontalAlignment": "CENTER",
                                    "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}
                                }
                            },
                            "fields": "userEnteredFormat(textFormat,horizontalAlignment,backgroundColor)"
                        }
                    },
                    {
                        "repeatCell": {
                            "range": {
                                "sheetId": sheet_id,
                                "startRowIndex": 2,
                                "endRowIndex": 2+max_rows
                            },
                            "cell": {
                                "userEnteredFormat": {
                                    "horizontalAlignment": "CENTER"
                                }
                            },
                            "fields": "userEnteredFormat(horizontalAlignment)"
                        }
                    }
                ]
            }
            sheet.batchUpdate(
                spreadsheetId=GOOGLE_SHEET_ID,
                body=requests_body
            ).execute()
            return True
        except Exception as e:
            print(f"Google Sheets update error: {e}")
            return False

async def setup(bot):
    await bot.add_cog(UpgradeSheetSync(bot))
