#!/bin/bash
set -e

echo "🚀 Setting up local environment..."

# 1. Install dependencies
sudo apt-get update
sudo apt-get install -y postgresql postgresql-contrib libssl1.1 || {
    echo "Falling back to downloading libssl1.1 manually..."
    wget http://nz2.archive.ubuntu.com/ubuntu/pool/main/o/openssl/libssl1.1_1.1.1f-1ubuntu2_amd64.deb
    sudo dpkg -i libssl1.1_1.1.1f-1ubuntu2_amd64.deb
    rm libssl1.1_1.1.1f-1ubuntu2_amd64.deb
}

# 2. Start PostgreSQL
sudo service postgresql start || sudo -u postgres /usr/lib/postgresql/*/bin/pg_ctl -D /var/lib/postgresql/*/main -l logfile start

# 3. Create DB and User
sudo -u postgres psql -c "CREATE USER postgres WITH PASSWORD 'postgres';" || true
sudo -u postgres psql -c "CREATE DATABASE telegram_bots;" || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE telegram_bots TO postgres;" || true

# 4. Install Python requirements
pip install -r requirements.txt

# 5. Run Database Initialization
python3 -c "
import asyncio
from add.database import DatabaseManager
from storage.database import StorageDatabaseManager
from transf.database import TransferDatabaseManager
async def init():
    for db in [DatabaseManager(), StorageDatabaseManager(), TransferDatabaseManager()]:
        await db.connect()
        await db.close()
asyncio.run(init())
"

echo "✅ Local setup complete!"
