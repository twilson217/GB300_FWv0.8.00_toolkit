# GB300 Firmare v0.8.00 Toolkit

A comprehensive Python toolkit for managing NVIDIA GB300 compute and switch systems, including YAML configuration generation, connectivity testing, BMC management, and power control operations.

## 🚀 Features

### YAML Configuration Generation
- **Automated YAML creation** for firmware updates
- **IP range and system name parsing** with exclusion support
- **Firmware file detection** and validation
- **Conflict detection** between compute and switch configurations

### System Connectivity Testing
- **Ping connectivity** testing across all systems
- **TCP port 443** reachability verification
- **Cross-platform support** (Windows, Linux, macOS)
- **Real-time progress** indicators

### BMC Management
- **BMC reset operations** via Redfish API
- **Comprehensive validation** before operations
- **User confirmation** with detailed warnings
- **Success/failure reporting**

### Power Management
- **Three-phase power cycling** (off → wait → cycle)
- **Visual countdown timer** with progress bar
- **Force power off** followed by power cycle
- **Data loss warnings** and safety confirmations

## 📋 Prerequisites

### Development & Testing Environment
- **Developed and tested on:** Ubuntu 24.04 with Python 3.12
- **Assumes:** Python3 is already installed

### Ubuntu Setup
```bash
# Install pip
sudo apt install python3-pip

# Install venv module
sudo apt install python3.12-venv

# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate
```

### Python Requirements
```bash
pip install -r requirements.txt
```

### Dependencies
- **PyYAML** ≥ 6.0 - YAML file processing
- **requests** ≥ 2.25.0 - HTTP/Redfish API calls
- **urllib3** ≥ 1.26.0 - HTTP utilities and SSL handling

### System Requirements
- Python 3.7 or higher
- Network access to GB300 BMCs
- Valid BMC credentials

## 🚀 Complete Firmware Update Workflow

This section provides a step-by-step guide to update GB300 compute and switch firmware using the toolkit along with the `nvfwupd` command.

### 🔧 Initial Setup

**Start a persistent session** (recommended for long-running operations):
   ```bash
   tmux
   ```

**Activate Python virtual environment**:
```bash
source .venv/bin/activate
```

**Generate YAML configuration files**:
```bash
python gen_compute_yaml.py
python gen_switch_yaml.py
```

### 💻 Compute Systems Firmware Update

#### Step 1: Update Compute BMC Firmware
```bash
nvfwupd -c compute_bmc.yaml update_fw
```

#### Step 2: Verify BMC Update Success
```bash
nvfwupd -c compute_bmc.yaml show_version | grep '^Displaying version info for\|^FW_ERoT_BMC_0'
```
**All outputs should show:**
```
FW_ERoT_BMC_0                            01.04.0031.0000_n04            01.04.0031.0000_n04            Yes
```

#### Step 3: Activate BMC Firmware (Cold Reset)
```bash
nvfwupd -c compute_bmc.yaml activate_fw -c RESET_COLD
```

#### Step 4: Update Compute HMC Firmware
```bash
nvfwupd -c compute_hmc.yaml update_fw
```

#### Step 5: Activate HMC Firmware (Auxiliary Power Cycle)
```bash
python aux_powercycle_compute.py
```

#### Step 6: Verify HMC Update Success
```bash
nvfwupd -c compute_hmc.yaml show_version | grep '^Displaying version info for\|^HGX_FW_BMC_0\|^HGX_FW_CPLD_0\|^HGX_FW_CPU_0\|^HGX_FW_CPU_1\|^HGX_FW_ERoT_BMC_0\|^HGX_FW_ERoT_CPU_0\|^HGX_FW_ERoT_CPU_1\|^HGX_FW_ERoT_FPGA_0\|^HGX_FW_ERoT_FPGA_1'
```

**All outputs should show:**
```
HGX_FW_BMC_0                             GB200Nvl-25.07-7               GB200Nvl-25.07-7               Yes
HGX_FW_CPLD_0                            0.22                           0.22                           Yes
HGX_FW_CPU_0                             02.04.07a                      02.04.12                       Yes
HGX_FW_CPU_1                             02.04.07a                      02.04.12                       Yes
HGX_FW_ERoT_BMC_0                        01.04.0031.0000_n04            01.04.0031.0000_n04            Yes
HGX_FW_ERoT_CPU_0                        01.04.0031.0000_n04            01.04.0031.0000_n04            Yes
HGX_FW_ERoT_CPU_1                        01.04.0031.0000_n04            01.04.0031.0000_n04            Yes
HGX_FW_ERoT_FPGA_0                       01.04.0031.0000_n04            01.04.0031.0000_n04            Yes
HGX_FW_ERoT_FPGA_1                       01.04.0031.0000_n04            01.04.0031.0000_n04            Yes
```

### 🔌 Switch Systems Firmware Update

#### Step 1: Update Switch BMC Firmware
```bash
python nvsw_fw_update.py -p bmc
```

#### Step 2: Monitor Update Progress
```bash
python switch_redfish_status.py
```
- Monitor until all systems show `PercentComplete: 100%`.

#### Step 3: Activate BMC Firmware (Power Cycle)
```bash
python powercycle_switch.py
```


#### Step 4: Verify Switch BMC Update Success
```bash
nvfwupd -c switch_bmc.yaml show_version | grep '^Displaying version info for\|^MGX_FW_BMC_0\|^MGX_FW_ERoT_BMC_\|^MGX_FW_ERoT_CPU_0\|^MGX_FW_ERoT_FPGA_0\|^MGX_FW_ERoT_NVSwitch_0\|^MGX_FW_ERoT_NVSwitch_1\|^MGX_FW_FPGA_0'
```

**All outputs should show:**
```
MGX_FW_BMC_0                             88.0002.1950                   88.0002.1950                   Yes
MGX_FW_ERoT_BMC_0                        01.04.0026.0000_n04            01.04.0026.0000_n04            Yes
MGX_FW_ERoT_CPU_0                        01.04.0026.0000_n04            01.04.0026.0000_n04            Yes
MGX_FW_ERoT_FPGA_0                       01.04.0026.0000_n04            01.04.0026.0000_n04            Yes
MGX_FW_ERoT_NVSwitch_0                   01.04.0026.0000_n04            01.04.0026.0000_n04            Yes
MGX_FW_ERoT_NVSwitch_1                   01.04.0026.0000_n04            01.04.0026.0000_n04            Yes
MGX_FW_FPGA_0                            0.14                           0.14                           Yes
```

#### Step 5: Update Switch BIOS (If Needed)
```bash
python nvsw_fw_update.py -p bios
```
⚠️ **Note**: This step may be unnecessary if BIOS components are already included in the BMC package.

#### Step 6: Update Switch CPLD (Manual Process)
Due to Redfish API limitations with CPLD, manual installation via NVOS is required:

1. **Extract CPLD firmware**:
   ```bash
   nvfwupd unpack -o cpld/ -p nvfw_GB300-P4093_0007_250629.1.0_prod-signed.fwpkg
   ```

2. **Install via NVOS** (on each switch):
   ```bash
   nv action fetch platform firmware CPLD1 scp://user@server/path/to/CPLD_file.bin
   nv action install platform firmware CPLD1 files CPLD_file.bin
   ```

3. **Verify CPLD versions**:
   ```bash
   nv show platform firmware
   ```

### 🔍 Monitoring and Troubleshooting

#### Monitor Task Progress
- **Compute systems**: `python compute_redfish_status.py`
- **Switch systems**: `python switch_redfish_status.py`

#### Check Logs
All operations log detailed information to `./logs/` directory:
- `aux_powercycle_compute.log` - Auxiliary power cycle operations
- `redfish_tasks.log` - Task monitoring and Redfish API responses
- `switch_bmc.log` / `switch_bios.log` / `switch_cpld.log` - Firmware update operations

#### Common Issues and Solutions

**Authentication Failures**: BMC passwords may reset to `0penBmc` during some operations. Reset with:
```bash
ipmitool -I lanplus -H <ip_address> -U root -P '0penBmc' user set password 1 '<new_password>'
```

**Firmware Activation Issues**: If firmware shows "PendingActivation" status:
- For compute systems: Use auxiliary power cycle (`python aux_powercycle_compute.py`)
    - If you have trouble getting some HMC firmware to activate, you can status with `curl -s -k -u root:'<pw>' -X GET https://<bmc_ip>/redfish/v1/UpdateService/FirmwareInventory/HGX_FW_BMC_0`
- For switch systems: Use system power cycle (`python powercycle_switch.py`)

**Sequential Updates**: If parallel updates fail, use sequential processing:
```bash
python compute_hmc_sequential.py
```

### ✅ Verification Commands Summary

| Component | Verification Command |
|-----------|---------------------|
| Compute BMC | `nvfwupd -c compute_bmc.yaml show_version \| grep ERoT_BMC_0` |
| Compute HMC | `nvfwupd -c compute_hmc.yaml show_version \| grep HGX_FW` |
| Switch BMC | `nvfwupd -c switch_bmc.yaml show_version \| grep MGX_FW` |
| Switch CPLD | `nv show platform firmware` (on switch) |

## 📁 Project Structure

```
FW v0.8.00/
├── example yaml/              # Sample YAML configurations
│   ├── compute_bmc.yaml       # Compute BMC firmware config
│   ├── compute_hmc.yaml       # Compute HMC firmware config
│   ├── compute_mcu.yaml       # Compute MCU firmware config
│   ├── switch_bmc.yaml        # Switch BMC firmware config
│   ├── switch_bios.yaml       # Switch BIOS firmware config
│   └── switch_cpld.yaml       # Switch CPLD firmware config
│
├── gen_compute_yaml.py        # Generate compute YAML files
├── gen_switch_yaml.py         # Generate switch YAML files
├── test_compute_reachability.py   # Test compute connectivity
├── test_switch_reachability.py    # Test switch connectivity
├── mc_reset_compute.py        # Reset compute BMCs
├── mc_reset_switch.py         # Reset switch BMCs
├── powercycle_compute.py      # Power cycle compute systems
├── powercycle_switch.py       # Power cycle switch systems
│
├── README_BMC_Reset.md        # BMC reset documentation
├── README_PowerCycle.md       # Power cycle documentation
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

## 🛠️ Quick Start

### 1. Generate YAML Configurations

#### For Compute Systems:
```bash
python gen_compute_yaml.py
```
**Input Examples:**
- IP Range: `10.102.112.79-96`
- System Names: `CP-[01-18]`
- Generates: `compute_bmc.yaml`, `compute_hmc.yaml`, `compute_mcu.yaml`

#### For Switch Systems:
```bash
python gen_switch_yaml.py
```
**Input Examples:**
- IP Range: `10.102.112.70-72`
- System Names: `SW-[01-03]`
- Generates: `switch_bmc.yaml`, `switch_bios.yaml`, `switch_cpld.yaml`

### 2. Test System Connectivity

#### Test Compute Systems:
```bash
python test_compute_reachability.py
```

#### Test Switch Systems:
```bash
python test_switch_reachability.py
```

**Features:**
- Ping connectivity testing
- Optional TCP port 443 testing
- Real-time progress indicators
- Comprehensive summary reports

### 3. BMC Management Operations

#### Reset Compute BMCs:
```bash
python mc_reset_compute.py
```

#### Reset Switch BMCs:
```bash
python mc_reset_switch.py
```

**Safety Features:**
- ✅ YAML validation and IP consistency checks
- ✅ User confirmation with system details
- ✅ Real-time operation status
- ✅ Complete success/failure summary

### 4. Power Management Operations

#### Power Cycle Compute Systems:
```bash
python powercycle_compute.py
```

#### Power Cycle Switch Systems:
```bash
python powercycle_switch.py
```

**Power Cycle Sequence:**
1. **Phase 1:** Force power off all systems
2. **Phase 2:** 15-second countdown with visual progress bar
3. **Phase 3:** Power cycle all systems

## 🔒 Validation & Safety

### IP Address Validation
- **Consistency Check:** All YAML files of same type must have identical IP addresses
- **Conflict Prevention:** Compute and switch systems must use different IP addresses
- **Cross-Reference:** Automatic validation against existing configurations

### User Safety Features
- **Comprehensive Warnings:** Clear indication of potential data loss
- **User Confirmation:** Required approval before destructive operations
- **Progress Tracking:** Real-time status updates during operations
- **Error Handling:** Detailed error messages and recovery guidance

## 📊 Example Workflows

### Complete System Setup
```bash
# 1. Generate configurations
python gen_compute_yaml.py    # Creates compute_*.yaml files
python gen_switch_yaml.py     # Creates switch_*.yaml files

# 2. Test connectivity
python test_compute_reachability.py
python test_switch_reachability.py

# 3. Reset BMCs if needed
python mc_reset_compute.py
python mc_reset_switch.py

# 4. Power cycle if required
python powercycle_compute.py
python powercycle_switch.py
```

### Maintenance Operations
```bash
# Quick connectivity check
python test_compute_reachability.py

# BMC reset for unresponsive systems
python mc_reset_compute.py

# Emergency power cycle
python powercycle_compute.py
```

## 🔧 Configuration Examples

### IP Address Formats
```bash
# Single IP
10.102.112.79

# Comma-separated list
10.102.112.79,10.102.112.80,10.102.112.81

# Short range
10.102.112.79-96

# Full range
10.102.112.79-10.102.112.96
```

### System Name Formats
```bash
# Single name
CP-01

# Comma-separated list
CP-01,CP-02,CP-03

# Bracket range (with zero padding)
CP-[01-18]

# Double-dot range
CP-01..CP-18
```

## 🌐 Redfish API Details

### BMC Reset
- **Endpoint:** `/redfish/v1/Managers/1/Actions/Manager.Reset`
- **Method:** POST
- **Payload:** `{"ResetType": "ForceRestart"}`

### Power Control
- **Endpoint:** `/redfish/v1/Systems/1/Actions/ComputerSystem.Reset`
- **Method:** POST
- **Power Off:** `{"ResetType": "ForceOff"}`
- **Power Cycle:** `{"ResetType": "PowerCycle"}`

### Authentication
- **Type:** HTTP Basic Authentication
- **SSL:** Disabled verification (self-signed certificates)
- **Timeout:** 30 seconds per request

## ⚠️ Important Warnings

### Data Loss Risk
- **Power cycling** systems without proper shutdown may cause data corruption
- **BMC resets** may temporarily interrupt management connectivity
- Always ensure **recent backups** before power operations

### Network Impact
- Operations may cause **temporary service interruption**
- Plan operations during **maintenance windows**
- Verify **network connectivity** before bulk operations

## 🐛 Troubleshooting

### Common Issues

#### YAML Validation Errors
```bash
# IP address mismatch between files
Validation Error: IP address mismatch between compute_bmc.yaml and compute_hmc.yaml

# Solution: Ensure all compute YAML files have identical IP addresses
```

#### Connectivity Issues
```bash
# Connection timeout
✗ FAILED (Timeout)

# Solution: Verify BMC IP addresses and network connectivity
```

#### Authentication Failures
```bash
# HTTP 401 Unauthorized
✗ FAILED (HTTP 401)

# Solution: Verify username and password in YAML files
```

### Debug Steps
1. **Verify YAML files** have consistent IP addresses
2. **Test connectivity** using ping/telnet
3. **Check credentials** with manual BMC access
4. **Review firewall** and network routing
5. **Examine BMC logs** for error details

## 📝 Compatibility

### Firmware Version
- **Designed for:** Firmware release v0.8.00
- **Target Systems:** GB300 compute and switch systems only
- **Platform Support:** GB300 and GB300switch

### Operating Systems
- **Windows** (PowerShell/Command Prompt)
- **Linux** (bash/zsh)
- **macOS** (Terminal)

## 🤝 Contributing

### Development Guidelines
1. Follow existing code structure and naming conventions
2. Add comprehensive error handling and user feedback
3. Include detailed docstrings and comments
4. Test with various input scenarios
5. Update documentation for new features

### Testing
- Validate with sample YAML configurations
- Test error conditions and edge cases
- Verify cross-platform compatibility
- Confirm Redfish API interactions

## 📄 License

This toolkit is designed for internal use with NVIDIA GB300 systems. Please ensure compliance with your organization's software policies and NVIDIA's licensing terms.

## 🆘 Support

For issues, questions, or contributions:
1. Check existing documentation (README_BMC_Reset.md, README_PowerCycle.md)
2. Review troubleshooting section above
3. Examine script output for detailed error messages
4. Verify system requirements and dependencies

---

**⚡ NVIDIA GB300 System Management Toolkit - Efficient, Safe, Comprehensive**
