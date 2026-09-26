#!/bin/bash
set -e

# Runs once, the first time the database volume is created.
# psql -v passes shell env vars in as psql variables (:'name' inserts a quoted literal).
psql -v ON_ERROR_STOP=1 \
     --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
     -v app_pw="$APP_RW_PASSWORD" \
     -v ro_pw="$ANALYST_RO_PASSWORD" <<'EOSQL'

-- 1. Roles
CREATE ROLE app_rw     LOGIN PASSWORD :'app_pw';
CREATE ROLE analyst_ro LOGIN PASSWORD :'ro_pw';

-- 2. Schemas, owned by the read-write app role
CREATE SCHEMA meta      AUTHORIZATION app_rw;
CREATE SCHEMA user_data AUTHORIZATION app_rw;

-- 3. Nobody may create objects in the default public schema
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- 4. Read-only analyst: can look inside user_data, and nothing else
GRANT USAGE ON SCHEMA user_data TO analyst_ro;

-- Tables that app_rw creates in the future automatically become SELECT-able by analyst_ro
ALTER DEFAULT PRIVILEGES FOR ROLE app_rw IN SCHEMA user_data
    GRANT SELECT ON TABLES TO analyst_ro;

-- 5. Belt and braces settings for the analyst role
ALTER ROLE analyst_ro SET statement_timeout = '10s';
ALTER ROLE analyst_ro SET default_transaction_read_only = on;
ALTER ROLE analyst_ro SET search_path = user_data;

EOSQL
