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

sql_escape_literal() {
  printf "%s" "$1" | sed "s/'/''/g"
}

sql_escape_ident() {
  printf "%s" "$1" | sed 's/"/""/g'
}

db_user_lit=$(sql_escape_literal "$DB_USER")
db_user_ident=$(sql_escape_ident "$DB_USER")
db_password_lit=$(sql_escape_literal "$DB_PASSWORD")
db_name_ident=$(sql_escape_ident "$DB_NAME")
db_owner_ident=$(sql_escape_ident "$DB_OWNER")

role_exists=$(
  psql -v ON_ERROR_STOP=1 \
    -h "$PGHOST" \
    -p "$PGPORT" \
    -U "$PGUSER" \
    -d postgres \
    -tAc "SELECT 1 FROM pg_roles WHERE rolname = '${db_user_lit}'"
)

if [[ -z "$role_exists" ]]; then
  psql -v ON_ERROR_STOP=1 \
    -h "$PGHOST" \
    -p "$PGPORT" \
    -U "$PGUSER" \
    -d postgres \
    -c "CREATE ROLE \"${db_user_ident}\" LOGIN PASSWORD '${db_password_lit}';"
fi

db_exists=$(
  psql -v ON_ERROR_STOP=1 \
    -h "$PGHOST" \
    -p "$PGPORT" \
    -U "$PGUSER" \
    -d postgres \
    -tAc "SELECT 1 FROM pg_database WHERE datname = '${db_name_ident}'"
)

if [[ -z "$db_exists" ]]; then
  psql -v ON_ERROR_STOP=1 \
    -h "$PGHOST" \
    -p "$PGPORT" \
    -U "$PGUSER" \
    -d postgres \
    -c "CREATE DATABASE \"${db_name_ident}\" OWNER \"${db_owner_ident}\";"
fi

psql -v ON_ERROR_STOP=1 \
  -h "$PGHOST" \
  -p "$PGPORT" \
  -U "$PGUSER" \
  -d postgres \
  -c "ALTER DATABASE \"${db_name_ident}\" OWNER TO \"${db_owner_ident}\";"

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
