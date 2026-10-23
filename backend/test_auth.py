import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import auth
from backend.auth import create_admin, initialize_database
from backend.main import app


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PDF = PROJECT_ROOT / "data" / "sample_contracts" / "sample_contract.pdf"
TEST_PASSWORD = "test-password-with-enough-length"


class AuthenticationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.previous_database = os.environ.get("AUTH_DATABASE_PATH")
        os.environ["AUTH_DATABASE_PATH"] = str(
            Path(cls.temp_dir.name) / "test-accounts.sqlite3"
        )
        os.environ["AUTH_COOKIE_SECURE"] = "false"
        initialize_database()
        create_admin("reviewadmin", "review@example.test", TEST_PASSWORD)

    @classmethod
    def tearDownClass(cls):
        if cls.previous_database is None:
            os.environ.pop("AUTH_DATABASE_PATH", None)
        else:
            os.environ["AUTH_DATABASE_PATH"] = cls.previous_database
        os.environ.pop("AUTH_COOKIE_SECURE", None)
        cls.temp_dir.cleanup()

    def setUp(self):
        with auth.connect() as connection:
            connection.execute("DELETE FROM auth_login_attempts")
        self.client = TestClient(app, follow_redirects=False)

    def tearDown(self):
        self.client.close()

    def csrf(self):
        response = self.client.get("/api/auth/csrf")
        self.assertEqual(response.status_code, 200)
        return response.json()["csrf_token"]

    def login(self, remember_me=False):
        csrf = self.csrf()
        return self.client.post(
            "/api/auth/login",
            headers={"X-CSRF-Token": csrf},
            json={
                "username": "reviewadmin",
                "password": TEST_PASSWORD,
                "remember_me": remember_me,
            },
        )

    def test_login_page_loads_and_dashboard_requires_authentication(self):
        login_page = self.client.get("/login")
        self.assertEqual(login_page.status_code, 200)
        self.assertIn("Contract Intelligence", login_page.text)
        login_script = self.client.get("/login.js")
        self.assertEqual(login_script.status_code, 200)
        self.assertEqual(login_script.headers["cache-control"], "no-store")
        dashboard_script = self.client.get("/app.js")
        self.assertEqual(dashboard_script.status_code, 200)
        self.assertEqual(dashboard_script.headers["cache-control"], "no-store")
        self.assertIn("Finishing secure sign-in", dashboard_script.text)
        self.assertEqual(self.client.get("/style.css").status_code, 200)
        self.assertEqual(self.client.get("/").headers["location"], "/login")
        dashboard = self.client.get("/dashboard")
        self.assertEqual(dashboard.status_code, 303)
        self.assertEqual(dashboard.headers["location"], "/login")
        self.assertEqual(self.client.get("/index.html").status_code, 303)

    def test_valid_credentials_issue_http_only_session(self):
        response = self.login()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["authenticated"])
        self.assertIn("ci_session", self.client.cookies)
        self.assertIn("httponly", response.headers["set-cookie"].lower())
        status = self.client.get("/api/auth/status")
        self.assertTrue(status.json()["authenticated"])
        self.assertEqual(self.client.get("/dashboard").status_code, 200)

    def test_email_login_and_nonpersistent_expiry(self):
        csrf = self.csrf()
        response = self.client.post(
            "/api/auth/login",
            headers={"X-CSRF-Token": csrf},
            json={"username": "review@example.test", "password": TEST_PASSWORD},
        )
        self.assertEqual(response.status_code, 200)
        token_hash = auth._token_hash(self.client.cookies["ci_session"])
        with auth.connect() as connection:
            session = connection.execute(
                "SELECT persistent, expires_at FROM auth_sessions WHERE token_hash = ?",
                (token_hash,),
            ).fetchone()
        self.assertEqual(session["persistent"], 0)
        self.assertLessEqual(
            session["expires_at"] - int(__import__("time").time()),
            auth.SESSION_SECONDS,
        )

    def test_invalid_credentials_are_rejected(self):
        csrf = self.csrf()
        response = self.client.post(
            "/api/auth/login",
            headers={"X-CSRF-Token": csrf},
            json={"username": "reviewadmin", "password": "not-the-password"},
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json()["detail"], "Invalid username/email or password."
        )

    def test_cross_origin_login_is_rejected(self):
        csrf = self.csrf()
        response = self.client.post(
            "/api/auth/login",
            headers={
                "X-CSRF-Token": csrf,
                "Origin": "https://untrusted.example",
            },
            json={"username": "reviewadmin", "password": TEST_PASSWORD},
        )
        self.assertEqual(response.status_code, 403)

    def test_missing_login_fields_are_validated(self):
        response = self.client.post("/api/auth/login", json={"username": ""})
        self.assertEqual(response.status_code, 422)

    def test_unauthenticated_analysis_is_rejected(self):
        with open(SAMPLE_PDF, "rb") as contract:
            response = self.client.post(
                "/api/analyze",
                files={"file": ("sample_contract.pdf", contract, "application/pdf")},
            )
        self.assertEqual(response.status_code, 401)

    def test_authenticated_analysis_and_csrf(self):
        self.assertEqual(self.login().status_code, 200)
        csrf = self.client.get("/api/auth/status").json()["csrf_token"]
        with open(SAMPLE_PDF, "rb") as contract:
            rejected = self.client.post(
                "/api/analyze",
                files={"file": ("sample_contract.pdf", contract, "application/pdf")},
            )
        self.assertEqual(rejected.status_code, 403)

        with patch("backend.main.predict", return_value=("Unavailable", 0.0)):
            with open(SAMPLE_PDF, "rb") as contract:
                response = self.client.post(
                    "/api/analyze",
                    headers={"X-CSRF-Token": csrf},
                    files={"file": ("sample_contract.pdf", contract, "application/pdf")},
                )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertGreater(response.json()["text_length"], 0)
        self.assertTrue(response.json()["clauses"])
        self.assertTrue(
            all(clause["type"] != "Unavailable" for clause in response.json()["clauses"])
        )
        self.assertTrue(
            all(clause["classification_method"] == "heuristic" for clause in response.json()["clauses"])
        )
        self.assertTrue(
            all(clause["confidence"] is None for clause in response.json()["clauses"])
        )

    def test_logout_invalidates_session(self):
        self.assertEqual(self.login().status_code, 200)
        csrf = self.client.get("/api/auth/status").json()["csrf_token"]
        response = self.client.post(
            "/api/auth/logout", headers={"X-CSRF-Token": csrf}
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.client.get("/api/auth/status").json()["authenticated"])
        self.assertEqual(self.client.get("/dashboard").status_code, 303)

    def test_session_expiry_and_remember_me_are_server_managed(self):
        response = self.login(remember_me=True)
        self.assertEqual(response.status_code, 200)
        token_hash = auth._token_hash(self.client.cookies["ci_session"])
        with auth.connect() as connection:
            session = connection.execute(
                "SELECT persistent, expires_at FROM auth_sessions WHERE token_hash = ?",
                (token_hash,),
            ).fetchone()
            self.assertEqual(session["persistent"], 1)
            self.assertGreater(session["expires_at"], int(__import__("time").time()))
            connection.execute(
                "UPDATE auth_sessions SET expires_at = 0 WHERE token_hash = ?",
                (token_hash,),
            )
        self.assertFalse(self.client.get("/api/auth/status").json()["authenticated"])

    def test_password_is_stored_as_argon2_hash(self):
        with auth.connect() as connection:
            row = connection.execute(
                "SELECT password_hash FROM auth_users WHERE username = ?",
                ("reviewadmin",),
            ).fetchone()
        self.assertTrue(row["password_hash"].startswith("$argon2id$"))
        self.assertNotEqual(row["password_hash"], TEST_PASSWORD)

    def test_initialization_is_repeatable_and_preserves_accounts(self):
        with auth.connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO auth_login_attempts "
                "(attempt_key, failures, window_started, locked_until) VALUES (?, 2, 100, 0)",
                ("preservation-check",),
            )
        initialize_database()
        with auth.connect() as connection:
            user = connection.execute(
                "SELECT id FROM auth_users WHERE username = ?",
                ("reviewadmin",),
            ).fetchone()
            attempt = connection.execute(
                "SELECT failures FROM auth_login_attempts WHERE attempt_key = ?",
                ("preservation-check",),
            ).fetchone()
        self.assertIsNotNone(user)
        self.assertEqual(attempt["failures"], 2)

    def test_rate_limit_blocks_repeated_bad_passwords(self):
        csrf = self.csrf()
        body = {"username": "reviewadmin", "password": "wrong-password"}
        for _ in range(auth.LOGIN_MAX_FAILURES):
            response = self.client.post(
                "/api/auth/login",
                headers={"X-CSRF-Token": csrf},
                json=body,
            )
            self.assertEqual(response.status_code, 401)
        limited = self.client.post(
            "/api/auth/login",
            headers={"X-CSRF-Token": csrf},
            json=body,
        )
        self.assertEqual(limited.status_code, 429)


if __name__ == "__main__":
    unittest.main()
