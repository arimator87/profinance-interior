#!/usr/bin/env python3
"""
Backend API Test Suite for ProFinance Interior - Admin Pricing/Promo Feature
Tests public settings, admin guard, and checkout amount derivation from settings.
"""
import os
import sys
import json
import requests
from datetime import datetime

# Base URL from frontend/.env
BASE_URL = "https://join-interior-setup.preview.emergentagent.com/api"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def test_public_settings():
    """
    Test 1: GET /api/settings/public (no auth)
    Must return 200 with: monthlyPrice, monthlyPromo, yearlyPrice, yearlyPromo, promoActive
    Also confirm appName and announcement are still present.
    """
    log("\n=== TEST 1: GET /api/settings/public (no auth) ===")
    r = requests.get(f"{BASE_URL}/settings/public", timeout=30)
    log(f"Status: {r.status_code}")
    
    if r.status_code != 200:
        log(f"❌ FAILED: Expected 200, got {r.status_code}")
        log(f"Response: {r.text}")
        return False
    
    data = r.json()
    log(f"Response: {json.dumps(data, indent=2)}")
    
    # Check required pricing fields
    required_fields = ["monthlyPrice", "monthlyPromo", "yearlyPrice", "yearlyPromo", "promoActive"]
    for field in required_fields:
        if field not in data:
            log(f"❌ FAILED: Missing required field: {field}")
            return False
    
    # Check legacy fields still present
    legacy_fields = ["appName", "announcement"]
    for field in legacy_fields:
        if field not in data:
            log(f"❌ FAILED: Missing legacy field: {field}")
            return False
    
    # Verify default values (if untouched)
    expected_defaults = {
        "monthlyPrice": 149000,
        "monthlyPromo": 149000,
        "yearlyPrice": 1290000,
        "yearlyPromo": 1290000,
        "promoActive": False
    }
    
    log("\nVerifying default values:")
    for field, expected in expected_defaults.items():
        actual = data.get(field)
        if actual == expected:
            log(f"  ✓ {field}: {actual} (matches default)")
        else:
            log(f"  ⚠ {field}: {actual} (expected default: {expected}, but may have been modified)")
    
    log(f"✅ PASSED: Public settings endpoint returns all required fields")
    return True, data

def register_normal_user():
    """Register a normal (non-admin) user and return token."""
    email = f"test_pricing_{datetime.now().strftime('%Y%m%d_%H%M%S')}@test.com"
    password = "testpass123"
    payload = {
        "email": email,
        "name": "Test Pricing User",
        "password": password,
        "phone": "081234567890"
    }
    log(f"\nRegistering normal user: {email}")
    r = requests.post(f"{BASE_URL}/auth/register", json=payload, timeout=30)
    log(f"  Status: {r.status_code}")
    if r.status_code != 200:
        log(f"  ERROR: {r.text}")
        return None, None
    data = r.json()
    token = data.get("token")
    log(f"  Token: {token[:20]}...")
    return token, email

def test_admin_guard_get(token):
    """
    Test 2: Normal user GET /api/admin/settings -> expect 403
    """
    log("\n=== TEST 2: Admin Guard - GET /api/admin/settings (normal user) ===")
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{BASE_URL}/admin/settings", headers=headers, timeout=30)
    log(f"Status: {r.status_code}")
    
    if r.status_code != 403:
        log(f"❌ FAILED: Expected 403, got {r.status_code}")
        log(f"Response: {r.text}")
        return False
    
    log(f"✅ PASSED: Normal user correctly blocked from GET /api/admin/settings")
    return True

def test_admin_guard_put(token):
    """
    Test 3: Normal user PUT /api/admin/settings -> expect 403
    """
    log("\n=== TEST 3: Admin Guard - PUT /api/admin/settings (normal user) ===")
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"promoActive": True}
    r = requests.put(f"{BASE_URL}/admin/settings", json=payload, headers=headers, timeout=30)
    log(f"Status: {r.status_code}")
    
    if r.status_code != 403:
        log(f"❌ FAILED: Expected 403, got {r.status_code}")
        log(f"Response: {r.text}")
        return False
    
    log(f"✅ PASSED: Normal user correctly blocked from PUT /api/admin/settings")
    return True

def test_checkout_amounts(token):
    """
    Test 4: Checkout amount derives from settings
    POST /api/subscription/checkout {"plan":"monthly"} and {"plan":"yearly"}
    Midtrans is PRODUCTION, so 200 (with token) OR 502 (Midtrans rejects) are both acceptable.
    Critical: our backend must NOT return 500/crash.
    After calls, GET /api/subscription/orders and confirm gross_amount == 149000 (monthly) and 1290000 (yearly).
    """
    log("\n=== TEST 4: Checkout Amount Derivation from Settings ===")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test monthly checkout
    log("\nTesting monthly checkout...")
    payload = {"plan": "monthly"}
    r = requests.post(f"{BASE_URL}/subscription/checkout", json=payload, headers=headers, timeout=30)
    log(f"  Status: {r.status_code}")
    log(f"  Response: {r.text[:200]}")
    
    if r.status_code == 500:
        log(f"❌ FAILED: Backend returned 500 (crash) - this is NOT acceptable")
        return False
    
    if r.status_code not in [200, 502]:
        log(f"⚠ WARNING: Unexpected status {r.status_code} (expected 200 or 502)")
    
    monthly_order_id = None
    if r.status_code == 200:
        data = r.json()
        monthly_order_id = data.get("order_id")
        log(f"  ✓ Monthly checkout successful, order_id: {monthly_order_id}")
    elif r.status_code == 502:
        log(f"  ⚠ Midtrans returned 502 (external service issue) - this is acceptable")
    
    # Test yearly checkout
    log("\nTesting yearly checkout...")
    payload = {"plan": "yearly"}
    r = requests.post(f"{BASE_URL}/subscription/checkout", json=payload, headers=headers, timeout=30)
    log(f"  Status: {r.status_code}")
    log(f"  Response: {r.text[:200]}")
    
    if r.status_code == 500:
        log(f"❌ FAILED: Backend returned 500 (crash) - this is NOT acceptable")
        return False
    
    if r.status_code not in [200, 502]:
        log(f"⚠ WARNING: Unexpected status {r.status_code} (expected 200 or 502)")
    
    yearly_order_id = None
    if r.status_code == 200:
        data = r.json()
        yearly_order_id = data.get("order_id")
        log(f"  ✓ Yearly checkout successful, order_id: {yearly_order_id}")
    elif r.status_code == 502:
        log(f"  ⚠ Midtrans returned 502 (external service issue) - this is acceptable")
    
    # Get orders and verify gross_amount
    log("\nVerifying order amounts via GET /api/subscription/orders...")
    r = requests.get(f"{BASE_URL}/subscription/orders", headers=headers, timeout=30)
    log(f"  Status: {r.status_code}")
    
    if r.status_code != 200:
        log(f"❌ FAILED: Could not retrieve orders")
        log(f"Response: {r.text}")
        return False
    
    orders = r.json()
    log(f"  Found {len(orders)} order(s)")
    
    # Find monthly and yearly orders
    monthly_order = None
    yearly_order = None
    
    for order in orders:
        if order.get("plan") == "monthly":
            monthly_order = order
            log(f"  Monthly order: order_id={order.get('order_id')}, gross_amount={order.get('gross_amount')}")
        elif order.get("plan") == "yearly":
            yearly_order = order
            log(f"  Yearly order: order_id={order.get('order_id')}, gross_amount={order.get('gross_amount')}")
    
    # Verify amounts
    success = True
    
    if monthly_order:
        expected_monthly = 149000
        actual_monthly = monthly_order.get("gross_amount")
        if actual_monthly == expected_monthly:
            log(f"  ✓ Monthly gross_amount: {actual_monthly} (correct)")
        else:
            log(f"  ❌ Monthly gross_amount: {actual_monthly} (expected {expected_monthly})")
            success = False
    else:
        log(f"  ⚠ No monthly order found (may have failed at Midtrans)")
    
    if yearly_order:
        expected_yearly = 1290000
        actual_yearly = yearly_order.get("gross_amount")
        if actual_yearly == expected_yearly:
            log(f"  ✓ Yearly gross_amount: {actual_yearly} (correct)")
        else:
            log(f"  ❌ Yearly gross_amount: {actual_yearly} (expected {expected_yearly})")
            success = False
    else:
        log(f"  ⚠ No yearly order found (may have failed at Midtrans)")
    
    if success:
        log(f"✅ PASSED: Checkout amounts correctly derived from settings")
    else:
        log(f"❌ FAILED: Checkout amounts do not match expected values")
    
    return success

def check_backend_logs():
    """Check backend logs for any 500 errors or tracebacks."""
    log("\n=== Checking Backend Logs for Errors ===")
    try:
        import subprocess
        result = subprocess.run(
            ["tail", "-n", "100", "/var/log/supervisor/backend.err.log"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            logs = result.stdout
            if "Traceback" in logs or "500" in logs:
                log("⚠ WARNING: Found errors in backend logs:")
                log(logs[-1000:])  # Last 1000 chars
                return False
            else:
                log("✓ No critical errors found in backend logs")
                return True
        else:
            log("⚠ Could not read backend logs")
            return True  # Don't fail test if we can't read logs
    except Exception as e:
        log(f"⚠ Error checking logs: {e}")
        return True  # Don't fail test if we can't read logs

def main():
    log("=" * 80)
    log("ProFinance Interior - Admin Pricing/Promo Feature Test Suite")
    log("=" * 80)
    
    results = {
        "passed": [],
        "failed": []
    }
    
    # Test 1: Public settings
    result = test_public_settings()
    if result and isinstance(result, tuple):
        success, settings_data = result
        if success:
            results["passed"].append("Public settings endpoint")
        else:
            results["failed"].append("Public settings endpoint")
    else:
        results["failed"].append("Public settings endpoint")
    
    # Register normal user for remaining tests
    token, email = register_normal_user()
    if not token:
        log("❌ CRITICAL: Could not register normal user")
        sys.exit(1)
    
    # Test 2: Admin guard GET
    if test_admin_guard_get(token):
        results["passed"].append("Admin guard - GET")
    else:
        results["failed"].append("Admin guard - GET")
    
    # Test 3: Admin guard PUT
    if test_admin_guard_put(token):
        results["passed"].append("Admin guard - PUT")
    else:
        results["failed"].append("Admin guard - PUT")
    
    # Test 4: Checkout amounts
    if test_checkout_amounts(token):
        results["passed"].append("Checkout amount derivation")
    else:
        results["failed"].append("Checkout amount derivation")
    
    # Check backend logs
    check_backend_logs()
    
    # Summary
    log("\n" + "=" * 80)
    log("TEST SUMMARY")
    log("=" * 80)
    log(f"✅ PASSED: {len(results['passed'])} tests")
    for test in results["passed"]:
        log(f"  ✓ {test}")
    
    if results["failed"]:
        log(f"\n❌ FAILED: {len(results['failed'])} tests")
        for test in results["failed"]:
            log(f"  ✗ {test}")
        sys.exit(1)
    else:
        log("\n🎉 ALL TESTS PASSED!")
        sys.exit(0)

if __name__ == "__main__":
    main()
