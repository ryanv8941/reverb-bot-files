import aiosqlite
import os
import datetime
from datetime import timezone
import random

class Database:
    def __init__(self, db_path: str = "reverb_bot.db"):
        self.db_path = db_path
        self.conn = None

    async def connect(self):
        """Connect to SQLite database and create tables if they don't exist."""
        self.conn = await aiosqlite.connect(self.db_path)
        await self.conn.execute("PRAGMA foreign_keys = ON")
        
        # Create tables if they don't exist
        await self._create_tables()
        print("[DB] SQLite connection established successfully.")

    async def _create_tables(self):
        """Create all necessary tables if they don't exist."""
        # Create trial_threads table
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS trial_threads (
                user_id INTEGER PRIMARY KEY,
                thread_id INTEGER NOT NULL
            )
        """)
        
        # Create welcome_message table
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS welcome_message (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                message TEXT NOT NULL
            )
        """)
        
        # Insert default welcome message if table is empty
        cursor = await self.conn.execute("SELECT COUNT(*) FROM welcome_message")
        count = await cursor.fetchone()
        if count[0] == 0:
            await self.conn.execute("""
                INSERT INTO welcome_message (id, message) 
                VALUES (1, '# Welcome to your trial thread, {mention}!\n- This thread exists as a way to privately chat with <@&1291413329751048243> about any concerns, suggestions, issues, or comments you might have during your trial.\n- This thread will also be used to provide feedback on your trial 😄\n- You can view the overview of requirements and expectations of your trial here: https://discord.com/channels/1291413329444737096/1294140302663225439/1294142408455487522')
            """)
        
        # Create settings table
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                expansion_id INTEGER
            )
        """)

        # Create gold ledger
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS gold_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                reason TEXT NOT NULL,
                reference_id TEXT,
                officer_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create bets table
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS bets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                game TEXT NOT NULL,
                wager INTEGER NOT NULL,
                outcome TEXT NOT NULL,
                payout INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create payout requests table
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS payout_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                status TEXT NOT NULL,
                requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP,
                officer_id INTEGER,
                notes TEXT
            )
        """)


                # Create lotteries table
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS lotteries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lottery_number INTEGER NOT NULL,
                start_time DATETIME NOT NULL,
                end_time DATETIME NOT NULL,
                ticket_price INTEGER NOT NULL,
                guild_cut_percent INTEGER NOT NULL,
                message_id INTEGER NULL,
                status TEXT NOT NULL CHECK(status IN ('active','completed'))
            )
        """)

        # Create lottery_tickets table
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS lottery_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lottery_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                purchased_at DATETIME NOT NULL,
                FOREIGN KEY (lottery_id) REFERENCES lotteries(id)
            )
        """)

        # Create lottery_winners table
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS lottery_winners (
                lottery_id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                winning_ticket_id INTEGER NOT NULL,
                total_pot INTEGER NOT NULL,
                payout INTEGER NOT NULL,
                guild_cut INTEGER NOT NULL
            )
        """)
        
        # Insert default settings if table is empty
        cursor = await self.conn.execute("SELECT COUNT(*) FROM settings")
        count = await cursor.fetchone()
        if count[0] == 0:
            await self.conn.execute("""
                INSERT INTO settings (id, expansion_id) 
                VALUES (1, NULL)
            """)
        
        await self.conn.commit()

    async def close(self):
        """Close the database connection."""
        if self.conn:
            await self.conn.close()

    async def get_trial_thread(self, user_id: int):
        """Get the thread_id for a given user_id."""
        cursor = await self.conn.execute(
            "SELECT thread_id FROM trial_threads WHERE user_id = ?", 
            (user_id,)
        )
        result = await cursor.fetchone()
        return result[0] if result else None

    async def set_trial_thread(self, user_id: int, thread_id: int):
        """Set or update the thread_id for a given user_id."""
        await self.conn.execute(
            """
            INSERT OR REPLACE INTO trial_threads (user_id, thread_id)
            VALUES (?, ?)
            """,
            (user_id, thread_id)
        )
        await self.conn.commit()

    async def delete_trial_thread(self, user_id: int):
        """Delete the trial thread entry for a given user_id."""
        await self.conn.execute(
            "DELETE FROM trial_threads WHERE user_id = ?",
            (user_id,)
        )
        await self.conn.commit()

    async def get_welcome_message(self):
        """Get the welcome message."""
        cursor = await self.conn.execute("SELECT message FROM welcome_message WHERE id = 1")
        result = await cursor.fetchone()
        return result[0] if result else None
        
    async def set_welcome_message(self, welcome_message: str):
        """Update the welcome message."""
        await self.conn.execute(
            "UPDATE welcome_message SET message = ? WHERE id = 1",
            (welcome_message,)
        )
        await self.conn.commit()

    async def get_expansion_id(self):
        """Get the expansion_id from settings."""
        cursor = await self.conn.execute("SELECT expansion_id FROM settings WHERE id = 1")
        result = await cursor.fetchone()
        return result[0] if result else None

    async def set_expansion_id(self, expansion_id: int):
        """Update the expansion_id in settings."""
        await self.conn.execute(
            "UPDATE settings SET expansion_id = ? WHERE id = 1",
            (expansion_id,)
        )
        await self.conn.commit()

    

    #-----------------gamba helpers-----------------

    async def get_gold_balance(self, user_id: int) -> int:
        """Return the user's current gold balance."""
        cursor = await self.conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM gold_ledger
            WHERE user_id = ?
            """,
            (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


    async def add_ledger_entry(
        self,
        user_id: int,
        amount: int,
        reason: str,
        reference_id: str | None = None,
        officer_id: int | None = None
    ):
        """Add a gold ledger entry (credit, bet, win, loss, payout)."""
        await self.conn.execute(
            """
            INSERT INTO gold_ledger (
                user_id, amount, reason, reference_id, officer_id
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, amount, reason, reference_id, officer_id)
        )
        await self.conn.commit()


    async def credit_gold(
        self,
        user_id: int,
        amount: int,
        officer_id: int
    ):
        """Credit gold to a user (manual officer action)."""
        if amount <= 0:
            raise ValueError("Credit amount must be positive")

        await self.add_ledger_entry(
            user_id=user_id,
            amount=amount,
            reason="credit",
            officer_id=officer_id
        )

    async def place_bet(
        self,
        user_id: int,
        game: str,
        wager: int,
        outcome: str,
        payout: int
    ) -> int:
        """
        Record a bet and apply gold changes.
        Returns bet_id.
        """
        if wager <= 0:
            raise ValueError("Wager must be positive")

        balance = await self.get_gold_balance(user_id)
        if balance < wager:
            raise ValueError("Insufficient balance")

        # Create bet record
        cursor = await self.conn.execute(
            """
            INSERT INTO bets (user_id, game, wager, outcome, payout)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, game, wager, outcome, payout)
        )
        bet_id = cursor.lastrowid

        # Deduct wager
        await self.add_ledger_entry(
            user_id=user_id,
            amount=-wager,
            reason="bet",
            reference_id=f"bet:{bet_id}"
        )

        # Apply payout if win
        if payout > 0:
            await self.add_ledger_entry(
                user_id=user_id,
                amount=payout,
                reason="win",
                reference_id=f"bet:{bet_id}"
            )

        return bet_id

    
    async def create_payout_request(self, user_id: int, amount: int) -> int:
        """Create a payout request if user has enough balance."""
        if amount <= 0:
            raise ValueError("Payout amount must be positive")

        balance = await self.get_gold_balance(user_id)
        if balance < amount:
            raise ValueError("Insufficient balance")

        cursor = await self.conn.execute(
            """
            INSERT INTO payout_requests (user_id, amount, status)
            VALUES (?, ?, 'pending')
            """,
            (user_id, amount)
        )
        await self.conn.commit()
        return cursor.lastrowid


    async def complete_payout(
        self,
        payout_id: int,
        officer_id: int,
        notes: str | None = None
    ):
        """Mark payout as paid and deduct gold."""
        cursor = await self.conn.execute(
            """
            SELECT user_id, amount, status
            FROM payout_requests
            WHERE id = ?
            """,
            (payout_id,)
        )
        row = await cursor.fetchone()

        if not row:
            raise ValueError("Payout request not found")

        user_id, amount, status = row

        if status != "pending":
            raise ValueError("Payout already processed")

        # Deduct gold
        await self.add_ledger_entry(
            user_id=user_id,
            amount=-amount,
            reason="payout",
            reference_id=f"payout:{payout_id}",
            officer_id=officer_id
        )

        # Update payout status
        await self.conn.execute(
            """
            UPDATE payout_requests
            SET status = 'paid',
                processed_at = CURRENT_TIMESTAMP,
                officer_id = ?,
                notes = ?
            WHERE id = ?
            """,
            (officer_id, notes, payout_id)
        )
        await self.conn.commit()

    async def get_pending_payout_sum(self, user_id: int):
        """Return the sum of all pending payout requests for a user."""
        cursor = await self.conn.execute(
            "SELECT SUM(amount) FROM payout_requests WHERE user_id = ? AND status = 'pending'",
            (user_id,)
        )
        result = await cursor.fetchone()
        return result[0] if result[0] else 0


    async def get_total_credited_gold(self) -> int:
        cursor = await self.conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM gold_ledger
            WHERE reason = 'credit'
            """
        )
        row = await cursor.fetchone()
        return row[0] or 0


    async def get_total_gold_balance(self) -> int:
        cursor = await self.conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM gold_ledger
            """
        )
        row = await cursor.fetchone()
        return row[0] or 0




    # ----------------------------
    # Lottery helper functions
    # ----------------------------



    async def get_lottery_total_tickets(self, lottery_id: int) -> int:
        """Return the total number of tickets sold in a given lottery."""
        cursor = await self.conn.execute(
            "SELECT COUNT(*) FROM lottery_tickets WHERE lottery_id = ?",
            (lottery_id,)
        )
        count = await cursor.fetchone()
        return count[0] if count else 0


    async def get_active_lottery(self):
        """Return the active lottery row as a dictionary, or None if none exists."""
        cursor = await self.conn.execute(
            "SELECT id, lottery_number, start_time, end_time, ticket_price, guild_cut_percent, message_id, status FROM lotteries WHERE status = 'active' ORDER BY start_time DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            'id': row[0],
            'lottery_number': row[1],
            'start_time': row[2],
            'end_time': row[3],
            'ticket_price': row[4],
            'guild_cut_percent': row[5],
            'message_id': row[6],
            'status': row[7]
        }



    async def create_lottery(self, start_time: datetime.datetime, end_time: datetime.datetime,
                            ticket_price: int = 5000, guild_cut_percent: int = 20):
        """Create a new lottery and return its ID."""
        # Determine next lottery number
        cursor = await self.conn.execute("SELECT MAX(lottery_number) FROM lotteries")
        last_number = await cursor.fetchone()
        lottery_number = (last_number[0] or 0) + 1

        cursor = await self.conn.execute("""
            INSERT INTO lotteries (lottery_number, start_time, end_time, ticket_price, guild_cut_percent, status)
            VALUES (?, ?, ?, ?, ?, 'active')
        """, (lottery_number, start_time, end_time, ticket_price, guild_cut_percent))
        await self.conn.commit()
        return cursor.lastrowid



    async def buy_lottery_tickets(self, user_id: int, lottery_id: int, amount: int):
        """Buy a number of tickets for a lottery."""
        # Count existing tickets
        cursor = await self.conn.execute(
            "SELECT COUNT(*) FROM lottery_tickets WHERE lottery_id = ? AND user_id = ?",
            (lottery_id, user_id)
        )
        count = await cursor.fetchone()
        existing_tickets = count[0] if count else 0

        if existing_tickets + amount > 20:
            raise ValueError("Cannot buy more than 20 tickets per user per lottery.")

        purchased_at = datetime.datetime.now(timezone.utc)
        for _ in range(amount):
            await self.conn.execute(
                "INSERT INTO lottery_tickets (lottery_id, user_id, purchased_at) VALUES (?, ?, ?)",
                (lottery_id, user_id, purchased_at)
            )
        await self.conn.commit()



    async def get_lottery_ticket_count(self, lottery_id: int, user_id: int):
        """Return the number of tickets a user has in a lottery."""
        cursor = await self.conn.execute(
            "SELECT COUNT(*) FROM lottery_tickets WHERE lottery_id = ? AND user_id = ?",
            (lottery_id, user_id)
        )
        count = await cursor.fetchone()
        return count[0] if count else 0



    async def close_lottery(self, lottery_id: int):
        """Close an active lottery, draw a winner, and return payout details."""
        # Get tickets
        cursor = await self.conn.execute(
            "SELECT id, user_id FROM lottery_tickets WHERE lottery_id = ?",
            (lottery_id,)
        )
        tickets = await cursor.fetchall()

        if not tickets:
            # No tickets sold
            await self.conn.execute(
                "UPDATE lotteries SET status = 'completed' WHERE id = ?",
                (lottery_id,)
            )
            await self.conn.commit()
            return None  # No winner

        # Draw winner
        winning_ticket = random.choice(tickets)
        winning_ticket_id, winner_user_id = winning_ticket

        # Get lottery info
        cursor = await self.conn.execute("SELECT ticket_price, guild_cut_percent FROM lotteries WHERE id = ?", (lottery_id,))
        lottery_info = await cursor.fetchone()
        ticket_price, guild_cut_percent = lottery_info

        total_tickets = len(tickets)
        total_pot = total_tickets * ticket_price
        guild_cut = total_pot * guild_cut_percent // 100
        payout = total_pot - guild_cut

        # Record winner
        await self.conn.execute("""
            INSERT INTO lottery_winners (lottery_id, user_id, winning_ticket_id, total_pot, payout, guild_cut)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (lottery_id, winner_user_id, winning_ticket_id, total_pot, payout, guild_cut))

        await self.add_ledger_entry(
            user_id=winner_user_id,
            amount=payout,
            reason="lottery_win",
            reference_id=f"lottery:{lottery_id}"
        )

        # Mark lottery as completed
        await self.conn.execute("UPDATE lotteries SET status = 'completed' WHERE id = ?", (lottery_id,))
        await self.conn.commit()

        return {
            "winner_user_id": winner_user_id,
            "winning_ticket_id": winning_ticket_id,
            "total_pot": total_pot,
            "guild_cut": guild_cut,
            "payout": payout,
            "total_tickets": total_tickets
        }



    async def get_lottery_history(self, limit: int = 10):
        """Return last N completed lotteries with winner info."""
        cursor = await self.conn.execute("""
            SELECT l.lottery_number, l.start_time, l.end_time, w.user_id, w.payout, w.guild_cut
            FROM lotteries l
            JOIN lottery_winners w ON l.id = w.lottery_id
            WHERE l.status = 'completed'
            ORDER BY l.start_time DESC
            LIMIT ?
        """, (limit,))
        return await cursor.fetchall()