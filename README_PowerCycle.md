# GB300 Power Cycle Scripts

This directory contains scripts to execute power cycles via Redfish API for GB300 compute and switch systems.

## Scripts

### `powercycle_compute.py`
Executes power cycle sequence for all IP addresses found in `compute_*.yaml` files.

### `powercycle_switch.py`
Executes power cycle sequence for all IP addresses found in `switch_*.yaml` files.

## Prerequisites

Install required Python packages:
```bash
pip install -r requirements.txt
```

## Power Cycle Sequence

Both scripts perform the following sequence:

1. **Validation Phase**: Comprehensive IP address and YAML file validation
2. **Phase 1 - Power Off**: Send `ForceOff` command to all systems
3. **Phase 2 - Wait**: 15-second countdown with visual progress indicator
4. **Phase 3 - Power Cycle**: Send `PowerCycle` command to all systems

## Validation Features

### Same validation as BMC Reset scripts:

1. **YAML File Discovery** - Searches current directory and subdirectories
2. **IP Address Consistency** - Ensures all YAML files of same type have identical IPs
3. **Cross-System Validation** - Prevents compute/switch IP conflicts
4. **YAML Structure Validation** - Validates required fields and data types
5. **Credential Consistency** - Ensures uniform authentication

## Usage

### Compute Power Cycle
```bash
python powercycle_compute.py
```

### Switch Power Cycle
```bash
python powercycle_switch.py
```

## Example Output

```
GB300 Compute Power Cycle Tool
========================================

============================================================
VALIDATING COMPUTE YAML FILES
============================================================
Found 3 compute YAML files:
  - example yaml/compute_bmc.yaml
  - example yaml/compute_hmc.yaml
  - example yaml/compute_mcu.yaml

✓ All compute YAML files have consistent IP addresses
✓ Total unique IP addresses: 2
✓ No IP conflicts between compute (2) and switch (2) files

✓ Using credentials - Username: admin

============================================================
READY TO EXECUTE POWER CYCLE
============================================================
Total systems to power cycle: 6
Unique IP addresses: 2

Systems that will be power cycled:
  - CP-01 (10.102.112.79)
  - CP-02 (10.102.112.80)

⚠ WARNING: This will power cycle all 6 systems!
⚠ This operation will:
  1. Force power off all systems
  2. Wait 15 seconds
  3. Power cycle all systems
⚠ This may cause data loss if systems are not properly shut down!

Do you want to proceed with power cycling 6 systems? (yes/no): yes

============================================================
PHASE 1: POWERING OFF SYSTEMS
============================================================
[1/2]   Executing ForceOff for CP-01 (10.102.112.79)... ✓ SUCCESS
[2/2]   Executing ForceOff for CP-02 (10.102.112.80)... ✓ SUCCESS

Power off completed: 2/2 successful

============================================================
PHASE 2: WAITING BEFORE POWER CYCLE
============================================================

Waiting 15 seconds before power cycle...
[████████████████████████████████████████]  0s remaining
Ready for power cycle!

============================================================
PHASE 3: POWER CYCLING SYSTEMS
============================================================
[1/2]   Executing PowerCycle for CP-01 (10.102.112.79)... ✓ SUCCESS
[2/2]   Executing PowerCycle for CP-02 (10.102.112.80)... ✓ SUCCESS

============================================================
POWER CYCLE SUMMARY
============================================================
Total unique systems: 2
Successful power offs: 2
Successful power cycles: 2
✓ All power cycle operations completed successfully!
```

## Visual Features

### Progress Countdown Timer
During the 15-second wait period, the script displays:
- Real-time countdown (15, 14, 13... seconds)
- Visual progress bar that fills up over time
- Clear indication when ready for power cycle

Example:
```
[██████████████████░░░░░░░░░░░░░░░░░░░░░░]  5s remaining
```

## Redfish API Details

### Power Off Command
- **URL**: `https://{BMC_IP}/redfish/v1/Systems/1/Actions/ComputerSystem.Reset`
- **Method**: POST
- **Payload**: `{"ResetType": "ForceOff"}`

### Power Cycle Command  
- **URL**: `https://{BMC_IP}/redfish/v1/Systems/1/Actions/ComputerSystem.Reset`
- **Method**: POST
- **Payload**: `{"ResetType": "PowerCycle"}`

### Common Settings
- **Authentication**: HTTP Basic Auth
- **SSL Verification**: Disabled (for self-signed certificates)
- **Timeout**: 30 seconds per request

## Safety Features

1. **Comprehensive validation** before any operations
2. **User confirmation** with detailed warning about data loss
3. **Three-phase execution** with clear progress indication
4. **Duplicate IP handling** - only sends commands once per unique IP
5. **Error handling** with detailed status reporting
6. **Rate limiting** - 1-second delay between requests
7. **Summary reporting** with success/failure counts

## Important Warnings

⚠ **DATA LOSS RISK**: Power cycling systems without proper shutdown may cause:
- Data corruption
- File system damage  
- Loss of unsaved work
- Database inconsistencies

⚠ **SYSTEM IMPACT**: Power cycling will:
- Immediately terminate all running processes
- Force restart the systems
- Cause temporary service interruption
- Require systems to go through full boot cycle

## Error Handling

Same comprehensive error handling as BMC reset scripts:
- IP address conflicts and inconsistencies
- Missing or malformed YAML files
- Network connectivity issues
- Authentication failures
- Redfish API errors

## Best Practices

1. **Graceful Shutdown**: When possible, shut down systems gracefully before power cycling
2. **Maintenance Windows**: Perform power cycles during scheduled maintenance windows
3. **Backup Verification**: Ensure recent backups before power cycling critical systems
4. **Monitoring**: Monitor system status after power cycle completion
5. **Documentation**: Log power cycle operations for audit trails

## Comparison with BMC Reset

| Feature | BMC Reset | Power Cycle |
|---------|-----------|-------------|
| **Target** | BMC only | Entire system |
| **Impact** | Management plane | Full system |
| **Downtime** | ~1-2 minutes | ~3-5 minutes |
| **Data Risk** | None | High |
| **Use Case** | BMC issues | System hangs |
| **Commands** | Manager.Reset | ComputerSystem.Reset |
