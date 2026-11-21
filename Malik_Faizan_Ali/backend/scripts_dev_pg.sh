#!/bin/sh
# Sandbox-only helper: start the local PostgreSQL cluster if it is not running.
pg_isready -h localhost -q || su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D /var/lib/pgdata -l /var/lib/pgdata/log -o '-c listen_addresses=localhost' start -w" >/dev/null 2>&1
pg_isready -h localhost
