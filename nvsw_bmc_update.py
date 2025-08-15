#!/usr/bin/env python3
"""
GB300 Switch BMC Firmware Update Script
Parses switch_bmc.yaml and performs BMC firmware updates via Redfish API.
"""

import os
import sys
import yaml
import requests
import time
import logging
from datetime import datetime
from typing import List, Dict, Tuple
import urllib3
from requests.auth import HTTPBasicAuth

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class BMCUpdateError(Exception):
    """Custom exception for BMC update operations."""
    pass


def setup_logging():
    """Set up logging to both console and file with timestamps."""
    # Create logs directory if it doesn't exist
    log_dir = './logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        print(f"Created logs directory: {log_dir}")
    
    # Set up logging configuration
    log_file = os.path.join(log_dir, 'nvsw_bmc_update.log')
    
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
    
    # File handler (append mode)
    file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(console_handler)
    
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
    logging.info(f"Script: nvsw_bmc_update.py")
    logging.info(f"Working Directory: {os.getcwd()}")
    logging.info(f"{separator}")


def load_switch_bmc_yaml() -> Tuple[List[Dict], str, str]:
    """
    Load and parse switch_bmc.yaml file.
    Returns tuple of (targets, username, password).
    """
    yaml_file = 'switch_bmc.yaml'
    
    if not os.path.exists(yaml_file):
        raise BMCUpdateError(f"File not found: {yaml_file}")
    
    try:
        with open(yaml_file, 'r') as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise BMCUpdateError(f"Error parsing {yaml_file}: {e}")
    except Exception as e:
        raise BMCUpdateError(f"Error reading {yaml_file}: {e}")
    
    if 'Targets' not in data:
        raise BMCUpdateError(f"No 'Targets' section found in {yaml_file}")
    
    targets = data['Targets']
    if not isinstance(targets, list):
        raise BMCUpdateError(f"'Targets' section in {yaml_file} is not a list")
    
    if not targets:
        raise BMCUpdateError(f"'Targets' section in {yaml_file} is empty")
    
    # Validate each target has required fields
    for i, target in enumerate(targets):
        required_fields = ['BMC_IP', 'RF_USERNAME', 'RF_PASSWORD', 'PACKAGE', 'SYSTEM_NAME']
        for field in required_fields:
            if field not in target:
                raise BMCUpdateError(f"Target {i+1} in {yaml_file} missing required field: {field}")
    
    # Extract username and password (assuming all targets use same credentials)
    username = targets[0]['RF_USERNAME']
    password = targets[0]['RF_PASSWORD']
    
    # Validate credentials are consistent
    for i, target in enumerate(targets):
        if target['RF_USERNAME'] != username or target['RF_PASSWORD'] != password:
            raise BMCUpdateError(f"Inconsistent credentials found in target {i+1}")
    
    return targets, username, password


def validate_firmware_file(package_path: str) -> None:
    """Validate that the firmware file exists and is accessible."""
    if not os.path.exists(package_path):
        raise BMCUpdateError(f"Firmware file not found: {package_path}")
    
    if not os.path.isfile(package_path):
        raise BMCUpdateError(f"Path is not a file: {package_path}")
    
    # Check file size (should be > 0)
    file_size = os.path.getsize(package_path)
    if file_size == 0:
        raise BMCUpdateError(f"Firmware file is empty: {package_path}")
    
    log_print(f"Firmware file validated: {package_path} ({file_size:,} bytes)")


def execute_bmc_update(ip: str, username: str, password: str, system_name: str, 
                      package_path: str, timeout: int = 300) -> bool:
    """
    Execute BMC firmware update via Redfish API.
    Returns True if successful, False otherwise.
    """
    base_url = f"https://{ip}"
    update_url = f"{base_url}/redfish/v1/UpdateService"
    
    headers = {
        'Content-Type': 'application/octet-stream'
    }
    
    try:
        log_print(f"  Uploading firmware to {system_name} ({ip})...", end=" ", flush=True)
        
        # Open and read the firmware file
        with open(package_path, 'rb') as firmware_file:
            response = requests.post(
                update_url,
                headers=headers,
                data=firmware_file,
                auth=HTTPBasicAuth(username, password),
                verify=False,
                timeout=timeout
            )
        
        if response.status_code in [200, 202, 204]:
            log_print("✓ SUCCESS")
            return True
        else:
            log_print(f"✗ FAILED (HTTP {response.status_code})")
            try:
                error_data = response.json()
                log_print(f"    Error: {error_data}")
            except:
                log_print(f"    Response: {response.text}")
            return False
    
    except requests.exceptions.Timeout:
        log_print("✗ FAILED (Timeout)")
        return False
    except requests.exceptions.ConnectionError:
        log_print("✗ FAILED (Connection Error)")
        return False
    except FileNotFoundError:
        log_print(f"✗ FAILED (Firmware file not found: {package_path})")
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


def display_summary(targets: List[Dict], package_path: str) -> None:
    """Display update summary before execution."""
    log_print(f"\n" + "=" * 60)
    log_print("BMC FIRMWARE UPDATE SUMMARY")
    log_print("=" * 60)
    log_print(f"YAML file: switch_bmc.yaml")
    log_print(f"Firmware package: {os.path.basename(package_path)}")
    log_print(f"Unique systems to update: {len(targets)}")
    
    log_print(f"\nSystems that will be updated:")
    for target in targets:
        log_print(f"  - {target['SYSTEM_NAME']} ({target['BMC_IP']})")
    
    log_print(f"\n⚠ WARNING: This will update BMC firmware on {len(targets)} systems!")
    log_print("⚠ This operation may take several minutes per system.")
    log_print("⚠ Do not interrupt the process once started.")


def get_user_confirmation(targets: List[Dict]) -> bool:
    """Get user confirmation before proceeding."""
    while True:
        choice = input(f"\nDo you want to proceed with updating {len(targets)} BMC systems? (yes/no): ").strip().lower()
        # Log the user's choice
        logging.info(f"User confirmation prompt: proceed with updating {len(targets)} BMC systems?")
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
    
    log_print("GB300 Switch BMC Firmware Update Tool")
    log_print("=" * 45)
    
    try:
        # Load and parse switch_bmc.yaml
        log_print("Loading switch_bmc.yaml...")
        targets, username, password = load_switch_bmc_yaml()
        
        # Get unique targets (eliminate duplicates)
        unique_targets = get_unique_targets(targets)
        
        log_print(f"Found {len(targets)} total targets, {len(unique_targets)} unique systems")
        
        # Validate firmware file exists (use first target's package path)
        package_path = unique_targets[0]['PACKAGE']
        validate_firmware_file(package_path)
        
        # Validate all targets use the same firmware package
        for target in unique_targets:
            if target['PACKAGE'] != package_path:
                raise BMCUpdateError(f"Inconsistent firmware packages found. All targets must use the same firmware file.")
        
        log_print(f"\n✓ Using credentials - Username: {username}")
        
        # Display summary and get confirmation
        display_summary(unique_targets, package_path)
        
        if not get_user_confirmation(unique_targets):
            log_print("Operation cancelled by user.")
            return
        
        # Execute BMC updates
        log_print(f"\n" + "=" * 60)
        log_print("EXECUTING BMC FIRMWARE UPDATES")
        log_print("=" * 60)
        log_print(f"Updating {len(unique_targets)} unique systems...")
        
        success_count = 0
        total_count = len(unique_targets)
        
        for i, target in enumerate(unique_targets, 1):
            log_print(f"\n[{i}/{total_count}]", end=" ")
            
            success = execute_bmc_update(
                target['BMC_IP'],
                username,
                password,
                target['SYSTEM_NAME'],
                target['PACKAGE']
            )
            
            if success:
                success_count += 1
            
            # Delay between updates to avoid overwhelming the network
            if i < total_count:
                log_print("  Waiting 5 seconds before next update...")
                time.sleep(5)
        
        # Final summary
        log_print(f"\n" + "=" * 60)
        log_print("BMC UPDATE SUMMARY")
        log_print("=" * 60)
        log_print(f"Total systems: {total_count}")
        log_print(f"Successful updates: {success_count}")
        log_print(f"Failed updates: {total_count - success_count}")
        
        if success_count == total_count:
            log_print("✓ All BMC firmware updates completed successfully!")
        else:
            log_print("⚠ Some BMC updates failed. Check the output above for details.")
            sys.exit(1)
    
    except KeyboardInterrupt:
        log_print("\n\nOperation cancelled by user.")
        sys.exit(1)
    except BMCUpdateError as e:
        log_print(f"\nError: {e}")
        sys.exit(1)
    except Exception as e:
        log_print(f"\nUnexpected Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
