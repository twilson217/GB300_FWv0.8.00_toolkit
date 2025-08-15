#!/usr/bin/env python3
"""
GB300 Switch YAML Generator
Generates switch_bmc.yaml, switch_bios.yaml, and switch_cpld.yaml files
for use with Firmware release v0.8.00 for GB300 systems only.
"""

import os
import re
import ipaddress
import subprocess
import sys
import yaml
from typing import List, Tuple, Union, Set


def display_intro():
    """Display introduction message about script compatibility."""
    print("=" * 70)
    print("GB300 Switch YAML Generator")
    print("This script was designed for use with Firmware release v0.8.00")
    print("for GB300 systems only.")
    print("=" * 70)
    print()


def parse_ip_range(ip_input: str) -> List[str]:
    """
    Parse IP address input (list or range) and return list of IP addresses.
    
    Supports formats:
    - Single IP: 10.102.112.79
    - Comma-separated list: 10.102.112.79,10.102.112.80,10.102.112.81
    - Range format 1: 10.102.112.79-96
    - Range format 2: 10.102.112.79-10.102.112.96
    """
    ip_input = ip_input.strip()
    
    # Check if it's a comma-separated list
    if ',' in ip_input:
        return [ip.strip() for ip in ip_input.split(',') if ip.strip()]
    
    # Check if it's a range
    if '-' in ip_input:
        parts = ip_input.split('-')
        if len(parts) != 2:
            raise ValueError(f"Invalid IP range format: {ip_input}")
        
        start_ip = parts[0].strip()
        end_part = parts[1].strip()
        
        # Validate start IP
        try:
            start_ip_obj = ipaddress.IPv4Address(start_ip)
        except ipaddress.AddressValueError:
            raise ValueError(f"Invalid start IP address: {start_ip}")
        
        # Handle different end formats
        if '.' in end_part:
            # Full IP format (e.g., 10.102.112.79-10.102.112.96)
            try:
                end_ip_obj = ipaddress.IPv4Address(end_part)
            except ipaddress.AddressValueError:
                raise ValueError(f"Invalid end IP address: {end_part}")
        else:
            # Short format (e.g., 10.102.112.79-96)
            try:
                end_octet = int(end_part)
                if not (0 <= end_octet <= 255):
                    raise ValueError(f"Invalid IP octet: {end_octet}")
                
                start_parts = start_ip.split('.')
                end_ip = f"{start_parts[0]}.{start_parts[1]}.{start_parts[2]}.{end_octet}"
                end_ip_obj = ipaddress.IPv4Address(end_ip)
            except (ValueError, ipaddress.AddressValueError):
                raise ValueError(f"Invalid IP range end: {end_part}")
        
        # Generate IP list
        start_int = int(start_ip_obj)
        end_int = int(end_ip_obj)
        
        if start_int > end_int:
            raise ValueError(f"Start IP {start_ip} is greater than end IP {end_ip_obj}")
        
        return [str(ipaddress.IPv4Address(ip)) for ip in range(start_int, end_int + 1)]
    
    # Single IP
    try:
        ipaddress.IPv4Address(ip_input)
        return [ip_input]
    except ipaddress.AddressValueError:
        raise ValueError(f"Invalid IP address: {ip_input}")


def parse_system_name_range(name_input: str) -> List[str]:
    """
    Parse system name input (list or range) and return list of system names.
    
    Supports formats:
    - Single name: SW-01
    - Comma-separated list: SW-01,SW-02,SW-03
    - Range format 1: SW-[01-18]
    - Range format 2: SW-01..SW-18
    """
    name_input = name_input.strip()
    
    # Check if it's a comma-separated list
    if ',' in name_input:
        return [name.strip() for name in name_input.split(',') if name.strip()]
    
    # Check for bracket range format (e.g., SW-[01-18])
    bracket_match = re.match(r'^(.+)\[(\d+)-(\d+)\](.*)$', name_input)
    if bracket_match:
        prefix = bracket_match.group(1)
        start_num = int(bracket_match.group(2))
        end_num = int(bracket_match.group(3))
        suffix = bracket_match.group(4)
        
        if start_num > end_num:
            raise ValueError(f"Start number {start_num} is greater than end number {end_num}")
        
        # Determine zero-padding based on input format
        start_str = bracket_match.group(2)
        padding = len(start_str) if start_str.startswith('0') else 0
        
        names = []
        for i in range(start_num, end_num + 1):
            if padding > 0:
                num_str = str(i).zfill(padding)
            else:
                num_str = str(i)
            names.append(f"{prefix}{num_str}{suffix}")
        
        return names
    
    # Check for double-dot range format (e.g., SW-01..SW-18)
    if '..' in name_input:
        parts = name_input.split('..')
        if len(parts) != 2:
            raise ValueError(f"Invalid system name range format: {name_input}")
        
        start_name = parts[0].strip()
        end_name = parts[1].strip()
        
        # Extract prefix and numbers
        start_match = re.match(r'^(.+?)(\d+)(.*)$', start_name)
        end_match = re.match(r'^(.+?)(\d+)(.*)$', end_name)
        
        if not start_match or not end_match:
            raise ValueError(f"Cannot parse numeric range from: {name_input}")
        
        start_prefix = start_match.group(1)
        start_num = int(start_match.group(2))
        start_suffix = start_match.group(3)
        
        end_prefix = end_match.group(1)
        end_num = int(end_match.group(2))
        end_suffix = end_match.group(3)
        
        if start_prefix != end_prefix or start_suffix != end_suffix:
            raise ValueError(f"Prefix or suffix mismatch in range: {name_input}")
        
        if start_num > end_num:
            raise ValueError(f"Start number {start_num} is greater than end number {end_num}")
        
        # Determine zero-padding
        start_num_str = start_match.group(2)
        padding = len(start_num_str) if start_num_str.startswith('0') else 0
        
        names = []
        for i in range(start_num, end_num + 1):
            if padding > 0:
                num_str = str(i).zfill(padding)
            else:
                num_str = str(i)
            names.append(f"{start_prefix}{num_str}{start_suffix}")
        
        return names
    
    # Single name
    return [name_input]


def get_ip_addresses() -> List[str]:
    """Get IP addresses from user input with optional exclusions."""
    while True:
        try:
            ip_input = input("Enter IP address list (comma separated) or range (e.g., 10.102.112.70-72): ").strip()
            if not ip_input:
                print("IP address input cannot be empty. Please try again.")
                continue
            
            ip_list = parse_ip_range(ip_input)
            print(f"Parsed {len(ip_list)} IP addresses: {ip_list[0]} to {ip_list[-1]}")
            
            # Check if it was a range and ask for exclusions
            if '-' in ip_input:
                exclude_input = input("Enter IP addresses to exclude (comma separated, range, or press Enter for none): ").strip()
                if exclude_input:
                    exclude_list = parse_ip_range(exclude_input)
                    ip_list = [ip for ip in ip_list if ip not in exclude_list]
                    print(f"After exclusions: {len(ip_list)} IP addresses")
            
            if not ip_list:
                print("No IP addresses remaining after exclusions. Please try again.")
                continue
            
            return ip_list
            
        except ValueError as e:
            print(f"Error: {e}")
            print("Please try again.")


def get_system_names() -> List[str]:
    """Get system names from user input with optional exclusions."""
    while True:
        try:
            name_input = input("Enter system name list (comma separated) or range (e.g., SW-[01-18] or SW-01..SW-18): ").strip()
            if not name_input:
                print("System name input cannot be empty. Please try again.")
                continue
            
            name_list = parse_system_name_range(name_input)
            print(f"Parsed {len(name_list)} system names: {name_list[0]} to {name_list[-1]}")
            
            # Check if it was a range and ask for exclusions
            if '[' in name_input or '..' in name_input:
                exclude_input = input("Enter system names to exclude (comma separated, range, or press Enter for none): ").strip()
                if exclude_input:
                    exclude_list = parse_system_name_range(exclude_input)
                    name_list = [name for name in name_list if name not in exclude_list]
                    print(f"After exclusions: {len(name_list)} system names")
            
            if not name_list:
                print("No system names remaining after exclusions. Please try again.")
                continue
            
            return name_list
            
        except ValueError as e:
            print(f"Error: {e}")
            print("Please try again.")


def get_credentials() -> Tuple[str, str]:
    """Get username and password from user."""
    username = input("Enter username: ").strip()
    while not username:
        print("Username cannot be empty.")
        username = input("Enter username: ").strip()
    
    password = input("Enter password: ").strip()
    while not password:
        print("Password cannot be empty.")
        password = input("Enter password: ").strip()
    
    return username, password


def get_firmware_path() -> str:
    """Get and validate firmware file path."""
    while True:
        path = input("Enter absolute path to firmware files directory: ").strip()
        if not path:
            print("Path cannot be empty. Please try again.")
            continue
        
        if not os.path.isabs(path):
            print("Please provide an absolute path.")
            continue
        
        if not os.path.exists(path):
            print(f"Path does not exist: {path}")
            print("Please re-enter the path.")
            continue
        
        if not os.path.isdir(path):
            print(f"Path is not a directory: {path}")
            print("Please re-enter the path.")
            continue
        
        return path


def find_firmware_files(firmware_dir: str) -> Tuple[str, str, str]:
    """Find the specific firmware files in the directory."""
    files = os.listdir(firmware_dir)
    
    bmc_file = None
    bios_file = None
    cpld_file = None
    
    for file in files:
        if file.endswith('.fwpkg'):
            file_lower = file.lower()
            if 'p4093' in file_lower and any(x in file_lower for x in ['0004', '4']):
                bmc_file = file
            elif 'p4978' in file_lower and any(x in file_lower for x in ['0006', '6']):
                bios_file = file
            elif 'p4093' in file_lower and any(x in file_lower for x in ['0007', '7']):
                cpld_file = file
    
    # If we couldn't auto-detect, let user choose
    fwpkg_files = [f for f in files if f.endswith('.fwpkg')]
    
    if not fwpkg_files:
        raise FileNotFoundError("No .fwpkg files found in the specified directory")
    
    if not bmc_file:
        print(f"\nFound {len(fwpkg_files)} .fwpkg files:")
        for i, file in enumerate(fwpkg_files, 1):
            print(f"{i}. {file}")
        
        while True:
            try:
                choice = int(input("Select BMC firmware file number: ")) - 1
                if 0 <= choice < len(fwpkg_files):
                    bmc_file = fwpkg_files[choice]
                    break
                else:
                    print("Invalid selection. Please try again.")
            except ValueError:
                print("Please enter a valid number.")
    
    if not bios_file:
        remaining_files = [f for f in fwpkg_files if f != bmc_file]
        if remaining_files:
            print(f"\nRemaining {len(remaining_files)} .fwpkg files:")
            for i, file in enumerate(remaining_files, 1):
                print(f"{i}. {file}")
            
            while True:
                try:
                    choice = int(input("Select BIOS firmware file number: ")) - 1
                    if 0 <= choice < len(remaining_files):
                        bios_file = remaining_files[choice]
                        break
                    else:
                        print("Invalid selection. Please try again.")
                except ValueError:
                    print("Please enter a valid number.")
    
    if not cpld_file:
        remaining_files = [f for f in fwpkg_files if f not in [bmc_file, bios_file]]
        if remaining_files:
            print(f"\nRemaining {len(remaining_files)} .fwpkg files:")
            for i, file in enumerate(remaining_files, 1):
                print(f"{i}. {file}")
            
            while True:
                try:
                    choice = int(input("Select CPLD firmware file number: ")) - 1
                    if 0 <= choice < len(remaining_files):
                        cpld_file = remaining_files[choice]
                        break
                    else:
                        print("Invalid selection. Please try again.")
                except ValueError:
                    print("Please enter a valid number.")
    
    return bmc_file, bios_file, cpld_file


def generate_yaml_content(ip_list: List[str], name_list: List[str], username: str, 
                         password: str, package_path: str, update_params: dict) -> str:
    """Generate YAML content for a specific firmware type."""
    
    # Ensure we have matching lists
    if len(ip_list) != len(name_list):
        raise ValueError(f"Number of IP addresses ({len(ip_list)}) must match number of system names ({len(name_list)})")
    
    yaml_content = """# To enable parallel update in nvfwupd, set the ParallelUpdate key to true
ParallelUpdate: true

# When ParallelUpdate is enabled, "Targets" becomes a list of systems alongside their packages
# BMC_IP, RF_USERNAME, RF_PASSWORD, PACKAGE are mandatory when using parallel update
# TARGET_PLATFORM would be needed for any systems that would normally require it from the command line (i.e: GB200, gb200switch, etc.)
# UPDATE_PARAMETERS_TARGETS is optional, but uses the same exact params as the special target file for nvfwupd "-s" option in json format with a given system
# SYSTEM_NAME is an entirely optional, but recommended user defined string. It is used to more easily distinguish systems as it is used in task printouts
Targets:
"""
    
    for ip, name in zip(ip_list, name_list):
        yaml_content += f'''      - BMC_IP: "{ip}"
        SYSTEM_NAME: "{name}"
        RF_USERNAME: "{username}"
        RF_PASSWORD: "{password}"
        TARGET_PLATFORM: 'GB300switch'
        PACKAGE: "{package_path}"
        UPDATE_PARAMETERS_TARGETS: {update_params}
'''
    
    return yaml_content


def load_ip_addresses_from_yaml_files(file_patterns: List[str]) -> Set[str]:
    """Load IP addresses from YAML files matching given patterns."""
    ip_addresses = set()
    
    for pattern in file_patterns:
        if os.path.exists(pattern):
            try:
                with open(pattern, 'r') as f:
                    data = yaml.safe_load(f)
                
                if 'Targets' in data:
                    for target in data['Targets']:
                        if 'BMC_IP' in target:
                            ip_addresses.add(target['BMC_IP'])
            
            except yaml.YAMLError as e:
                print(f"Warning: Error parsing {pattern}: {e}")
            except Exception as e:
                print(f"Warning: Error reading {pattern}: {e}")
    
    return ip_addresses


def check_ip_conflicts(new_ips: List[str], existing_yaml_files: List[str], 
                      system_type: str) -> bool:
    """
    Check for IP address conflicts between new IPs and existing YAML files.
    Returns True if conflicts found, False otherwise.
    """
    existing_ips = load_ip_addresses_from_yaml_files(existing_yaml_files)
    
    if not existing_ips:
        return False  # No existing files or IPs to conflict with
    
    conflicts = set(new_ips) & existing_ips
    
    if conflicts:
        print(f"\n⚠ WARNING: IP Address Conflicts Detected!")
        print(f"The following IP addresses are already used in {system_type} YAML files:")
        for ip in sorted(conflicts):
            print(f"  - {ip}")
        print(f"\nSwitch and compute systems must use different IP addresses.")
        print("Please use different IP addresses for your switch configuration.")
        return True
    
    return False


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


def run_reachability_test():
    """Run the reachability test script."""
    try:
        # Check if the test script exists
        if not os.path.exists('test_switch_reachability.py'):
            print("Error: test_switch_reachability.py not found in current directory.")
            print("Please ensure the reachability test script is in the same directory.")
            return
        
        # Run the reachability test script
        print("\nLaunching reachability test...")
        result = subprocess.run([sys.executable, 'test_switch_reachability.py'], 
                              check=False)
        
        if result.returncode != 0:
            print("Reachability test completed with errors.")
        
    except Exception as e:
        print(f"Error running reachability test: {e}")


def main():
    """Main program flow."""
    display_intro()
    
    try:
        # Get user inputs
        ip_list = get_ip_addresses()
        name_list = get_system_names()
        username, password = get_credentials()
        firmware_dir = get_firmware_path()
        
        # Find firmware files
        print("\nSearching for firmware files...")
        bmc_file, bios_file, cpld_file = find_firmware_files(firmware_dir)
        
        # Validate all files were found/selected
        if not all([bmc_file, bios_file, cpld_file]):
            print("Error: Could not find all required firmware files.")
            return
        
        # Create full paths
        bmc_path = os.path.join(firmware_dir, bmc_file).replace('\\', '/')
        bios_path = os.path.join(firmware_dir, bios_file).replace('\\', '/')
        cpld_path = os.path.join(firmware_dir, cpld_file).replace('\\', '/')
        
        print(f"\nSelected firmware files:")
        print(f"BMC: {bmc_file}")
        print(f"BIOS: {bios_file}")
        print(f"CPLD: {cpld_file}")
        
        # Check for IP conflicts with compute YAML files
        compute_yaml_files = ['compute_bmc.yaml', 'compute_hmc.yaml', 'compute_mcu.yaml']
        if check_ip_conflicts(ip_list, compute_yaml_files, "compute"):
            if not get_user_choice("\nDo you want to continue anyway?"):
                print("Operation cancelled.")
                return
        
        # Generate YAML files
        print(f"\nGenerating YAML files for {len(ip_list)} systems...")
        
        # BMC YAML (empty UPDATE_PARAMETERS_TARGETS)
        bmc_content = generate_yaml_content(ip_list, name_list, username, password, 
                                          bmc_path, {})
        with open('switch_bmc.yaml', 'w') as f:
            f.write(bmc_content)
        print("Generated: switch_bmc.yaml")
        
        # BIOS YAML (empty UPDATE_PARAMETERS_TARGETS)
        bios_content = generate_yaml_content(ip_list, name_list, username, password, 
                                           bios_path, {})
        with open('switch_bios.yaml', 'w') as f:
            f.write(bios_content)
        print("Generated: switch_bios.yaml")
        
        # CPLD YAML (empty UPDATE_PARAMETERS_TARGETS)
        cpld_content = generate_yaml_content(ip_list, name_list, username, password, 
                                           cpld_path, {})
        with open('switch_cpld.yaml', 'w') as f:
            f.write(cpld_content)
        print("Generated: switch_cpld.yaml")
        
        print(f"\nSuccessfully generated all 3 YAML files for {len(ip_list)} systems!")
        
        # Ask user if they want to test IP reachability
        print()
        if get_user_choice("Would you like to test IP reachability to the addresses in the generated YAML files?"):
            run_reachability_test()
        else:
            print("Skipping reachability test. Exiting...")
        
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
    except Exception as e:
        print(f"\nError: {e}")


if __name__ == "__main__":
    main()
