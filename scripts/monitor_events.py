#!/usr/bin/env python3
"""
Tesseract Event Monitor Script

Monitors contract events in real-time or from a specific block.
Useful for debugging and auditing transaction activity.
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()


class EventMonitor:
    def __init__(self, network: str = "local"):
        self.network = network
        self.w3 = None
        self.contract = None

    def connect(self):
        """Connect to network and load contract"""
        config_path = Path("config/networks.json")
        with open(config_path) as f:
            config = json.load(f)["networks"].get(self.network)

        if not config:
            raise ValueError(f"Unknown network: {self.network}")

        if "rpc_url" in config:
            rpc_url = config["rpc_url"]
        else:
            api_key = os.getenv("ALCHEMY_API_KEY", "")
            rpc_url = config["rpc_url_template"].replace("{ALCHEMY_API_KEY}", api_key)

        self.w3 = Web3(Web3.HTTPProvider(rpc_url))

        if not self.w3.is_connected():
            raise ConnectionError(f"Cannot connect to {self.network}")

        # Load contract
        deployment_file = Path(f"deployments/{self.network}_deployment.json")
        abi_file = Path("deployments/TesseractBuffer_abi.json")

        if not deployment_file.exists() or not abi_file.exists():
            raise FileNotFoundError("Deployment files not found")

        with open(deployment_file) as f:
            deployment = json.load(f)

        with open(abi_file) as f:
            abi = json.load(f)

        self.contract = self.w3.eth.contract(
            address=deployment['contract_address'],
            abi=abi
        )

        self.deployment_block = deployment['block_number']

        return True

    def format_event(self, event):
        """Format event for display"""
        timestamp = datetime.fromtimestamp(
            self.w3.eth.get_block(event['blockNumber']).timestamp
        ).strftime('%Y-%m-%d %H:%M:%S')

        return {
            "event": event['event'],
            "block": event['blockNumber'],
            "tx_hash": event['transactionHash'].hex(),
            "timestamp": timestamp,
            "args": dict(event['args'])
        }

    def get_historical_events(self, from_block: int = None, to_block: int = None):
        """Get historical events"""
        if from_block is None:
            from_block = self.deployment_block
        if to_block is None:
            to_block = 'latest'

        events = []

        # Transaction events
        try:
            buffered = self.contract.events.TransactionBuffered.get_logs(
                fromBlock=from_block, toBlock=to_block
            )
            events.extend([('TransactionBuffered', e) for e in buffered])
        except Exception:
            pass

        try:
            ready = self.contract.events.TransactionReady.get_logs(
                fromBlock=from_block, toBlock=to_block
            )
            events.extend([('TransactionReady', e) for e in ready])
        except Exception:
            pass

        try:
            failed = self.contract.events.TransactionFailed.get_logs(
                fromBlock=from_block, toBlock=to_block
            )
            events.extend([('TransactionFailed', e) for e in failed])
        except Exception:
            pass

        # Access control events
        try:
            granted = self.contract.events.RoleGranted.get_logs(
                fromBlock=from_block, toBlock=to_block
            )
            events.extend([('RoleGranted', e) for e in granted])
        except Exception:
            pass

        try:
            revoked = self.contract.events.RoleRevoked.get_logs(
                fromBlock=from_block, toBlock=to_block
            )
            events.extend([('RoleRevoked', e) for e in revoked])
        except Exception:
            pass

        # Emergency events
        try:
            paused = self.contract.events.EmergencyPause.get_logs(
                fromBlock=from_block, toBlock=to_block
            )
            events.extend([('EmergencyPause', e) for e in paused])
        except Exception:
            pass

        try:
            unpaused = self.contract.events.EmergencyUnpause.get_logs(
                fromBlock=from_block, toBlock=to_block
            )
            events.extend([('EmergencyUnpause', e) for e in unpaused])
        except Exception:
            pass

        # Sort by block number
        events.sort(key=lambda x: x[1]['blockNumber'])

        return events

    def print_event(self, event_name: str, event):
        """Print a single event"""
        block = event['blockNumber']
        tx_hash = event['transactionHash'].hex()[:16] + "..."

        # Color coding for different event types
        if event_name in ['TransactionFailed', 'EmergencyPause']:
            prefix = "[!]"
        elif event_name in ['TransactionReady']:
            prefix = "[+]"
        else:
            prefix = "[*]"

        print(f"{prefix} Block {block} | {event_name}")
        print(f"    TX: {tx_hash}")

        # Print event-specific details
        args = event['args']
        if event_name == 'TransactionBuffered':
            print(f"    tx_id: {args['tx_id'].hex()[:16]}...")
            print(f"    origin: {args['origin_rollup']}")
            print(f"    target: {args['target_rollup']}")
        elif event_name == 'TransactionReady':
            print(f"    tx_id: {args['tx_id'].hex()[:16]}...")
        elif event_name == 'TransactionFailed':
            print(f"    tx_id: {args['tx_id'].hex()[:16]}...")
            print(f"    reason: {args['reason']}")
        elif event_name == 'RoleGranted':
            print(f"    role: {args['role'].hex()[:16]}...")
            print(f"    account: {args['account']}")
        elif event_name == 'RoleRevoked':
            print(f"    role: {args['role'].hex()[:16]}...")
            print(f"    account: {args['account']}")
        elif event_name in ['EmergencyPause', 'EmergencyUnpause']:
            print(f"    caller: {args['caller']}")

        print()

    def watch(self, poll_interval: int = 5):
        """Watch for new events"""
        print(f"Watching for events on {self.network}...")
        print("Press Ctrl+C to stop")
        print()

        last_block = self.w3.eth.block_number

        while True:
            try:
                current_block = self.w3.eth.block_number

                if current_block > last_block:
                    events = self.get_historical_events(
                        from_block=last_block + 1,
                        to_block=current_block
                    )

                    for event_name, event in events:
                        self.print_event(event_name, event)

                    last_block = current_block

                time.sleep(poll_interval)

            except KeyboardInterrupt:
                print("\nStopping event monitor...")
                break
            except Exception as e:
                print(f"[ERROR] {e}")
                time.sleep(poll_interval)


def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description="Monitor Tesseract contract events")
    parser.add_argument("network", nargs="?", default="local", help="Network to monitor")
    parser.add_argument("--from-block", type=int, help="Start from specific block")
    parser.add_argument("--watch", "-w", action="store_true", help="Watch for new events")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    monitor = EventMonitor(args.network)

    try:
        monitor.connect()
    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    print("=" * 50)
    print(f"Tesseract Event Monitor - {args.network}")
    print(f"Contract: {monitor.contract.address}")
    print("=" * 50)
    print()

    if args.watch:
        monitor.watch()
    else:
        from_block = args.from_block or monitor.deployment_block
        events = monitor.get_historical_events(from_block=from_block)

        if args.json:
            output = []
            for event_name, event in events:
                output.append({
                    "event": event_name,
                    "block": event['blockNumber'],
                    "tx_hash": event['transactionHash'].hex(),
                    "args": {k: v.hex() if isinstance(v, bytes) else v for k, v in event['args'].items()}
                })
            print(json.dumps(output, indent=2))
        else:
            if not events:
                print("No events found")
            else:
                print(f"Found {len(events)} events from block {from_block}:")
                print()
                for event_name, event in events:
                    monitor.print_event(event_name, event)


if __name__ == "__main__":
    main()
