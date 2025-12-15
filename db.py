import aiosqlite
import os

class Database:
    def __init__(self, db_path: str = "/app/reverb_bot.db"):
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