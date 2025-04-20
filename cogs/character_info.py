import discord
from discord.ext import commands
from discord import app_commands
import json
import asyncio
import requests


RAIDERIO_BASE_URL_API = 'https://raider.io/api/v1/characters/profile'
RAIDERIO_CHAR_PROFILE_URL = 'https://raider.io/characters/us/'
WARCRAFT_LOGS_URL = 'https://www.warcraftlogs.com/character/us/'
RECRUIT_FINDS_CHANNEL = '1308802260129677404'

class CharacterInfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="characterinfo", description="Fetch character info and links")
    @app_commands.describe(character_name="The character name", realm="The realm of the character")
    async def characterinfo(self, interaction: discord.Interaction, character_name: str, realm: str):

        await interaction.response.defer()

        msg_string = ''
        raiderio_page = RAIDERIO_CHAR_PROFILE_URL + realm + '/' + character_name
        warcraftlogs_page = WARCRAFT_LOGS_URL + realm + '/' + character_name
        params = {
            'region': 'us',
            'realm': realm.replace(' ', '-').lower(),
            'name': character_name,
            'fields': 'raid_progression:current-expansion,mythic_plus_scores_by_season:current'
        }

        response = requests.get(RAIDERIO_BASE_URL_API, params=params)

        if response.status_code != 200:
            await interaction.followup.send("Character not found on Raider.io, check name and realm")
            return
        
        data = response.json()
        score_data = data["mythic_plus_scores_by_season"][0]["segments"]["all"]

        embed = discord.Embed(
            title=f"{character_name} - {realm}",
            url=raiderio_page,
            description=f"Character information for {character_name} on {realm}",
            color=int(score_data["color"].replace("#", ""), 16)  # Color from RaiderIO score
        )


        embed.add_field(name="Class and Spec", value=f"{data['active_spec_name']} {data['class']}")
        embed.add_field(name="RaiderIO Score", value=f"{score_data['score']}", inline=False)

        raid_prog_string = ""
        for raid in data["raid_progression"]:
            raid_name = raid.replace('-', ' ').title()  # Format the raid name
            raid_summary = data["raid_progression"][raid]["summary"]
            raid_prog_string += f"{raid_name}: {raid_summary}\n"
    
        embed.add_field(name="Raid Progression", value=raid_prog_string or "No raid progression data available.", inline=False)
        embed.add_field(name="RaiderIO Link", value=raiderio_page, inline=False)
        embed.add_field(name="Warcraft Logs Link", value=warcraftlogs_page, inline=False)
        embed.set_footer(text=f"Last crawled at: {data['last_crawled_at']}")
        embed.set_thumbnail(url=data["thumbnail_url"])

        
        

        await interaction.followup.send(embed=embed)
        
"""         raid_prog_string = ''
        score_data = data["mythic_plus_scores_by_season"][0]["segments"]["all"]

        for raid in data["raid_progression"]:
            raid_prog_string += raid.replace('-', ' ') + ': ' + data['raid_progression'][raid]['summary'] + '\n'

        msg_string += '**Name:** ' + character_name + ' **Realm:** ' + realm
        msg_string += '\n**Raid Progression:**\n' + raid_prog_string
        score_data = data["mythic_plus_scores_by_season"][0]["segments"]["all"]
        msg_string += f'**RaiderIO Score**: {score_data["score"]} (Color: {score_data["color"]})\n'
        msg_string += '**RaiderIO Link:** ' + raiderio_page + '\n'
        msg_string += '**Warcraft Logs Link:** ' + warcraftlogs_page



        await interaction.followup.send(msg_string)
 """


        
        
async def setup(bot):
    await bot.add_cog(CharacterInfo(bot))