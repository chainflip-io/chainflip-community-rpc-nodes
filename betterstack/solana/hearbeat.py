import argparse
import requests
import json
import time
import logging

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def load_config(config_file):
    """Loads the JSON configuration file for hosts and heartbeat endpoint."""
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
        logging.info("Configuration file loaded successfully.")
        return config
    except Exception as e:
        logging.error(f"Error loading config file: {e}")
        raise


def send_heartbeat(url):
    """Send a heartbeat ping to the specified URL."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        logging.info(f"Heartbeat ping sent successfully to {url}")
    except requests.RequestException as e:
        logging.error(f"Error sending heartbeat to {url}: {e}")


def check_rpc_call(host):
    """Make an RPC call to the Solana node and check for errors."""
    url = host["rpc_url"]
    headers = {"Content-Type": "application/json"}
    payload = {"jsonrpc": "2.0", "id": 1, "method": "getHealth"}

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()

        # Check for errors in the response body
        result = response.json()
        if "error" in result:
            logging.error(f"RPC call returned an error from {url}: {result['error']}")
            return False
        else:
            logging.info(
                f"RPC call to {host['host']} successful. Slot: {result.get('result')}"
            )
            return True

    except requests.RequestException as e:
        logging.error(f"Error during RPC call to {url}: {e}")
        return False


def job(config):
    """Scheduled job to check RPC call and ping heartbeat if successful."""
    for host in config["hosts"]:
        if check_rpc_call(host):
            send_heartbeat(host["heartbeat_endpoint"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Solana Node RPC Call and Heartbeat Script"
    )
    parser.add_argument(
        "--config", type=str, default="config.json", help="Path to the JSON config file"
    )
    args = parser.parse_args()

    # Load the configuration file
    try:
        config = load_config(args.config)
    except Exception as e:
        logging.critical(f"Failed to load config: {e}")
        exit(1)

    # Run the job once to start
    job(config)

    # Schedule the job to run every 30 seconds
    while True:
        time.sleep(30)
        job(config)
