#!/usr/bin/env python3
"""
GB300 Compute Redfish Task Status Script
Queries Redfish TaskService to check task progress for compute systems.
Reads from compute_bmc.yaml and displays PercentComplete for each system.
"""

import os
import sys
import yaml
import requests
import json
import logging
from datetime import datetime
from typing import List, Dict, Tuple, Optional
import urllib3
from requests.auth import HTTPBasicAuth

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class RedfishStatusError(Exception):
    """Custom exception for Redfish status operations."""
    pass


def setup_logging():
    """Set up logging to file with timestamps."""
    # Create logs directory if it doesn't exist
    log_dir = './logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        print(f"Created logs directory: {log_dir}")
    
    # Set up logging configuration
    log_file = os.path.join(log_dir, 'redfish_tasks.log')
    
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
    
    return logger


def log_session_start():
    """Log the start of a new session."""
    session_start = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    separator = "=" * 80
    
    logging.info(f"\n{separator}")
    logging.info(f"NEW SESSION STARTED: {session_start}")
    logging.info(f"Script: compute_redfish_status.py")
    logging.info(f"Working Directory: {os.getcwd()}")
    logging.info(f"{separator}")


def load_compute_bmc_yaml() -> Tuple[List[Dict], str, str]:
    """
    Load and parse compute_bmc.yaml file.
    Returns tuple of (targets, username, password).
    """
    yaml_file = 'compute_bmc.yaml'
    
    if not os.path.exists(yaml_file):
        raise RedfishStatusError(f"File not found: {yaml_file}")
    
    try:
        with open(yaml_file, 'r') as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise RedfishStatusError(f"Error parsing {yaml_file}: {e}")
    except Exception as e:
        raise RedfishStatusError(f"Error reading {yaml_file}: {e}")
    
    if 'Targets' not in data:
        raise RedfishStatusError(f"No 'Targets' section found in {yaml_file}")
    
    targets = data['Targets']
    if not isinstance(targets, list):
        raise RedfishStatusError(f"'Targets' section in {yaml_file} is not a list")
    
    if not targets:
        raise RedfishStatusError(f"'Targets' section in {yaml_file} is empty")
    
    # Validate each target has required fields
    for i, target in enumerate(targets):
        required_fields = ['BMC_IP', 'RF_USERNAME', 'RF_PASSWORD', 'SYSTEM_NAME']
        for field in required_fields:
            if field not in target:
                raise RedfishStatusError(f"Target {i+1} in {yaml_file} missing required field: {field}")
    
    # Extract username and password (assuming all targets use same credentials)
    username = targets[0]['RF_USERNAME']
    password = targets[0]['RF_PASSWORD']
    
    # Validate credentials are consistent
    for i, target in enumerate(targets):
        if target['RF_USERNAME'] != username or target['RF_PASSWORD'] != password:
            raise RedfishStatusError(f"Inconsistent credentials found in target {i+1}")
    
    return targets, username, password


def get_task_collection(ip: str, username: str, password: str) -> Optional[Dict]:
    """
    Get the task collection from Redfish TaskService.
    Returns the JSON response or None if failed.
    """
    url = f"https://{ip}/redfish/v1/TaskService/Tasks/"
    
    try:
        response = requests.get(
            url,
            auth=HTTPBasicAuth(username, password),
            verify=False,
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            logging.error(f"Failed to get task collection from {ip}: HTTP {response.status_code}")
            return None
    
    except requests.exceptions.Timeout:
        logging.error(f"Timeout getting task collection from {ip}")
        return None
    except requests.exceptions.ConnectionError:
        logging.error(f"Connection error getting task collection from {ip}")
        return None
    except Exception as e:
        logging.error(f"Error getting task collection from {ip}: {e}")
        return None


def get_latest_task_id(task_collection: Dict) -> Optional[str]:
    """
    Extract the latest (highest numbered) task ID from the task collection.
    Returns the task ID string or None if no tasks found.
    """
    try:
        members = task_collection.get('Members', [])
        if not members:
            return None
        
        # Extract task IDs from the @odata.id paths
        task_ids = []
        for member in members:
            odata_id = member.get('@odata.id', '')
            # Extract the task ID from paths like "/redfish/v1/TaskService/Tasks/13"
            if '/Tasks/' in odata_id:
                task_id = odata_id.split('/Tasks/')[-1]
                if task_id.isdigit():
                    task_ids.append(int(task_id))
        
        if task_ids:
            # Return the highest task ID as string
            return str(max(task_ids))
        
        return None
    
    except Exception as e:
        logging.error(f"Error extracting task ID: {e}")
        return None


def get_task_details(ip: str, username: str, password: str, task_id: str) -> Optional[Dict]:
    """
    Get detailed information for a specific task.
    Returns the JSON response or None if failed.
    """
    url = f"https://{ip}/redfish/v1/TaskService/Tasks/{task_id}"
    
    try:
        response = requests.get(
            url,
            auth=HTTPBasicAuth(username, password),
            verify=False,
            timeout=30
        )
        
        # Log the full response
        logging.info(f"Task details response from {ip} (Task {task_id}):")
        logging.info(f"Status Code: {response.status_code}")
        logging.info(f"Response Headers: {dict(response.headers)}")
        if response.text:
            try:
                response_json = response.json()
                logging.info(f"Response Body: {json.dumps(response_json, indent=2)}")
            except:
                logging.info(f"Response Body (raw): {response.text}")
        else:
            logging.info("Response Body: (empty)")
        
        if response.status_code == 200:
            return response.json()
        else:
            logging.error(f"Failed to get task details from {ip}: HTTP {response.status_code}")
            return None
    
    except requests.exceptions.Timeout:
        logging.error(f"Timeout getting task details from {ip}")
        return None
    except requests.exceptions.ConnectionError:
        logging.error(f"Connection error getting task details from {ip}")
        return None
    except Exception as e:
        logging.error(f"Error getting task details from {ip}: {e}")
        return None


def get_percent_complete(task_details: Dict) -> Optional[int]:
    """
    Extract PercentComplete from task details.
    Returns the percentage as integer or None if not found.
    """
    try:
        percent = task_details.get('PercentComplete')
        if percent is not None:
            return int(percent)
        return None
    except:
        return None


def get_unique_targets(targets: List[Dict]) -> List[Dict]:
    """Get unique targets based on IP addresses."""
    unique_targets = {}
    for target in targets:
        ip = target['BMC_IP']
        if ip not in unique_targets:
            unique_targets[ip] = target
    
    return list(unique_targets.values())


def main():
    """Main program flow."""
    # Set up logging first
    logger = setup_logging()
    log_session_start()
    
    print("GB300 Compute Redfish Task Status Checker")
    print("=" * 45)
    
    try:
        # Load and parse compute_bmc.yaml file
        print("Loading compute_bmc.yaml...")
        targets, username, password = load_compute_bmc_yaml()
        
        # Get unique targets (eliminate duplicates)
        unique_targets = get_unique_targets(targets)
        
        print(f"Found {len(targets)} total targets, {len(unique_targets)} unique systems")
        print(f"Using credentials - Username: {username}")
        
        print(f"\nChecking task status for {len(unique_targets)} systems...")
        print("=" * 50)
        
        # Check status for each system
        for target in unique_targets:
            ip = target['BMC_IP']
            system_name = target['SYSTEM_NAME']
            
            print(f"{ip} ({system_name}):", end=" ", flush=True)
            
            # Get task collection
            task_collection = get_task_collection(ip, username, password)
            if not task_collection:
                print("ERROR - Could not get task collection")
                continue
            
            # Get latest task ID
            task_id = get_latest_task_id(task_collection)
            if not task_id:
                print("NO TASKS FOUND")
                continue
            
            # Get task details
            task_details = get_task_details(ip, username, password, task_id)
            if not task_details:
                print(f"ERROR - Could not get details for task {task_id}")
                continue
            
            # Extract percent complete
            percent_complete = get_percent_complete(task_details)
            if percent_complete is not None:
                print(f"PercentComplete: {percent_complete}%")
            else:
                print("PercentComplete: Not Available")
        
        print("\n" + "=" * 50)
        print("Task status check completed.")
        print("Detailed logs saved to ./logs/redfish_tasks.log")
    
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(1)
    except RedfishStatusError as e:
        print(f"\nError: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
