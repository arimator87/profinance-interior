#!/usr/bin/env python3
"""
Backend Test Suite - Round 17
Test NEW endpoint: GET /api/admin/manual-orders/count
"""

import requests
import json
import time
from datetime import datetime

# Base URL - using internal localhost
BASE_URL = "http://localhost:8001/api"

# Admin credentials
ADMIN_EMAIL = "furnitrue.mail@gmail.com"
ADMIN_PASSWORD = "Password123"

# Test results
test_results = []

def log_test(test_name, passed, details=""):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    result = f"{status} - {test_name}"
    if details:
        result += f": {details}"
    test_results.append(result)
    print(result)
    return passed

def test_manual_orders_count():
    """Test GET /api/admin/manual-orders/count endpoint"""
    
    print("\n" + "="*80)
    print("ROUND 17: Testing GET /api/admin/manual-orders/count")
    print("="*80 + "\n")
    
    # Generate unique timestamp for test users
    timestamp = int(time.time())
    
    # ========================================================================
    # TEST 1: GET /api/admin/manual-orders/count without token -> 401
    # ========================================================================
    print("\n[TEST 1] GET /api/admin/manual-orders/count without auth -> expect 401")
    try:
        response = requests.get(f"{BASE_URL}/admin/manual-orders/count")
        if response.status_code == 401:
            log_test("Test 1: Unauthenticated access", True, "401 Unauthorized")
        else:
            log_test("Test 1: Unauthenticated access", False, f"Expected 401, got {response.status_code}")
    except Exception as e:
        log_test("Test 1: Unauthenticated access", False, f"Exception: {str(e)}")
    
    # ========================================================================
    # TEST 2: Register regular user -> GET count with regular user token -> 403
    # ========================================================================
    print("\n[TEST 2] Register regular user -> GET count -> expect 403")
    regular_user_email = f"test_count_regular_{timestamp}@test.com"
    regular_user_password = "TestPass123"
    regular_user_token = None
    
    try:
        # Register regular user
        reg_response = requests.post(f"{BASE_URL}/auth/register", json={
            "email": regular_user_email,
            "password": regular_user_password,
            "name": "Test Regular User"
        })
        
        if reg_response.status_code == 200:
            regular_user_token = reg_response.json().get("token")
            print(f"   ✓ Registered regular user: {regular_user_email}")
            
            # Try to access count endpoint with regular user token
            headers = {"Authorization": f"Bearer {regular_user_token}"}
            count_response = requests.get(f"{BASE_URL}/admin/manual-orders/count", headers=headers)
            
            if count_response.status_code == 403:
                log_test("Test 2: Regular user access", True, "403 Forbidden")
            else:
                log_test("Test 2: Regular user access", False, f"Expected 403, got {count_response.status_code}")
        else:
            log_test("Test 2: Regular user access", False, f"Failed to register user: {reg_response.status_code}")
    except Exception as e:
        log_test("Test 2: Regular user access", False, f"Exception: {str(e)}")
    
    # ========================================================================
    # TEST 3: Admin login -> GET count -> 200 {count: N}
    # ========================================================================
    print("\n[TEST 3] Admin login -> GET count -> expect 200 with count")
    admin_token = None
    initial_count = None
    
    try:
        # Admin login
        login_response = requests.post(f"{BASE_URL}/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        
        if login_response.status_code == 200:
            admin_token = login_response.json().get("token")
            print(f"   ✓ Admin logged in: {ADMIN_EMAIL}")
            
            # GET count as admin
            headers = {"Authorization": f"Bearer {admin_token}"}
            count_response = requests.get(f"{BASE_URL}/admin/manual-orders/count", headers=headers)
            
            if count_response.status_code == 200:
                count_data = count_response.json()
                if "count" in count_data and isinstance(count_data["count"], int):
                    initial_count = count_data["count"]
                    log_test("Test 3: Admin get count", True, f"200 OK, count={initial_count}")
                else:
                    log_test("Test 3: Admin get count", False, f"Response missing 'count' field or not int: {count_data}")
            else:
                log_test("Test 3: Admin get count", False, f"Expected 200, got {count_response.status_code}")
        else:
            log_test("Test 3: Admin get count", False, f"Admin login failed: {login_response.status_code}")
            return  # Cannot continue without admin token
    except Exception as e:
        log_test("Test 3: Admin get count", False, f"Exception: {str(e)}")
        return
    
    # ========================================================================
    # TEST 4: Create manual order -> count should increase by +1
    # ========================================================================
    print("\n[TEST 4] Create manual order (pending_review) -> count should increase by +1")
    test_user_email = f"test_count_user_{timestamp}@test.com"
    test_user_password = "TestPass123"
    test_user_token = None
    order_id_1 = None
    
    try:
        # Register test user
        reg_response = requests.post(f"{BASE_URL}/auth/register", json={
            "email": test_user_email,
            "password": test_user_password,
            "name": "Test Count User"
        })
        
        if reg_response.status_code == 200:
            test_user_token = reg_response.json().get("token")
            print(f"   ✓ Registered test user: {test_user_email}")
            
            # Create manual order (paymentMethod is currently 'manual' per user request)
            headers = {"Authorization": f"Bearer {test_user_token}"}
            checkout_response = requests.post(f"{BASE_URL}/subscription/checkout-manual", 
                                             json={"plan": "monthly"}, 
                                             headers=headers)
            
            if checkout_response.status_code == 200:
                order_data = checkout_response.json()
                order_id_1 = order_data.get("order_id")
                status = order_data.get("status")
                print(f"   ✓ Created manual order: {order_id_1}, status={status}")
                
                if status == "pending_review":
                    # Check count as admin
                    admin_headers = {"Authorization": f"Bearer {admin_token}"}
                    count_response = requests.get(f"{BASE_URL}/admin/manual-orders/count", headers=admin_headers)
                    
                    if count_response.status_code == 200:
                        new_count = count_response.json().get("count")
                        expected_count = initial_count + 1
                        
                        if new_count == expected_count:
                            log_test("Test 4: Count after create order", True, f"count increased from {initial_count} to {new_count}")
                        else:
                            log_test("Test 4: Count after create order", False, f"Expected count={expected_count}, got {new_count}")
                    else:
                        log_test("Test 4: Count after create order", False, f"Failed to get count: {count_response.status_code}")
                else:
                    log_test("Test 4: Count after create order", False, f"Order status is {status}, expected pending_review")
            else:
                log_test("Test 4: Count after create order", False, f"Failed to create order: {checkout_response.status_code} - {checkout_response.text}")
        else:
            log_test("Test 4: Count after create order", False, f"Failed to register user: {reg_response.status_code}")
    except Exception as e:
        log_test("Test 4: Count after create order", False, f"Exception: {str(e)}")
    
    # ========================================================================
    # TEST 5: Admin approve order -> count should return to initial value
    # ========================================================================
    print("\n[TEST 5] Admin approve order -> count should return to initial value")
    
    if order_id_1 and admin_token:
        try:
            admin_headers = {"Authorization": f"Bearer {admin_token}"}
            approve_response = requests.post(f"{BASE_URL}/admin/orders/{order_id_1}/approve", 
                                            headers=admin_headers)
            
            if approve_response.status_code == 200:
                print(f"   ✓ Approved order: {order_id_1}")
                
                # Check count
                count_response = requests.get(f"{BASE_URL}/admin/manual-orders/count", headers=admin_headers)
                
                if count_response.status_code == 200:
                    new_count = count_response.json().get("count")
                    
                    if new_count == initial_count:
                        log_test("Test 5: Count after approve", True, f"count returned to {initial_count}")
                    else:
                        log_test("Test 5: Count after approve", False, f"Expected count={initial_count}, got {new_count}")
                else:
                    log_test("Test 5: Count after approve", False, f"Failed to get count: {count_response.status_code}")
            else:
                log_test("Test 5: Count after approve", False, f"Failed to approve order: {approve_response.status_code}")
        except Exception as e:
            log_test("Test 5: Count after approve", False, f"Exception: {str(e)}")
    else:
        log_test("Test 5: Count after approve", False, "Skipped - no order_id or admin_token")
    
    # ========================================================================
    # TEST 6: Create another order -> count +1 -> reject -> count returns to initial
    # ========================================================================
    print("\n[TEST 6] Create another order -> count +1 -> reject -> count returns to initial")
    order_id_2 = None
    
    if test_user_token and admin_token:
        try:
            # Create another manual order
            headers = {"Authorization": f"Bearer {test_user_token}"}
            checkout_response = requests.post(f"{BASE_URL}/subscription/checkout-manual", 
                                             json={"plan": "monthly"}, 
                                             headers=headers)
            
            if checkout_response.status_code == 200:
                order_data = checkout_response.json()
                order_id_2 = order_data.get("order_id")
                print(f"   ✓ Created second manual order: {order_id_2}")
                
                # Check count increased
                admin_headers = {"Authorization": f"Bearer {admin_token}"}
                count_response = requests.get(f"{BASE_URL}/admin/manual-orders/count", headers=admin_headers)
                
                if count_response.status_code == 200:
                    count_after_create = count_response.json().get("count")
                    expected_count = initial_count + 1
                    
                    if count_after_create == expected_count:
                        print(f"   ✓ Count increased to {count_after_create}")
                        
                        # Reject the order
                        reject_response = requests.post(f"{BASE_URL}/admin/orders/{order_id_2}/reject", 
                                                       headers=admin_headers)
                        
                        if reject_response.status_code == 200:
                            print(f"   ✓ Rejected order: {order_id_2}")
                            
                            # Check count returned to initial
                            count_response = requests.get(f"{BASE_URL}/admin/manual-orders/count", headers=admin_headers)
                            
                            if count_response.status_code == 200:
                                final_count = count_response.json().get("count")
                                
                                if final_count == initial_count:
                                    log_test("Test 6: Count after reject", True, f"count returned to {initial_count}")
                                else:
                                    log_test("Test 6: Count after reject", False, f"Expected count={initial_count}, got {final_count}")
                            else:
                                log_test("Test 6: Count after reject", False, f"Failed to get count: {count_response.status_code}")
                        else:
                            log_test("Test 6: Count after reject", False, f"Failed to reject order: {reject_response.status_code}")
                    else:
                        log_test("Test 6: Count after reject", False, f"Count after create: expected {expected_count}, got {count_after_create}")
                else:
                    log_test("Test 6: Count after reject", False, f"Failed to get count: {count_response.status_code}")
            else:
                log_test("Test 6: Count after reject", False, f"Failed to create second order: {checkout_response.status_code}")
        except Exception as e:
            log_test("Test 6: Count after reject", False, f"Exception: {str(e)}")
    else:
        log_test("Test 6: Count after reject", False, "Skipped - no test_user_token or admin_token")
    
    # ========================================================================
    # TEST 7: Cleanup test data
    # ========================================================================
    print("\n[TEST 7] Cleanup test data")
    print(f"   ℹ Test users created: {regular_user_email}, {test_user_email}")
    print(f"   ℹ Test orders created: {order_id_1} (approved), {order_id_2} (rejected)")
    print(f"   ℹ Test users can remain, test orders can be manually deleted from orders collection if needed")
    log_test("Test 7: Cleanup", True, "Test data noted for optional cleanup")
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed_count = sum(1 for r in test_results if "✅ PASS" in r)
    total_count = len(test_results)
    
    for result in test_results:
        print(result)
    
    print(f"\nTotal: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("\n✅ ALL TESTS PASSED")
        return True
    else:
        print(f"\n❌ {total_count - passed_count} TEST(S) FAILED")
        return False

if __name__ == "__main__":
    try:
        success = test_manual_orders_count()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        exit(1)
