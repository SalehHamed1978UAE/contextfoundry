import asyncpg
import redis.asyncio as aioredis
from typing import Optional
from contextlib import asynccontextmanager

from src.config import settings


class DatabaseManager:
    """Manages database connections for PostgreSQL and Redis"""

    def __init__(self):
        self.pg_pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[aioredis.Redis] = None

    async def init_postgres(self):
        """Initialize PostgreSQL connection pool"""
        self.pg_pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=2,
            max_size=10,
            command_timeout=60
        )
        print("✓ PostgreSQL connection pool initialized")

    async def init_redis(self):
        """Initialize Redis client"""
        self.redis_client = await aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        await self.redis_client.ping()
        print("✓ Redis connection initialized")

    async def close(self):
        """Close all database connections"""
        if self.pg_pool:
            await self.pg_pool.close()
            print("✓ PostgreSQL connection pool closed")

        if self.redis_client:
            await self.redis_client.close()
            print("✓ Redis connection closed")

    @asynccontextmanager
    async def get_postgres_connection(self):
        """Get a PostgreSQL connection from the pool"""
        async with self.pg_pool.acquire() as conn:
            yield conn

    async def execute_cypher(self, query: str, params: dict = None):
        """Execute a Cypher query using Apache AGE"""
        async with self.get_postgres_connection() as conn:
            # Set up AGE
            await conn.execute("LOAD 'age';")
            await conn.execute("SET search_path = ag_catalog, '$user', public;")

            # Build the Cypher query
            cypher_query = f"""
            SELECT * FROM cypher('{settings.graph_name}', $$
                {query}
            $$) as (result agtype);
            """

            result = await conn.fetch(cypher_query)
            return result

    async def get_redis_client(self) -> aioredis.Redis:
        """Get Redis client"""
        return self.redis_client


# Global database manager instance
db_manager = DatabaseManager()


async def init_databases():
    """Initialize all database connections"""
    await db_manager.init_postgres()
    await db_manager.init_redis()


async def close_databases():
    """Close all database connections"""
    await db_manager.close()
