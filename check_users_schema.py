import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect('postgresql://kostakunak@localhost:5432/five_chairs')
    columns = await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_name = 'users'")
    print('Users table columns:', [col['column_name'] for col in columns])
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())