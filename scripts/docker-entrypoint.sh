#!/bin/bash
set -e

# Initialize PostgreSQL if needed
if [ ! -d "/var/lib/postgresql/15/main" ]; then
    echo "Initializing PostgreSQL..."
    mkdir -p /var/lib/postgresql/15/main
    chown -R postgres:postgres /var/lib/postgresql
    gosu postgres /usr/lib/postgresql/15/bin/initdb -D /var/lib/postgresql/15/main

    # Configure PostgreSQL
    echo "listen_addresses = '127.0.0.1'" >> /var/lib/postgresql/15/main/postgresql.conf
    echo "port = 5432" >> /var/lib/postgresql/15/main/postgresql.conf

    # Start PostgreSQL temporarily to create database
    gosu postgres /usr/lib/postgresql/15/bin/pg_ctl -D /var/lib/postgresql/15/main start
    sleep 3

    # Create database and user
    gosu postgres psql -c "CREATE USER tesseract WITH PASSWORD 'tesseract';" || true
    gosu postgres psql -c "CREATE DATABASE tesseract_relayer OWNER tesseract;" || true
    gosu postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE tesseract_relayer TO tesseract;" || true

    gosu postgres /usr/lib/postgresql/15/bin/pg_ctl -D /var/lib/postgresql/15/main stop
    sleep 2
    echo "PostgreSQL initialized."
fi

# Update config with environment variables
if [ -n "$TESSERACT_BUFFER_ADDRESS" ]; then
    sed -i "s|\${TESSERACT_BUFFER_ADDRESS}|$TESSERACT_BUFFER_ADDRESS|g" /app/config/demo.toml
fi
if [ -n "$COORDINATOR_ADDRESS" ]; then
    sed -i "s|\${COORDINATOR_ADDRESS}|$COORDINATOR_ADDRESS|g" /app/config/demo.toml
fi

# Export database URL for relayer
export DATABASE_URL="postgres://tesseract:tesseract@127.0.0.1:5432/tesseract_relayer"

echo "Starting services via supervisord..."
exec /usr/bin/supervisord -c /etc/supervisor/supervisord.conf
