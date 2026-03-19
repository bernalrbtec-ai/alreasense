from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.test.utils import override_settings

from apps.ai.services.dify_chat_service import (
    ensure_active_dify_state_for_conversation,
    resolve_dify_assignment_for_conversation,
)


class ResolveDifyAssignmentTests(TestCase):
    @override_settings(DIFY_AUTO_START_ENABLED=False)
    def test_returns_none_when_global_flag_disabled(self):
        tenant = SimpleNamespace(id="t1")
        conversation = SimpleNamespace(id="c1", department_id="d1")

        result = resolve_dify_assignment_for_conversation(tenant, conversation)
        self.assertIsNone(result)

    @patch("apps.ai.models.DifySettings")
    @patch("apps.ai.models.DifyAssignment")
    def test_department_assignment_selected_when_enabled(self, mock_assignment_cls, mock_settings_cls):
        tenant = SimpleNamespace(id="t1")
        conversation = SimpleNamespace(id="c1", department_id="d1")

        mock_settings_cls.objects.filter.return_value.only.return_value.first.return_value = SimpleNamespace(enabled=True)
        mock_assignment_cls.SCOPE_DEPARTMENT = "department"
        mock_assignment_cls.SCOPE_INBOX = "inbox"

        assignment = SimpleNamespace(
            catalog_id="cat-1",
            scope_type="department",
            scope_id="d1",
            catalog=SimpleNamespace(display_name="Comercial IA", dify_app_id="app-x"),
        )
        mock_assignment_cls.objects.select_related.return_value.filter.return_value.first.return_value = assignment

        result = resolve_dify_assignment_for_conversation(tenant, conversation)

        self.assertIsNotNone(result)
        self.assertEqual(result["catalog_id"], "cat-1")
        self.assertEqual(result["display_name"], "Comercial IA")
        self.assertEqual(result["scope_type"], "department")

    @patch("apps.ai.models.DifySettings")
    @patch("apps.ai.models.DifyAssignment")
    def test_inbox_assignment_used_when_conversation_has_no_department(self, mock_assignment_cls, mock_settings_cls):
        tenant = SimpleNamespace(id="t1")
        conversation = SimpleNamespace(id="c1", department_id=None)

        mock_settings_cls.objects.filter.return_value.only.return_value.first.return_value = SimpleNamespace(enabled=True)
        mock_assignment_cls.SCOPE_DEPARTMENT = "department"
        mock_assignment_cls.SCOPE_INBOX = "inbox"

        assignment = SimpleNamespace(
            catalog_id="cat-inbox",
            scope_type="inbox",
            scope_id=None,
            catalog=SimpleNamespace(display_name="", dify_app_id="agent-inbox"),
        )
        mock_assignment_cls.objects.select_related.return_value.filter.return_value.first.return_value = assignment

        result = resolve_dify_assignment_for_conversation(tenant, conversation)

        self.assertIsNotNone(result)
        self.assertEqual(result["catalog_id"], "cat-inbox")
        self.assertEqual(result["display_name"], "agent-inbox")
        self.assertEqual(result["scope_type"], "inbox")

    @patch("apps.ai.models.DifySettings")
    def test_returns_none_when_dify_disabled(self, mock_settings_cls):
        tenant = SimpleNamespace(id="t1")
        conversation = SimpleNamespace(id="c1", department_id="d1")

        mock_settings_cls.objects.filter.return_value.only.return_value.first.return_value = SimpleNamespace(enabled=False)

        result = resolve_dify_assignment_for_conversation(tenant, conversation)
        self.assertIsNone(result)


class EnsureActiveDifyStateTests(TestCase):
    @patch("apps.chat.utils.websocket.broadcast_to_tenant")
    @patch("apps.ai.services.dify_chat_service.resolve_dify_assignment_for_conversation")
    @patch("apps.ai.services.dify_chat_service._conn.cursor")
    @patch("django.db.transaction.atomic")
    def test_creates_active_state_when_none_exists(
        self,
        mock_atomic,
        mock_cursor_factory,
        mock_resolve_assignment,
        mock_broadcast,
    ):
        tenant = SimpleNamespace(id="t1")
        conversation = SimpleNamespace(id="c1")
        mock_resolve_assignment.return_value = {
            "catalog_id": "cat-1",
            "display_name": "Comercial IA",
        }

        mock_atomic.return_value.__enter__.return_value = None
        mock_atomic.return_value.__exit__.return_value = False

        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            None,  # SELECT active
            ("cat-1", "active"),  # INSERT .. RETURNING
        ]
        mock_cursor_factory.return_value.__enter__.return_value = cursor
        mock_cursor_factory.return_value.__exit__.return_value = False

        result = ensure_active_dify_state_for_conversation(tenant, conversation)

        self.assertIsNotNone(result)
        self.assertTrue(result["activated"])
        self.assertEqual(result["catalog_id"], "cat-1")
        mock_broadcast.assert_called_once()

    @patch("apps.chat.utils.websocket.broadcast_to_tenant")
    @patch("apps.ai.services.dify_chat_service.resolve_dify_assignment_for_conversation")
    @patch("apps.ai.services.dify_chat_service._conn.cursor")
    @patch("django.db.transaction.atomic")
    def test_does_not_overwrite_when_already_active(
        self,
        mock_atomic,
        mock_cursor_factory,
        mock_resolve_assignment,
        mock_broadcast,
    ):
        tenant = SimpleNamespace(id="t1")
        conversation = SimpleNamespace(id="c1")
        mock_resolve_assignment.return_value = {
            "catalog_id": "cat-2",
            "display_name": "Suporte IA",
        }

        mock_atomic.return_value.__enter__.return_value = None
        mock_atomic.return_value.__exit__.return_value = False

        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            ("cat-existing", "active"),  # SELECT active
        ]
        mock_cursor_factory.return_value.__enter__.return_value = cursor
        mock_cursor_factory.return_value.__exit__.return_value = False

        result = ensure_active_dify_state_for_conversation(tenant, conversation)

        self.assertIsNotNone(result)
        self.assertFalse(result["activated"])
        self.assertTrue(result["already_active"])
        self.assertEqual(result["catalog_id"], "cat-existing")
        mock_broadcast.assert_not_called()

    @patch("apps.ai.services.dify_chat_service.resolve_dify_assignment_for_conversation")
    def test_returns_none_when_assignment_has_no_catalog(self, mock_resolve_assignment):
        tenant = SimpleNamespace(id="t1")
        conversation = SimpleNamespace(id="c1")
        mock_resolve_assignment.return_value = {"display_name": "Sem catalog"}

        result = ensure_active_dify_state_for_conversation(tenant, conversation)
        self.assertIsNone(result)
