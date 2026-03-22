"""
Testes de fumaça para a API Redis em Serviços (overview, permissões).
"""
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.servicos.views import _overview_redis_info
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
        self.assertIn("usage_history", data)
        self.assertIsInstance(data["usage_history"], list)

    def test_redis_overview_returns_403_for_non_superuser(self):
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.get("/api/servicos/redis/overview/")
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertIn("error", data)

    def test_redis_overview_returns_401_when_unauthenticated(self):
        response = self.client.get("/api/servicos/redis/overview/")
        self.assertEqual(response.status_code, 401)

    def test_rabbitmq_overview_returns_200_for_superuser(self):
        self.client.force_authenticate(user=self.superuser)
        response = self.client.get("/api/servicos/rabbitmq/overview/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("config_ok", data)
        self.assertIn("connection_ok", data)
        self.assertIn("queues", data)
        self.assertIn("warnings", data)

    def test_rabbitmq_overview_returns_403_for_non_superuser(self):
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.get("/api/servicos/rabbitmq/overview/")
        self.assertEqual(response.status_code, 403)

    def test_postgres_overview_returns_200_for_superuser(self):
        self.client.force_authenticate(user=self.superuser)
        response = self.client.get("/api/servicos/postgres/overview/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("config_ok", data)
        self.assertIn("connection_count", data)
        self.assertIn("database_size_bytes", data)
        self.assertIn("top_tables", data)

    def test_postgres_overview_returns_403_for_non_superuser(self):
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.get("/api/servicos/postgres/overview/")
        self.assertEqual(response.status_code, 403)

    def test_celery_overview_returns_200_for_superuser(self):
        self.client.force_authenticate(user=self.superuser)
        response = self.client.get("/api/servicos/celery/overview/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("config_ok", data)
        self.assertIn("broker_url_masked", data)
        self.assertIn("broker_transport", data)
        self.assertIn("default_queue", data)
        self.assertIn("task_always_eager", data)
        self.assertIn("overview_api_path", data)
        self.assertIn("worker_start_command", data)
        self.assertIn("dify_debounce_task", data)
        self.assertIn("warnings", data)

    def test_celery_overview_returns_403_for_non_superuser(self):
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.get("/api/servicos/celery/overview/")
        self.assertEqual(response.status_code, 403)

    def test_redis_overview_keyspace_parses_string_format(self):
        """Garante que keys_total é extraído do formato Redis 'keys=N,expires=N'."""
        mock_client = MagicMock()
        mock_client.info.side_effect = lambda section: {
            "memory": {"used_memory": 1_000_000, "used_memory_human": "1M"},
            "persistence": {"aof_enabled": False, "rdb_last_save_time": 0},
            "keyspace": {"db0": "keys=42,expires=0"},
        }.get(section, {})

        with patch("apps.servicos.views.redis.Redis.from_url", return_value=mock_client), patch(
            "apps.servicos.views._get_client", return_value=None
        ):
            with patch.object(settings, "REDIS_URL", "redis://localhost/0"):
                data = _overview_redis_info()
        self.assertTrue(data.get("config_ok"))
        self.assertEqual(data.get("keys_total"), 42)
