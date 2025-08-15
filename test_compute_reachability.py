#!/usr/bin/env python3
"""
GB300 Compute Reachability Test
Tests ping and TCP port 443 connectivity to IP addresses from generated YAML files.
"""

import os
import sys
import subprocess
import socket
import platform
import yaml
from typing import List, Dict, Tuple
import time


def load_yaml_files() -> List[str]:
    """Load IP addresses from all compute YAML files."""
    yaml_files = ['compute_bmc.yaml', 'compute_hmc.yaml', 'compute_mcu.yaml']
    ip_addresses = set()
    
    for yaml_file in yaml_files:
        if not os.path.exists(yaml_file):
            print(f"Warning: {yaml_file} not found, skipping...")
            continue
        
        try:
            with open(yaml_file, 'r') as f:
                data = yaml.safe_load(f)
            
            if 'Targets' in data:
                for target in data['Targets']:
                    if 'BMC_IP' in target:
                        ip_addresses.add(target['BMC_IP'])
        
        except yaml.YAMLError as e:
            print(f"Error parsing {yaml_file}: {e}")
            continue
        except Exception as e:
            print(f"Error reading {yaml_file}: {e}")
            continue
    
    if not ip_addresses:
        print("No IP addresses found in YAML files.")
        print("Make sure the compute_*.yaml files exist and contain valid data.")
        sys.exit(1)
    
    return sorted(list(ip_addresses))


def ping_host(ip_address: str, timeout: int = 3) -> bool:
    """
    Ping a host and return True if reachable, False otherwise.
    Works on Windows, Linux, and macOS.
    """
    system = platform.system().lower()
    
    try:
        if system == "windows":
            # Windows ping command
            cmd = ["ping", "-n", "1", "-w", str(timeout * 1000), ip_address]
        else:
            # Linux/macOS ping command
            cmd = ["ping", "-c", "1", "-W", str(timeout), ip_address]
        
        # Run ping command
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout + 2
        )
        
        return result.returncode == 0
    
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False


def test_tcp_port(ip_address: str, port: int = 443, timeout: int = 5) -> bool:
    """
    Test TCP connectivity to a specific port.
    Returns True if connection successful, False otherwise.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip_address, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def run_ping_tests(ip_addresses: List[str]) -> Dict[str, bool]:
    """Run ping tests for all IP addresses."""
    print(f"\nTesting ping connectivity to {len(ip_addresses)} IP addresses...")
    print("=" * 50)
    
    results = {}
    
    for i, ip in enumerate(ip_addresses, 1):
        print(f"[{i}/{len(ip_addresses)}] Pinging {ip}...", end=" ", flush=True)
        
        is_reachable = ping_host(ip)
        results[ip] = is_reachable
        
        if is_reachable:
            print("✓ SUCCESS")
        else:
            print("✗ FAILED")
    
    return results


def run_tcp_tests(ip_addresses: List[str], port: int = 443) -> Dict[str, bool]:
    """Run TCP port connectivity tests for all IP addresses."""
    print(f"\nTesting TCP port {port} connectivity to {len(ip_addresses)} IP addresses...")
    print("=" * 50)
    
    results = {}
    
    for i, ip in enumerate(ip_addresses, 1):
        print(f"[{i}/{len(ip_addresses)}] Testing {ip}:{port}...", end=" ", flush=True)
        
        is_reachable = test_tcp_port(ip, port)
        results[ip] = is_reachable
        
        if is_reachable:
            print("✓ SUCCESS")
        else:
            print("✗ FAILED")
    
    return results


def display_summary(ping_results: Dict[str, bool], tcp_results: Dict[str, bool] = None):
    """Display test results summary."""
    print("\n" + "=" * 60)
    print("CONNECTIVITY TEST SUMMARY")
    print("=" * 60)
    
    # Ping results summary
    ping_success = sum(1 for result in ping_results.values() if result)
    ping_total = len(ping_results)
    print(f"Ping Test Results: {ping_success}/{ping_total} successful")
    
    if ping_success < ping_total:
        print("Failed ping tests:")
        for ip, result in ping_results.items():
            if not result:
                print(f"  ✗ {ip}")
    
    # TCP results summary (if tested)
    if tcp_results:
        print()
        tcp_success = sum(1 for result in tcp_results.values() if result)
        tcp_total = len(tcp_results)
        print(f"TCP Port 443 Test Results: {tcp_success}/{tcp_total} successful")
        
        if tcp_success < tcp_total:
            print("Failed TCP port 443 tests:")
            for ip, result in tcp_results.items():
                if not result:
                    print(f"  ✗ {ip}:443")
    
    print("=" * 60)


def get_user_choice(prompt: str) -> bool:
    """Get yes/no choice from user."""
    while True:
        choice = input(f"{prompt} (y/n): ").strip().lower()
        if choice in ['y', 'yes']:
            return True
        elif choice in ['n', 'no']:
            return False
        else:
            print("Please enter 'y' for yes or 'n' for no.")


def main():
    """Main program flow."""
    print("GB300 Compute Reachability Test")
    print("=" * 40)
    
    try:
        # Load IP addresses from YAML files
        print("Loading IP addresses from YAML files...")
        ip_addresses = load_yaml_files()
        
        print(f"Found {len(ip_addresses)} unique IP addresses:")
        for ip in ip_addresses:
            print(f"  - {ip}")
        
        # Run ping tests
        ping_results = run_ping_tests(ip_addresses)
        
        # Display ping results
        ping_success = sum(1 for result in ping_results.values() if result)
        print(f"\nPing test completed: {ping_success}/{len(ip_addresses)} hosts reachable")
        
        # Ask user if they want to test TCP port 443
        if not get_user_choice("\nWould you like to test TCP port 443 reachability?"):
            display_summary(ping_results)
            print("Exiting...")
            return
        
        # Run TCP tests
        tcp_results = run_tcp_tests(ip_addresses)
        
        # Display final summary
        display_summary(ping_results, tcp_results)
        
        # Final status
        tcp_success = sum(1 for result in tcp_results.values() if result)
        if ping_success == len(ip_addresses) and tcp_success == len(ip_addresses):
            print("✓ All connectivity tests passed!")
        else:
            print("⚠ Some connectivity tests failed. Check the summary above.")
    
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
