from django.conf import settings
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from .models import NCADivision, User


class RequesterProfileTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("profile-admin@nca.test", "password", name="Admin", role="NCA_ADMIN")
        self.client.force_authenticate(self.admin)

    def test_admin_creates_named_requester_with_managed_division_and_grade(self):
        division = NCADivision.objects.create(code="rips", name="Research and Innovation")
        response = self.client.post("/api/v1/auth/users/", {"name":"Named Requester", "email":"named.requester@nca.test", "password":"long-test-password", "role":"NCA_VIEWER", "division_id":division.id, "grade":"Manager"}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["division"]["name"], division.name)
        self.assertEqual(response.data["grade"], "Manager")
        duplicate = self.client.post("/api/v1/auth/users/", {"name":"Another Person", "email":"named.requester@nca.test", "password":"long-test-password", "role":"NCA_VIEWER", "division_id":division.id, "grade":"Director"}, format="json")
        self.assertEqual(duplicate.status_code, 400)

    def test_requester_requires_active_division_and_grade(self):
        division = NCADivision.objects.create(code="inactive", name="Inactive Division", is_active=False)
        response = self.client.post("/api/v1/auth/users/", {"name":"Incomplete", "email":"incomplete@nca.test", "password":"long-test-password", "role":"NCA_VIEWER", "division_id":division.id, "grade":""}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_officer_has_operational_parity_but_not_users_or_data_requests(self):
        officer = User.objects.create_user("parity-officer@nca.test", "password", name="Officer", role="NCA_OFFICER")
        self.client.force_authenticate(officer)
        self.assertEqual(self.client.get("/api/v1/form-templates/").status_code, 200)
        self.assertEqual(self.client.get("/api/v1/provider-form-coverage/").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/governance/readiness/").status_code, 200)
        self.assertEqual(self.client.get("/api/v1/auth/users/").status_code, 403)
        self.assertEqual(self.client.get("/api/v1/nca-divisions/").status_code, 403)
        self.assertEqual(self.client.get("/api/v1/data-requests/").status_code, 403)


class AuthenticationSecurityTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("secure@nca.test", "secure-password-123", name="Secure", role="NCA_OFFICER")

    def test_login_sets_httponly_cookies_without_tokens_in_body(self):
        response = self.client.post("/api/v1/auth/login/", {"email": self.user.email, "password": "secure-password-123"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertNotIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        self.assertTrue(response.cookies[settings.AUTH_ACCESS_COOKIE]["httponly"])
        self.assertTrue(response.cookies[settings.AUTH_REFRESH_COOKIE]["httponly"])

    @override_settings(LOGIN_MAX_FAILURES=2, LOGIN_LOCKOUT_MINUTES=15)
    def test_failed_logins_lock_the_account(self):
        for _ in range(2):
            self.client.post("/api/v1/auth/login/", {"email": self.user.email, "password": "wrong-password"}, format="json")
        self.user.refresh_from_db()
        self.assertEqual(self.user.failed_login_attempts, 2)
        self.assertGreater(self.user.locked_until, timezone.now())
        blocked = self.client.post("/api/v1/auth/login/", {"email": self.user.email, "password": "secure-password-123"}, format="json")
        self.assertEqual(blocked.status_code, 401)

    def test_admin_reset_requires_password_change(self):
        admin = User.objects.create_user("admin-reset@nca.test", "admin-password-123", name="Admin", role="NCA_ADMIN")
        self.client.force_authenticate(admin)
        response = self.client.post(f"/api/v1/auth/users/{self.user.id}/reset-password/", {"temporary_password": "temporary-password-456"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.must_change_password)
        self.assertTrue(self.user.check_password("temporary-password-456"))

    def test_cookie_auth_requires_csrf_and_rotates_refresh(self):
        client = APIClient(enforce_csrf_checks=True)
        csrf_response = client.get("/api/v1/auth/csrf/")
        csrf_token = csrf_response.data["csrfToken"]
        login = client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "secure-password-123"},
            format="json", HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(login.status_code, 200, login.data)
        previous_refresh = login.cookies[settings.AUTH_REFRESH_COOKIE].value
        denied = client.post("/api/v1/auth/logout/", {}, format="json")
        self.assertEqual(denied.status_code, 403)
        refreshed = client.post("/api/v1/auth/refresh/", {}, format="json", HTTP_X_CSRFTOKEN=csrf_token)
        self.assertEqual(refreshed.status_code, 200, refreshed.data)
        self.assertNotEqual(refreshed.cookies[settings.AUTH_REFRESH_COOKIE].value, previous_refresh)

    def test_temporary_password_blocks_other_api_until_changed(self):
        self.user.must_change_password = True
        self.user.save(update_fields=["must_change_password"])
        client = APIClient()
        client.force_authenticate(self.user)
        # Header-based force authentication remains supported by the test
        # client; the policy is enforced for real cookie/JWT authentication.
        refresh = RefreshToken.for_user(self.user)
        client.force_authenticate(user=None)
        client.cookies[settings.AUTH_ACCESS_COOKIE] = str(refresh.access_token)
        denied = client.get("/api/v1/form-templates/")
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(client.get("/api/v1/auth/me/").status_code, 200)
