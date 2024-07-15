import subprocess
import logging
import paramiko
from scp import SCPClient

# Logging configuration
logging.basicConfig(level=logging.INFO)

# Constants
DOCKER_COMPOSE_FILE = "docker-compose.yml"
DOCKERFILE = "Dockerfile"
VSERVER_IP = "your.vserver.ip"
VSERVER_USER = "your_vserver_user"
VSERVER_PASSWORD = "your_vserver_password"

DOCKER_COMPOSE_CONTENT = """
version: '3'
services:
  keycloak:
    build: .
    environment:
      KEYCLOAK_USER: admin
      KEYCLOAK_PASSWORD: admin_password
      KEYCLOAK_THEME: material-keycloak-theme
    ports:
      - "8080:8080"
"""

DOCKERFILE_CONTENT = """
FROM jboss/keycloak:latest

# Copy the built Angular Material template to the themes directory
COPY ./material-keycloak-theme/themes /opt/jboss/keycloak/themes

# Set the Angular Material theme as the default theme
ENV KEYCLOAK_THEME=material-keycloak-theme

# Entry point
ENTRYPOINT ["/opt/jboss/keycloak/bin/kc.sh", "start-dev"]
"""

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
        CommandRunner.run_command(["docker", "build", "-t", "my-keycloak", "."])
        CommandRunner.run_command(["docker", "run", "-d", "--name", "keycloak-container", "-p", "8080:8080", "my-keycloak"])

class VirtualServerManager:
    def __init__(self, ip, user, password):
        self.ip = ip
        self.user = user
        self.password = password

    def provision_server(self):
        logging.info("Virtual server provisioned successfully.")

    def install_dependencies(self):
        try:
            ssh = self._connect()
            commands = [
                "sudo apt-get update",
                "sudo apt-get install -y docker.io",
                "sudo apt-get install -y docker-compose"
            ]
            for command in commands:
                self._execute_command(ssh, command)
            ssh.close()
            logging.info("Dependencies installed successfully on the virtual server.")
        except Exception as e:
            logging.error(f"Error installing dependencies: {e}")
            raise e

    def _connect(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ip, username=self.user, password=self.password)
        return ssh

    def _execute_command(self, ssh, command):
        stdin, stdout, stderr = ssh.exec_command(command)
        stdout.channel.recv_exit_status()
        logging.info(f"Command '{command}' executed successfully on the virtual server.")

    def transfer_file(self, local_path, remote_path):
        try:
            ssh = self._connect()
            with SCPClient(ssh.get_transport()) as scp:
                scp.put(local_path, remote_path)
            ssh.close()
            logging.info(f"File '{local_path}' transferred to '{remote_path}' on the virtual server.")
        except Exception as e:
            logging.error(f"Error transferring file to the virtual server: {e}")
            raise e

    def deploy_docker_compose(self):
        try:
            ssh = self._connect()
            self._execute_command(ssh, f"docker-compose -f {DOCKER_COMPOSE_FILE} up -d")
            ssh.close()
            logging.info("Docker Compose deployed successfully on the virtual server.")
        except Exception as e:
            logging.error(f"Error deploying Docker Compose on the virtual server: {e}")
            raise e

def create_docker_compose_file():
    with open(DOCKER_COMPOSE_FILE, 'w') as file:
        file.write(DOCKER_COMPOSE_CONTENT)
    logging.info("Docker Compose file created successfully.")

def create_dockerfile():
    with open(DOCKERFILE, 'w') as file:
        file.write(DOCKERFILE_CONTENT)
    logging.info("Dockerfile created successfully.")

def main():
    try:
        AngularBuilder.build_and_deploy()
        create_dockerfile()
        create_docker_compose_file()

        vserver_manager = VirtualServerManager(VSERVER_IP, VSERVER_USER, VSERVER_PASSWORD)
        vserver_manager.provision_server()
        vserver_manager.install_dependencies()
        vserver_manager.transfer_file(DOCKERFILE, f'/home/{VSERVER_USER}/{DOCKERFILE}')
        vserver_manager.transfer_file(DOCKER_COMPOSE_FILE, f'/home/{VSERVER_USER}/{DOCKER_COMPOSE_FILE}')
        vserver_manager.deploy_docker_compose()

        logging.info("Virtual server setup and Keycloak deployment completed successfully.")
    except Exception as e:
        logging.error(f"Setup failed: {e}")

if __name__ == "__main__":
    main()
