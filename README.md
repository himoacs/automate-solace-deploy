# Solace PubSub+ Broker Configuration Script

A Python script that deploys a Solace PubSub+ software broker as a Docker container and configures it using SEMP v2 API to create Message VPNs, queues, and client usernames.

## Features

- 🐳 **Docker Deployment**: Automatically deploys Solace PubSub+ broker as a Docker container
- 🔧 **Simple Configuration**: Create Message VPNs, queues, and usernames with minimal setup
- 📝 **Flexible Input**: Support for command-line arguments and JSON configuration files
- ♻️ **Idempotent**: Safe to run multiple times, handles existing objects gracefully
- 🧹 **Easy Cleanup**: Built-in container removal functionality

## Prerequisites

- **Docker**: Installed and running
  - Install from [https://www.docker.com/get-started](https://www.docker.com/get-started)
  - Verify installation: `docker --version`
- **Python**: Version 3.7 or higher
  - Verify installation: `python3 --version`

## Installation

1. **Clone or download this repository**

2. **Create a virtual environment** (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Make the script executable** (optional):
   ```bash
   chmod +x solace_config.py
   ```
# If using virtual environment, activate it first
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Run the script

## Quick Start

Deploy a Solace broker and create a VPN with queues and a username:

```bash
python solace_config.py --vpn my-vpn --queues q1,q2,q3 --username client1
```

This will:
1. Deploy a Solace broker Docker container (if not already running)
2. Wait for the broker to be ready
3. Create a Message VPN named `my-vpn`
4. Create three queues: `q1`, `q2`, `q3`
5. Create a client username `client1`

Access the PubSub+ Manager web interface at: **http://localhost:8080**

## Usage

### Basic Usage

```bash
# Deploy broker and create VPN with queues and username
python solace_config.py --vpn my-vpn --queues queue1,queue2 --username myuser

# With custom admin credentials
python solace_config.py --admin-user admin --admin-pass secret \
  --vpn production --queues orders,notifications --username app-client
```

### Using a Configuration File

Create a `config.json` file (use `config.example.json` as a template):

```json
{
  "broker": "localhost:8080",
  "admin_user": "admin",
  "admin_pass": "admin",
  "vpn": "my-vpn",
  "queues": "queue1,queue2,queue3",
  "username": "client1"
}
```

Then run:

```bash
python solace_config.py --config config.json
```

**Note**: Command-line arguments override configuration file values.

### Using an Existing Broker

If you already have a Solace broker running (not deployed by this script):

```bash
python solace_config.py --skip-docker --broker remote-host:8080 \
  --admin-user admin --admin-pass mypassword \
  --vpn my-vpn --queues myqueue --username myuser
```

### Cleanup

Remove the Solace broker container:

```bash
python solace_config.py --remove-container
```

This stops and removes the Docker container named `solace`.

## Command-Line Options

### Docker Options

- `--skip-docker`: Skip Docker container deployment (use existing broker)
- `--remove-container`: Stop and remove the Solace broker container, then exit

### Broker Connection

- `--broker HOST:PORT`: Broker URL (default: `localhost:8080`)
- `--admin-user USER`: Admin username for SEMP API (default: `admin`)
- `--admin-pass PASS`: Admin password for SEMP API (default: `admin`)

### Configuration

- `--config PATH`: Path to JSON configuration file (CLI args override config file)

### Object Creation

- `--vpn NAME`: Message VPN name to create (required)
- `--queues NAMES`: Comma-separated list of queue names to create
- `--username NAME`: Client username to create

### Logging

- `--log-level LEVEL`: Set logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) (default: `INFO`)

## Docker Container Configuration

The script deploys a Solace PubSub+ broker with the following configuration:

- **Ports**:
  - `8080`: SEMP API and Web Manager
  - `55555`: SMF messaging
- **Scaling** (1K connections profile):
  - Max connections: 1,000
  - Max queue message count: 240
  - Max bridges: 25
  - Max subscriptions: 500,000
  - Max guaranteed message size: 10 MB
  - Message spool usage: 1,500 MB
- **Image**: `solace/solace-pubsub-standard`
- **Container name**: `solace`

## Examples

### Example 1: Simple Development Setup

```bash
python solace_config.py --vpn dev-vpn --queues inbox,outbox --username dev-user
```

### Example 2: Multiple Queues for Microservices

```bash
python solace_config.py \
  --vpn microservices \
  --queues user-service,order-service,payment-service,notification-service \
  --username api-gateway
```

### Example 3: Using Config File with Overrides

```bash
# Use config.json for defaults, override VPN name
python solace_config.py --config config.json --vpn test-vpn
```

### Example 4: Production Broker (External)

```bash
python solace_config.py \
  --skip-docker \
  --broker prod-solace.example.com:8080 \
  --admin-user prod-admin \
  --admin-pass $SOLACE_ADMIN_PASS \
  --vpn production \
  --queues critical-events,audit-logs \
  --username app-service
```

## SEMP API Endpoints Used

The script uses the following Solace SEMP v2 Config API endpoints:

- **Create Message VPN**: `POST /SEMP/v2/config/msgVpns`
- **Create Queue**: `POST /SEMP/v2/config/msgVpns/{vpnName}/queues`
- **Create Client Username**: `POST /SEMP/v2/config/msgVpns/{vpnName}/clientUsernames`
- **Health Check**: `GET /SEMP/v2/config/about`

All objects are created with default settings:
- `enabled: true`
- Queues: `permission: delete`, `ingressEnabled: true`, `egressEnabled: true`

## Troubleshooting

### Docker Not Found

```
Error: Docker command not found
```

**Solution**: Install Docker and ensure it's in your PATH.

### Port Already in Use

```
Error: Bind for 0.0.0.0:8080 failed: port is already allocated
```

**Solution**: Stop the service using port 8080 or remove the existing `solace` container:
```bash
docker stop solace && docker rm solace
```

### Authentication Failed

```
Error: Authentication failed (status 401)
```

**Solution**: Verify admin credentials with `--admin-user` and `--admin-pass`. Default is `admin/admin`.

### Broker Not Ready Timeout

```
Error: Broker did not become ready within 60 seconds
```

**Solution**: 
- Check Docker container logs: `docker logs solace`
- Ensure sufficient system resources (memory, CPU)
- Increase timeout by modifying `BROKER_READY_TIMEOUT` in the script

### VPN Creation Failed

```
Error: Failed to create Message VPN (status 400)
```

**Solution**: Check the error details in the log. Common causes:
- Invalid VPN name (use alphanumeric characters, hyphens, underscores)
- Insufficient broker resources

## Accessing the Broker

After deployment:

- **PubSub+ Manager**: http://localhost:8080
  - Username: `admin`
  - Password: `admin`
- **SEMP API**: http://localhost:8080/SEMP/v2/
- **SMF Protocol**: `localhost:55555`

## Default Object Settings

All created objects use Solace defaults with minimal configuration:

**Message VPN**:
```json
{
  "msgVpnName": "vpn-name",
  "enabled": true
}
```

**Queue**:
```json
{
  "queueName": "queue-name",
  "enabled": true,
  "permission": "delete",
  "ingressEnabled": true,
  "egressEnabled": true
}
```

**Client Username**:
```json
{
  "clientUsername": "username",
  "enabled": true
}
```

## Idempotency

The script is idempotent - running it multiple times with the same parameters is safe:

- Existing Docker container: Reuses running container or starts stopped one
- Existing VPN: Logs "already exists" and continues
- Existing queues: Logs "already exists" for each and continues
- Existing username: Logs "already exists" and continues

HTTP 409 (Conflict) responses are treated as success with "already exists" status.

## References

- [Solace SEMP API Documentation](https://docs.solace.com/Admin/SEMP/Using-SEMP.htm)
- [Solace SEMP Config API Reference](https://docs.solace.com/API-Developer-Online-Ref-Documentation/swagger-ui/software-broker/config/index.html)
- [Solace PubSub+ Standard Docker Image](https://hub.docker.com/r/solace/solace-pubsub-standard)

## License

This script is provided as-is for demonstration and testing purposes.

## Support

For issues with:
- **This script**: Open an issue in the repository
- **Solace PubSub+**: Contact [support@solace.com](mailto:support@solace.com)
- **SEMP API**: Consult [Solace documentation](https://docs.solace.com/)
