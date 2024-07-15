# Stage 1: Build stage
FROM quay.io/keycloak/keycloak:21.0 as builder

# Configure a database vendor
ENV KC_DB=postgres

WORKDIR /opt/keycloak

# Generate a self-signed certificate for demonstration purposes
RUN keytool -genkeypair -storepass password -storetype PKCS12 -keyalg RSA -keysize 2048 -dname "CN=server" -alias server -ext "SAN:c=DNS:localhost,IP:127.0.0.1" -keystore conf/server.keystore

# Build the Keycloak server
RUN /opt/keycloak/bin/kc.sh build

# Stage 2: Final stage
FROM quay.io/keycloak/keycloak:latest


# Copy custom theme into the Keycloak themes directory
COPY material-keycloak-theme/keycloak/themes/material-theme /opt/keycloak/themes/

ENTRYPOINT ["/opt/keycloak/bin/kc.sh"]
