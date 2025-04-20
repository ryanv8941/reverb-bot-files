import asyncpg
import os

class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):

         self.pool = await asyncpg.create_pool(
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT")
        )
         print("[DB] Connection pool created successfully.")


    '''self.pool = await asyncpg.create_pool(
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            database=os.getenv("POSTGRES_DB", "reverb_bot"),
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", 5432)
        )'''

    async def get_trial_thread(self, user_id: int):
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(
                "SELECT thread_id FROM public.trial_threads WHERE user_id = $1", user_id
            )
            return result["thread_id"] if result else None

    async def set_trial_thread(self, user_id: int, thread_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO public.trial_threads (user_id, thread_id)
                VALUES ($1, $2)
                ON CONFLICT (user_id)
                DO UPDATE SET thread_id = EXCLUDED.thread_id
                """,
                user_id, thread_id
            )

    async def delete_trial_thread(self, user_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM public.trial_threads WHERE user_id = $1",
                user_id
            )

    async def get_welcome_message(self):
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow("SELECT message FROM public.welcome_message LIMIT 1")
            return result["message"] if result else None
        
    async def set_welcome_message(self, welcome_message: str):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE public.welcome_message SET welcome_message = $1", welcome_message
            )

    async def get_expansion_id(self):
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow("SELECT expansion_id FROM public.settings LIMIT 1")
            return result["expansion_id"] if result else None

    async def set_expansion_id(self, expansion_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE public.settings SET expansion_id = $1", expansion_id
            )

# Usage example (in bot.py or your main entry file):
# db = Database()
# await db.connect()
