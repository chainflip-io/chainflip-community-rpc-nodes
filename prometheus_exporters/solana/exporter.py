import argparse
import requests
import json
import time
import schedule
import logging
from prometheus_client import start_http_server, Gauge

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# Define Prometheus metrics
NODE_SLOT_NUMBER = Gauge(
    "solana_node_slot_number", "Slot number of the Solana node", ["host"]
)
REFERENCE_SLOT_NUMBER = Gauge(
    "solana_reference_slot_number", "Slot number of the reference endpoint"
)
SLOT_DIFFERENCE = Gauge(
    "solana_slot_difference", "Difference between node and reference slot", ["host"]
)
NODE_SLOT_NUMBER_ERROR_COUNT = Gauge(
    "solana_node_slot_error_count", "Number of errors fetching slot", ["host"]
)
REFERENCE_SLOT_NUMBER_ERROR_COUNT = Gauge(
    "solana_reference_slot_error_count", "Number of errors fetching slot"
)


def load_config(config_file):
    """Loads the JSON configuration file for hosts and reference endpoint."""
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
        logging.info("Configuration file loaded successfully.")
        return config
    except Exception as e:
        logging.error(f"Error loading config file: {e}")
        raise


def get_slot_number(url):
    """Fetch the current slot number from the specified Solana RPC endpoint."""
    headers = {"Content-Type": "application/json"}
    payload = {"jsonrpc": "2.0", "id": 1, "method": "getSlot"}

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        return response.json().get("result")
    except requests.RequestException as e:
        logging.error(f"Error fetching slot from {url}: {e}")
        return None


def check_node_slots(config):
    """Check the slot number of each node and compare with the reference."""
    reference_url = config["reference_endpoint"]
    reference_slot = get_slot_number(reference_url)

    if reference_slot is not None:
        REFERENCE_SLOT_NUMBER.set(reference_slot)
        logging.info(f"Reference endpoint slot: {reference_slot}")
    else:
        logging.error(f"Error fetching reference slot from {reference_url}")
        REFERENCE_SLOT_NUMBER_ERROR_COUNT.inc()
        return

    # For each node, get its slot and compare with the reference
    for host in config["hosts"]:
        node_url = host["rpc_url"]
        node_slot = get_slot_number(node_url)

        if node_slot is not None:
            NODE_SLOT_NUMBER.labels(host=host["host"]).set(node_slot)
            slot_difference = reference_slot - node_slot
            SLOT_DIFFERENCE.labels(host=host["host"]).set(slot_difference)
            logging.info(
                f"Host: {host['host']}, Node Slot: {node_slot}, Slot Difference: {slot_difference}"
            )
        else:
            logging.error(f"Error fetching slot for host {host['host']}")
            NODE_SLOT_NUMBER_ERROR_COUNT.labels(host=host["host"]).inc()


def job(config):
    """Scheduled job to compare node slots with the reference endpoint."""
    logging.info("Running job to check node slots")
    check_node_slots(config)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Solana Node Slot Comparison Exporter")
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

    # Start up the server to expose the metrics.
    try:
        start_http_server(config["prometheus_exporter_port"])
        logging.info(
            f"Prometheus metrics exposed on port {config['prometheus_exporter_port']}"
        )
    except Exception as e:
        logging.critical(f"Failed to start Prometheus HTTP server: {e}")
        exit(1)

    # Schedule the job to run every 5 seconds
    schedule.every(5).seconds.do(job, config=config)

    # Run the schedule
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Exporter stopped manually.")
    except Exception as e:
        logging.critical(f"Unexpected error occurred: {e}")
