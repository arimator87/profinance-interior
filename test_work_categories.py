#!/usr/bin/env python3
"""
Backend test for ProFinance Interior - Work Categories Endpoints
Tests the new work categories endpoints (public list + admin CRUD with guards).
"""
import sys
import json
import httpx
from datetime import datetime

# Configuration
BACKEND_URL = "https://join-interior-setup.preview.emergentagent.com/api"

# Test results
test_results = []

def log_test(test_name, passed, details=""):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    test_results.append({
        "test": test_name,
        "passed": passed,
        "details": details
    })
    print(f"{status}: {test_name}")
    if details:
        print(f"  Details: {details}")

def register_user(email, password="testpass123"):
    """Register a new user"""
    response = httpx.post(
        f"{BACKEND_URL}/auth/register",
        json={
            "email": email,
            "name": "Test User",
            "password": password,
            "phone": ""
        },
        timeout=30
    )
    return response

def main():
    print("=" * 80)
    print("ProFinance Interior - Work Categories Endpoints Backend Tests")
    print("=" * 80)
    print()
    
    # Store first call results for comparison
    first_call_categories = None
    first_call_ids = None
    
    # TEST 1: GET /api/work-categories (no auth) - first call
    print("\n--- TEST 1: GET /api/work-categories (no auth) - First Call ---")
    try:
        response = httpx.get(f"{BACKEND_URL}/work-categories", timeout=30)
        if response.status_code == 200:
            data = response.json()
            
            # Verify it's an array
            if not isinstance(data, list):
                log_test(
                    "GET /api/work-categories returns JSON array",
                    False,
                    f"Expected array, got {type(data)}"
                )
            else:
                # Verify at least 3 items
                if len(data) < 3:
                    log_test(
                        "GET /api/work-categories returns at least 3 items",
                        False,
                        f"Expected at least 3 items, got {len(data)}"
                    )
                else:
                    # Verify required names
                    names = [item.get("name") for item in data]
                    required_names = ["Residensial", "Komersial", "Kantor"]
                    missing_names = [n for n in required_names if n not in names]
                    
                    if missing_names:
                        log_test(
                            "GET /api/work-categories includes required categories",
                            False,
                            f"Missing categories: {missing_names}. Found: {names}"
                        )
                    else:
                        # Verify each item has required fields
                        all_valid = True
                        invalid_items = []
                        for item in data:
                            if not isinstance(item.get("id"), str):
                                all_valid = False
                                invalid_items.append(f"{item.get('name')}: id is not a string")
                            if not isinstance(item.get("name"), str):
                                all_valid = False
                                invalid_items.append(f"{item.get('name')}: name is not a string")
                            if "imageUrl" not in item:
                                all_valid = False
                                invalid_items.append(f"{item.get('name')}: missing imageUrl field")
                            if "createdAt" not in item:
                                all_valid = False
                                invalid_items.append(f"{item.get('name')}: missing createdAt field")
                        
                        if all_valid:
                            # Store for comparison
                            first_call_categories = data
                            first_call_ids = {item["name"]: item["id"] for item in data}
                            
                            log_test(
                                "GET /api/work-categories returns valid array with required categories",
                                True,
                                f"Status: 200, Count: {len(data)}, Categories: {names}, Sample ID: {data[0]['id']}"
                            )
                        else:
                            log_test(
                                "GET /api/work-categories returns valid array with required categories",
                                False,
                                f"Invalid items: {invalid_items}"
                            )
        else:
            log_test(
                "GET /api/work-categories returns valid array with required categories",
                False,
                f"Status: {response.status_code}, Body: {response.text}"
            )
    except Exception as e:
        log_test("GET /api/work-categories returns valid array with required categories", False, f"Exception: {e}")
    
    # TEST 2: GET /api/work-categories (no auth) - second call to verify idempotency
    print("\n--- TEST 2: GET /api/work-categories (no auth) - Second Call (Idempotency) ---")
    try:
        response = httpx.get(f"{BACKEND_URL}/work-categories", timeout=30)
        if response.status_code == 200:
            data = response.json()
            
            if first_call_categories is None:
                log_test(
                    "GET /api/work-categories returns same IDs (seeded once)",
                    False,
                    "First call failed, cannot compare"
                )
            else:
                # Compare IDs
                second_call_ids = {item["name"]: item["id"] for item in data}
                
                mismatches = []
                for name in first_call_ids:
                    if name not in second_call_ids:
                        mismatches.append(f"{name} missing in second call")
                    elif first_call_ids[name] != second_call_ids[name]:
                        mismatches.append(f"{name}: ID changed from {first_call_ids[name]} to {second_call_ids[name]}")
                
                if mismatches:
                    log_test(
                        "GET /api/work-categories returns same IDs (seeded once)",
                        False,
                        f"ID mismatches: {mismatches}"
                    )
                else:
                    log_test(
                        "GET /api/work-categories returns same IDs (seeded once)",
                        True,
                        f"All IDs match between calls. Sample: Residensial={first_call_ids.get('Residensial')}"
                    )
        else:
            log_test(
                "GET /api/work-categories returns same IDs (seeded once)",
                False,
                f"Status: {response.status_code}, Body: {response.text}"
            )
    except Exception as e:
        log_test("GET /api/work-categories returns same IDs (seeded once)", False, f"Exception: {e}")
    
    # TEST 3: Admin guard - Register normal user and test POST
    print("\n--- TEST 3: Admin Guard - POST /api/admin/work-categories (403 expected) ---")
    try:
        # Register a normal user
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        test_email = f"test_workcategory_{timestamp}@test.com"
        reg_response = register_user(test_email)
        
        if reg_response.status_code == 200:
            token = reg_response.json()["token"]
            print(f"Registered normal user: {test_email}")
            
            # Try to create a work category (should be blocked)
            response = httpx.post(
                f"{BACKEND_URL}/admin/work-categories",
                json={"name": "Test Cat"},
                headers={"Authorization": f"Bearer {token}"},
                timeout=30
            )
            
            if response.status_code == 403:
                log_test(
                    "POST /api/admin/work-categories blocks normal user (403)",
                    True,
                    f"Status: 403 (correctly blocked), Body: {response.text[:100]}"
                )
            else:
                log_test(
                    "POST /api/admin/work-categories blocks normal user (403)",
                    False,
                    f"Expected 403, got {response.status_code}, Body: {response.text}"
                )
        else:
            log_test(
                "POST /api/admin/work-categories blocks normal user (403)",
                False,
                f"Failed to register user: {reg_response.status_code}"
            )
    except Exception as e:
        log_test("POST /api/admin/work-categories blocks normal user (403)", False, f"Exception: {e}")
    
    # TEST 4: Admin guard - PUT /api/admin/work-categories/{id}
    print("\n--- TEST 4: Admin Guard - PUT /api/admin/work-categories/{id} (403 expected) ---")
    try:
        if 'token' in locals() and first_call_ids:
            # Get ID of "Residensial" category
            residensial_id = first_call_ids.get("Residensial")
            
            if residensial_id:
                # Try to update the category (should be blocked)
                response = httpx.put(
                    f"{BACKEND_URL}/admin/work-categories/{residensial_id}",
                    json={"name": "X"},
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=30
                )
                
                if response.status_code == 403:
                    log_test(
                        "PUT /api/admin/work-categories/{id} blocks normal user (403)",
                        True,
                        f"Status: 403 (correctly blocked), Body: {response.text[:100]}"
                    )
                else:
                    log_test(
                        "PUT /api/admin/work-categories/{id} blocks normal user (403)",
                        False,
                        f"Expected 403, got {response.status_code}, Body: {response.text}"
                    )
            else:
                log_test(
                    "PUT /api/admin/work-categories/{id} blocks normal user (403)",
                    False,
                    "Residensial category ID not found"
                )
        else:
            log_test(
                "PUT /api/admin/work-categories/{id} blocks normal user (403)",
                False,
                "No token or first_call_ids available"
            )
    except Exception as e:
        log_test("PUT /api/admin/work-categories/{id} blocks normal user (403)", False, f"Exception: {e}")
    
    # TEST 5: Admin guard - DELETE /api/admin/work-categories/{id}
    print("\n--- TEST 5: Admin Guard - DELETE /api/admin/work-categories/{id} (403 expected) ---")
    try:
        if 'token' in locals() and first_call_ids:
            # Get ID of "Residensial" category
            residensial_id = first_call_ids.get("Residensial")
            
            if residensial_id:
                # Try to delete the category (should be blocked)
                response = httpx.delete(
                    f"{BACKEND_URL}/admin/work-categories/{residensial_id}",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=30
                )
                
                if response.status_code == 403:
                    log_test(
                        "DELETE /api/admin/work-categories/{id} blocks normal user (403)",
                        True,
                        f"Status: 403 (correctly blocked), Body: {response.text[:100]}"
                    )
                else:
                    log_test(
                        "DELETE /api/admin/work-categories/{id} blocks normal user (403)",
                        False,
                        f"Expected 403, got {response.status_code}, Body: {response.text}"
                    )
            else:
                log_test(
                    "DELETE /api/admin/work-categories/{id} blocks normal user (403)",
                    False,
                    "Residensial category ID not found"
                )
        else:
            log_test(
                "DELETE /api/admin/work-categories/{id} blocks normal user (403)",
                False,
                "No token or first_call_ids available"
            )
    except Exception as e:
        log_test("DELETE /api/admin/work-categories/{id} blocks normal user (403)", False, f"Exception: {e}")
    
    # TEST 6: Verify categories list unchanged after blocked attempts
    print("\n--- TEST 6: Verify categories list unchanged after blocked attempts ---")
    try:
        response = httpx.get(f"{BACKEND_URL}/work-categories", timeout=30)
        if response.status_code == 200:
            data = response.json()
            
            if first_call_categories is None:
                log_test(
                    "Categories list unchanged after blocked attempts",
                    False,
                    "First call failed, cannot compare"
                )
            else:
                # Compare with first call
                final_ids = {item["name"]: item["id"] for item in data}
                
                # Check count
                if len(data) != len(first_call_categories):
                    log_test(
                        "Categories list unchanged after blocked attempts",
                        False,
                        f"Count changed: {len(first_call_categories)} -> {len(data)}"
                    )
                else:
                    # Check IDs
                    mismatches = []
                    for name in first_call_ids:
                        if name not in final_ids:
                            mismatches.append(f"{name} missing")
                        elif first_call_ids[name] != final_ids[name]:
                            mismatches.append(f"{name}: ID changed")
                    
                    # Check for new categories
                    new_categories = [name for name in final_ids if name not in first_call_ids]
                    if new_categories:
                        mismatches.append(f"New categories added: {new_categories}")
                    
                    if mismatches:
                        log_test(
                            "Categories list unchanged after blocked attempts",
                            False,
                            f"Changes detected: {mismatches}"
                        )
                    else:
                        log_test(
                            "Categories list unchanged after blocked attempts",
                            True,
                            f"All categories unchanged. Count: {len(data)}, Default categories still present: {list(first_call_ids.keys())}"
                        )
        else:
            log_test(
                "Categories list unchanged after blocked attempts",
                False,
                f"Status: {response.status_code}, Body: {response.text}"
            )
    except Exception as e:
        log_test("Categories list unchanged after blocked attempts", False, f"Exception: {e}")
    
    # Print summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for r in test_results if r["passed"])
    total = len(test_results)
    
    for result in test_results:
        status = "✅ PASS" if result["passed"] else "❌ FAIL"
        print(f"{status}: {result['test']}")
        if result["details"]:
            print(f"  {result['details']}")
    
    print()
    print(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
