# GB300 BMC Reset Scripts

This directory contains scripts to execute BMC resets via Redfish API for GB300 compute and switch systems.

## Scripts

### `mc_reset_compute.py`
Executes BMC resets for all IP addresses found in `compute_*.yaml` files.

### `mc_reset_switch.py`
Executes BMC resets for all IP addresses found in `switch_*.yaml` files.

## Prerequisites

Install required Python packages:
```bash
pip install -r requirements.txt
```

## Validation Features

Both scripts perform comprehensive validation before executing any BMC resets:

### 1. YAML File Discovery
- Searches current directory and all subdirectories for relevant YAML files
- `mc_reset_compute.py` looks for files starting with `compute_`
- `mc_reset_switch.py` looks for files starting with `switch_`

### 2. IP Address Consistency Validation
- **Within system type**: Ensures all YAML files of the same type (compute or switch) contain identical IP addresses
- **Across system types**: Validates that compute and switch systems use different IP addresses
- **Error reporting**: Provides detailed information about any IP conflicts or inconsistencies

### 3. YAML Structure Validation
- Validates presence of required sections (`Targets`)
- Ensures all targets have required fields: `BMC_IP`, `RF_USERNAME`, `RF_PASSWORD`, `SYSTEM_NAME`
- Validates data types and formats

### 4. Credential Consistency
- Ensures all targets use the same username and password
- Reports error if multiple credentials are found

## Usage

### Compute BMC Reset
```bash
python mc_reset_compute.py
```

### Switch BMC Reset
```bash
python mc_reset_switch.py
```

## Example Output

```
GB300 Compute BMC Reset Tool
========================================

============================================================
VALIDATING COMPUTE YAML FILES
============================================================
Found 3 compute YAML files:
  - FW v0.8.00/example yaml/compute_bmc.yaml
  - FW v0.8.00/example yaml/compute_hmc.yaml
  - FW v0.8.00/example yaml/compute_mcu.yaml

Validating FW v0.8.00/example yaml/compute_bmc.yaml...
  Found 2 targets with 2 unique IPs

Validating FW v0.8.00/example yaml/compute_hmc.yaml...
  Found 2 targets with 2 unique IPs

Validating FW v0.8.00/example yaml/compute_mcu.yaml...
  Found 2 targets with 2 unique IPs

Validating IP address consistency across compute files...
✓ All compute YAML files have consistent IP addresses
✓ Total unique IP addresses: 2

Validating no conflicts with switch YAML files...
  Found 3 switch YAML files
✓ No IP conflicts between compute (2) and switch (2) files

✓ Using credentials - Username: admin

============================================================
READY TO EXECUTE BMC RESETS
============================================================
Total systems to reset: 6
Unique IP addresses: 2

Systems that will be reset:
  - CP-01 (10.102.112.79)
  - CP-02 (10.102.112.80)
  - CP-01 (10.102.112.79)
  - CP-02 (10.102.112.80)
  - CP-01 (10.102.112.79)
  - CP-02 (10.102.112.80)

⚠ WARNING: This will reset the BMC on all 6 systems!
⚠ This may cause temporary loss of management connectivity.

Do you want to proceed with resetting 6 BMCs? (yes/no):
```

## Error Handling

The scripts provide detailed error messages for various scenarios:

### IP Address Conflicts
```
Validation Error: IP address conflicts detected between compute and switch YAML files: ['10.102.112.70']
```

### IP Address Inconsistency
```
Validation Error: IP address mismatch between compute_bmc.yaml and compute_hmc.yaml:
  Missing in compute_hmc.yaml: ['10.102.112.81']
  Extra in compute_hmc.yaml: ['10.102.112.82']
```

### Missing Required Fields
```
Validation Error: Target 1 in compute_bmc.yaml missing required field: BMC_IP
```

## Redfish API Details

The scripts use the following Redfish endpoint for BMC resets:
- **URL**: `https://{BMC_IP}/redfish/v1/Managers/1/Actions/Manager.Reset`
- **Method**: POST
- **Reset Type**: ForceRestart
- **Authentication**: HTTP Basic Auth
- **SSL Verification**: Disabled (for self-signed certificates)

## Safety Features

1. **Comprehensive validation** before any operations
2. **User confirmation** required before executing resets
3. **Detailed progress reporting** during execution
4. **Timeout handling** for network operations
5. **Graceful error handling** with detailed error messages
6. **Summary reporting** after completion

## Notes

- BMC resets may cause temporary loss of management connectivity
- Systems will typically come back online within 1-2 minutes after BMC reset
- The scripts include a 1-second delay between reset requests to avoid overwhelming BMCs
- All YAML files must contain identical IP addresses for validation to pass
- Compute and switch systems must use different IP addresses
