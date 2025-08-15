#!/usr/bin/env python3
"""
GB300 Compute Auxiliary Power Cycle Script
Sends auxiliary power cycle commands to compute systems via Redfish API.
Reads from compute_hmc.yaml and executes AuxPowerCycleForce for each system.
"""

import os
import sys
import yaml
import requests
import json
import logging
from datetime import datetime
from typing import List, Dict, Tuple
import urllib3
from requests.auth import HTTPBasicAuth

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class AuxPowerCycleError(Exception):
    """Custom exception for auxiliary power cycle operations."""
    pass


def setup_logging():
    """Set up logging to both console and file with timestamps."""
    # Create logs directory if it doesn't exist
    log_dir = './logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        print(f"Created logs directory: {log_dir}")
    
    # Set up logging configuration
    log_file = os.path.join(log_dir, 'aux_powercycle_compute.log')
    
    # Create custom formatter with timestamp
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Set up root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Remove any existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # File handler (append mode) - console output handled by log_print function
    file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger


def log_print(message, end='\n', flush=False):
    """Print message to both console and log file."""
    # Print to console
    print(message, end=end, flush=flush)
    
    # Log to file (only if it's not an empty line or just whitespace)
    if message.strip():
        logging.info(message.rstrip())


def log_session_start():
    """Log the start of a new session."""
    session_start = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    separator = "=" * 80
    
    logging.info(f"\n{separator}")
    logging.info(f"NEW SESSION STARTED: {session_start}")
    logging.info(f"Script: aux_powercycle_compute.py")
    logging.info(f"Working Directory: {os.getcwd()}")
    logging.info(f"{separator}")


def load_compute_hmc_yaml() -> Tuple[List[Dict], str, str]:
    """
    Load and parse compute_hmc.yaml file.
    Returns tuple of (targets, username, password).
    """
    yaml_file = 'compute_hmc.yaml'
    
    if not os.path.exists(yaml_file):
        raise AuxPowerCycleError(f"File not found: {yaml_file}")
    
    try:
        with open(yaml_file, 'r') as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise AuxPowerCycleError(f"Error parsing {yaml_file}: {e}")
    except Exception as e:
        raise AuxPowerCycleError(f"Error reading {yaml_file}: {e}")
    
    if 'Targets' not in data:
        raise AuxPowerCycleError(f"No 'Targets' section found in {yaml_file}")
    
    targets = data['Targets']
    if not isinstance(targets, list):
        raise AuxPowerCycleError(f"'Targets' section in {yaml_file} is not a list")
    
    if not targets:
        raise AuxPowerCycleError(f"'Targets' section in {yaml_file} is empty")
    
    # Validate each target has required fields
    for i, target in enumerate(targets):
        required_fields = ['BMC_IP', 'RF_USERNAME', 'RF_PASSWORD', 'SYSTEM_NAME']
        for field in required_fields:
            if field not in target:
                raise AuxPowerCycleError(f"Target {i+1} in {yaml_file} missing required field: {field}")
    
    # Extract username and password (assuming all targets use same credentials)
    username = targets[0]['RF_USERNAME']
    password = targets[0]['RF_PASSWORD']
    
    # Validate credentials are consistent
    for i, target in enumerate(targets):
        if target['RF_USERNAME'] != username or target['RF_PASSWORD'] != password:
            raise AuxPowerCycleError(f"Inconsistent credentials found in target {i+1}")
    
    return targets, username, password


def execute_aux_power_cycle(ip: str, username: str, password: str, system_name: str) -> bool:
    """
    Execute auxiliary power cycle via Redfish API.
    Returns True if successful, False otherwise.
    """
    url = f"https://{ip}/redfish/v1/Chassis/BMC_0/Actions/Oem/NvidiaChassis.AuxPowerReset"
    
    headers = {
        'Content-Type': 'application/json'
    }
    
    payload = {
        'ResetType': 'AuxPowerCycleForce'
    }
    
    try:
        log_print(f"  Sending auxiliary power cycle to {system_name} ({ip})...", end=" ", flush=True)
        
        # Log request details
        log_print(f"\n    Request URL: {url}")
        log_print(f"    Request Headers: {headers}")
        log_print(f"    Request Method: POST")
        log_print(f"    Authentication: Basic (user: {username})")
        log_print(f"    Request Payload: {json.dumps(payload)}")
        
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            auth=HTTPBasicAuth(username, password),
            verify=False,
            timeout=30
        )
        
        # Log comprehensive response details
        log_print(f"\n    HTTP Response Details:")
        log_print(f"    Status Code: {response.status_code}")
        log_print(f"    Status Reason: {response.reason}")
        log_print(f"    Response Headers: {dict(response.headers)}")
        log_print(f"    Response URL: {response.url}")
        log_print(f"    Response Time: {response.elapsed.total_seconds():.2f} seconds")
        
        # Log response content
        if response.text:
            log_print(f"    Response Body:")
            try:
                # Try to parse as JSON for prettier output
                response_json = response.json()
                log_print(f"    {json.dumps(response_json, indent=6)}")
            except:
                # If not JSON, log as plain text
                for line in response.text.splitlines():
                    log_print(f"    {line}")
        else:
            log_print(f"    Response Body: (empty)")
        
        if response.status_code in [200, 202, 204]:
            log_print("    Result: ✓ SUCCESS")
            return True
        else:
            log_print(f"    Result: ✗ FAILED (HTTP {response.status_code})")
            return False
    
    except requests.exceptions.Timeout:
        log_print("✗ FAILED (Timeout)")
        return False
    except requests.exceptions.ConnectionError:
        log_print("✗ FAILED (Connection Error)")
        return False
    except Exception as e:
        log_print(f"✗ FAILED ({e})")
        return False


def get_unique_targets(targets: List[Dict]) -> List[Dict]:
    """Get unique targets based on IP addresses."""
    unique_targets = {}
    for target in targets:
        ip = target['BMC_IP']
        if ip not in unique_targets:
            unique_targets[ip] = target
    
    return list(unique_targets.values())


def display_summary(targets: List[Dict]) -> None:
    """Display auxiliary power cycle summary before execution."""
    log_print(f"\n" + "=" * 60)
    log_print("GB300 COMPUTE AUXILIARY POWER CYCLE SUMMARY")
    log_print("=" * 60)
    log_print(f"YAML file: compute_hmc.yaml")
    log_print(f"Unique systems to power cycle: {len(targets)}")
    
    log_print(f"\nSystems that will be power cycled:")
    for target in targets:
        log_print(f"  - {target['SYSTEM_NAME']} ({target['BMC_IP']})")
    
    log_print(f"\n⚠ WARNING: This will perform auxiliary power cycle on {len(targets)} systems!")
    log_print("⚠ This operation will force a power cycle of auxiliary power.")
    log_print("⚠ Systems may become temporarily unavailable.")


def get_user_confirmation(targets: List[Dict]) -> bool:
    """Get user confirmation before proceeding."""
    while True:
        choice = input(f"\nDo you want to proceed with auxiliary power cycle on {len(targets)} systems? (yes/no): ").strip().lower()
        # Log the user's choice
        logging.info(f"User confirmation prompt: proceed with auxiliary power cycle on {len(targets)} systems?")
        logging.info(f"User response: {choice}")
        
        if choice in ['yes', 'y']:
            return True
        elif choice in ['no', 'n']:
            return False
        else:
            log_print("Please enter 'yes' or 'no'")


def main():
    """Main program flow."""
    # Set up logging first (before any output)
    logger = setup_logging()
    log_session_start()
    
    log_print("GB300 Compute Auxiliary Power Cycle Tool")
    log_print("=" * 45)
    
    try:
        # Load and parse compute_hmc.yaml file
        log_print("Loading compute_hmc.yaml...")
        targets, username, password = load_compute_hmc_yaml()
        
        # Get unique targets (eliminate duplicates)
        unique_targets = get_unique_targets(targets)
        
        log_print(f"Found {len(targets)} total targets, {len(unique_targets)} unique systems")
        
        log_print(f"\n✓ Using credentials - Username: {username}")
        
        # Display summary and get confirmation
        display_summary(unique_targets)
        
        if not get_user_confirmation(unique_targets):
            log_print("Operation cancelled by user.")
            return
        
        # Execute auxiliary power cycles
        log_print(f"\n" + "=" * 60)
        log_print("EXECUTING AUXILIARY POWER CYCLES")
        log_print("=" * 60)
        log_print(f"Processing {len(unique_targets)} unique systems...")
        
        success_count = 0
        total_count = len(unique_targets)
        
        for i, target in enumerate(unique_targets, 1):
            log_print(f"\n[{i}/{total_count}]", end=" ")
            
            success = execute_aux_power_cycle(
                target['BMC_IP'],
                username,
                password,
                target['SYSTEM_NAME']
            )
            
            if success:
                success_count += 1
            
            # Delay between operations to avoid overwhelming the network
            if i < total_count:
                log_print("  Waiting 3 seconds before next operation...")
                import time
                time.sleep(3)
        
        # Final summary
        log_print(f"\n" + "=" * 60)
        log_print("AUXILIARY POWER CYCLE SUMMARY")
        log_print("=" * 60)
        log_print(f"Total systems: {total_count}")
        log_print(f"Successful operations: {success_count}")
        log_print(f"Failed operations: {total_count - success_count}")
        
        if success_count == total_count:
            log_print("✓ All auxiliary power cycle operations completed successfully!")
        else:
            log_print("⚠ Some auxiliary power cycle operations failed. Check the output above for details.")
            sys.exit(1)
    
    except KeyboardInterrupt:
        log_print("\n\nOperation cancelled by user.")
        sys.exit(1)
    except AuxPowerCycleError as e:
        log_print(f"\nError: {e}")
        sys.exit(1)
    except Exception as e:
        log_print(f"\nUnexpected Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
