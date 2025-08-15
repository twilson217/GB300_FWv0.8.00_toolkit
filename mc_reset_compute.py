#!/usr/bin/env python3
"""
GB300 Compute BMC Reset Script
Executes BMC resets via Redfish API for all IP addresses in compute_*.yaml files.
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


class BMCResetError(Exception):
    """Custom exception for BMC reset operations."""
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
        raise BMCResetError(f"Error parsing YAML file {file_path}: {e}")
    except FileNotFoundError:
        raise BMCResetError(f"YAML file not found: {file_path}")
    except Exception as e:
        raise BMCResetError(f"Error reading YAML file {file_path}: {e}")


def extract_targets_from_yaml(yaml_data: Dict, file_path: str) -> List[Dict]:
    """Extract target information from YAML data."""
    if 'Targets' not in yaml_data:
        raise BMCResetError(f"No 'Targets' section found in {file_path}")
    
    targets = yaml_data['Targets']
    if not isinstance(targets, list):
        raise BMCResetError(f"'Targets' section in {file_path} is not a list")
    
    if not targets:
        raise BMCResetError(f"'Targets' section in {file_path} is empty")
    
    # Validate each target has required fields
    for i, target in enumerate(targets):
        required_fields = ['BMC_IP', 'RF_USERNAME', 'RF_PASSWORD', 'SYSTEM_NAME']
        for field in required_fields:
            if field not in target:
                raise BMCResetError(f"Target {i+1} in {file_path} missing required field: {field}")
        
        # Validate IP format (basic check)
        ip = target['BMC_IP']
        if not isinstance(ip, str) or not ip.strip():
            raise BMCResetError(f"Invalid BMC_IP in target {i+1} of {file_path}: {ip}")
    
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
        raise BMCResetError("No compute_*.yaml files found in current directory or subdirectories")
    
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
            
            raise BMCResetError(error_msg.strip())
    
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
        raise BMCResetError(f"IP address conflicts detected between compute and switch YAML files: {sorted(conflicts)}")
    
    print(f"✓ No IP conflicts between compute ({len(compute_ips)}) and switch ({len(switch_ips)}) files")


def get_unique_credentials(targets: List[Dict]) -> Tuple[str, str]:
    """
    Extract and validate that all targets use the same credentials.
    Returns tuple of (username, password).
    """
    usernames = {target['RF_USERNAME'] for target in targets}
    passwords = {target['RF_PASSWORD'] for target in targets}
    
    if len(usernames) > 1:
        raise BMCResetError(f"Multiple usernames found in YAML files: {usernames}")
    
    if len(passwords) > 1:
        raise BMCResetError(f"Multiple passwords found in YAML files: {passwords}")
    
    return usernames.pop(), passwords.pop()


def execute_bmc_reset(ip: str, username: str, password: str, system_name: str, timeout: int = 30) -> bool:
    """
    Execute BMC reset via Redfish API.
    Returns True if successful, False otherwise.
    """
    base_url = f"https://{ip}"
    reset_url = f"{base_url}/redfish/v1/Managers/1/Actions/Manager.Reset"
    
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    reset_payload = {
        "ResetType": "ForceRestart"
    }
    
    try:
        print(f"  Executing BMC reset for {system_name} ({ip})...", end=" ", flush=True)
        
        response = requests.post(
            reset_url,
            headers=headers,
            data=json.dumps(reset_payload),
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


def get_user_confirmation(targets: List[Dict], compute_ips: Set[str]) -> bool:
    """Get user confirmation before executing BMC resets."""
    print("\n" + "=" * 60)
    print("READY TO EXECUTE BMC RESETS")
    print("=" * 60)
    
    # Create unique targets for display
    unique_targets = {}
    for target in targets:
        ip = target['BMC_IP']
        if ip not in unique_targets:
            unique_targets[ip] = target
    
    unique_target_list = list(unique_targets.values())
    
    print(f"Unique systems to reset: {len(unique_target_list)}")
    print(f"Unique IP addresses: {len(compute_ips)}")
    print("\nSystems that will be reset:")
    
    for target in unique_target_list:
        print(f"  - {target['SYSTEM_NAME']} ({target['BMC_IP']})")
    
    print(f"\n⚠ WARNING: This will reset the BMC on {len(unique_target_list)} unique systems!")
    print("⚠ This may cause temporary loss of management connectivity.")
    
    while True:
        choice = input(f"\nDo you want to proceed with resetting {len(unique_target_list)} BMCs? (yes/no): ").strip().lower()
        if choice in ['yes', 'y']:
            return True
        elif choice in ['no', 'n']:
            return False
        else:
            print("Please enter 'yes' or 'no'")


def main():
    """Main program flow."""
    print("GB300 Compute BMC Reset Tool")
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
        
        # Execute BMC resets (using unique IPs only)
        print(f"\n" + "=" * 60)
        print("EXECUTING BMC RESETS")
        print("=" * 60)
        
        # Create unique targets based on unique IPs
        unique_targets = {}
        for target in all_targets:
            ip = target['BMC_IP']
            if ip not in unique_targets:
                unique_targets[ip] = target
        
        unique_target_list = list(unique_targets.values())
        success_count = 0
        total_count = len(unique_target_list)
        
        print(f"Executing BMC resets for {total_count} unique IP addresses...")
        
        for i, target in enumerate(unique_target_list, 1):
            print(f"[{i}/{total_count}]", end=" ")
            
            success = execute_bmc_reset(
                target['BMC_IP'],
                username,
                password,
                target['SYSTEM_NAME']
            )
            
            if success:
                success_count += 1
            
            # Small delay between requests to avoid overwhelming BMCs
            if i < total_count:
                time.sleep(1)
        
        # Summary
        print(f"\n" + "=" * 60)
        print("BMC RESET SUMMARY")
        print("=" * 60)
        print(f"Total systems: {total_count}")
        print(f"Successful resets: {success_count}")
        print(f"Failed resets: {total_count - success_count}")
        
        if success_count == total_count:
            print("✓ All BMC resets completed successfully!")
        else:
            print("⚠ Some BMC resets failed. Check the output above for details.")
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(1)
    except BMCResetError as e:
        print(f"\nValidation Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
