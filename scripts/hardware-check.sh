#!/bin/bash
#
# Hardware Check Script — Uses OQL DSL to detect and validate peripherals
#
# Usage:
#   ./hardware-check.sh              # Run full check
#   ./hardware-check.sh --quick      # Quick health check only
#   ./hardware-check.sh --usb        # List USB devices only
#
# Returns:
#   Exit code 0 if all hardware OK
#   Exit code 1 if any hardware issues detected
#

set -e

FIRMWARE_URL="${FIRMWARE_URL:-http://localhost:8202}"
OQLCTL="${OQLCTL:-python -m oqlos.tools.cql_cli}"
DIAGNOSE="${DIAGNOSE:-python -m oqlos.tools.hardware_diagnose}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# === Function: Detect USB Peripherals ===
detect_usb_peripherals() {
    log_info "Detecting USB/Serial peripherals..."
    
    # Use hardware_diagnose tool to get JSON list
    local devices
    devices=$($DIAGNOSE --list --json 2>/dev/null || echo '{}')
    
    # Extract real USB devices (with VID/PID)
    local usb_count
    usb_count=$(echo "$devices" | python3 -c "
import sys, json
data = json.load(sys.stdin)
real = [d for d in data.get('usb_devices', []) if d.get('vid')]
print(len(real))
")
    
    if [ "$usb_count" -eq 0 ]; then
        log_error "No USB serial devices detected!"
        return 1
    fi
    
    log_info "Found $usb_count USB serial device(s)"
    
    # List each device
    echo "$devices" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for d in data.get('usb_devices', []):
    if d.get('vid'):
        print(f\"  {d['device']:15} | {d['vid']}:{d['pid']} | {d.get('product', '-')} | {d.get('manufacturer', '-')}\")
"
    
    return 0
}

# === Function: Detect I2C Buses ===
detect_i2c_buses() {
    log_info "Detecting I2C buses..."
    
    local buses
    buses=$($DIAGNOSE --list --json 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
buses = data.get('i2c_buses', [])
print(' '.join(buses))
")
    
    if [ -z "$buses" ]; then
        log_warn "No I2C buses detected (may require i2c-dev kernel module)"
        return 1
    fi
    
    log_info "Found I2C buses: $buses"
    return 0
}

# === Function: Check Firmware Health ===
check_firmware_health() {
    log_info "Checking firmware bridge health at $FIRMWARE_URL..."
    
    local health
    health=$($DIAGNOSE --health --json 2>/dev/null || echo '{}')
    
    # Check mode
    local mode
    mode=$(echo "$health" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('mode', 'unknown'))")
    
    if [ "$mode" != "real" ]; then
        log_warn "Firmware in '$mode' mode (expected 'real')"
    else
        log_info "Firmware in REAL mode ✓"
    fi
    
    # Check individual components
    local piadc motor modbus
    piadc=$(echo "$health" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('piadc', 'unknown'))")
    motor=$(echo "$health" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('motor', 'unknown'))")
    modbus=$(echo "$health" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('modbus', 'unknown'))")
    
    [ "$piadc" = "ok" ] && log_info "PIADC (sensors): OK ✓" || log_warn "PIADC: $piadc"
    [ "$motor" = "ok" ] && log_info "Motor (DRI0050): OK ✓" || log_warn "Motor: $motor"
    
    if echo "$modbus" | grep -q "ttyACM"; then
        log_info "Modbus RTU: Connected ✓ ($modbus)"
    else
        log_warn "Modbus: $modbus"
    fi
    
    return 0
}

# === Function: Run Smoke Test via DSL ===
run_smoke_test() {
    local test_type="$1"
    log_info "Running $test_type smoke test via DSL..."
    
    # Create temporary OQL script
    local oql_file
    oql_file=$(mktemp /tmp/hardware-smoke-XXXXXX.oql)
    
    case "$test_type" in
        pump)
            cat > "$oql_file" << 'OQL'
GOAL: Pump smoke test
  LOG "Starting pump test..."
  SET "pompa 1" "3"
  SET WAIT '500 ms'
  GET_SENSOR "sc-sensor"
  ASSERT_SENSOR "sc-sensor" ">" "0" "mbar"
  SET "pompa 1" "0"
  LOG "Pump test complete"
OQL
            ;;
        valves)
            cat > "$oql_file" << 'OQL'
GOAL: Valves smoke test
  LOG "Testing valves..."
  SET "zawor NC" "ON"
  SET WAIT '200 ms'
  SET "zawor NC" "OFF"
  SET "zawor SC" "ON"
  SET WAIT '200 ms'
  SET "zawor SC" "OFF"
  LOG "Valve test complete"
OQL
            ;;
        *)
            log_error "Unknown test type: $test_type"
            rm -f "$oql_file"
            return 1
            ;;
    esac
    
    # Run OQL script
    if $OQLCTL "$oql_file" --mode execute --json --firmware-url "$FIRMWARE_URL" 2>/dev/null; then
        log_info "$test_type smoke test: PASSED ✓"
        rm -f "$oql_file"
        return 0
    else
        log_error "$test_type smoke test: FAILED ✗"
        rm -f "$oql_file"
        return 1
    fi
}

# === Function: Run Calibration ===
run_calibration() {
    log_info "Running hardware calibration test..."
    
    local result
    result=$($DIAGNOSE --calibrate --json 2>/dev/null || echo '{}')
    
    local passed failed
    passed=$(echo "$result" | jq -r '.passed // 0')
    failed=$(echo "$result" | jq -r '.failed // 0')
    
    log_info "Calibration: $passed passed, $failed failed"
    
    # List failed tests
    if [ "$failed" -gt 0 ]; then
        echo "$result" | jq -r '.tests[] | select(.passed == false) | "  ❌ \(.name): \(.details)"'
        return 1
    fi
    
    return 0
}

# === Function: Generate Report ===
generate_report() {
    local filename="${1:-auto}"
    log_info "Generating diagnostic report..."
    
    local saved_path
    saved_path=$($DIAGNOSE --report "$filename" --json 2>/dev/null | jq -r '.report_file // empty')
    
    if [ -n "$saved_path" ]; then
        log_info "Report saved: $saved_path"
        
        # Show summary from report
        echo
        echo "Report summary:"
        jq '. | {timestamp, usb_devices: (.usb_devices | length), health: .firmware_health.mode, calibration_passed: .calibration.passed}' "$saved_path"
        return 0
    else
        log_error "Failed to save report"
        return 1
    fi
}

# === Function: Full Diagnostic Report ===
full_diagnostic() {
    log_info "=== Hardware Diagnostic Report ==="
    echo
    
    local exit_code=0
    
    detect_usb_peripherals || exit_code=1
    echo
    detect_i2c_buses || true  # Non-critical
    echo
    check_firmware_health || exit_code=1
    echo
    
    # Run calibration
    run_calibration || exit_code=1
    echo
    
    # Run smoke tests
    run_smoke_test "pump" || exit_code=1
    echo
    run_smoke_test "valves" || exit_code=1
    echo
    
    if [ $exit_code -eq 0 ]; then
        log_info "=== ALL CHECKS PASSED ==="
    else
        log_error "=== SOME CHECKS FAILED ==="
    fi
    
    return $exit_code
}

# === Main ===
main() {
    case "${1:-}" in
        --usb|-u)
            detect_usb_peripherals
            ;;
        --i2c|-i)
            detect_i2c_buses
            ;;
        --health|-h)
            check_firmware_health
            ;;
        --test-pump)
            run_smoke_test "pump"
            ;;
        --test-valves)
            run_smoke_test "valves"
            ;;
        --quick|-q)
            check_firmware_health
            ;;
        --calibrate)
            run_calibration
            ;;
        --report)
            generate_report "${2:-auto}"
            shift
            ;;
        --help|-?)
            cat << 'HELP'
Hardware Check Script — USB/I2C/Firmware Detection

Usage:
  hardware-check.sh [OPTION]

Options:
  --usb, -u         List USB/serial peripherals only
  --i2c, -i         List I2C buses only
  --health, -h      Check firmware health only
  --calibrate       Run calibration test
  --report [file]   Save diagnostic report (auto filename if not provided)
  --test-pump       Run pump smoke test
  --test-valves     Run valves smoke test
  --quick, -q       Quick health check only
  --help            Show this help

Environment:
  FIRMWARE_URL      Firmware bridge URL (default: http://localhost:8202)
  OQLCTL            OQL CLI command (default: python -m oqlos.tools.cql_cli)
  DIAGNOSE          Diagnose CLI (default: python -m oqlos.tools.hardware_diagnose)

Examples:
  # Full diagnostic
  ./hardware-check.sh

  # Check USB devices only
  ./hardware-check.sh --usb

  # Quick health check
  ./hardware-check.sh --quick

  # Run calibration test
  ./hardware-check.sh --calibrate

  # Generate report
  ./hardware-check.sh --report

  # Run with custom firmware URL
  FIRMWARE_URL=http://192.168.1.100:8202 ./hardware-check.sh
HELP
            ;;
        *)
            full_diagnostic
            ;;
    esac
}

main "$@"
