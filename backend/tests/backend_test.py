"""ProFinance Interior backend tests - comprehensive API coverage."""
import os
import time
import uuid
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://join-interior-setup.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"

PREMIUM_EMAIL = "furnitrue.mail@gmail.com"
PREMIUM_PASS = "Password123"


# ---------- Fixtures ----------
@pytest.fixture(scope="session")
def premium_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": PREMIUM_EMAIL, "password": PREMIUM_PASS})
    assert r.status_code == 200, f"premium login failed: {r.status_code} {r.text}"
    token = r.json()["token"]
    s.headers.update({"Authorization": f"Bearer {token}"})
    s.token = token
    return s


@pytest.fixture(scope="session")
def fresh_user():
    """Create a new free-tier user."""
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    s = requests.Session()
    r = s.post(f"{API}/auth/register", json={"email": email, "name": "TEST User", "password": "Password123"})
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    data = r.json()
    token = data["token"]
    s.headers.update({"Authorization": f"Bearer {token}"})
    s.token = token
    s.email = email
    s.user = data["user"]
    return s


# ---------- Auth ----------
class TestAuth:
    def test_register_new_user_is_free(self, fresh_user):
        assert fresh_user.user["subscriptionTier"] == "free"
        assert fresh_user.user["email"] == fresh_user.email

    def test_premium_login(self, premium_session):
        r = premium_session.get(f"{API}/auth/me")
        assert r.status_code == 200
        me = r.json()
        assert me["email"] == PREMIUM_EMAIL
        assert me["subscriptionTier"] == "premium"

    def test_bearer_auth_works(self, premium_session):
        r = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {premium_session.token}"})
        assert r.status_code == 200

    def test_cookie_auth_works(self, premium_session):
        r = requests.get(f"{API}/auth/me", cookies={"session_token": premium_session.token})
        assert r.status_code == 200
        assert r.json()["email"] == PREMIUM_EMAIL

    def test_login_bad_password(self):
        r = requests.post(f"{API}/auth/login", json={"email": PREMIUM_EMAIL, "password": "wrongpass"})
        assert r.status_code in (400, 401)


# ---------- Seed / Dashboard / Projects ----------
class TestSeedAndDashboard:
    def test_seed_demo_creates_three(self, fresh_user):
        r = fresh_user.post(f"{API}/seed-demo")
        assert r.status_code == 200, r.text
        assert r.json()["created"] == 3

    def test_second_seed_returns_400(self, fresh_user):
        r = fresh_user.post(f"{API}/seed-demo")
        assert r.status_code == 400

    def test_dashboard_matches_project_sums(self, fresh_user):
        dash = fresh_user.get(f"{API}/dashboard").json()
        projects = fresh_user.get(f"{API}/projects").json()
        assert len(projects) == 3
        total_balance = sum(p["summary"]["balance"] for p in projects)
        total_sisa = sum(p["summary"]["sisaTagihan"] for p in projects)
        total_budget = sum(p["summary"]["nominal"] for p in projects)
        assert dash["saldoBersih"] == total_balance
        assert dash["totalSisaTagihan"] == total_sisa
        assert dash["totalBudget"] == total_budget
        assert dash["projectCount"] == 3

    def test_project_summary_formulas(self, fresh_user):
        projects = fresh_user.get(f"{API}/projects").json()
        for p in projects:
            s = p["summary"]
            assert s["balance"] == s["totalIn"] - s["totalOut"]
            if s["nominal"]:
                assert abs(s["marginPct"] - round(s["balance"] / s["nominal"] * 100, 2)) < 0.01
                assert abs(s["realisasiPct"] - round(s["totalIn"] / s["nominal"] * 100, 2)) < 0.01


# ---------- Transactions & sisaTagihan ----------
class TestTransactions:
    def test_lainnya_category_does_not_reduce_sisa(self, fresh_user):
        projects = fresh_user.get(f"{API}/projects").json()
        pid = projects[0]["id"]
        before = fresh_user.get(f"{API}/projects/{pid}").json()["summary"]
        # Add 'in' with category Lainnya - should NOT reduce sisaTagihan
        r = fresh_user.post(f"{API}/projects/{pid}/transactions", json={
            "type": "in", "amount": 5000000, "category": "Lainnya", "description": "TEST lainnya"
        })
        assert r.status_code == 200
        after = fresh_user.get(f"{API}/projects/{pid}").json()["summary"]
        assert after["sisaTagihan"] == before["sisaTagihan"], "Lainnya must not decrease sisaTagihan"
        assert after["totalIn"] == before["totalIn"] + 5000000

    def test_termin_category_reduces_sisa(self, fresh_user):
        projects = fresh_user.get(f"{API}/projects").json()
        pid = projects[0]["id"]
        before = fresh_user.get(f"{API}/projects/{pid}").json()["summary"]
        r = fresh_user.post(f"{API}/projects/{pid}/transactions", json={
            "type": "in", "amount": 3000000, "category": "Termin", "description": "TEST termin"
        })
        assert r.status_code == 200
        after = fresh_user.get(f"{API}/projects/{pid}").json()["summary"]
        assert after["sisaTagihan"] == before["sisaTagihan"] - 3000000

    def test_create_project_and_transactions(self, fresh_user):
        r = fresh_user.post(f"{API}/projects", json={
            "name": "TEST Project", "owner": "TEST", "nominal": 100000000, "category": "Residensial"
        })
        assert r.status_code == 200
        pid = r.json()["id"]
        assert r.json()["summary"]["nominal"] == 100000000
        fresh_user.post(f"{API}/projects/{pid}/transactions", json={"type": "in", "amount": 30000000, "category": "Downpayment"})
        fresh_user.post(f"{API}/projects/{pid}/transactions", json={"type": "out", "amount": 10000000, "category": "Material"})
        s = fresh_user.get(f"{API}/projects/{pid}").json()["summary"]
        assert s["totalIn"] == 30000000
        assert s["totalOut"] == 10000000
        assert s["balance"] == 20000000
        assert s["sisaTagihan"] == 70000000


# ---------- Workers ----------
class TestWorkers:
    def test_worker_pay_creates_transaction_with_correct_category(self, fresh_user):
        projects = fresh_user.get(f"{API}/projects").json()
        pid = projects[0]["id"]
        wr = fresh_user.post(f"{API}/projects/{pid}/workers", json={"name": "TEST Pak Budi", "borongan": 50000000})
        assert wr.status_code == 200
        wid = wr.json()["id"]

        # kasbon
        k = fresh_user.post(f"{API}/workers/{wid}/pay", json={"type": "kasbon", "amount": 10000000})
        assert k.status_code == 200
        assert k.json()["totalKasbon"] == 10000000
        # pelunasan
        p = fresh_user.post(f"{API}/workers/{wid}/pay", json={"type": "pelunasan", "amount": 5000000})
        assert p.status_code == 200
        assert p.json()["totalPelunasan"] == 5000000
        assert p.json()["sisaHutang"] == 50000000 - 10000000 - 5000000

        # verify tx categories
        txs = fresh_user.get(f"{API}/projects/{pid}/transactions").json()
        cats = [t["category"] for t in txs]
        assert "Kasbon Tukang TEST Pak Budi" in cats
        assert "Pelunasan Tukang TEST Pak Budi" in cats


# ---------- Premium gating ----------
class TestPremiumGating:
    def test_free_user_blocked_from_premium_endpoints(self, fresh_user):
        projects = fresh_user.get(f"{API}/projects").json()
        pid = projects[0]["id"]
        r1 = fresh_user.post(f"{API}/projects/{pid}/workitems", json={"name": "X", "nilai": 1000})
        r2 = fresh_user.get(f"{API}/projects/{pid}/report")
        r3 = fresh_user.get(f"{API}/projects/{pid}/report/pdf")
        assert r1.status_code == 403
        assert r2.status_code == 403
        assert r3.status_code == 403

    def test_upgrade_unlocks_premium(self, fresh_user):
        r = fresh_user.post(f"{API}/subscription/upgrade", json={"plan": "monthly"})
        assert r.status_code == 200
        assert r.json()["subscriptionTier"] == "premium"
        projects = fresh_user.get(f"{API}/projects").json()
        pid = projects[0]["id"]
        r2 = fresh_user.get(f"{API}/projects/{pid}/report")
        assert r2.status_code == 200

    def test_toggle_flips_tier(self, fresh_user):
        before = fresh_user.get(f"{API}/auth/me").json()["subscriptionTier"]
        fresh_user.post(f"{API}/subscription/toggle")
        after = fresh_user.get(f"{API}/auth/me").json()["subscriptionTier"]
        assert after != before
        # flip back to premium for downstream tests
        if after == "free":
            fresh_user.post(f"{API}/subscription/toggle")


# ---------- Premium: Work items, Progress, Report ----------
class TestPremiumFlows:
    def test_workitems_progress_and_summary(self, premium_session):
        projects = premium_session.get(f"{API}/projects").json()
        assert len(projects) >= 1
        pid = projects[0]["id"]
        # add work item
        wi = premium_session.post(f"{API}/projects/{pid}/workitems", json={"name": "TEST Item", "nilai": 10000000})
        assert wi.status_code == 200
        iid = wi.json()["id"]
        assert wi.json()["weight"] > 0
        # add progress
        pg = premium_session.post(f"{API}/workitems/{iid}/progress", json={"progress": 50, "notes": "half"})
        assert pg.status_code == 200
        # summary
        ps = premium_session.get(f"{API}/projects/{pid}/progress-summary")
        assert ps.status_code == 200
        data = ps.json()
        assert "totalProgress" in data
        assert "items" in data
        assert "curve" in data
        assert isinstance(data["curve"], list)
        if data["curve"]:
            assert "planned" in data["curve"][0]
            assert "actual" in data["curve"][0]
        # cleanup
        premium_session.delete(f"{API}/workitems/{iid}")

    def test_report_structure(self, premium_session):
        projects = premium_session.get(f"{API}/projects").json()
        pid = projects[0]["id"]
        r = premium_session.get(f"{API}/projects/{pid}/report")
        assert r.status_code == 200
        rep = r.json()
        assert "summary" in rep
        assert "expenseByCategory" in rep
        assert "inOut" in rep
        assert "marginBar" in rep
        # tukang grouping
        cats = [e["name"] for e in rep["expenseByCategory"]]
        # can't assert presence but check no raw Kasbon Tukang X leaking
        for c in cats:
            assert not c.startswith("Kasbon Tukang ")
            assert not c.startswith("Pelunasan Tukang ")

    def test_report_pdf_via_query_token(self, premium_session):
        projects = premium_session.get(f"{API}/projects").json()
        pid = projects[0]["id"]
        r = requests.get(f"{API}/projects/{pid}/report/pdf", params={"auth": premium_session.token})
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"


# ---------- Categories ----------
class TestMisc:
    def test_categories_endpoint(self):
        r = requests.get(f"{API}/categories")
        assert r.status_code == 200
        d = r.json()
        assert "Downpayment" in d["income"]
        assert "Termin" in d["income"]
        assert "Pelunasan" in d["income"]
        assert "Lainnya" in d["income"]


# ---------- Sub Items (Premium) ----------
class TestSubItems:
    def _make_workitem(self, s):
        projects = s.get(f"{API}/projects").json()
        pid = projects[0]["id"]
        r = s.post(f"{API}/projects/{pid}/workitems", json={"name": "TEST WI subs", "nilai": 0})
        assert r.status_code == 200
        return pid, r.json()["id"]

    def test_free_user_blocked_from_subitems(self, fresh_user):
        # fresh_user is free (no seed yet in this class scope - use fresh reg)
        email = f"free_{uuid.uuid4().hex[:8]}@example.com"
        s = requests.Session()
        r = s.post(f"{API}/auth/register", json={"email": email, "name": "F", "password": "Password123"})
        assert r.status_code == 200
        s.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
        # try a random item id
        r1 = s.post(f"{API}/workitems/does-not-matter/subitems", json={"name": "x", "harga": 1})
        r2 = s.get(f"{API}/workitems/does-not-matter/subitems")
        r3 = s.put(f"{API}/subitems/xxx", json={"name": "x", "harga": 1})
        r4 = s.delete(f"{API}/subitems/xxx")
        assert r1.status_code == 403
        assert r2.status_code == 403
        assert r3.status_code == 403
        assert r4.status_code == 403

    def test_subitem_crud_and_autosum(self, premium_session):
        pid, iid = self._make_workitem(premium_session)
        try:
            # create 2 subs
            r1 = premium_session.post(f"{API}/workitems/{iid}/subitems", json={"name": "TEST kayu", "harga": 4000000, "status": False})
            r2 = premium_session.post(f"{API}/workitems/{iid}/subitems", json={"name": "TEST cat", "harga": 6000000, "status": True})
            assert r1.status_code == 200 and r2.status_code == 200
            s1_id = r1.json()["id"]
            s2_id = r2.json()["id"]
            # list
            lst = premium_session.get(f"{API}/workitems/{iid}/subitems").json()
            assert len(lst) == 2
            assert all("project_id" not in s for s in lst), "project_id should not leak"

            # workitems reflects autosum
            wis = premium_session.get(f"{API}/projects/{pid}/workitems").json()
            parent = next(w for w in wis if w["id"] == iid)
            assert parent["hasSubs"] is True
            assert parent["subTotal"] == 10000000
            assert parent["nilai"] == 10000000  # nilai auto-sum
            assert parent["doneValue"] == 6000000
            assert parent["lastProgress"] == 60.0

            # toggle s2 done->false
            up = premium_session.put(f"{API}/subitems/{s2_id}", json={"name": "TEST cat", "harga": 6000000, "status": False})
            assert up.status_code == 200
            wis = premium_session.get(f"{API}/projects/{pid}/workitems").json()
            parent = next(w for w in wis if w["id"] == iid)
            assert parent["doneValue"] == 0
            assert parent["lastProgress"] == 0

            # toggle s1 to done
            premium_session.put(f"{API}/subitems/{s1_id}", json={"name": "TEST kayu", "harga": 4000000, "status": True})
            wis = premium_session.get(f"{API}/projects/{pid}/workitems").json()
            parent = next(w for w in wis if w["id"] == iid)
            assert parent["doneValue"] == 4000000
            assert parent["lastProgress"] == 40.0

            # delete a sub
            d = premium_session.delete(f"{API}/subitems/{s2_id}")
            assert d.status_code == 200
            wis = premium_session.get(f"{API}/projects/{pid}/workitems").json()
            parent = next(w for w in wis if w["id"] == iid)
            assert parent["subTotal"] == 4000000
            assert parent["subCount"] == 1
        finally:
            premium_session.delete(f"{API}/workitems/{iid}")

    def test_cost_loaded_project_progress_hybrid(self, premium_session):
        # Create project with nominal, add one item with subs and another manual
        r = premium_session.post(f"{API}/projects", json={
            "name": "TEST Sub Hybrid", "owner": "T", "nominal": 100000000, "category": "Residensial"
        })
        pid = r.json()["id"]
        try:
            # item A: with subs 20jt done 10jt
            a = premium_session.post(f"{API}/projects/{pid}/workitems", json={"name": "A", "nilai": 0}).json()
            premium_session.post(f"{API}/workitems/{a['id']}/subitems", json={"name": "s1", "harga": 10000000, "status": True})
            premium_session.post(f"{API}/workitems/{a['id']}/subitems", json={"name": "s2", "harga": 10000000, "status": False})
            # item B: manual, nilai 30jt, progress 50%
            b = premium_session.post(f"{API}/projects/{pid}/workitems", json={"name": "B", "nilai": 30000000}).json()
            premium_session.post(f"{API}/workitems/{b['id']}/progress", json={"progress": 50, "notes": "n"})
            ps = premium_session.get(f"{API}/projects/{pid}/progress-summary").json()
            # A contributes 10jt done, B contributes 50%*30jt=15jt -> 25jt / 100jt = 25%
            assert ps["totalProgress"] == 25.0
        finally:
            premium_session.delete(f"{API}/projects/{pid}")

    def test_delete_workitem_cascades_subitems(self, premium_session):
        pid, iid = self._make_workitem(premium_session)
        premium_session.post(f"{API}/workitems/{iid}/subitems", json={"name": "TEST k", "harga": 1000, "status": False})
        assert len(premium_session.get(f"{API}/workitems/{iid}/subitems").json()) == 1
        premium_session.delete(f"{API}/workitems/{iid}")
        r = premium_session.get(f"{API}/workitems/{iid}/subitems")
        assert r.status_code == 404

    def test_delete_project_cascades_subitems(self, premium_session):
        r = premium_session.post(f"{API}/projects", json={
            "name": "TEST cascade", "owner": "T", "nominal": 1000000, "category": "Residensial"
        }).json()
        pid = r["id"]
        wi = premium_session.post(f"{API}/projects/{pid}/workitems", json={"name": "X", "nilai": 0}).json()
        premium_session.post(f"{API}/workitems/{wi['id']}/subitems", json={"name": "s", "harga": 100, "status": False})
        premium_session.delete(f"{API}/projects/{pid}")
        r = premium_session.get(f"{API}/workitems/{wi['id']}/subitems")
        assert r.status_code == 404
