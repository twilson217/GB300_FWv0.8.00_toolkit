#!/usr/bin/env python3
"""
GB300 Compute HMC Sequential Update Script
Creates Compute_Full.json and executes nvfwupd commands sequentially for each IP address
from compute_hmc.yaml file.
"""

import os
import sys
import yaml
import subprocess
import json
import logging
from datetime import datetime
from typing import List, Dict, Tuple


class HMCUpdateError(Exception):
    """Custom exception for HMC update operations."""
    pass


def setup_logging():
    """Set up logging to both console and file with timestamps."""
    # Create logs directory if it doesn't exist
    log_dir = './logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        print(f"Created logs directory: {log_dir}")
    
    # Set up logging configuration
    log_file = os.path.join(log_dir, 'compute_hmc.log')
    
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
    logging.info(f"Script: compute_hmc_sequential.py")
    logging.info(f"Working Directory: {os.getcwd()}")
    logging.info(f"{separator}")


def create_compute_full_json():
    """Create the Compute_Full.json file with the required content."""
    json_content = {
        "Targets": ["/redfish/v1/Chassis/HGX_Chassis_0"]
    }
    
    json_file = "Compute_Full.json"
    
    try:
        with open(json_file, 'w') as f:
            json.dump(json_content, f, indent=2)
        
        log_print(f"✓ Created {json_file}")
        return json_file
    
    except Exception as e:
        raise HMCUpdateError(f"Failed to create {json_file}: {e}")


def load_compute_hmc_yaml() -> Tuple[List[Dict], str, str, str]:
    """
    Load and parse compute_hmc.yaml file.
    Returns tuple of (targets, username, password, package_path).
    """
    yaml_file = 'compute_hmc.yaml'
    
    if not os.path.exists(yaml_file):
        raise HMCUpdateError(f"File not found: {yaml_file}")
    
    try:
        with open(yaml_file, 'r') as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise HMCUpdateError(f"Error parsing {yaml_file}: {e}")
    except Exception as e:
        raise HMCUpdateError(f"Error reading {yaml_file}: {e}")
    
    if 'Targets' not in data:
        raise HMCUpdateError(f"No 'Targets' section found in {yaml_file}")
    
    targets = data['Targets']
    if not isinstance(targets, list):
        raise HMCUpdateError(f"'Targets' section in {yaml_file} is not a list")
    
    if not targets:
        raise HMCUpdateError(f"'Targets' section in {yaml_file} is empty")
    
    # Validate each target has required fields
    for i, target in enumerate(targets):
        required_fields = ['BMC_IP', 'RF_USERNAME', 'RF_PASSWORD', 'PACKAGE', 'SYSTEM_NAME']
        for field in required_fields:
            if field not in target:
                raise HMCUpdateError(f"Target {i+1} in {yaml_file} missing required field: {field}")
    
    # Extract username, password, and package path (assuming all targets use same values)
    username = targets[0]['RF_USERNAME']
    password = targets[0]['RF_PASSWORD']
    package_path = targets[0]['PACKAGE']
    
    # Validate consistency across all targets
    for i, target in enumerate(targets):
        if target['RF_USERNAME'] != username:
            raise HMCUpdateError(f"Inconsistent username found in target {i+1}")
        if target['RF_PASSWORD'] != password:
            raise HMCUpdateError(f"Inconsistent password found in target {i+1}")
        if target['PACKAGE'] != package_path:
            raise HMCUpdateError(f"Inconsistent package path found in target {i+1}")
    
    return targets, username, password, package_path


def validate_package_file(package_path: str) -> None:
    """Validate that the package file exists and is accessible."""
    if not os.path.exists(package_path):
        raise HMCUpdateError(f"Package file not found: {package_path}")
    
    if not os.path.isfile(package_path):
        raise HMCUpdateError(f"Path is not a file: {package_path}")
    
    # Check file size (should be > 0)
    file_size = os.path.getsize(package_path)
    if file_size == 0:
        raise HMCUpdateError(f"Package file is empty: {package_path}")
    
    log_print(f"✓ Package file validated: {package_path} ({file_size:,} bytes)")


def get_unique_targets(targets: List[Dict]) -> List[Dict]:
    """Get unique targets based on IP addresses."""
    unique_targets = {}
    for target in targets:
        ip = target['BMC_IP']
        if ip not in unique_targets:
            unique_targets[ip] = target
    
    return list(unique_targets.values())


def execute_nvfwupd_command(ip: str, username: str, password: str, system_name: str, 
                           json_file: str, package_path: str) -> bool:
    """
    Execute nvfwupd command for a single target.
    Returns True if successful, False otherwise.
    """
    cmd = [
        'nvfwupd',
        '-t',
        f'ip={ip}',
        f'user={username}',
        f'password={password}',
        'servertype=GB300',
        'update_fw',
        '-s',
        json_file,
        '-p',
        package_path
    ]
    
    log_print(f"\n  Executing nvfwupd for {system_name} ({ip})...")
    log_print(f"  Command: {' '.join(cmd)}")
    
    try:
        # Execute the command and capture output
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1800  # 30 minute timeout
        )
        
        # Log the command output
        if result.stdout:
            log_print("  STDOUT:")
            for line in result.stdout.splitlines():
                log_print(f"    {line}")
        
        if result.stderr:
            log_print("  STDERR:")
            for line in result.stderr.splitlines():
                log_print(f"    {line}")
        
        # Check return code
        if result.returncode == 0:
            log_print(f"  ✓ SUCCESS - nvfwupd completed for {system_name}")
            return True
        else:
            log_print(f"  ✗ FAILED - nvfwupd failed for {system_name} (exit code: {result.returncode})")
            return False
    
    except subprocess.TimeoutExpired:
        log_print(f"  ✗ FAILED - nvfwupd timed out for {system_name}")
        return False
    except FileNotFoundError:
        log_print(f"  ✗ FAILED - nvfwupd command not found. Please ensure nvfwupd is installed and in PATH.")
        return False
    except Exception as e:
        log_print(f"  ✗ FAILED - Unexpected error for {system_name}: {e}")
        return False


def display_summary(targets: List[Dict], package_path: str, json_file: str) -> None:
    """Display update summary before execution."""
    log_print(f"\n" + "=" * 60)
    log_print("GB300 COMPUTE HMC UPDATE SUMMARY")
    log_print("=" * 60)
    log_print(f"YAML file: compute_hmc.yaml")
    log_print(f"JSON file: {json_file}")
    log_print(f"Package file: {os.path.basename(package_path)}")
    log_print(f"Unique systems to update: {len(targets)}")
    
    log_print(f"\nSystems that will be updated:")
    for target in targets:
        log_print(f"  - {target['SYSTEM_NAME']} ({target['BMC_IP']})")
    
    log_print(f"\n⚠ WARNING: This will update HMC firmware on {len(targets)} systems!")
    log_print("⚠ This operation may take several minutes per system.")
    log_print("⚠ Do not interrupt the process once started.")


def get_user_confirmation(targets: List[Dict]) -> bool:
    """Get user confirmation before proceeding."""
    while True:
        choice = input(f"\nDo you want to proceed with updating HMC firmware on {len(targets)} systems? (yes/no): ").strip().lower()
        # Log the user's choice
        logging.info(f"User confirmation prompt: proceed with updating HMC firmware on {len(targets)} systems?")
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
    
    log_print("GB300 Compute HMC Sequential Update Tool")
    log_print("=" * 45)
    
    try:
        # Create Compute_Full.json file
        log_print("Creating Compute_Full.json...")
        json_file = create_compute_full_json()
        
        # Load and parse compute_hmc.yaml file
        log_print("Loading compute_hmc.yaml...")
        targets, username, password, package_path = load_compute_hmc_yaml()
        
        # Get unique targets (eliminate duplicates)
        unique_targets = get_unique_targets(targets)
        
        log_print(f"Found {len(targets)} total targets, {len(unique_targets)} unique systems")
        
        # Validate package file exists
        validate_package_file(package_path)
        
        log_print(f"\n✓ Using credentials - Username: {username}")
        
        # Display summary and get confirmation
        display_summary(unique_targets, package_path, json_file)
        
        if not get_user_confirmation(unique_targets):
            log_print("Operation cancelled by user.")
            return
        
        # Execute HMC updates sequentially
        log_print(f"\n" + "=" * 60)
        log_print("EXECUTING HMC FIRMWARE UPDATES")
        log_print("=" * 60)
        log_print(f"Processing {len(unique_targets)} unique systems sequentially...")
        
        success_count = 0
        total_count = len(unique_targets)
        
        for i, target in enumerate(unique_targets, 1):
            log_print(f"\n[{i}/{total_count}] Processing {target['SYSTEM_NAME']} ({target['BMC_IP']})")
            
            success = execute_nvfwupd_command(
                target['BMC_IP'],
                username,
                password,
                target['SYSTEM_NAME'],
                json_file,
                package_path
            )
            
            if success:
                success_count += 1
            
            # Add a brief delay between updates
            if i < total_count:
                log_print("  Waiting 3 seconds before next update...")
                import time
                time.sleep(3)
        
        # Final summary
        log_print(f"\n" + "=" * 60)
        log_print("HMC UPDATE SUMMARY")
        log_print("=" * 60)
        log_print(f"Total systems: {total_count}")
        log_print(f"Successful updates: {success_count}")
        log_print(f"Failed updates: {total_count - success_count}")
        
        if success_count == total_count:
            log_print("✓ All HMC firmware updates completed successfully!")
        else:
            log_print("⚠ Some HMC firmware updates failed. Check the output above for details.")
            sys.exit(1)
    
    except KeyboardInterrupt:
        log_print("\n\nOperation cancelled by user.")
        sys.exit(1)
    except HMCUpdateError as e:
        log_print(f"\nError: {e}")
        sys.exit(1)
    except Exception as e:
        log_print(f"\nUnexpected Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
