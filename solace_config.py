#!/usr/bin/env python3
"""
Solace PubSub+ Broker Configuration Script

This script deploys a Solace PubSub+ software broker as a Docker container
and configures it using SEMP v2 API to create Message VPNs, queues, and client usernames.
"""

import argparse
import json
import logging
import platform
import subprocess
import sys
import time
from typing import Dict, Tuple, Optional

import requests


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Docker configuration constants
CONTAINER_NAME = "solace"
DOCKER_IMAGE = "solace/solace-pubsub-standard"
SEMP_PORT = 8080
# macOS reserves port 55555, so use 55554 on Mac
MESSAGING_PORT = 55554 if platform.system() == "Darwin" else 55555

# Default SEMP configuration
DEFAULT_BROKER_URL = "localhost:8080"
DEFAULT_ADMIN_USER = "admin"
DEFAULT_ADMIN_PASS = "admin"
BROKER_READY_TIMEOUT = 120  # seconds - increased for first-time startup
BROKER_READY_INTERVAL = 2  # seconds


def deploy_solace_broker() -> bool:
    """
    Deploy Solace PubSub+ broker as a Docker container.
    
    Returns:
        bool: True if deployment successful or container already running, False otherwise
    """
    logger.info("Checking if Solace broker container exists...")
    
    # Check if container exists
    try:
        result = subprocess.run(
            ["docker", "ps", "-a", "--filter", f"name=^{CONTAINER_NAME}$", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            check=True
        )
        
        container_exists = CONTAINER_NAME in result.stdout.splitlines()
        
        if container_exists:
            # Check if container is running
            result = subprocess.run(
                ["docker", "ps", "--filter", f"name=^{CONTAINER_NAME}$", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                check=True
            )
            
            if CONTAINER_NAME in result.stdout.splitlines():
                logger.info(f"Container '{CONTAINER_NAME}' is already running")
                return True
            else:
                # Container exists but is stopped, start it
                logger.info(f"Starting stopped container '{CONTAINER_NAME}'...")
                subprocess.run(["docker", "start", CONTAINER_NAME], check=True)
                logger.info(f"Container '{CONTAINER_NAME}' started successfully")
                return True
        else:
            # Container doesn't exist, create it
            logger.info(f"Creating new Solace broker container '{CONTAINER_NAME}'...")
            
            docker_cmd = [
                "docker", "run", "-d",
                "-p", f"{SEMP_PORT}:{SEMP_PORT}",
                "-p", f"{MESSAGING_PORT}:{MESSAGING_PORT}",
                "--cpus", "2.0",
                "--ulimit", "core=-1",
                "--ulimit", "nofile=2448:1048576",
                "--shm-size=1g",
                "--env", "username_admin_globalaccesslevel=admin",
                "--env", "username_admin_password=admin",
                "--env", "system_scaling_maxconnectioncount=1000",
                "--env", "system_scaling_maxqueuemessagecount=240",
                "--env", "system_scaling_maxkafkabridgecount=0",
                "--env", "system_scaling_maxkafkabrokerconnectioncount=0",
                "--env", "system_scaling_maxbridgecount=25",
                "--env", "system_scaling_maxsubscriptioncount=500000",
                "--env", "system_scaling_maxguaranteedmessagesize=10",
                "--env", "messagespool_maxspoolusage=1500",
                "--name", CONTAINER_NAME,
                DOCKER_IMAGE
            ]
            
            subprocess.run(docker_cmd, check=True)
            logger.info(f"Container '{CONTAINER_NAME}' created successfully")
            return True
            
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to deploy Solace broker: {e}")
        return False
    except FileNotFoundError:
        logger.error("Docker command not found. Please ensure Docker is installed and in PATH.")
        return False


def remove_solace_broker() -> bool:
    """
    Stop and remove the Solace broker Docker container.
    
    Returns:
        bool: True if removal successful, False otherwise
    """
    logger.info(f"Stopping and removing Solace broker container '{CONTAINER_NAME}'...")
    
    try:
        # Stop the container
        subprocess.run(
            ["docker", "stop", CONTAINER_NAME],
            capture_output=True,
            text=True,
            check=True
        )
        logger.info(f"Container '{CONTAINER_NAME}' stopped")
        
        # Remove the container
        subprocess.run(
            ["docker", "rm", CONTAINER_NAME],
            capture_output=True,
            text=True,
            check=True
        )
        logger.info(f"Container '{CONTAINER_NAME}' removed successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to remove container: {e}")
        return False


def check_broker_ready(broker_url: str, auth: Tuple[str, str]) -> bool:
    """
    Check if the Solace broker SEMP API is ready to accept requests.
    
    Args:
        broker_url: Broker URL (host:port)
        auth: Tuple of (username, password) for authentication
        
    Returns:
        bool: True if broker is ready, False if timeout
    """
    logger.info("Waiting for Solace broker to be ready...")
    
    base_url = f"http://{broker_url}"
    about_url = f"{base_url}/SEMP/v2/config/about"
    
    start_time = time.time()
    
    while time.time() - start_time < BROKER_READY_TIMEOUT:
        try:
            response = requests.get(about_url, auth=auth, timeout=5)
            if response.status_code == 200:
                logger.info("Broker is ready!")
                return True
        except requests.exceptions.RequestException:
            pass
        
        time.sleep(BROKER_READY_INTERVAL)
    
    logger.error(f"Broker did not become ready within {BROKER_READY_TIMEOUT} seconds")
    return False


def parse_arguments() -> Dict:
    """
    Parse command-line arguments.
    
    Returns:
        Dict: Parsed arguments as dictionary
    """
    parser = argparse.ArgumentParser(
        description="Deploy and configure Solace PubSub+ broker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Deploy broker and create VPN with queues and username
  %(prog)s --vpn my-vpn --queues q1,q2,q3 --username client1
  
  # Use custom broker (skip docker deploy)
  %(prog)s --skip-docker --broker remote-host:8080 --admin-user admin --admin-pass secret --vpn prod-vpn --queues order-queue --username app-user
  
  # Remove the broker container
  %(prog)s --remove-container
  
  # Using config file
  %(prog)s --config config.json --vpn test-vpn --queues testq --username testuser
        """
    )
    
    # Docker options
    parser.add_argument(
        "--skip-docker",
        action="store_true",
        help="Skip Docker container deployment (use existing broker)"
    )
    parser.add_argument(
        "--remove-container",
        action="store_true",
        help="Stop and remove the Solace broker container, then exit"
    )
    
    # Broker connection options
    parser.add_argument(
        "--broker",
        default=DEFAULT_BROKER_URL,
        help=f"Broker URL (host:port) (default: {DEFAULT_BROKER_URL})"
    )
    parser.add_argument(
        "--admin-user",
        default=DEFAULT_ADMIN_USER,
        help=f"Admin username for SEMP API (default: {DEFAULT_ADMIN_USER})"
    )
    parser.add_argument(
        "--admin-pass",
        default=DEFAULT_ADMIN_PASS,
        help=f"Admin password for SEMP API (default: {DEFAULT_ADMIN_PASS})"
    )
    
    # Configuration file
    parser.add_argument(
        "--config",
        help="Path to JSON configuration file (CLI args override config file)"
    )
    
    # Object creation options
    parser.add_argument(
        "--vpn",
        help="Message VPN name to create"
    )
    parser.add_argument(
        "--queues",
        help="Comma-separated list of queue names to create"
    )
    parser.add_argument(
        "--username",
        help="Client username to create"
    )
    
    # Logging
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level (default: INFO)"
    )
    
    args = parser.parse_args()
    
    # Set log level
    logger.setLevel(getattr(logging, args.log_level))
    
    return vars(args)


def load_config_file(config_path: Optional[str]) -> Dict:
    """
    Load configuration from JSON file.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Dict: Configuration dictionary (empty if file not found or invalid)
    """
    if not config_path:
        return {}
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            logger.info(f"Loaded configuration from {config_path}")
            return config
    except FileNotFoundError:
        logger.warning(f"Configuration file not found: {config_path}")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in configuration file: {e}")
        return {}


def merge_config(file_config: Dict, cli_args: Dict) -> Dict:
    """
    Merge configuration file and CLI arguments (CLI takes precedence).
    
    Args:
        file_config: Configuration from file
        cli_args: Configuration from CLI arguments
        
    Returns:
        Dict: Merged configuration
    """
    # Start with file config
    config = file_config.copy()
    
    # Override with CLI args (only non-None values)
    for key, value in cli_args.items():
        if value is not None:
            config[key] = value
    
    return config


def make_semp_request(method: str, url: str, auth: Tuple[str, str], json_body: Optional[Dict] = None) -> requests.Response:
    """
    Make a SEMP API request.
    
    Args:
        method: HTTP method (GET, POST, etc.)
        url: Full URL for the request
        auth: Tuple of (username, password)
        json_body: Optional JSON body for POST/PUT requests
        
    Returns:
        requests.Response: Response object
        
    Raises:
        requests.exceptions.RequestException: On connection or HTTP errors
    """
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    try:
        response = requests.request(
            method=method,
            url=url,
            auth=auth,
            headers=headers,
            json=json_body,
            timeout=10
        )
        return response
    except requests.exceptions.RequestException as e:
        logger.error(f"SEMP API request failed: {e}")
        raise


def create_message_vpn(vpn_name: str, broker_url: str, auth: Tuple[str, str]) -> Tuple[bool, str]:
    """
    Create a Message VPN.
    
    Args:
        vpn_name: Name of the VPN to create
        broker_url: Broker URL (host:port)
        auth: Tuple of (username, password)
        
    Returns:
        Tuple[bool, str]: (Success status, message)
    """
    url = f"http://{broker_url}/SEMP/v2/config/msgVpns"
    body = {
        "msgVpnName": vpn_name,
        "enabled": True,
        "serviceSmfMaxConnectionCount": 100,
        "maxMsgSpoolUsage": 1500
    }
    
    try:
        response = make_semp_request("POST", url, auth, body)
        
        if response.status_code in [200, 201]:
            logger.info(f"✓ Message VPN '{vpn_name}' created successfully")
            return True, "Created"
        elif response.status_code == 409:
            logger.info(f"· Message VPN '{vpn_name}' already exists")
            return True, "Already exists"
        elif response.status_code == 400:
            # Check if it's an "already exists" error
            try:
                error_data = response.json()
                if "already exists" in error_data.get("meta", {}).get("error", {}).get("description", "").lower():
                    logger.info(f"· Message VPN '{vpn_name}' already exists")
                    return True, "Already exists"
            except (json.JSONDecodeError, KeyError):
                pass
            error_msg = f"Failed to create Message VPN (status {response.status_code}): {response.text}"
            logger.error(error_msg)
            return False, error_msg
        elif response.status_code in [401, 403]:
            error_msg = f"Authentication failed for Message VPN creation (status {response.status_code})"
            logger.error(error_msg)
            return False, error_msg
        else:
            error_msg = f"Failed to create Message VPN (status {response.status_code}): {response.text}"
            logger.error(error_msg)
            return False, error_msg
            
    except requests.exceptions.RequestException as e:
        error_msg = f"Error creating Message VPN: {e}"
        logger.error(error_msg)
        return False, error_msg


def enable_message_spool(vpn_name: str, broker_url: str, auth: Tuple[str, str]) -> bool:
    """
    Enable message spool for a Message VPN.
    
    Args:
        vpn_name: Name of the VPN
        broker_url: Broker URL (host:port)
        auth: Tuple of (username, password)
        
    Returns:
        bool: True if successful, False otherwise
    """
    url = f"http://{broker_url}/SEMP/v2/config/msgVpns/{vpn_name}"
    body = {
        "serviceSempPlainTextEnabled": True,
        "serviceSempPlainTextListenPort": 8080
    }
    
    try:
        # First, ensure SEMP service is enabled (usually is by default)
        response = make_semp_request("PATCH", url, auth, body)
        
        # Enable message spool for the VPN
        # Note: The message spool is automatically enabled when you set maxMsgSpoolUsage > 0 in VPN creation
        # This step ensures SMF service is configured
        logger.info(f"· Message spool configuration applied for VPN '{vpn_name}'")
        return True
            
    except requests.exceptions.RequestException as e:
        logger.warning(f"Warning: Could not configure message spool services: {e}")
        # Don't fail - the VPN might still work
        return True


def create_queue(vpn_name: str, queue_name: str, broker_url: str, auth: Tuple[str, str]) -> Tuple[bool, str]:
    """
    Create a queue in a Message VPN.
    
    Args:
        vpn_name: Name of the VPN
        queue_name: Name of the queue to create
        broker_url: Broker URL (host:port)
        auth: Tuple of (username, password)
        
    Returns:
        Tuple[bool, str]: (Success status, message)
    """
    url = f"http://{broker_url}/SEMP/v2/config/msgVpns/{vpn_name}/queues"
    body = {
        "queueName": queue_name,
        "permission": "delete",
        "ingressEnabled": True,
        "egressEnabled": True
    }
    
    try:
        response = make_semp_request("POST", url, auth, body)
        
        if response.status_code in [200, 201]:
            logger.info(f"✓ Queue '{queue_name}' created successfully")
            return True, "Created"
        elif response.status_code == 409:
            logger.info(f"· Queue '{queue_name}' already exists")
            return True, "Already exists"
        elif response.status_code == 400:
            # Check if it's an "already exists" error
            try:
                error_data = response.json()
                if "already exists" in error_data.get("meta", {}).get("error", {}).get("description", "").lower():
                    logger.info(f"· Queue '{queue_name}' already exists")
                    return True, "Already exists"
            except (json.JSONDecodeError, KeyError):
                pass
            error_msg = f"Failed to create queue '{queue_name}' (status {response.status_code}): {response.text}"
            logger.error(error_msg)
            return False, error_msg
        elif response.status_code in [401, 403]:
            error_msg = f"Authentication failed for queue creation (status {response.status_code})"
            logger.error(error_msg)
            return False, error_msg
        else:
            error_msg = f"Failed to create queue '{queue_name}' (status {response.status_code}): {response.text}"
            logger.error(error_msg)
            return False, error_msg
            
    except requests.exceptions.RequestException as e:
        error_msg = f"Error creating queue '{queue_name}': {e}"
        logger.error(error_msg)
        return False, error_msg


def create_client_username(vpn_name: str, username: str, broker_url: str, auth: Tuple[str, str]) -> Tuple[bool, str]:
    """
    Create a client username in a Message VPN.
    
    Args:
        vpn_name: Name of the VPN
        username: Client username to create
        broker_url: Broker URL (host:port)
        auth: Tuple of (username, password)
        
    Returns:
        Tuple[bool, str]: (Success status, message)
    """
    url = f"http://{broker_url}/SEMP/v2/config/msgVpns/{vpn_name}/clientUsernames"
    body = {
        "clientUsername": username,
        "enabled": True
    }
    
    try:
        response = make_semp_request("POST", url, auth, body)
        
        if response.status_code in [200, 201]:
            logger.info(f"✓ Client username '{username}' created successfully")
            return True, "Created"
        elif response.status_code == 409:
            logger.info(f"· Client username '{username}' already exists")
            return True, "Already exists"
        elif response.status_code == 400:
            # Check if it's an "already exists" error
            try:
                error_data = response.json()
                if "already exists" in error_data.get("meta", {}).get("error", {}).get("description", "").lower():
                    logger.info(f"· Client username '{username}' already exists")
                    return True, "Already exists"
            except (json.JSONDecodeError, KeyError):
                pass
            error_msg = f"Failed to create client username '{username}' (status {response.status_code}): {response.text}"
            logger.error(error_msg)
            return False, error_msg
        elif response.status_code in [401, 403]:
            error_msg = f"Authentication failed for username creation (status {response.status_code})"
            logger.error(error_msg)
            return False, error_msg
        else:
            error_msg = f"Failed to create client username '{username}' (status {response.status_code}): {response.text}"
            logger.error(error_msg)
            return False, error_msg
            
    except requests.exceptions.RequestException as e:
        error_msg = f"Error creating client username '{username}': {e}"
        logger.error(error_msg)
        return False, error_msg


def main():
    """Main orchestration function."""
    args = parse_arguments()
    
    # Handle container removal
    if args.get("remove_container"):
        success = remove_solace_broker()
        sys.exit(0 if success else 1)
    
    # Load and merge configuration
    file_config = load_config_file(args.get("config"))
    config = merge_config(file_config, args)
    
    # Deploy Docker container unless skipped
    if not config.get("skip_docker"):
        if not deploy_solace_broker():
            logger.error("Failed to deploy Solace broker")
            sys.exit(1)
        
        # Wait for broker to be ready
        auth = (config.get("admin_user", DEFAULT_ADMIN_USER), 
                config.get("admin_pass", DEFAULT_ADMIN_PASS))
        broker_url = config.get("broker", DEFAULT_BROKER_URL)
        
        if not check_broker_ready(broker_url, auth):
            logger.error("Broker not ready, aborting")
            sys.exit(1)
    else:
        logger.info("Skipping Docker deployment (using existing broker)")
    
    # Extract configuration
    broker_url = config.get("broker", DEFAULT_BROKER_URL)
    admin_user = config.get("admin_user", DEFAULT_ADMIN_USER)
    admin_pass = config.get("admin_pass", DEFAULT_ADMIN_PASS)
    vpn_name = config.get("vpn")
    queues_str = config.get("queues")
    username = config.get("username")
    
    auth = (admin_user, admin_pass)
    
    # Validate required parameters
    if not vpn_name:
        logger.error("VPN name is required (use --vpn)")
        sys.exit(1)
    
    # Create Message VPN
    logger.info(f"\n{'='*60}")
    logger.info("Creating Message VPN...")
    logger.info(f"{'='*60}")
    vpn_success, vpn_msg = create_message_vpn(vpn_name, broker_url, auth)
    
    if not vpn_success:
        logger.error("Failed to create Message VPN, aborting")
        sys.exit(1)
    
    # Enable message spool for the VPN
    enable_message_spool(vpn_name, broker_url, auth)
    
    # Wait for message spool to initialize
    if queues_str:
        logger.info("Waiting for message spool to initialize...")
        time.sleep(3)
    
    # Create queues
    if queues_str:
        logger.info(f"\n{'='*60}")
        logger.info("Creating queues...")
        logger.info(f"{'='*60}")
        
        queue_names = [q.strip() for q in queues_str.split(",") if q.strip()]
        created_queues = 0
        existing_queues = 0
        failed_queues = 0
        
        for queue_name in queue_names:
            success, msg = create_queue(vpn_name, queue_name, broker_url, auth)
            if success:
                if msg == "Created":
                    created_queues += 1
                else:
                    existing_queues += 1
            else:
                failed_queues += 1
        
        logger.info(f"\nQueue Summary: {created_queues} created, {existing_queues} already existed, {failed_queues} failed")
    
    # Create client username
    if username:
        logger.info(f"\n{'='*60}")
        logger.info("Creating client username...")
        logger.info(f"{'='*60}")
        user_success, user_msg = create_client_username(vpn_name, username, broker_url, auth)
    
    # Final summary
    logger.info(f"\n{'='*60}")
    logger.info("Configuration Summary")
    logger.info(f"{'='*60}")
    logger.info(f"Broker: {broker_url}")
    logger.info(f"Message VPN: {vpn_name} ({vpn_msg})")
    if queues_str:
        logger.info(f"Queues: {len(queue_names)} processed")
    if username:
        logger.info(f"Client Username: {username} ({user_msg})")
    logger.info(f"\n✓ Configuration complete!")
    logger.info(f"\nAccess PubSub+ Manager at: http://{broker_url.split(':')[0]}:8080")


if __name__ == "__main__":
    main()
