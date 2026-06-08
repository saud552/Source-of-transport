import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_transf_db():
    from transf.database import TransferDatabaseManager
    db = TransferDatabaseManager()
    await db.connect()
    await db.close()
    print("Transf DB ok")

if __name__ == "__main__":
    asyncio.run(test_transf_db())
