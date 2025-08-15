#!/usr/bin/env python3
"""
GB300 Compute Power Cycle Script
Executes power off followed by power cycle via Redfish API for all IP addresses in compute_*.yaml files.
Includes comprehensive validation of YAML files and IP address consistency.
"""

import os
import sys
import yaml
import requests
import json
import time
from typing import List, Dict, Set, Tuple
import urllib3
from requests.auth import HTTPBasicAuth

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class PowerCycleError(Exception):
    """Custom exception for power cycle operations."""
    pass


def find_yaml_files(pattern: str) -> List[str]:
    """Find YAML files matching the pattern in the current directory only."""
    yaml_files = []
    
    # Check current directory only (avoid duplicates from os.walk)
    for file in os.listdir('.'):
        if file.startswith(pattern) and file.endswith('.yaml'):
            yaml_files.append(file)
    
    return sorted(yaml_files)


def load_yaml_data(file_path: str) -> Dict:
    """Load and parse a YAML file."""
    try:
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
        return data
    except yaml.YAMLError as e:
        raise PowerCycleError(f"Error parsing YAML file {file_path}: {e}")
    except FileNotFoundError:
        raise PowerCycleError(f"YAML file not found: {file_path}")
    except Exception as e:
        raise PowerCycleError(f"Error reading YAML file {file_path}: {e}")


def extract_targets_from_yaml(yaml_data: Dict, file_path: str) -> List[Dict]:
    """Extract target information from YAML data."""
    if 'Targets' not in yaml_data:
        raise PowerCycleError(f"No 'Targets' section found in {file_path}")
    
    targets = yaml_data['Targets']
    if not isinstance(targets, list):
        raise PowerCycleError(f"'Targets' section in {file_path} is not a list")
    
    if not targets:
        raise PowerCycleError(f"'Targets' section in {file_path} is empty")
    
    # Validate each target has required fields
    for i, target in enumerate(targets):
        required_fields = ['BMC_IP', 'RF_USERNAME', 'RF_PASSWORD', 'SYSTEM_NAME']
        for field in required_fields:
            if field not in target:
                raise PowerCycleError(f"Target {i+1} in {file_path} missing required field: {field}")
        
        # Validate IP format (basic check)
        ip = target['BMC_IP']
        if not isinstance(ip, str) or not ip.strip():
            raise PowerCycleError(f"Invalid BMC_IP in target {i+1} of {file_path}: {ip}")
    
    return targets


def validate_compute_yaml_files() -> Tuple[List[Dict], Set[str]]:
    """
    Validate all compute YAML files and ensure IP address consistency.
    Returns tuple of (all_targets, all_ips).
    """
    print("=" * 60)
    print("VALIDATING COMPUTE YAML FILES")
    print("=" * 60)
    
    # Find compute YAML files
    compute_files = find_yaml_files('compute_')
    if not compute_files:
        raise PowerCycleError("No compute_*.yaml files found in current directory or subdirectories")
    
    print(f"Found {len(compute_files)} compute YAML files:")
    for file in compute_files:
        print(f"  - {file}")
    
    # Load and validate each file
    all_targets = []
    file_ip_sets = {}
    
    for file_path in compute_files:
        print(f"\nValidating {file_path}...")
        yaml_data = load_yaml_data(file_path)
        targets = extract_targets_from_yaml(yaml_data, file_path)
        
        # Extract IPs from this file
        file_ips = {target['BMC_IP'] for target in targets}
        file_ip_sets[file_path] = file_ips
        
        print(f"  Found {len(targets)} targets with {len(file_ips)} unique IPs")
        
        all_targets.extend(targets)
    
    # Validate IP consistency across all compute files
    print(f"\nValidating IP address consistency across compute files...")
    reference_file = compute_files[0]
    reference_ips = file_ip_sets[reference_file]
    
    for file_path, file_ips in file_ip_sets.items():
        if file_path == reference_file:
            continue
        
        if file_ips != reference_ips:
            missing_in_current = reference_ips - file_ips
            extra_in_current = file_ips - reference_ips
            
            error_msg = f"IP address mismatch between {reference_file} and {file_path}:\n"
            if missing_in_current:
                error_msg += f"  Missing in {file_path}: {sorted(missing_in_current)}\n"
            if extra_in_current:
                error_msg += f"  Extra in {file_path}: {sorted(extra_in_current)}\n"
            
            raise PowerCycleError(error_msg.strip())
    
    print(f"✓ All compute YAML files have consistent IP addresses")
    print(f"✓ Total unique IP addresses: {len(reference_ips)}")
    
    return all_targets, reference_ips


def validate_no_switch_conflicts(compute_ips: Set[str]) -> None:
    """Validate that compute IPs don't conflict with switch YAML files."""
    print(f"\nValidating no conflicts with switch YAML files...")
    
    # Find switch YAML files
    switch_files = find_yaml_files('switch_')
    if not switch_files:
        print("  No switch YAML files found - skipping conflict check")
        return
    
    print(f"  Found {len(switch_files)} switch YAML files")
    
    # Extract all switch IPs
    switch_ips = set()
    for file_path in switch_files:
        try:
            yaml_data = load_yaml_data(file_path)
            targets = extract_targets_from_yaml(yaml_data, file_path)
            file_ips = {target['BMC_IP'] for target in targets}
            switch_ips.update(file_ips)
        except Exception as e:
            print(f"  Warning: Could not process {file_path}: {e}")
            continue
    
    # Check for conflicts
    conflicts = compute_ips & switch_ips
    if conflicts:
        raise PowerCycleError(f"IP address conflicts detected between compute and switch YAML files: {sorted(conflicts)}")
    
    print(f"✓ No IP conflicts between compute ({len(compute_ips)}) and switch ({len(switch_ips)}) files")


def get_unique_credentials(targets: List[Dict]) -> Tuple[str, str]:
    """
    Extract and validate that all targets use the same credentials.
    Returns tuple of (username, password).
    """
    usernames = {target['RF_USERNAME'] for target in targets}
    passwords = {target['RF_PASSWORD'] for target in targets}
    
    if len(usernames) > 1:
        raise PowerCycleError(f"Multiple usernames found in YAML files: {usernames}")
    
    if len(passwords) > 1:
        raise PowerCycleError(f"Multiple passwords found in YAML files: {passwords}")
    
    return usernames.pop(), passwords.pop()


def execute_power_command(ip: str, username: str, password: str, system_name: str, 
                         command: str, timeout: int = 30) -> bool:
    """
    Execute power command via Redfish API.
    command should be 'ForceOff' or 'PowerCycle'
    Returns True if successful, False otherwise.
    """
    base_url = f"https://{ip}"
    power_url = f"{base_url}/redfish/v1/Systems/1/Actions/ComputerSystem.Reset"
    
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    power_payload = {
        "ResetType": command
    }
    
    try:
        print(f"  Executing {command} for {system_name} ({ip})...", end=" ", flush=True)
        
        response = requests.post(
            power_url,
            headers=headers,
            data=json.dumps(power_payload),
            auth=HTTPBasicAuth(username, password),
            verify=False,
            timeout=timeout
        )
        
        if response.status_code in [200, 202, 204]:
            print("✓ SUCCESS")
            return True
        else:
            print(f"✗ FAILED (HTTP {response.status_code})")
            try:
                error_data = response.json()
                print(f"    Error: {error_data}")
            except:
                print(f"    Response: {response.text}")
            return False
    
    except requests.exceptions.Timeout:
        print("✗ FAILED (Timeout)")
        return False
    except requests.exceptions.ConnectionError:
        print("✗ FAILED (Connection Error)")
        return False
    except Exception as e:
        print(f"✗ FAILED ({e})")
        return False


def display_countdown_timer(seconds: int):
    """Display a countdown timer with progress indicator."""
    print(f"\nWaiting {seconds} seconds before power cycle...")
    
    for remaining in range(seconds, 0, -1):
        # Calculate progress bar
        progress = (seconds - remaining) / seconds
        bar_length = 40
        filled_length = int(bar_length * progress)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        
        # Display countdown with progress bar
        print(f"\r[{bar}] {remaining:2d}s remaining", end="", flush=True)
        time.sleep(1)
    
    # Final progress bar
    bar = '█' * bar_length
    print(f"\r[{bar}] Ready for power cycle!")
    print()


def get_user_confirmation(targets: List[Dict], compute_ips: Set[str]) -> bool:
    """Get user confirmation before executing power cycle."""
    print("\n" + "=" * 60)
    print("READY TO EXECUTE POWER CYCLE")
    print("=" * 60)
    
    # Create unique targets for display
    unique_targets = {}
    for target in targets:
        ip = target['BMC_IP']
        if ip not in unique_targets:
            unique_targets[ip] = target
    
    unique_target_list = list(unique_targets.values())
    
    print(f"Unique systems to power cycle: {len(unique_target_list)}")
    print(f"Unique IP addresses: {len(compute_ips)}")
    print("\nSystems that will be power cycled:")
    
    for target in unique_target_list:
        print(f"  - {target['SYSTEM_NAME']} ({target['BMC_IP']})")
    
    print(f"\n⚠ WARNING: This will power cycle {len(unique_target_list)} unique systems!")
    print("⚠ This operation will:")
    print("  1. Force power off all systems")
    print("  2. Wait 15 seconds")
    print("  3. Power cycle all systems")
    print("⚠ This may cause data loss if systems are not properly shut down!")
    
    while True:
        choice = input(f"\nDo you want to proceed with power cycling {len(unique_target_list)} systems? (yes/no): ").strip().lower()
        if choice in ['yes', 'y']:
            return True
        elif choice in ['no', 'n']:
            return False
        else:
            print("Please enter 'yes' or 'no'")


def execute_power_sequence(targets: List[Dict], username: str, password: str) -> Tuple[int, int]:
    """
    Execute the complete power cycle sequence.
    Returns tuple of (successful_power_offs, successful_power_cycles).
    """
    unique_targets = {}
    for target in targets:
        ip = target['BMC_IP']
        if ip not in unique_targets:
            unique_targets[ip] = target
    
    unique_target_list = list(unique_targets.values())
    
    # Phase 1: Power Off
    print(f"\n" + "=" * 60)
    print("PHASE 1: POWERING OFF SYSTEMS")
    print("=" * 60)
    
    power_off_success = 0
    for i, target in enumerate(unique_target_list, 1):
        print(f"[{i}/{len(unique_target_list)}]", end=" ")
        
        success = execute_power_command(
            target['BMC_IP'],
            username,
            password,
            target['SYSTEM_NAME'],
            'ForceOff'
        )
        
        if success:
            power_off_success += 1
        
        # Small delay between requests
        if i < len(unique_target_list):
            time.sleep(1)
    
    print(f"\nPower off completed: {power_off_success}/{len(unique_target_list)} successful")
    
    # Phase 2: Wait 15 seconds
    print(f"\n" + "=" * 60)
    print("PHASE 2: WAITING BEFORE POWER CYCLE")
    print("=" * 60)
    
    display_countdown_timer(15)
    
    # Phase 3: Power Cycle
    print(f"\n" + "=" * 60)
    print("PHASE 3: POWER CYCLING SYSTEMS")
    print("=" * 60)
    
    power_cycle_success = 0
    for i, target in enumerate(unique_target_list, 1):
        print(f"[{i}/{len(unique_target_list)}]", end=" ")
        
        success = execute_power_command(
            target['BMC_IP'],
            username,
            password,
            target['SYSTEM_NAME'],
            'PowerCycle'
        )
        
        if success:
            power_cycle_success += 1
        
        # Small delay between requests
        if i < len(unique_target_list):
            time.sleep(1)
    
    return power_off_success, power_cycle_success


def main():
    """Main program flow."""
    print("GB300 Compute Power Cycle Tool")
    print("=" * 40)
    
    try:
        # Validate YAML files and extract data
        all_targets, compute_ips = validate_compute_yaml_files()
        
        # Validate no conflicts with switch files
        validate_no_switch_conflicts(compute_ips)
        
        # Get credentials (assuming all systems use same credentials)
        username, password = get_unique_credentials(all_targets)
        print(f"\n✓ Using credentials - Username: {username}")
        
        # Get user confirmation
        if not get_user_confirmation(all_targets, compute_ips):
            print("Operation cancelled by user.")
            return
        
        # Execute power cycle sequence
        power_off_success, power_cycle_success = execute_power_sequence(all_targets, username, password)
        
        # Summary
        unique_count = len(set(target['BMC_IP'] for target in all_targets))
        print(f"\n" + "=" * 60)
        print("POWER CYCLE SUMMARY")
        print("=" * 60)
        print(f"Total unique systems: {unique_count}")
        print(f"Successful power offs: {power_off_success}")
        print(f"Successful power cycles: {power_cycle_success}")
        
        if power_off_success == unique_count and power_cycle_success == unique_count:
            print("✓ All power cycle operations completed successfully!")
        else:
            print("⚠ Some power cycle operations failed. Check the output above for details.")
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(1)
    except PowerCycleError as e:
        print(f"\nValidation Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
