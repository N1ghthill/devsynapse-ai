#!/usr/bin/env python3
"""
Test runner for DevSynapse AI
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path


def run_tests(test_type="all", verbose=False, coverage=False):
    """Run tests with specified options"""
    
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    # Build pytest command
    cmd = ["pytest"]
    
    if verbose:
        cmd.append("-v")
    
    if coverage:
        cmd.extend(["--cov=.", "--cov-report=term-missing", "--cov-report=html"])
    
    # Select test type
    if test_type == "unit":
        cmd.append("tests/unit")
    elif test_type == "integration":
        cmd.append("tests/integration")
    elif test_type == "fast":
        cmd.append("-m", "not slow")
    elif test_type == "all":
        cmd.append("tests/")
    else:
        print(f"Unknown test type: {test_type}")
        return False
    
    print(f"Running tests: {' '.join(cmd)}")
    print("-" * 80)
    
    # Run tests
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print("\n✅ All tests passed!")
        return True
    else:
        print("\n❌ Some tests failed")
        return False

def run_specific_test(test_file, test_function=None):
    """Run a specific test file or function"""
    
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    cmd = ["pytest", "-v"]
    
    if test_function:
        cmd.append(f"{test_file}::{test_function}")
    else:
        cmd.append(test_file)
    
    print(f"Running specific test: {' '.join(cmd)}")
    print("-" * 80)
    
    result = subprocess.run(cmd)
    return result.returncode == 0

def generate_coverage_report():
    """Generate HTML coverage report"""
    
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    cmd = ["pytest", "--cov=.", "--cov-report=html", "--cov-report=term-missing", "tests/"]
    
    print("Generating coverage report...")
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print("\n📊 Coverage report generated in htmlcov/")
        print("Open htmlcov/index.html in your browser to view the report")
        return True
    else:
        print("\nFailed to generate coverage report")
        return False

def main():
    parser = argparse.ArgumentParser(description="DevSynapse AI Test Runner")
    parser.add_argument(
        "test_type",
        nargs="?",
        default="all",
        choices=["all", "unit", "integration", "fast", "coverage"],
        help="Type of tests to run"
    )
    parser.add_argument(
        "--file",
        help="Run specific test file"
    )
    parser.add_argument(
        "--function",
        help="Run specific test function (requires --file)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )
    
    args = parser.parse_args()
    
    if args.file:
        success = run_specific_test(args.file, args.function)
    elif args.test_type == "coverage":
        success = generate_coverage_report()
    else:
        success = run_tests(args.test_type, args.verbose, coverage=False)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()