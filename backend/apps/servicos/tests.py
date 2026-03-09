"""
Testes de fumaça para a API Redis em Serviços (overview, permissões).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.tenancy.models import Tenant

User = get_user_model()


class RedisServicosAPITestCase(TestCase):
    """Testes de permissão e resposta do overview Redis."""

    def setUp(self):
        self.client = APIClient()
        self.tenant, _ = Tenant.objects.get_or_create(
            name="Test Tenant Servicos",
            defaults={"name": "Test Tenant Servicos"},
        )
        self.superuser = User.objects.filter(is_superuser=True).first()
        if not self.superuser:
            self.superuser = User.objects.create_superuser(
                username="admin-servicos@test.com",
                email="admin-servicos@test.com",
                password="testpass123",
                tenant=self.tenant,
            )
        self.normal_user = User.objects.create_user(
            email="user-servicos@test.com",
            password="testpass123",
            username="user-servicos@test.com",
            tenant=self.tenant,
            is_superuser=False,
            is_staff=False,
        )

    def test_redis_overview_returns_200_for_superuser(self):
        self.client.force_authenticate(user=self.superuser)
        response = self.client.get("/api/servicos/redis/overview/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("config_ok", data)
        self.assertIn("used_memory_human", data)
        self.assertIn("last_cleanup", data)
        self.assertIn("warnings", data)

    def test_redis_overview_returns_403_for_non_superuser(self):
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.get("/api/servicos/redis/overview/")
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertIn("error", data)

    def test_redis_overview_returns_401_when_unauthenticated(self):
        response = self.client.get("/api/servicos/redis/overview/")
        self.assertEqual(response.status_code, 401)
