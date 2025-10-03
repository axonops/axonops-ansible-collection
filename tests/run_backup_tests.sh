#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the tests directory to ensure relative paths work
cd "$SCRIPT_DIR"

# Default values for local testing
DEFAULT_BASE_URL="http://localhost:3000"
DEFAULT_ORG="testorg"
DEFAULT_CLUSTER="backup-apis"

# Use environment variables or defaults
BASE_URL="${AXONOPS_TEST_URL:-$DEFAULT_BASE_URL}"
ORG="${AXONOPS_TEST_ORG:-$DEFAULT_ORG}"
CLUSTER="${AXONOPS_TEST_CLUSTER:-$DEFAULT_CLUSTER}"

# Allow command line overrides
while [[ $# -gt 0 ]]; do
  case $1 in
    --url)
      BASE_URL="$2"
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
    --help)
      echo "Usage: $0 [options]"
      echo "Options:"
      echo "  --url URL       AxonOps base URL (default: $DEFAULT_BASE_URL)"
      echo "  --org ORG       Organization name (default: $DEFAULT_ORG)"
      echo "  --cluster NAME  Cluster name (default: $DEFAULT_CLUSTER)"
      echo ""
      echo "You can also set environment variables:"
      echo "  AXONOPS_TEST_URL, AXONOPS_TEST_ORG, AXONOPS_TEST_CLUSTER"
      echo ""
      echo "Examples:"
      echo "  $0                                    # Use defaults (local)"
      echo "  $0 --url https://dash.axonops.cloud   # Use SaaS"
      echo "  $0 --org myorg --cluster mycluster    # Different org/cluster"
      exit 0
      ;;
    *)
      echo "Unknown option $1"
      exit 1
      ;;
  esac
done

echo "Running AxonOps Backup Tests"
echo "=============================="
echo "Base URL: $BASE_URL"
echo "Org:      $ORG"
echo "Cluster:  $CLUSTER"
echo ""

# Function to run a test playbook with the specified parameters
run_test() {
    local playbook=$1
    local test_name=$2

    echo "Running $test_name..."
    echo "----------------------------------------"

    set -x
    ansible-playbook "$playbook" \
        -e "base_url=$BASE_URL" \
        -e "org=$ORG" \
        -e "cluster=$CLUSTER" \
        -v
    local exit_code=$?
    set +x
    if [ $exit_code -eq 0 ]; then
        echo "✅ $test_name PASSED"
    else
        echo "❌ $test_name FAILED (exit code: $exit_code)"
    fi
    echo ""
    return $exit_code
}

# Run all tests
echo "Starting test suite..."
echo ""

failed_tests=0

# Basic backup functionality test
run_test "test_backup.yml" "Basic Backup Test"
if [ $? -ne 0 ]; then ((failed_tests++)); fi

# Comprehensive backup test
run_test "test_backup_comprehensive.yml" "Comprehensive Backup Test"
if [ $? -ne 0 ]; then ((failed_tests++)); fi

# Backup edge cases test
run_test "test_backup_edge_cases.yml" "Edge Cases Test"
if [ $? -ne 0 ]; then ((failed_tests++)); fi

# Basic adaptive repair test
run_test "test_adaptive_repair.yml" "Basic Adaptive Repair Test"
if [ $? -ne 0 ]; then ((failed_tests++)); fi

# Summary
echo "Test Summary"
echo "============"
if [ $failed_tests -eq 0 ]; then
    echo "🎉 All tests PASSED!"
    exit 0
else
    echo "⚠️  $failed_tests test(s) FAILED"
    exit 1
fi
