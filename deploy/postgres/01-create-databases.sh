#!/bin/sh
set -eu
# No imprimir variables ni activar trazas: contienen credenciales.
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set=ON_ERROR_STOP=1 <<'SQL'
\getenv productos_password PRODUCTOS_DB_PASSWORD
\getenv pedidos_password PEDIDOS_DB_PASSWORD
CREATE ROLE productos_app LOGIN PASSWORD :'productos_password';
CREATE ROLE pedidos_app LOGIN PASSWORD :'pedidos_password';
CREATE DATABASE productos_db OWNER productos_app;
CREATE DATABASE pedidos_db OWNER pedidos_app;
REVOKE ALL ON DATABASE productos_db FROM PUBLIC;
REVOKE ALL ON DATABASE pedidos_db FROM PUBLIC;
GRANT CONNECT ON DATABASE productos_db TO productos_app;
GRANT CONNECT ON DATABASE pedidos_db TO pedidos_app;
\connect productos_db
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT ALL ON SCHEMA public TO productos_app;
\connect pedidos_db
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT ALL ON SCHEMA public TO pedidos_app;
SQL
