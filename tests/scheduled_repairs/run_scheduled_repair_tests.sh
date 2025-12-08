#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the tests directory to ensure relative paths work
cd "$SCRIPT_DIR"

# Default values for local testing
DEFAULT_URL="http://localhost:3000"
DEFAULT_ORG="testorg"
DEFAULT_CLUSTER="testcluster"
INTERACTIVE=false

# Use environment variables or defaults
URL="${AXONOPS_URL:-$DEFAULT_URL}"
ORG="${AXONOPS_ORG:-$DEFAULT_ORG}"
CLUSTER="${AXONOPS_CLUSTER:-$DEFAULT_CLUSTER}"

# Allow command line overrides
while [[ $# -gt 0 ]]; do
  case $1 in
    --url)
      URL="$2"
      shift 2
      ;;
    --org)
      ORG="$2"
      shift 2
      ;;
    --cluster)
      CLUSTER="$2"
      shift 2
      ;;
    --confirm|-i)
      INTERACTIVE=true
      shift
      ;;
    --help)
      echo "Usage: $0 [options]"
      echo "Options:"
      echo "  --url URL       AxonOps base URL (default: $DEFAULT_URL)"
      echo "  --org ORG       Organization name (default: $DEFAULT_ORG)"
      echo "  --cluster NAME  Cluster name (default: $DEFAULT_CLUSTER)"
      echo "  --confirm, -i   Interactive mode - pause before each test for confirmation"
      echo ""
      echo "You can also set environment variables:"
      echo "  AXONOPS_URL, AXONOPS_ORG, AXONOPS_CLUSTER"
      echo "  AXONOPS_TOKEN (for AxonOps Cloud)"
      echo "  AXONOPS_USERNAME, AXONOPS_PASSWORD (for self-hosted with auth)"
      echo ""
      echo "Examples:"
      echo "  $0                                    # Use defaults (local)"
      echo "  $0 --url https://dash.axonops.cloud  # Use SaaS"
      echo "  $0 --org myorg --cluster mycluster   # Different org/cluster"
      echo "  $0 --confirm                         # Interactive mode"
      exit 0
      ;;
    *)
      echo "Unknown option $1"
      exit 1
      ;;
  esac
done

echo "Running AxonOps Scheduled Repair Tests"
echo "======================================="
echo "URL:     $URL"
echo "Org:     $ORG"
echo "Cluster: $CLUSTER"
echo ""

# Function to run a test playbook with the specified parameters
run_test() {
    local playbook=$1
    local test_name=$2

    echo "Running $test_name..."
    echo "----------------------------------------"

    set -x
    ansible-playbook "$playbook" \
        -e "url=$URL" \
        -e "org=$ORG" \
        -e "cluster=$CLUSTER" \
        -e "interactive=$INTERACTIVE" \
        -v
    local exit_code=$?
    set +x
    if [ $exit_code -eq 0 ]; then
        echo "PASS $test_name PASSED"
    else
        echo "FAIL $test_name FAILED (exit code: $exit_code)"
    fi
    echo ""
    return $exit_code
}

# Run all tests
echo "Starting test suite..."
echo ""

failed_tests=0

# Scheduled Repair functionality test
run_test "test_scheduled_repair.yml" "Scheduled Repair Test"
if [ $? -ne 0 ]; then ((failed_tests++)); fi

# Summary
echo "Test Summary"
echo "============"
if [ $failed_tests -eq 0 ]; then
    echo "All tests PASSED!"
    exit 0
else
    echo "$failed_tests test(s) FAILED"
    exit 1
fi
