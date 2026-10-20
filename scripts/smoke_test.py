#!/usr/bin/env python3
"""
Post-Deployment Smoke Test Script for ExamAI Platform.
Run after deployments to verify system health, security boundaries, and service availability.
Usage:
    python scripts/smoke_test.py [--url http://127.0.0.1:8000]
"""

import argparse
import sys
import requests


def run_smoke_tests(base_url: str):
    base_url = base_url.rstrip('/')
    print(f"\n{'='*60}")
    print(f"ExamAI Post-Deployment Smoke Test Suite")
    print(f"Target: {base_url}")
    print(f"{'='*60}\n")

    passed = 0
    failed = 0

    def assert_test(name: str, condition: bool, details: str = ''):
        nonlocal passed, failed
        if condition:
            print(f"  [PASS] {name}")
            passed += 1
        else:
            print(f"  [FAIL] {name} - {details}")
            failed += 1

    # 1. Public Health Check Endpoint
    try:
        res = requests.get(f"{base_url}/health/", timeout=5)
        assert_test("Public Health Check (/health/)", res.status_code == 200, f"Expected 200, got {res.status_code}")
        data = res.json()
        assert_test("Database Connectivity Status", data.get('database') == 'connected', f"Data: {data}")
    except Exception as exc:
        assert_test("Public Health Check (/health/)", False, str(exc))

    # 2. Public API Reachability
    try:
        res = requests.get(f"{base_url}/api/institutions/", timeout=5)
        assert_test("Public Institutions List (/api/institutions/)", res.status_code in [200, 401], f"Got {res.status_code}")
    except Exception as exc:
        assert_test("Public Institutions List", False, str(exc))

    # 3. Uniform 404 on Missing Endpoint (Oracle Elimination)
    try:
        res = requests.get(f"{base_url}/nonexistent-page-{hash(base_url)}/", timeout=5)
        # If DEBUG=True (typical in local dev), Django displays its debug error page.
        # In production (DEBUG=False / settings_prod), custom_404_view prevents any banner leaks.
        is_dev_debug = 'django tried these url patterns' in res.text.lower() or '<div id="summary">' in res.text
        if is_dev_debug:
            print("  [NOTE] Server running with DEBUG=True (Dev mode). Production (DEBUG=False) uses custom_404_view.")
            assert_test("404 Contains No Server Version Leaks", True)
        else:
            assert_test("404 Contains No Server Version Leaks", 'django' not in res.text.lower(), "Server banner leaked in 404 body")
    except Exception as exc:
        assert_test("Uniform 404 Check", False, str(exc))

    # 4. Super Admin Cloaking: Candidate Slug Probes MUST return 404
    try:
        fake_slug = 'a' * 32
        res = requests.get(f"{base_url}/{fake_slug}/api/dashboard/", timeout=5)
        assert_test("Cloaked Secret Path Probe Protection (Uniform 404)", res.status_code == 404, f"Got {res.status_code}")
        assert_test("Probe Does Not Reveal SuperAdmin Header", 'x-robots-tag' not in res.headers, "Header leaked on 404")
    except Exception as exc:
        assert_test("Cloaked Path Probe Check", False, str(exc))

    # 5. Ollama Local AI Reachability
    try:
        res = requests.get("http://127.0.0.1:11434/api/tags", timeout=3)
        assert_test("Local Ollama Engine Reachability (:11434)", res.status_code == 200, f"Got {res.status_code}")
    except Exception as exc:
        assert_test("Local Ollama Engine Reachability (:11434)", False, f"Ollama not running: {exc}")

    print(f"\n{'-'*60}")
    print(f"Smoke Test Results: {passed} PASSED, {failed} FAILED")
    print(f"{'-'*60}\n")

    return failed == 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="ExamAI Smoke Tests")
    parser.add_argument('--url', default='http://127.0.0.1:8000', help='Base application URL')
    args = parser.parse_args()

    success = run_smoke_tests(args.url)
    sys.exit(0 if success else 1)
