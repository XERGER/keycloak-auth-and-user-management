import subprocess
import json
import logging
import os
from keycloak import KeycloakAdmin
from keycloak.exceptions import KeycloakError
from time import sleep

# Logging configuration
logging.basicConfig(level=logging.INFO)

# Constants (replace with actual values or use environment variables)
DOCKER_IMAGE_NAME = os.getenv("DOCKER_IMAGE_NAME", "my-keycloak")
DOCKER_CONTAINER_NAME = os.getenv("DOCKER_CONTAINER_NAME", "keycloak-container")
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "https://localhost:8443/auth/")
REALM_NAME = os.getenv("REALM_NAME", "myrealm")
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin_password")
CLIENT_ID = os.getenv("CLIENT_ID", "myclient")
REDIRECT_URI = os.getenv("REDIRECT_URI", "https://localhost:4200/*")
EMAIL_SETTINGS = {
    "host": os.getenv("EMAIL_HOST", "smtp.example.com"),
    "port": int(os.getenv("EMAIL_PORT", 587)),
    "username": os.getenv("EMAIL_USERNAME", "email@example.com"),
    "password": os.getenv("EMAIL_PASSWORD", "password"),
    "from": os.getenv("EMAIL_FROM", "no-reply@example.com")
}
GROUPS = {
    "free": {"aiToken": 1000, "usedStorage": 500},
    "basic": {"aiToken": 10000, "usedStorage": 30000},
    "advanced": {"aiToken": 20000, "usedStorage": 100000},
    "pro": {"aiToken": 50000, "usedStorage": 300000}
}
SOCIAL_LOGINS = ["apple", "google", "microsoft"]
OPTIONAL_SOCIAL_LOGINS = ["github", "discord"]

class CommandRunner:
    @staticmethod
    def run_command(command):
        try:
            subprocess.run(command, check=True)
            logging.info(f"Successfully ran command: {' '.join(command)}")
        except subprocess.CalledProcessError as e:
            logging.error(f"Error running command: {' '.join(command)}")
            raise e

class AngularBuilder:
    @staticmethod
    def build_and_deploy():
        CommandRunner.run_command(["python", "build_and_deploy.py"])

class DockerManager:
    @staticmethod
    def build_keycloak_image():
        CommandRunner.run_command(["docker", "build", "-t", DOCKER_IMAGE_NAME, "."])
        CommandRunner.run_command(["docker", "run", "-d", "--name", DOCKER_CONTAINER_NAME, "-p", "8443:8443", "-e", "KEYCLOAK_USER=" + ADMIN_USER, "-e", "KEYCLOAK_PASSWORD=" + ADMIN_PASSWORD, DOCKER_IMAGE_NAME])

class KeycloakConfigurator:
    def __init__(self):
        self.keycloak_admin = None

    def connect(self):
        retry_attempts = 5
        while retry_attempts > 0:
            try:
                self.keycloak_admin = KeycloakAdmin(server_url=KEYCLOAK_URL,
                                                    username=ADMIN_USER,
                                                    password=ADMIN_PASSWORD,
                                                    realm_name="master",
                                                    verify=True)
                logging.info("Connected to Keycloak")
                break
            except KeycloakError as e:
                retry_attempts -= 1
                logging.error(f"Error connecting to Keycloak: {e}, retries left: {retry_attempts}")
                sleep(5)
        if retry_attempts == 0:
            raise Exception("Failed to connect to Keycloak after multiple attempts")

    def create_realm(self):
        try:
            self.keycloak_admin.create_realm(payload={"realm": REALM_NAME, "enabled": True})
            logging.info(f"Realm '{REALM_NAME}' created successfully.")
        except KeycloakError as e:
            logging.error(f"Error creating realm '{REALM_NAME}': {e}")
            raise e

    def create_client(self):
        try:
            self.keycloak_admin.create_client(payload={
                "clientId": CLIENT_ID,
                "redirectUris": [REDIRECT_URI],
                "publicClient": True,
                "directAccessGrantsEnabled": True
            }, realm_name=REALM_NAME)
            logging.info(f"Client '{CLIENT_ID}' created successfully.")
        except KeycloakError as e:
            logging.error(f"Error creating client '{CLIENT_ID}': {e}")
            raise e

    def create_groups_and_users(self):
        for group_name, attributes in GROUPS.items():
            try:
                self.keycloak_admin.create_group(payload={"name": group_name}, realm_name=REALM_NAME)
                group_id = self.keycloak_admin.get_group_id(group_name, realm_name=REALM_NAME)
                self.keycloak_admin.update_group(group_id, payload={
                    "attributes": {"aiToken": str(attributes["aiToken"]), "usedStorage": str(attributes["usedStorage"])}
                }, realm_name=REALM_NAME)
                logging.info(f"Group '{group_name}' created with attributes {attributes}.")

                self.keycloak_admin.create_user(payload={
                    "username": f"{group_name}_user",
                    "enabled": True,
                    "credentials": [{"type": "password", "value": "password", "temporary": False}],
                    "groups": [group_name]
                }, realm_name=REALM_NAME)
                logging.info(f"User '{group_name}_user' created and added to group '{group_name}'.")
            except KeycloakError as e:
                logging.error(f"Error creating group or user for '{group_name}': {e}")
                raise e

    def add_custom_claims(self):
        try:
            client_id = self.keycloak_admin.get_client_id(CLIENT_ID, realm_name=REALM_NAME)
            protocol_mappers = [
                {"name": "aiToken", "protocol": "openid-connect", "protocolMapper": "oidc-usermodel-attribute-mapper", "config": {"claim.name": "aiToken", "user.attribute": "aiToken", "id.token.claim": "true", "access.token.claim": "true"}},
                {"name": "usedStorage", "protocol": "openid-connect", "protocolMapper": "oidc-usermodel-attribute-mapper", "config": {"claim.name": "usedStorage", "user.attribute": "usedStorage", "id.token.claim": "true", "access.token.claim": "true"}}
            ]
            for mapper in protocol_mappers:
                self.keycloak_admin.create_client_protocol_mapper(client_id, mapper, realm_name=REALM_NAME)
            logging.info("Custom claims added successfully.")
        except KeycloakError as e:
            logging.error(f"Error adding custom claims: {e}")
            raise e

    def configure_email_settings(self):
        try:
            self.keycloak_admin.update_realm(REALM_NAME, payload={"smtpServer": EMAIL_SETTINGS})
            logging.info("Email settings configured successfully.")
        except KeycloakError as e:
            logging.error(f"Error configuring email settings: {e}")
            raise e

    def configure_social_logins(self):
        try:
            for provider in SOCIAL_LOGINS + OPTIONAL_SOCIAL_LOGINS:
                self.keycloak_admin.create_identity_provider({
                    "alias": provider,
                    "providerId": provider,
                    "enabled": True,
                    "trustEmail": True,
                    "storeToken": False,
                    "addReadTokenRoleOnCreate": True,
                    "authenticateByDefault": False,
                    "linkOnly": False,
                    "config": {"clientId": os.getenv(f"{provider.upper()}_CLIENT_ID", "client_id"), "clientSecret": os.getenv(f"{provider.upper()}_CLIENT_SECRET", "client_secret")}
                }, realm_name=REALM_NAME)
            logging.info("Social logins configured successfully.")
        except KeycloakError as e:
            logging.error(f"Error configuring social logins: {e}")
            raise e

    def configure_device_restrictions(self):
        try:
            restrictions = {
                "free": 2,
                "basic": 3,
                "advanced": 5,
                "pro": 5
            }
            self.keycloak_admin.update_realm(REALM_NAME, payload={
                "bruteForceProtected": True,
                "maxFailureWaitSeconds": 60,
                "minimumQuickLoginWaitSeconds": 60,
                "waitIncrementSeconds": 60,
                "quickLoginCheckMilliSeconds": 1000,
                "maxDeltaTimeSeconds": 43200,
                "failureFactor": 2,
                "permanentLockout": False,
                "maxLoginFailures": restrictions
            })
            logging.info("Device restrictions configured successfully.")
        except KeycloakError as e:
            logging.error(f"Error configuring device restrictions: {e}")
            raise e

    def configure_refresh_token_settings(self):
        try:
            client_id = self.keycloak_admin.get_client_id(CLIENT_ID, realm_name=REALM_NAME)
            self.keycloak_admin.update_client(client_id, payload={
                "attributes": {
                    "refreshTokenMaxReuse": 1,
                    "useRefreshTokens": True,
                    "ssoSessionMaxLifespan": 3600,
                    "ssoSessionIdleTimeout": 1800
                }
            }, realm_name=REALM_NAME)
            logging.info("Refresh token settings configured successfully.")
        except KeycloakError as e:
            logging.error(f"Error configuring refresh token settings: {e}")
            raise e

def main():
    try:
        AngularBuilder.build_and_deploy()
        DockerManager.build_keycloak_image()

        keycloak_configurator = KeycloakConfigurator()
        keycloak_configurator.connect()
        keycloak_configurator.create_realm()
        keycloak_configurator.create_client()
        keycloak_configurator.create_groups_and_users()
        keycloak_configurator.add_custom_claims()
        keycloak_configurator.configure_email_settings()
        keycloak_configurator.configure_social_logins()
        keycloak_configurator.configure_device_restrictions()
        keycloak_configurator.configure_refresh_token_settings()

        logging.info("Setup completed successfully.")
    except Exception as e:
        logging.error(f"Setup failed: {e}")

if __name__ == "__main__":
    main()
