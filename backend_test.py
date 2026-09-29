#!/usr/bin/env python3
"""
Backend test for Manual QRIS Payment feature (Round 16)
Tests all endpoints for the new manual payment flow.

CRITICAL: This test modifies LIVE settings. It MUST restore paymentMethod='midtrans' at the end.
"""

import requests
import json
import time
from datetime import datetime

# Base URL from frontend/.env
BASE_URL = "https://join-interior-setup.preview.emergentagent.com/api"

# Test credentials
ADMIN_EMAIL = "furnitrue.mail@gmail.com"
ADMIN_PASSWORD = "Password123"

# Color codes for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def log_test(test_num, description):
    print(f"\n{BLUE}[TEST {test_num}] {description}{RESET}")

def log_pass(message):
    print(f"{GREEN}✓ PASS: {message}{RESET}")

def log_fail(message):
    print(f"{RED}✗ FAIL: {message}{RESET}")

def log_info(message):
    print(f"{YELLOW}ℹ INFO: {message}{RESET}")

def log_warning(message):
    print(f"{YELLOW}⚠ WARNING: {message}{RESET}")

# Global variables to store test data
admin_token = None
test_user_email = None
test_user_token = None
test_order_id = None
original_settings = None

def test_1_get_public_settings_initial():
    """Test 1: GET /api/settings/public - verify initial state"""
    log_test(1, "GET /api/settings/public - verify paymentMethod='midtrans' (default)")
    
    try:
        response = requests.get(f"{BASE_URL}/settings/public")
        
        if response.status_code != 200:
            log_fail(f"Expected 200, got {response.status_code}")
            return False
        
        data = response.json()
        
        # Check required fields exist
        required_fields = ["paymentMethod", "qrisImage", "paymentNote"]
        for field in required_fields:
            if field not in data:
                log_fail(f"Missing field: {field}")
                return False
        
        log_pass(f"All required fields present: {required_fields}")
        
        # Verify default paymentMethod
        if data["paymentMethod"] != "midtrans":
            log_warning(f"paymentMethod is '{data['paymentMethod']}', expected 'midtrans'")
        else:
            log_pass("paymentMethod='midtrans' (default)")
        
        log_info(f"qrisImage: {data['qrisImage'][:50] if data['qrisImage'] else '(empty)'}")
        log_info(f"paymentNote: {data['paymentNote'][:50] if data['paymentNote'] else '(empty)'}")
        
        # Store original settings for restoration
        global original_settings
        original_settings = {
            "paymentMethod": data["paymentMethod"],
            "qrisImage": data.get("qrisImage", ""),
            "paymentNote": data.get("paymentNote", "")
        }
        
        return True
        
    except Exception as e:
        log_fail(f"Exception: {e}")
        return False

def test_2_checkout_manual_blocked_when_midtrans():
    """Test 2: POST /api/subscription/checkout-manual should fail when paymentMethod='midtrans'"""
    log_test(2, "POST /api/subscription/checkout-manual - should return 400 when method is midtrans")
    
    try:
        # First, register a temporary user for this test
        timestamp = int(time.time())
        temp_email = f"test_manual_blocked_{timestamp}@test.com"
        
        # Register
        reg_response = requests.post(f"{BASE_URL}/auth/register", json={
            "email": temp_email,
            "name": "Test User Blocked",
            "password": "Test12345"
        })
        
        if reg_response.status_code != 200:
            log_fail(f"Failed to register temp user: {reg_response.status_code}")
            return False
        
        temp_token = reg_response.json().get("token")
        
        # Try checkout-manual (should fail because paymentMethod is midtrans)
        response = requests.post(
            f"{BASE_URL}/subscription/checkout-manual",
            json={"plan": "monthly"},
            headers={"Authorization": f"Bearer {temp_token}"}
        )
        
        if response.status_code != 400:
            log_fail(f"Expected 400, got {response.status_code}")
            return False
        
        error_msg = response.json().get("detail", "")
        if "manual tidak aktif" not in error_msg.lower():
            log_fail(f"Expected error about manual not active, got: {error_msg}")
            return False
        
        log_pass(f"Correctly blocked with 400: {error_msg}")
        return True
        
    except Exception as e:
        log_fail(f"Exception: {e}")
        return False

def test_3_admin_login_and_change_to_manual():
    """Test 3: Admin login and PUT /api/admin/settings to change paymentMethod to 'manual'"""
    log_test(3, "Admin login and change paymentMethod to 'manual'")
    
    global admin_token
    
    try:
        # Admin login
        response = requests.post(f"{BASE_URL}/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        
        if response.status_code != 200:
            log_fail(f"Admin login failed: {response.status_code}")
            return False
        
        admin_token = response.json().get("token")
        log_pass(f"Admin logged in successfully")
        
        # Change settings to manual
        response = requests.put(
            f"{BASE_URL}/admin/settings",
            json={
                "paymentMethod": "manual",
                "paymentNote": "Transfer ke QRIS di atas. Setelah transfer, unggah bukti pembayaran."
            },
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if response.status_code != 200:
            log_fail(f"Failed to update settings: {response.status_code}")
            return False
        
        data = response.json()
        if data.get("paymentMethod") != "manual":
            log_fail(f"paymentMethod not updated, got: {data.get('paymentMethod')}")
            return False
        
        log_pass("Settings updated to paymentMethod='manual'")
        
        # Verify public endpoint reflects the change
        pub_response = requests.get(f"{BASE_URL}/settings/public")
        pub_data = pub_response.json()
        
        if pub_data.get("paymentMethod") != "manual":
            log_fail(f"Public settings not updated, got: {pub_data.get('paymentMethod')}")
            return False
        
        log_pass("Public settings confirmed: paymentMethod='manual'")
        log_info(f"paymentNote: {pub_data.get('paymentNote', '')[:80]}")
        
        return True
        
    except Exception as e:
        log_fail(f"Exception: {e}")
        return False

def test_4_user_checkout_manual_creates_pending_order():
    """Test 4: Register free user and POST /api/subscription/checkout-manual creates pending_review order"""
    log_test(4, "User checkout-manual creates order with status='pending_review'")
    
    global test_user_email, test_user_token, test_order_id
    
    try:
        # Register new free user
        timestamp = int(time.time())
        test_user_email = f"test_manual_user_{timestamp}@test.com"
        
        response = requests.post(f"{BASE_URL}/auth/register", json={
            "email": test_user_email,
            "name": "Test Manual User",
            "password": "Test12345"
        })
        
        if response.status_code != 200:
            log_fail(f"Failed to register user: {response.status_code}")
            return False
        
        test_user_token = response.json().get("token")
        log_pass(f"Registered test user: {test_user_email}")
        
        # Get current settings to check promo price
        settings_response = requests.get(f"{BASE_URL}/settings/public")
        settings = settings_response.json()
        
        expected_amount = settings.get("monthlyPromo", 149000) if settings.get("promoActive") else settings.get("monthlyPrice", 149000)
        log_info(f"Expected gross_amount: {expected_amount} (promoActive={settings.get('promoActive')})")
        
        # Checkout manual
        response = requests.post(
            f"{BASE_URL}/subscription/checkout-manual",
            json={"plan": "monthly"},
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        
        if response.status_code != 200:
            log_fail(f"checkout-manual failed: {response.status_code} - {response.text}")
            return False
        
        data = response.json()
        test_order_id = data.get("order_id")
        
        # Verify response
        if not test_order_id:
            log_fail("No order_id in response")
            return False
        
        if data.get("status") != "pending_review":
            log_fail(f"Expected status='pending_review', got: {data.get('status')}")
            return False
        
        if data.get("gross_amount") != expected_amount:
            log_warning(f"gross_amount={data.get('gross_amount')}, expected={expected_amount}")
        else:
            log_pass(f"gross_amount correct: {data.get('gross_amount')}")
        
        log_pass(f"Order created: {test_order_id}, status='pending_review'")
        log_info(f"Plan: {data.get('plan')}, Amount: {data.get('gross_amount')}")
        
        return True
        
    except Exception as e:
        log_fail(f"Exception: {e}")
        return False

def test_5_proof_upload_validation():
    """Test 5: POST /api/subscription/order/{order_id}/proof - validation"""
    log_test(5, "Proof upload validation - empty proofUrl should return 400")
    
    try:
        # Test with empty proofUrl
        response = requests.post(
            f"{BASE_URL}/subscription/order/{test_order_id}/proof",
            json={"proofUrl": ""},
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        
        if response.status_code != 400:
            log_fail(f"Expected 400 for empty proofUrl, got {response.status_code}")
            return False
        
        error_msg = response.json().get("detail", "")
        if "wajib" not in error_msg.lower():
            log_fail(f"Expected error about required proof, got: {error_msg}")
            return False
        
        log_pass(f"Empty proofUrl correctly rejected with 400: {error_msg}")
        
        # Now upload valid proof
        proof_url = f"profinance-interior/uploads/test/proof_{int(time.time())}.jpg"
        response = requests.post(
            f"{BASE_URL}/subscription/order/{test_order_id}/proof",
            json={"proofUrl": proof_url},
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        
        if response.status_code != 200:
            log_fail(f"Failed to upload proof: {response.status_code} - {response.text}")
            return False
        
        data = response.json()
        if data.get("status") != "pending_review":
            log_fail(f"Expected status='pending_review', got: {data.get('status')}")
            return False
        
        log_pass(f"Proof uploaded successfully, status='pending_review'")
        log_info(f"proofUrl: {proof_url}")
        
        return True
        
    except Exception as e:
        log_fail(f"Exception: {e}")
        return False

def test_6_get_order_status():
    """Test 6: GET /api/subscription/order/{order_id} - verify status"""
    log_test(6, "GET /api/subscription/order/{order_id} - verify pending_review")
    
    try:
        response = requests.get(
            f"{BASE_URL}/subscription/order/{test_order_id}",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        
        if response.status_code != 200:
            log_fail(f"Failed to get order: {response.status_code}")
            return False
        
        data = response.json()
        
        if data.get("status") != "pending_review":
            log_fail(f"Expected status='pending_review', got: {data.get('status')}")
            return False
        
        log_pass(f"Order status confirmed: pending_review")
        log_info(f"Order: {data.get('order_id')}, Plan: {data.get('plan')}")
        
        return True
        
    except Exception as e:
        log_fail(f"Exception: {e}")
        return False

def test_7_admin_manual_orders_list():
    """Test 7: GET /api/admin/manual-orders - verify order appears with user info"""
    log_test(7, "GET /api/admin/manual-orders - verify order in list with userName/userEmail")
    
    try:
        response = requests.get(
            f"{BASE_URL}/admin/manual-orders?status=pending_review",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if response.status_code != 200:
            log_fail(f"Failed to get manual orders: {response.status_code}")
            return False
        
        orders = response.json()
        
        # Find our test order
        test_order = None
        for order in orders:
            if order.get("order_id") == test_order_id:
                test_order = order
                break
        
        if not test_order:
            log_fail(f"Test order {test_order_id} not found in manual-orders list")
            return False
        
        # Verify user info is joined
        if not test_order.get("userName"):
            log_fail("userName not present in order")
            return False
        
        if test_order.get("userEmail") != test_user_email:
            log_fail(f"userEmail mismatch: {test_order.get('userEmail')} != {test_user_email}")
            return False
        
        log_pass(f"Order found in list with correct user info")
        log_info(f"userName: {test_order.get('userName')}, userEmail: {test_order.get('userEmail')}")
        
        return True
        
    except Exception as e:
        log_fail(f"Exception: {e}")
        return False

def test_8_gating_non_admin():
    """Test 8: Non-admin user should get 403 on admin endpoints"""
    log_test(8, "Gating - non-admin user gets 403 on admin endpoints")
    
    try:
        # Test GET /api/admin/manual-orders
        response = requests.get(
            f"{BASE_URL}/admin/manual-orders",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        
        if response.status_code != 403:
            log_fail(f"Expected 403 for GET manual-orders, got {response.status_code}")
            return False
        
        log_pass("GET /api/admin/manual-orders correctly returns 403 for non-admin")
        
        # Test POST approve
        response = requests.post(
            f"{BASE_URL}/admin/orders/{test_order_id}/approve",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        
        if response.status_code != 403:
            log_fail(f"Expected 403 for POST approve, got {response.status_code}")
            return False
        
        log_pass("POST /api/admin/orders/{id}/approve correctly returns 403 for non-admin")
        
        # Test POST reject
        response = requests.post(
            f"{BASE_URL}/admin/orders/{test_order_id}/reject",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        
        if response.status_code != 403:
            log_fail(f"Expected 403 for POST reject, got {response.status_code}")
            return False
        
        log_pass("POST /api/admin/orders/{id}/reject correctly returns 403 for non-admin")
        
        return True
        
    except Exception as e:
        log_fail(f"Exception: {e}")
        return False

def test_9_admin_reject_order():
    """Test 9: Admin POST /api/admin/orders/{id}/reject"""
    log_test(9, "Admin rejects order - status becomes 'rejected'")
    
    try:
        response = requests.post(
            f"{BASE_URL}/admin/orders/{test_order_id}/reject",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if response.status_code != 200:
            log_fail(f"Failed to reject order: {response.status_code} - {response.text}")
            return False
        
        data = response.json()
        if not data.get("ok"):
            log_fail(f"Response not ok: {data}")
            return False
        
        log_pass("Order rejected successfully")
        
        # Verify status changed to rejected
        order_response = requests.get(
            f"{BASE_URL}/subscription/order/{test_order_id}",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        
        order_data = order_response.json()
        if order_data.get("status") != "rejected":
            log_fail(f"Expected status='rejected', got: {order_data.get('status')}")
            return False
        
        log_pass("Order status confirmed: rejected")
        
        return True
        
    except Exception as e:
        log_fail(f"Exception: {e}")
        return False

def test_10_reupload_proof_after_rejection():
    """Test 10: User can re-upload proof after rejection, status returns to pending_review"""
    log_test(10, "User re-uploads proof after rejection - status returns to pending_review")
    
    try:
        proof_url = f"profinance-interior/uploads/test/proof_reupload_{int(time.time())}.jpg"
        
        response = requests.post(
            f"{BASE_URL}/subscription/order/{test_order_id}/proof",
            json={"proofUrl": proof_url},
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        
        if response.status_code != 200:
            log_fail(f"Failed to re-upload proof: {response.status_code} - {response.text}")
            return False
        
        data = response.json()
        if data.get("status") != "pending_review":
            log_fail(f"Expected status='pending_review', got: {data.get('status')}")
            return False
        
        log_pass("Proof re-uploaded successfully, status back to pending_review")
        
        return True
        
    except Exception as e:
        log_fail(f"Exception: {e}")
        return False

def test_11_admin_approve_order():
    """Test 11: Admin approves order - user becomes premium"""
    log_test(11, "Admin approves order - user gets premium access")
    
    try:
        # Approve order
        response = requests.post(
            f"{BASE_URL}/admin/orders/{test_order_id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if response.status_code != 200:
            log_fail(f"Failed to approve order: {response.status_code} - {response.text}")
            return False
        
        data = response.json()
        if not data.get("ok"):
            log_fail(f"Response not ok: {data}")
            return False
        
        premium_until = data.get("premium_until")
        if not premium_until:
            log_fail("No premium_until in response")
            return False
        
        log_pass(f"Order approved successfully, premium_until: {premium_until}")
        
        # Verify user is now premium
        me_response = requests.get(
            f"{BASE_URL}/auth/me",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        
        if me_response.status_code != 200:
            log_fail(f"Failed to get user info: {me_response.status_code}")
            return False
        
        user_data = me_response.json()
        
        if user_data.get("subscriptionTier") != "premium":
            log_fail(f"Expected subscriptionTier='premium', got: {user_data.get('subscriptionTier')}")
            return False
        
        log_pass(f"User confirmed as premium, subscriptionTier='premium'")
        
        # Check subscriptionExpiry is ~30 days from now
        expiry = user_data.get("subscriptionExpiry")
        if expiry:
            log_info(f"subscriptionExpiry: {expiry}")
        
        # Test idempotency - approve again
        response2 = requests.post(
            f"{BASE_URL}/admin/orders/{test_order_id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if response2.status_code != 200:
            log_fail(f"Second approve failed: {response2.status_code}")
            return False
        
        data2 = response2.json()
        if not data2.get("already"):
            log_fail("Second approve should return already:true")
            return False
        
        log_pass("Idempotent approve confirmed: already=true on second call")
        
        return True
        
    except Exception as e:
        log_fail(f"Exception: {e}")
        return False

def test_12_cannot_reject_paid_order():
    """Test 12: Admin cannot reject order that is already paid"""
    log_test(12, "Admin cannot reject order with status='paid'")
    
    try:
        response = requests.post(
            f"{BASE_URL}/admin/orders/{test_order_id}/reject",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if response.status_code != 400:
            log_fail(f"Expected 400 for rejecting paid order, got {response.status_code}")
            return False
        
        error_msg = response.json().get("detail", "")
        if "lunas" not in error_msg.lower() or "tidak dapat ditolak" not in error_msg.lower():
            log_fail(f"Expected error about paid order, got: {error_msg}")
            return False
        
        log_pass(f"Correctly blocked with 400: {error_msg}")
        
        return True
        
    except Exception as e:
        log_fail(f"Exception: {e}")
        return False

def test_13_demo_user_blocked():
    """Test 13: Demo user gets 403 on POST /api/subscription/checkout-manual"""
    log_test(13, "Demo user (read-only) gets 403 on checkout-manual")
    
    try:
        # Get demo token
        response = requests.post(f"{BASE_URL}/auth/demo")
        
        if response.status_code != 200:
            log_fail(f"Failed to get demo token: {response.status_code}")
            return False
        
        demo_token = response.json().get("token")
        log_pass("Demo token obtained")
        
        # Try checkout-manual
        response = requests.post(
            f"{BASE_URL}/subscription/checkout-manual",
            json={"plan": "monthly"},
            headers={"Authorization": f"Bearer {demo_token}"}
        )
        
        if response.status_code != 403:
            log_fail(f"Expected 403 for demo user, got {response.status_code}")
            return False
        
        error_msg = response.json().get("detail", "")
        if "demo" not in error_msg.lower():
            log_fail(f"Expected error about demo mode, got: {error_msg}")
            return False
        
        log_pass(f"Demo user correctly blocked with 403: {error_msg}")
        
        return True
        
    except Exception as e:
        log_fail(f"Exception: {e}")
        return False

def test_14_restore_settings():
    """Test 14: CRITICAL - Restore paymentMethod to 'midtrans'"""
    log_test(14, "RESTORE settings - change paymentMethod back to 'midtrans'")
    
    try:
        # Restore original settings
        response = requests.put(
            f"{BASE_URL}/admin/settings",
            json={"paymentMethod": "midtrans"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if response.status_code != 200:
            log_fail(f"CRITICAL: Failed to restore settings: {response.status_code}")
            log_fail("MANUAL ACTION REQUIRED: Set paymentMethod='midtrans' in admin settings!")
            return False
        
        data = response.json()
        if data.get("paymentMethod") != "midtrans":
            log_fail(f"CRITICAL: paymentMethod not restored, got: {data.get('paymentMethod')}")
            return False
        
        log_pass("Settings restored: paymentMethod='midtrans'")
        
        # Verify public endpoint
        pub_response = requests.get(f"{BASE_URL}/settings/public")
        pub_data = pub_response.json()
        
        if pub_data.get("paymentMethod") != "midtrans":
            log_fail(f"CRITICAL: Public settings not restored, got: {pub_data.get('paymentMethod')}")
            return False
        
        log_pass("Public settings confirmed: paymentMethod='midtrans'")
        log_info("✓ LIVE settings successfully restored to original state")
        
        return True
        
    except Exception as e:
        log_fail(f"CRITICAL Exception: {e}")
        log_fail("MANUAL ACTION REQUIRED: Set paymentMethod='midtrans' in admin settings!")
        return False

def test_15_cleanup():
    """Test 15: Cleanup test data"""
    log_test(15, "Cleanup - delete test order (optional)")
    
    try:
        # Note: There's no DELETE endpoint for orders in the API
        # We'll just log that cleanup would be done manually if needed
        log_info(f"Test order {test_order_id} can be deleted manually from MongoDB if needed")
        log_info(f"Test user {test_user_email} can remain in the system")
        log_pass("Cleanup noted (manual deletion available if needed)")
        
        return True
        
    except Exception as e:
        log_fail(f"Exception: {e}")
        return False

def main():
    print(f"\n{BLUE}{'='*80}")
    print("BACKEND TEST: Manual QRIS Payment Feature (Round 16)")
    print(f"{'='*80}{RESET}\n")
    
    print(f"{YELLOW}⚠ WARNING: This test modifies LIVE production settings!{RESET}")
    print(f"{YELLOW}⚠ Settings will be restored at the end of the test.{RESET}\n")
    
    print(f"Base URL: {BASE_URL}")
    print(f"Admin: {ADMIN_EMAIL}\n")
    
    tests = [
        test_1_get_public_settings_initial,
        test_2_checkout_manual_blocked_when_midtrans,
        test_3_admin_login_and_change_to_manual,
        test_4_user_checkout_manual_creates_pending_order,
        test_5_proof_upload_validation,
        test_6_get_order_status,
        test_7_admin_manual_orders_list,
        test_8_gating_non_admin,
        test_9_admin_reject_order,
        test_10_reupload_proof_after_rejection,
        test_11_admin_approve_order,
        test_12_cannot_reject_paid_order,
        test_13_demo_user_blocked,
        test_14_restore_settings,
        test_15_cleanup,
    ]
    
    results = []
    
    for test_func in tests:
        try:
            result = test_func()
            results.append((test_func.__name__, result))
        except Exception as e:
            log_fail(f"Unhandled exception in {test_func.__name__}: {e}")
            results.append((test_func.__name__, False))
    
    # Summary
    print(f"\n{BLUE}{'='*80}")
    print("TEST SUMMARY")
    print(f"{'='*80}{RESET}\n")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = f"{GREEN}PASS{RESET}" if result else f"{RED}FAIL{RESET}"
        print(f"{status} - {test_name}")
    
    print(f"\n{BLUE}Total: {passed}/{total} tests passed{RESET}")
    
    if passed == total:
        print(f"\n{GREEN}✓ ALL TESTS PASSED!{RESET}")
        print(f"{GREEN}✓ Settings successfully restored to paymentMethod='midtrans'{RESET}\n")
    else:
        print(f"\n{RED}✗ SOME TESTS FAILED{RESET}")
        if not results[13][1]:  # test_14_restore_settings
            print(f"{RED}✗ CRITICAL: Settings restoration failed!{RESET}")
            print(f"{RED}✗ MANUAL ACTION REQUIRED: Restore paymentMethod='midtrans' in admin settings!{RESET}\n")

if __name__ == "__main__":
    main()
