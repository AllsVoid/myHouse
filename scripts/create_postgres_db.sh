#!/usr/bin/env bash
set -euo pipefail

# Production PostgreSQL bootstrap script.
# It creates role, database, and optional extensions.

: "${PGHOST:=localhost}"
: "${PGPORT:=5432}"
: "${PGUSER:=postgres}"
: "${PGPASSWORD:=}"

: "${DB_NAME:=house}"
: "${DB_USER:=house}"
: "${DB_PASSWORD:=house}"
: "${DB_OWNER:=$DB_USER}"
: "${ENABLE_POSTGIS:=true}"

export PGPASSWORD

psql -v ON_ERROR_STOP=1 \
  -h "$PGHOST" \
  -p "$PGPORT" \
  -U "$PGUSER" \
  -d postgres \
  -v db_name="$DB_NAME" \
  -v db_user="$DB_USER" \
  -v db_password="$DB_PASSWORD" \
  -v db_owner="$DB_OWNER" <<'SQL'
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'db_user') THEN
    EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', :'db_user', :'db_password');
  END IF;
END
$$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'db_name') THEN
    EXECUTE format('CREATE DATABASE %I OWNER %I', :'db_name', :'db_owner');
  END IF;
END
$$;

ALTER DATABASE :db_name OWNER TO :db_owner;
SQL

if [[ "$ENABLE_POSTGIS" == "true" ]]; then
  psql -v ON_ERROR_STOP=1 \
    -h "$PGHOST" \
    -p "$PGPORT" \
    -U "$PGUSER" \
    -d "$DB_NAME" <<'SQL'
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
SQL
fi

echo "Database setup completed for: $DB_NAME"
