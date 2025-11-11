#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the tests directory to ensure relative paths work
cd "$SCRIPT_DIR"

# Default values for local testing
DEFAULT_BASE_URL="http://10.0.3.118:3000"
DEFAULT_ORG="testorg"
DEFAULT_CLUSTER="test-cluster"
DEFAULT_DASHBOARD_NAME="Overview"

# Use environment variables or defaults
BASE_URL="${AXONOPS_TEST_URL:-$DEFAULT_BASE_URL}"
ORG="${AXONOPS_TEST_ORG:-$DEFAULT_ORG}"
CLUSTER="${AXONOPS_TEST_CLUSTER:-$DEFAULT_CLUSTER}"
DASHBOARD_NAME="${AXONOPS_TEST_DASHBOARD:-$DEFAULT_DASHBOARD_NAME}"

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
    --dashboard)
      DASHBOARD_NAME="$2"
      shift 2
      ;;
    --help)
      echo "Usage: $0 [options]"
      echo "Options:"
      echo "  --url URL         AxonOps base URL (default: $DEFAULT_BASE_URL)"
      echo "  --org ORG         Organization name (default: $DEFAULT_ORG)"
      echo "  --cluster NAME    Cluster name (default: $DEFAULT_CLUSTER)"
      echo "  --dashboard NAME  Dashboard name to test (default: $DEFAULT_DASHBOARD_NAME)"
      echo ""
      echo "You can also set environment variables:"
      echo "  AXONOPS_TEST_URL, AXONOPS_TEST_ORG, AXONOPS_TEST_CLUSTER, AXONOPS_TEST_DASHBOARD"
      echo ""
      echo "Required environment variables for authentication:"
      echo "  AXONOPS_TOKEN (for token auth) or AXONOPS_USERNAME and AXONOPS_PASSWORD (for basic auth)"
      echo ""
      echo "Examples:"
      echo "  $0                                          # Use defaults"
      echo "  $0 --url https://dash.axonops.cloud         # Use SaaS"
      echo "  $0 --org myorg --cluster mycluster          # Different org/cluster"
      echo "  $0 --dashboard 'System Performance'         # Different dashboard"
      exit 0
      ;;
    *)
      echo "Unknown option $1"
      exit 1
      ;;
  esac
done

# Check for required environment variables
if [ -z "$AXONOPS_TOKEN" ] && ([ -z "$AXONOPS_USERNAME" ] || [ -z "$AXONOPS_PASSWORD" ]); then
    echo "ERROR: Required environment variables not set"
    echo "Please set either:"
    echo "  1. AXONOPS_TOKEN (for token-based auth), or"
    echo "  2. AXONOPS_USERNAME and AXONOPS_PASSWORD (for basic auth)"
    echo ""
    echo "Example:"
    echo "  export AXONOPS_TOKEN='your-token'"
    echo "  $0"
    echo ""
    echo "OR"
    echo ""
    echo "  export AXONOPS_USERNAME='your-username'"
    echo "  export AXONOPS_PASSWORD='your-password'"
    echo "  $0"
    exit 1
fi

# Set PYTHONPATH for Ansible to find collection modules
export PYTHONPATH=/tmp:$PYTHONPATH

echo "Running AxonOps Dashboard Tests"
echo "================================"
echo "Base URL:  $BASE_URL"
echo "Org:       $ORG"
echo "Cluster:   $CLUSTER"
echo "Dashboard: $DASHBOARD_NAME"
if [ -n "$AXONOPS_TOKEN" ]; then
    echo "Auth:      Token"
else
    echo "Auth:      Username/Password ($AXONOPS_USERNAME)"
fi
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
        -e "dashboard_name=$DASHBOARD_NAME" \
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

# Basic dashboard save test
run_test "test_dashboard_save.yml" "Dashboard Save Test"
if [ $? -ne 0 ]; then ((failed_tests++)); fi

# Comprehensive dashboard test (save, manipulate, load)
run_test "test_dashboard_comprehensive.yml" "Comprehensive Dashboard Test"
if [ $? -ne 0 ]; then ((failed_tests++)); fi

# Summary
echo "Test Summary"
echo "============"
if [ $failed_tests -eq 0 ]; then
    echo "🎉 All tests PASSED!"
    echo ""
    echo "Dashboard files have been saved to /tmp/dashboard_tests/"
    echo "You can inspect the saved YAML files:"
    echo "  - /tmp/dashboard_tests/original_dashboard.yml"
    echo "  - /tmp/dashboard_tests/modified_dashboard.yml"
    exit 0
else
    echo "⚠️  $failed_tests test(s) FAILED"
    exit 1
fi
