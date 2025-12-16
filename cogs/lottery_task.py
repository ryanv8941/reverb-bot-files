import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta, timezone


class Lottery(commands.Cog):
    def __init__(self, bot, database):
        self.bot = bot
        self.db = database
        self.lottery_channel_name = "lottery"  # channel name for lottery announcements
        self.lottery_task.start()  # start the background task to run lotteries automatically
        


    # ----------------------
    # /buyticket command
    # ----------------------
    @app_commands.command(name="buyticket", description="Buy lottery tickets")
    @app_commands.describe(amount="Number of tickets to buy")
    @app_commands.choices(amount=[
        app_commands.Choice(name="1 ticket", value=1),
        app_commands.Choice(name="2 tickets", value=2),
        app_commands.Choice(name="5 tickets", value=5),
        app_commands.Choice(name="10 tickets", value=10),
    ])
    async def buyticket(self, interaction: discord.Interaction, amount: int):

        user_id = interaction.user.id
        active_lottery = await self.db.get_active_lottery()
        if not active_lottery:
            await interaction.response.send_message("There is no active lottery at the moment.", ephemeral=True)
            return

        lottery_id = active_lottery['id']
        ticket_price = int(active_lottery['ticket_price'])

        user_balance = int(await self.db.get_gold_balance(user_id) or 0)
        total_cost = amount * ticket_price

        if total_cost > user_balance:
            await interaction.response.send_message("You do not have enough gold to buy that many tickets.", ephemeral=True)
            return

        try:
            await self.db.buy_lottery_tickets(user_id, lottery_id, amount)
            await self.db.add_ledger_entry(user_id, -total_cost, reason="lottery_ticket", reference_id=f"lottery:{lottery_id}")
            new_balance = await self.db.get_gold_balance(user_id) or 0

            await interaction.response.send_message(
                f"You successfully bought {amount} lottery ticket(s) for {total_cost:,}g! New balance: {new_balance:,}g.",
                ephemeral=True
            )

            guild = interaction.guild
            mod_log_channel = discord.utils.get(guild.text_channels, name="mod-logs")
            if mod_log_channel:
                await mod_log_channel.send(
                    f"💰 {interaction.user.mention} bought {amount} lottery ticket(s) for Lottery #{active_lottery['lottery_number']} "
                    f"for {total_cost:,}g. New balance: {new_balance:,}g."
                )




        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)


        

        total_tickets = await self.db.get_lottery_total_tickets(lottery_id)

        message_id = active_lottery["message_id"]

        guild = interaction.guild
        channel = discord.utils.get(guild.text_channels, name=self.lottery_channel_name)

        if channel and message_id:
            try:
                message = await channel.fetch_message(message_id)
                # Convert string dates to datetime objects
                start_time = datetime.fromisoformat(active_lottery["start_time"]) if isinstance(active_lottery["start_time"], str) else active_lottery["start_time"]
                end_time = datetime.fromisoformat(active_lottery["end_time"]) if isinstance(active_lottery["end_time"], str) else active_lottery["end_time"]
                
                new_text = self.format_lottery_message(
                    lottery_number=active_lottery["lottery_number"],
                    start_time=start_time,
                    end_time=end_time,
                    ticket_price=active_lottery["ticket_price"],
                    guild_cut=active_lottery["guild_cut_percent"],
                    total_tickets=total_tickets
                )
                await message.edit(content=new_text)
            except discord.NotFound:
                pass



    
    def format_lottery_message(
        self,
        lottery_number: int,
        start_time,
        end_time,
        ticket_price: int,
        guild_cut: int,
        total_tickets: int
    ) -> str:
        total_pot = total_tickets * ticket_price

        return (
            f"🎟️ **LOTTERY #{lottery_number} IS LIVE!**\n\n"
            f"**Rules**\n"
            f"• Ticket Price: **{ticket_price:,}g**\n"
            f"• Max Tickets per Player: **20**\n"
            f"• Guild Cut: **{guild_cut}%**\n\n"
            f"**Schedule**\n"
            f"• Start: {start_time:%Y-%m-%d %H:%M UTC}\n"
            f"• End: {end_time:%Y-%m-%d %H:%M UTC}\n\n"
            f"💰 **CURRENT POT:** **{total_pot:,}g**\n"
            f"🎫 **TOTAL TICKETS SOLD:** **{total_tickets}**\n\n"
            f"Use `/buyticket` to enter!"
        )

    # ----------------------
    # Background task to run lotteries automatically
    # ----------------------
    @tasks.loop(minutes=1)
    async def lottery_task(self):
        now = datetime.now(timezone.utc)
        active_lottery = await self.db.get_active_lottery()

        # Check if a new lottery should be created
        if not active_lottery:
            start_time = now
            end_time = start_time + timedelta(weeks=2)
            lottery_id = await self.db.create_lottery(start_time, end_time)
            
            # Fetch the created lottery to get lottery_number
            created_lottery = await self.db.get_active_lottery()
            if not created_lottery:
                return  # Should not happen, but safety check

            # Announce the lottery in the lottery channel
            guild = self.bot.guilds[0]  # assuming single guild
            lottery_channel = discord.utils.get(guild.text_channels, name=self.lottery_channel_name)
            if lottery_channel:
                message_text = self.format_lottery_message(
                    lottery_number=created_lottery['lottery_number'],
                    start_time=start_time,
                    end_time=end_time,
                    ticket_price=5000,
                    guild_cut=20,
                    total_tickets=0
                )

                message = await lottery_channel.send(message_text)

                await self.db.conn.execute(
                    "UPDATE lotteries SET message_id = ? WHERE id = ?",
                    (message.id, lottery_id)
                )
                await self.db.conn.commit()


        else:
            # Check if the active lottery has ended
            lottery_id = active_lottery['id']
            end_time_str = active_lottery['end_time']
            end_time = datetime.fromisoformat(end_time_str) if isinstance(end_time_str, str) else end_time_str
            if now >= end_time:
                payout_info = await self.db.close_lottery(lottery_id)
                guild = self.bot.guilds[0]
                lottery_channel = discord.utils.get(guild.text_channels, name=self.lottery_channel_name)
                if lottery_channel:
                    if payout_info:
                        
                        message_id = active_lottery['message_id']
                        channel = discord.utils.get(guild.text_channels, name=self.lottery_channel_name)

                        if channel and message_id:
                            try:
                                message = await channel.fetch_message(message_id)
                                await message.delete()
                            except discord.NotFound:
                                pass

                        
                        winner = guild.get_member(payout_info["winner_user_id"])
                        winner_text = winner.mention if winner else f"<@{payout_info['winner_user_id']}>"

                        await channel.send(
                            f"🎉 **LOTTERY #{active_lottery['lottery_number']} COMPLETE!**\n\n"
                            f"🏆 Winner: {winner_text}\n"
                            f"💰 Total Pot: **{payout_info['total_pot']:,}g**\n"
                            f"🏛️ Guild Cut: **{payout_info['guild_cut']:,}g**\n"
                            f"💎 Payout: **{payout_info['payout']:,}g**"
                        )
                    else:
                        await lottery_channel.send(f"Lottery #{lottery_id} ended with no tickets purchased.")


    @lottery_task.before_loop
    async def before_lottery_task(self):
        await self.bot.wait_until_ready()


async def setup(bot, database):
    # Make sure your bot has a `db` attribute or pass the db instance if you have one
    await bot.add_cog(Lottery(bot, database))
