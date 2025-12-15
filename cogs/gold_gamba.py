import discord
import asyncio
import random
from discord import app_commands
from discord.ext import commands


class GoldGamba(commands.Cog):
    def __init__(self, bot, database):
        self.bot = bot
        self.db = database
        self.active_wheel_users = set()  # Track users currently spinning

    # ----------------------
    # /balance
    # ----------------------
    @app_commands.command(name="balance", description="Check your gold balance")
    async def balance(self, interaction: discord.Interaction):
        balance = await self.db.get_gold_balance(interaction.user.id)
        await interaction.response.send_message(
            f"💰 Your current gold balance is **{balance:,}g**",
            ephemeral=True
        )

    # ----------------------
    # /credit (OFFICER ONLY)
    # ----------------------
    @app_commands.command(name="credit", description="Credit gold to a user (officers only)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def credit(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: int
    ):
        if amount <= 0:
            await interaction.response.send_message(
                "Amount must be greater than 0.",
                ephemeral=True
            )
            return

        new_balance = await self.db.credit_gold(
            officer_id=interaction.user.id,
            user_id=user.id,
            amount=amount
        )

        if new_balance is None:
            new_balance = await self.db.get_gold_balance(user.id)

        # Send confirmation in the channel
        await interaction.response.send_message(
            embed=discord.Embed(
                title="Gold Credited",
                description=f"**{amount:,}g** has been credited to {user.mention}.\nNew balance: **{new_balance:,}g**",
                color=discord.Color.green()
            )
        )

        # DM the credited user
        try:
            await user.send(
                embed=discord.Embed(
                    title="Gold Received!",
                    description=f"💰 You have been credited **{amount:,}g**.\nYour new gold balance is **{new_balance:,}g**.",
                    color=discord.Color.gold()
                )
            )
        except discord.Forbidden:
            pass

     # ----------------------
    # /coinflip
    # ----------------------
    @app_commands.command(name="coinflip", description="Flip a coin and bet gold")
    @app_commands.choices(guess=[
        app_commands.Choice(name="Heads", value="heads"),
        app_commands.Choice(name="Tails", value="tails")
    ])
    async def coinflip(
        self,
        interaction: discord.Interaction,
        wager: int,
        guess: app_commands.Choice[str]
    ):
    
        choice = guess.value.lower()
        if choice not in ("heads", "tails"):
            await interaction.response.send_message(
                "Choice must be 'heads' or 'tails'.",
                ephemeral=True
            )
            return

        result = random.choice(["heads", "tails"])
        win = choice == result
        payout = wager * 2 if win else 0

        try:
            await self.db.place_bet(
                user_id=interaction.user.id,
                game="coinflip",
                wager=wager,
                outcome="win" if win else "loss",
                payout=payout
            )
        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        balance = await self.db.get_gold_balance(interaction.user.id)

        if win:
            msg = (
                f"🪙 **Coinflip Result:** {result.upper()}\n"
                f"🎉 You won **{payout:,}g**!\n"
                f"💰 New balance: **{balance:,}g**"
            )
        else:
            msg = (
                f"🪙 **Coinflip Result:** {result.upper()}\n"
                f"❌ You lost **{wager:,}g**.\n"
                f"💰 New balance: **{balance:,}g**"
            )

        await interaction.response.send_message(msg)


    # ----------------------
    # /wheel (Spin the Wheel game with animation)
    # ----------------------
    @app_commands.command(name="wheel", description="Spin the gold wheel")
    async def wheel(self, interaction: discord.Interaction, amount: int):
        user_id = interaction.user.id

        # Prevent multiple spins at the same time
        if user_id in self.active_wheel_users:
            await interaction.response.send_message("You already have a wheel spin in progress. Please wait for it to finish.", ephemeral=True)
            return

        self.active_wheel_users.add(user_id)

        try:
            if amount <= 0:
                await interaction.response.send_message("Bet amount must be greater than 0.", ephemeral=True)
                return

            user_balance = await self.db.get_gold_balance(user_id) or 0
            if amount > user_balance:
                await interaction.response.send_message("You do not have enough gold to bet that amount.", ephemeral=True)
                return

            # Define wheel segments with adjusted payouts
            wheel_segments = [
                ("5x Gold!", 5, 2),
                ("2.5x Gold!", 2.5, 6),
                ("2x Gold!", 2, 8),
                ("1.5x Gold", 1.5, 12),
                ("1x Gold", 1, 22),
                ("0.5x Gold", .5, 20),
                ("Lose Gold", 0, 30)  # house edge
            ]

            labels, multipliers, weights = zip(*wheel_segments)
            result_index = random.choices(range(len(wheel_segments)), weights=weights)[0]
            result_label = labels[result_index]
            multiplier = multipliers[result_index]

            payout = amount * multiplier

            await self.db.place_bet(
                user_id=user_id,
                game="wheel",
                wager=amount,
                outcome=result_label,
                payout=payout
            )

            await interaction.response.send_message("Spinning the wheel...", ephemeral=True)
            spinning_message = await interaction.original_response()

            wheel_frames = []
            for i in range(len(labels)):
                frame = []
                for j, label in enumerate(labels):
                    if j == i:
                        frame.append(f"__**{label}**__")
                    else:
                        frame.append(label)
                wheel_frames.append(" | ".join(frame))

            for _ in range(3):
                for frame in wheel_frames:
                    await spinning_message.edit(content=f"🎡 {frame}")
                    await asyncio.sleep(0.3)

            final_frame = []
            for j, label in enumerate(labels):
                if j == result_index:
                    final_frame.append(f"__**{label}**__")
                else:
                    final_frame.append(label)
            await spinning_message.edit(content=f"🎡 {' | '.join(final_frame)}\nYou landed on **{result_label}**!")

            new_balance = await self.db.get_gold_balance(user_id) or 0
            embed = discord.Embed(
                title="🎡 Gold Wheel Result!",
                description=f"{interaction.user.mention} spun the wheel and landed on **{result_label}**!",
                color=discord.Color.gold()
            )
            embed.add_field(name="Bet Amount", value=f"**{amount:,}g**", inline=True)
            embed.add_field(name="Payout", value=f"**{payout:,}g**", inline=True)
            embed.add_field(name="New Balance", value=f"**{new_balance:,}g**", inline=True)

            await interaction.followup.send(embed=embed, ephemeral=False)

        finally:
            self.active_wheel_users.remove(user_id)



    # ----------------------
    # /payout_request
    # ----------------------
    @app_commands.command(name="payout_request", description="Request a payout to an in-game character")
    async def payout_request(
        self,
        interaction: discord.Interaction,
        amount: int,
        character: str,
        server: str
    ):
        if amount <= 0:
            await interaction.response.send_message("Amount must be greater than 0.", ephemeral=True)
            return

        # Fetch user's total gold balance
        user_balance = await self.db.get_gold_balance(interaction.user.id) or 0

        # Fetch sum of all pending payouts
        pending_sum = await self.db.get_pending_payout_sum(interaction.user.id) or 0

        available_balance = user_balance - pending_sum

        if amount > available_balance:
            await interaction.response.send_message(
                "You do not have enough available gold for this payout (If you have a pending payout request please wait for it to be completed before requesting a new one).",
                ephemeral=True
            )
            return

        payout_id = await self.db.create_payout_request(interaction.user.id, amount)

        # Send confirmation to the user
        await interaction.response.send_message(
            f"✅ Payout request for **{amount:,}g** to **{character}** has been submitted.",
            ephemeral=True
        )

        # Notify officers in the gamba-payouts channel as an embed
        guild = interaction.guild
        payout_channel = discord.utils.get(guild.text_channels, name="gamba-payouts")
        if payout_channel:
            embed = discord.Embed(
                title="💰 Payout Request",
                color=discord.Color.gold()
            )
            embed.add_field(name="User", value=interaction.user.mention, inline=True)
            embed.add_field(name="Amount", value=f"{amount:,}g", inline=True)
            embed.add_field(name="Character", value=character, inline=True)
            embed.add_field(name="Server", value=server, inline=True)
            embed.add_field(name="Status", value="Waiting", inline=True)
            embed.set_footer(text=f"Payout ID: {payout_id}")

            class PayoutSelect(discord.ui.Select):
                def __init__(self, db, embed):
                    options = [
                        discord.SelectOption(label="Waiting", value="waiting", default=True),
                        discord.SelectOption(label="Complete", value="complete")
                    ]
                    super().__init__(placeholder="Change status...", min_values=1, max_values=1, options=options)
                    self.db = db
                    self.embed = embed

                async def callback(self, interaction: discord.Interaction):
                    if self.values[0] == "complete":
                        officer_id = interaction.user.id
                        payout_id_text = self.embed.footer.text
                        payout_id = int(payout_id_text.replace('Payout ID: ', ''))
                        user_mention = self.embed.fields[0].value
                        user_id = int(user_mention.strip('<@!>'))

                        await self.db.complete_payout(payout_id, officer_id)

                        # Update the embed's status field
                        self.embed.set_field_at(4, name="Status", value="Complete", inline=True)

                        # Notify user with an embed
                        user = interaction.guild.get_member(user_id)
                        if user:
                            try:
                                dm_embed = discord.Embed(
                                    title="Payout Completed!",
                                    color=discord.Color.green()
                                )
                                dm_embed.add_field(name="Amount Paid", value=f"**{self.embed.fields[1].value}**", inline=False)
                                new_balance = await self.db.get_gold_balance(user_id) or 0
                                dm_embed.add_field(name="New Balance", value=f"**{new_balance:,}g**", inline=False)

                                character = self.embed.fields[2].value
                                server = self.embed.fields[3].value
                                dm_embed.add_field(
                                    name="Info",
                                    value=f"Payout Completed! Gold has been mailed to **{character}-{server}**. Please wait up to an hour for mail to arrive.",
                                    inline=False
                                )

                                await user.send(embed=dm_embed)
                            except discord.Forbidden:
                                pass

                        # Disable the dropdown
                        self.disabled = True
                        await interaction.response.edit_message(embed=self.embed, view=self.view)

            view = discord.ui.View()
            view.add_item(PayoutSelect(self.db, embed))
            await payout_channel.send(embed=embed, view=view)

    
    # ----------------------
    # /ledger (Officer overview of gold economy)
    # ----------------------
    @app_commands.command(name="ledger", description="View total credited gold vs total player balances")
    @app_commands.checks.has_permissions(administrator=True)
    async def ledger(self, interaction: discord.Interaction):
        """Officer-only command showing gold credited vs outstanding balances."""
        total_credited = await self.db.get_total_credited_gold()
        total_balances = await self.db.get_total_gold_balance()
        house_position = total_credited - total_balances

        embed = discord.Embed(
            title="📒 Gold Ledger Overview",
            color=discord.Color.blue()
        )
        embed.add_field(name="Total Gold Credited", value=f"**{total_credited:,}g**", inline=False)
        embed.add_field(name="Total Player Balances", value=f"**{total_balances:,}g**", inline=False)
        embed.add_field(name="Guild Position", value=f"**{house_position:,}g**", inline=False)
        embed.set_footer(text="Guild Position = Credited − Outstanding Balances")

        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot, database):
    await bot.add_cog(GoldGamba(bot, database))
