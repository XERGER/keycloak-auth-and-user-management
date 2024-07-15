#!/bin/bash

# Create DB if it does not exist
psql -U dev -tc "SELECT 1 FROM pg_database WHERE datname = 'keycloak'" \
| grep -q 1 || psql -U dev -c "CREATE DATABASE keycloak"

# Create user and grant privileges
psql -U dev -c "CREATE USER keycloak WITH PASSWORD 'kc'"
psql -U dev -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO keycloak"
psql -U dev -c "GRANT ALL PRIVILEGES ON DATABASE keycloak TO keycloak"
psql -U dev -c "ALTER USER keycloak WITH SUPERUSER"
