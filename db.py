import aiosqlite
import os

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
