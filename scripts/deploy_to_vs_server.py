import subprocess
import logging
import paramiko
from scp import SCPClient

# Logging configuration
logging.basicConfig(level=logging.INFO)

# Constants
DOCKER_COMPOSE_FILE = "docker-compose.yml"
VSERVER_IP = "your.vserver.ip"
VSERVER_USER = "your_vserver_user"
VSERVER_PASSWORD = "your_vserver_password"

DOCKER_COMPOSE_CONTENT = """
version: '3'
services:
  keycloak:
    image: jboss/keycloak:latest
    environment:
      KEYCLOAK_USER: admin
      KEYCLOAK_PASSWORD: admin_password
    ports:
      - "8080:8080"
"""

def create_docker_compose_file():
    with open(DOCKER_COMPOSE_FILE, 'w') as file:
        file.write(DOCKER_COMPOSE_CONTENT)
    logging.info("Docker Compose file created successfully.")

def transfer_file_to_vserver():
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(VSERVER_IP, username=VSERVER_USER, password=VSERVER_PASSWORD)
        
        with SCPClient(ssh.get_transport()) as scp:
            scp.put(DOCKER_COMPOSE_FILE, remote_path=f'/home/{VSERVER_USER}/{DOCKER_COMPOSE_FILE}')
        
        logging.info("Docker Compose file transferred to vServer successfully.")
    except Exception as e:
        logging.error(f"Error transferring Docker Compose file to vServer: {e}")
        raise e

def deploy_docker_compose_on_vserver():
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(VSERVER_IP, username=VSERVER_USER, password=VSERVER_PASSWORD)
        
        commands = [
            f"docker-compose -f /home/{VSERVER_USER}/{DOCKER_COMPOSE_FILE} up -d"
        ]
        
        for command in commands:
            stdin, stdout, stderr = ssh.exec_command(command)
            stdout.channel.recv_exit_status()
            logging.info(f"Command '{command}' executed successfully on vServer.")
        
        ssh.close()
    except Exception as e:
        logging.error(f"Error deploying Docker Compose on vServer: {e}")
        raise e

def main():
    try:
        create_docker_compose_file()
        transfer_file_to_vserver()
        deploy_docker_compose_on_vserver()
        logging.info("Keycloak deployed on vServer successfully.")
    except Exception as e:
        logging.error(f"Deployment failed: {e}")

if __name__ == "__main__":
    main()
