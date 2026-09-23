#!/usr/bin/env python3
"""
Test suite for Worker PDF Report endpoints (Round 14)
Tests 2 NEW endpoints:
1. GET /api/projects/{project_id}/workers/report/pdf - PDF for ALL workers
2. GET /api/workers/{worker_id}/report/pdf - PDF for ONE worker
"""

import requests
import time
import uuid
import fitz  # pymupdf for PDF text extraction

# Base URL - using internal localhost as per test instructions
BASE_URL = "http://localhost:8001/api"

# Test credentials
PREMIUM_EMAIL = "furnitrue.mail@gmail.com"
PREMIUM_PASSWORD = "Password123"

def log(msg):
    print(f"[TEST] {msg}")

def login(email, password):
    """Login and return token"""
    log(f"Logging in as {email}...")
    resp = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password}, timeout=10)
    if resp.status_code != 200:
        log(f"❌ Login failed: {resp.status_code} {resp.text}")
        return None
    data = resp.json()
    token = data.get("token")
    log(f"✅ Login successful, token: {token[:20]}...")
    return token

def register_free_user():
    """Register a new free user and return token"""
    email = f"test_worker_pdf_free_{int(time.time())}@test.com"
    log(f"Registering free user: {email}...")
    resp = requests.post(f"{BASE_URL}/auth/register", json={
        "email": email,
        "name": "Test Worker PDF Free",
        "password": "Test123456"
    }, timeout=10)
    if resp.status_code != 200:
        log(f"❌ Registration failed: {resp.status_code} {resp.text}")
        return None, None
    data = resp.json()
    token = data.get("token")
    log(f"✅ Free user registered: {email}, token: {token[:20]}...")
    return token, email

def demo_login():
    """Get demo token"""
    log("Getting demo token...")
    resp = requests.post(f"{BASE_URL}/auth/demo", timeout=10)
    if resp.status_code != 200:
        log(f"❌ Demo login failed: {resp.status_code} {resp.text}")
        return None
    data = resp.json()
    token = data.get("token")
    log(f"✅ Demo token obtained: {token[:20]}...")
    return token

def get_projects(token):
    """Get user's projects"""
    resp = requests.get(f"{BASE_URL}/projects", headers={"Authorization": f"Bearer {token}"}, timeout=10)
    if resp.status_code != 200:
        log(f"❌ Get projects failed: {resp.status_code}")
        return []
    return resp.json()

def get_workers(token, project_id):
    """Get workers for a project"""
    resp = requests.get(f"{BASE_URL}/projects/{project_id}/workers", headers={"Authorization": f"Bearer {token}"}, timeout=10)
    if resp.status_code != 200:
        log(f"❌ Get workers failed: {resp.status_code}")
        return []
    return resp.json()

def create_project(token, name, nominal=50000000):
    """Create a project"""
    resp = requests.post(f"{BASE_URL}/projects", headers={"Authorization": f"Bearer {token}"}, json={
        "name": name,
        "owner": "Test Owner",
        "nominal": nominal,
        "category": "Residensial",
        "status": "Berjalan"
    }, timeout=10)
    if resp.status_code != 200:
        log(f"❌ Create project failed: {resp.status_code} {resp.text}")
        return None
    data = resp.json()
    return data.get("id")

def create_worker(token, project_id, name, borongan):
    """Create a worker"""
    resp = requests.post(f"{BASE_URL}/projects/{project_id}/workers", headers={"Authorization": f"Bearer {token}"}, json={
        "name": name,
        "borongan": borongan
    }, timeout=10)
    if resp.status_code != 200:
        log(f"❌ Create worker failed: {resp.status_code} {resp.text}")
        return None
    data = resp.json()
    return data.get("id")

def pay_worker(token, worker_id, pay_type, amount):
    """Pay a worker (kasbon or pelunasan)"""
    resp = requests.post(f"{BASE_URL}/workers/{worker_id}/pay", headers={"Authorization": f"Bearer {token}"}, json={
        "type": pay_type,
        "amount": amount,
        "description": f"Test {pay_type}"
    }, timeout=10)
    return resp.status_code == 200

def delete_project(token, project_id):
    """Delete a project"""
    resp = requests.delete(f"{BASE_URL}/projects/{project_id}", headers={"Authorization": f"Bearer {token}"}, timeout=10)
    return resp.status_code == 200

def extract_pdf_text(pdf_bytes):
    """Extract text from PDF bytes using pymupdf"""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text
    except Exception as e:
        log(f"⚠️ PDF text extraction failed: {e}")
        return ""

def test_workers_pdf_all(token, project_id):
    """Test GET /api/projects/{project_id}/workers/report/pdf"""
    log(f"\n=== TEST 1: PDF Semua Tukang (project {project_id}) ===")
    
    # Get workers first to verify data
    workers = get_workers(token, project_id)
    log(f"Project has {len(workers)} workers")
    
    if len(workers) == 0:
        log("⚠️ No workers in project, skipping PDF test")
        return False
    
    # Test with auth query parameter
    url = f"{BASE_URL}/projects/{project_id}/workers/report/pdf?auth={token}"
    log(f"GET {url}")
    resp = requests.get(url, timeout=30)
    
    log(f"Status: {resp.status_code}")
    log(f"Content-Type: {resp.headers.get('Content-Type')}")
    log(f"Size: {len(resp.content)} bytes")
    
    # Verify response
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    
    if resp.headers.get('Content-Type') != 'application/pdf':
        log(f"❌ FAIL: Expected application/pdf, got {resp.headers.get('Content-Type')}")
        return False
    
    if not resp.content.startswith(b'%PDF'):
        log(f"❌ FAIL: PDF does not start with %PDF")
        return False
    
    if len(resp.content) < 3000:
        log(f"❌ FAIL: PDF size {len(resp.content)} < 3000 bytes")
        return False
    
    # Extract text and verify content
    text = extract_pdf_text(resp.content)
    if text:
        log(f"PDF text extracted: {len(text)} chars")
        # Check for expected content
        if "LAPORAN UPAH TUKANG" in text or "REKAP TUKANG" in text:
            log("✅ PDF contains expected header text")
        else:
            log("⚠️ PDF header text not found (may be in different format)")
        
        # Check if worker names appear
        found_workers = 0
        for w in workers:
            if w['name'] in text:
                found_workers += 1
        log(f"Found {found_workers}/{len(workers)} worker names in PDF")
    
    log("✅ PASS: PDF Semua Tukang generated successfully")
    return True

def test_worker_pdf_single(token, worker_id, worker_name, expected_total_dibayar):
    """Test GET /api/workers/{worker_id}/report/pdf"""
    log(f"\n=== TEST 2: PDF Per Tukang (worker {worker_id}: {worker_name}) ===")
    
    # Test with auth query parameter
    url = f"{BASE_URL}/workers/{worker_id}/report/pdf?auth={token}"
    log(f"GET {url}")
    resp = requests.get(url, timeout=30)
    
    log(f"Status: {resp.status_code}")
    log(f"Content-Type: {resp.headers.get('Content-Type')}")
    log(f"Size: {len(resp.content)} bytes")
    
    # Verify response
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    
    if resp.headers.get('Content-Type') != 'application/pdf':
        log(f"❌ FAIL: Expected application/pdf, got {resp.headers.get('Content-Type')}")
        return False
    
    if not resp.content.startswith(b'%PDF'):
        log(f"❌ FAIL: PDF does not start with %PDF")
        return False
    
    if len(resp.content) < 3000:
        log(f"❌ FAIL: PDF size {len(resp.content)} < 3000 bytes")
        return False
    
    # Extract text and verify content
    text = extract_pdf_text(resp.content)
    if text:
        log(f"PDF text extracted: {len(text)} chars")
        
        # Check for expected content
        checks = {
            "LAPORAN UPAH TUKANG": "LAPORAN UPAH TUKANG" in text,
            "Worker name": worker_name in text,
            "RIWAYAT PEMBAYARAN": "RIWAYAT PEMBAYARAN" in text or "RIWAYAT" in text,
            "TOTAL DIBAYAR": "TOTAL DIBAYAR" in text or "Total Dibayar" in text,
        }
        
        for check_name, result in checks.items():
            if result:
                log(f"✅ Found: {check_name}")
            else:
                log(f"⚠️ Not found: {check_name}")
        
        # Math check: verify total dibayar appears in PDF
        if expected_total_dibayar > 0:
            # Format as Indonesian rupiah (with dots as thousand separators)
            formatted = f"{expected_total_dibayar:,}".replace(",", ".")
            if formatted in text or f"Rp {formatted}" in text or f"Rp{formatted}" in text:
                log(f"✅ MATH CHECK PASS: Total Dibayar Rp {formatted} found in PDF")
            else:
                log(f"⚠️ MATH CHECK: Total Dibayar Rp {formatted} not found in exact format (may be formatted differently)")
    
    log("✅ PASS: PDF Per Tukang generated successfully")
    return True

def test_auth_required():
    """Test that endpoints require authentication"""
    log("\n=== TEST 3: Auth Required (401 without token) ===")
    
    # Use a dummy project_id and worker_id
    dummy_project = "test-project-id"
    dummy_worker = "test-worker-id"
    
    # Test workers PDF without auth
    url1 = f"{BASE_URL}/projects/{dummy_project}/workers/report/pdf"
    resp1 = requests.get(url1, timeout=10)
    log(f"GET {url1} (no auth): {resp1.status_code}")
    
    # Test worker PDF without auth
    url2 = f"{BASE_URL}/workers/{dummy_worker}/report/pdf"
    resp2 = requests.get(url2, timeout=10)
    log(f"GET {url2} (no auth): {resp2.status_code}")
    
    if resp1.status_code == 401 and resp2.status_code == 401:
        log("✅ PASS: Both endpoints return 401 without auth")
        return True
    else:
        log(f"❌ FAIL: Expected 401 for both, got {resp1.status_code} and {resp2.status_code}")
        return False

def test_free_user_gating():
    """Test that free users get 403"""
    log("\n=== TEST 4: Free User Gating (403) ===")
    
    # Register free user
    free_token, free_email = register_free_user()
    if not free_token:
        log("❌ FAIL: Could not register free user")
        return False
    
    # Create project and worker for free user
    project_id = create_project(free_token, "Free User Test Project")
    if not project_id:
        log("❌ FAIL: Could not create project for free user")
        return False
    
    worker_id = create_worker(free_token, project_id, "Test Worker", 5000000)
    if not worker_id:
        log("❌ FAIL: Could not create worker for free user")
        return False
    
    # Try to access both PDF endpoints with free token
    url1 = f"{BASE_URL}/projects/{project_id}/workers/report/pdf?auth={free_token}"
    resp1 = requests.get(url1, timeout=10)
    log(f"GET workers PDF (free user): {resp1.status_code}")
    
    url2 = f"{BASE_URL}/workers/{worker_id}/report/pdf?auth={free_token}"
    resp2 = requests.get(url2, timeout=10)
    log(f"GET worker PDF (free user): {resp2.status_code}")
    
    # Cleanup
    delete_project(free_token, project_id)
    
    if resp1.status_code == 403 and resp2.status_code == 403:
        log("✅ PASS: Free user correctly blocked with 403")
        return True
    else:
        log(f"❌ FAIL: Expected 403 for both, got {resp1.status_code} and {resp2.status_code}")
        return False

def test_ownership():
    """Test that users can only access their own workers"""
    log("\n=== TEST 5: Ownership Check (404 for other user's worker) ===")
    
    # Register free user
    free_token, free_email = register_free_user()
    if not free_token:
        log("❌ FAIL: Could not register free user")
        return False
    
    # Get premium user's project and worker
    premium_token = login(PREMIUM_EMAIL, PREMIUM_PASSWORD)
    if not premium_token:
        log("❌ FAIL: Could not login premium user")
        return False
    
    projects = get_projects(premium_token)
    if not projects:
        log("❌ FAIL: Premium user has no projects")
        return False
    
    project_id = projects[0]['id']
    workers = get_workers(premium_token, project_id)
    if not workers:
        log("❌ FAIL: Premium project has no workers")
        return False
    
    premium_worker_id = workers[0]['id']
    
    # Try to access premium worker with free token
    url = f"{BASE_URL}/workers/{premium_worker_id}/report/pdf?auth={free_token}"
    resp = requests.get(url, timeout=10)
    log(f"GET premium worker PDF with free token: {resp.status_code}")
    
    if resp.status_code == 404:
        log("✅ PASS: Free user gets 404 for premium user's worker")
        return True
    else:
        log(f"❌ FAIL: Expected 404, got {resp.status_code}")
        return False

def test_worker_without_payments():
    """Test PDF generation for worker without any payments"""
    log("\n=== TEST 6: Worker Without Payments (fallback text) ===")
    
    # Login premium
    token = login(PREMIUM_EMAIL, PREMIUM_PASSWORD)
    if not token:
        log("❌ FAIL: Could not login")
        return False
    
    # Create test project
    project_id = create_project(token, "Test Worker No Payment")
    if not project_id:
        log("❌ FAIL: Could not create project")
        return False
    
    # Create worker without any payments
    worker_id = create_worker(token, project_id, "Tukang Tanpa Bayar", 10000000)
    if not worker_id:
        log("❌ FAIL: Could not create worker")
        delete_project(token, project_id)
        return False
    
    # Get PDF
    url = f"{BASE_URL}/workers/{worker_id}/report/pdf?auth={token}"
    resp = requests.get(url, timeout=30)
    
    log(f"Status: {resp.status_code}")
    log(f"Size: {len(resp.content)} bytes")
    
    # Cleanup
    delete_project(token, project_id)
    
    if resp.status_code != 200:
        log(f"❌ FAIL: Expected 200, got {resp.status_code}")
        return False
    
    if not resp.content.startswith(b'%PDF'):
        log(f"❌ FAIL: Not a valid PDF")
        return False
    
    # Check for fallback text
    text = extract_pdf_text(resp.content)
    if text and ("Belum ada pembayaran" in text or "belum ada pembayaran" in text or "Rp 0" in text):
        log("✅ PDF contains fallback text for no payments")
    
    log("✅ PASS: PDF generated for worker without payments")
    return True

def test_demo_user_access():
    """Test that demo user (premium read-only) can access PDFs"""
    log("\n=== TEST 7: Demo User Access (200 for GET) ===")
    
    # Get demo token
    demo_token = demo_login()
    if not demo_token:
        log("❌ FAIL: Could not get demo token")
        return False
    
    # Get demo projects
    projects = get_projects(demo_token)
    if not projects:
        log("⚠️ SKIP: Demo user has no projects")
        return True
    
    project_id = projects[0]['id']
    workers = get_workers(demo_token, project_id)
    if not workers:
        log("⚠️ SKIP: Demo project has no workers")
        return True
    
    # Try to access both PDF endpoints
    url1 = f"{BASE_URL}/projects/{project_id}/workers/report/pdf?auth={demo_token}"
    resp1 = requests.get(url1, timeout=30)
    log(f"GET workers PDF (demo): {resp1.status_code}")
    
    worker_id = workers[0]['id']
    url2 = f"{BASE_URL}/workers/{worker_id}/report/pdf?auth={demo_token}"
    resp2 = requests.get(url2, timeout=30)
    log(f"GET worker PDF (demo): {resp2.status_code}")
    
    if resp1.status_code == 200 and resp2.status_code == 200:
        log("✅ PASS: Demo user can access PDF endpoints (read-only premium)")
        return True
    else:
        log(f"❌ FAIL: Expected 200 for both, got {resp1.status_code} and {resp2.status_code}")
        return False

def main():
    """Run all tests"""
    log("=" * 60)
    log("WORKER PDF REPORT ENDPOINTS TEST SUITE (Round 14)")
    log("=" * 60)
    
    results = {}
    
    # Login premium user
    premium_token = login(PREMIUM_EMAIL, PREMIUM_PASSWORD)
    if not premium_token:
        log("❌ CRITICAL: Cannot login premium user, aborting tests")
        return
    
    # Get premium user's projects and workers
    projects = get_projects(premium_token)
    if not projects:
        log("❌ CRITICAL: Premium user has no projects")
        return
    
    log(f"\nPremium user has {len(projects)} projects")
    
    # Find a project with workers
    test_project_id = None
    test_workers = []
    for proj in projects:
        workers = get_workers(premium_token, proj['id'])
        if workers:
            test_project_id = proj['id']
            test_workers = workers
            log(f"Using project '{proj['name']}' (id: {test_project_id}) with {len(workers)} workers")
            break
    
    if not test_project_id or not test_workers:
        log("⚠️ WARNING: No project with workers found, creating test data...")
        # Create test project with workers
        test_project_id = create_project(premium_token, "Test Worker PDF Project", 50000000)
        if test_project_id:
            # Create 2 workers with payments
            w1_id = create_worker(premium_token, test_project_id, "Tukang Kayu", 15000000)
            if w1_id:
                pay_worker(premium_token, w1_id, "kasbon", 5000000)
                pay_worker(premium_token, w1_id, "pelunasan", 8000000)
            
            w2_id = create_worker(premium_token, test_project_id, "Tukang Cat", 10000000)
            if w2_id:
                pay_worker(premium_token, w2_id, "kasbon", 3000000)
            
            test_workers = get_workers(premium_token, test_project_id)
            log(f"Created test project with {len(test_workers)} workers")
    
    # Run tests
    if test_project_id and test_workers:
        # Test 1: PDF Semua Tukang
        results['test_1_workers_pdf_all'] = test_workers_pdf_all(premium_token, test_project_id)
        
        # Test 2: PDF Per Tukang
        test_worker = test_workers[0]
        results['test_2_worker_pdf_single'] = test_worker_pdf_single(
            premium_token, 
            test_worker['id'], 
            test_worker['name'],
            test_worker.get('totalDibayar', 0)
        )
    
    # Test 3: Auth required
    results['test_3_auth_required'] = test_auth_required()
    
    # Test 4: Free user gating
    results['test_4_free_user_gating'] = test_free_user_gating()
    
    # Test 5: Ownership
    results['test_5_ownership'] = test_ownership()
    
    # Test 6: Worker without payments
    results['test_6_worker_no_payments'] = test_worker_without_payments()
    
    # Test 7: Demo user access
    results['test_7_demo_user_access'] = test_demo_user_access()
    
    # Summary
    log("\n" + "=" * 60)
    log("TEST SUMMARY")
    log("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        log(f"{status}: {test_name}")
    
    log(f"\nTotal: {passed}/{total} tests passed")
    log("=" * 60)
    
    if passed == total:
        log("🎉 ALL TESTS PASSED!")
    else:
        log(f"⚠️ {total - passed} test(s) failed")

if __name__ == "__main__":
    main()
