from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.test.utils import override_settings

from apps.ai.services.dify_chat_service import (
    ensure_active_dify_state_for_conversation,
    resolve_dify_assignment_for_conversation,
)
from apps.ai.services.dify_rag_memory_service import (
    _build_text_transcript,
    ingest_closed_conversation_transcript,
    launch_ingest_closed_conversation,
)


class ResolveDifyAssignmentTests(TestCase):
    @override_settings(DIFY_AUTO_START_ENABLED=False)
    def test_returns_none_when_global_flag_disabled(self):
        tenant = SimpleNamespace(id="t1")
        conversation = SimpleNamespace(id="c1", department_id="d1")

        result = resolve_dify_assignment_for_conversation(tenant, conversation)
        self.assertIsNone(result)

    @patch("apps.ai.models.DifyAssignment")
    def test_department_assignment_selected_when_enabled(self, mock_assignment_cls):
        tenant = SimpleNamespace(id="t1")
        conversation = SimpleNamespace(id="c1", department_id="d1")

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

    @patch("apps.ai.models.DifyAssignment")
    def test_inbox_assignment_used_when_conversation_has_no_department(self, mock_assignment_cls):
        tenant = SimpleNamespace(id="t1")
        conversation = SimpleNamespace(id="c1", department_id=None)

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

    @patch("apps.ai.models.DifyAssignment")
    def test_returns_none_when_no_assignment(self, mock_assignment_cls):
        tenant = SimpleNamespace(id="t1")
        conversation = SimpleNamespace(id="c1", department_id="d1")
        mock_assignment_cls.SCOPE_DEPARTMENT = "department"
        mock_assignment_cls.SCOPE_INBOX = "inbox"
        mock_assignment_cls.objects.select_related.return_value.filter.return_value.first.return_value = None
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


class DifyRagMemoryServiceTests(TestCase):
    def _msg(self, msg_id: str, content: str, *, direction: str = "incoming", message_id: str = "", is_internal: bool = False):
        return SimpleNamespace(
            id=msg_id,
            message_id=message_id,
            direction=direction,
            is_internal=is_internal,
            content=content,
            created_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            sender_name="",
        )

    def test_build_transcript_skips_media_placeholders(self):
        conv = SimpleNamespace(
            messages=SimpleNamespace(
                all=lambda: SimpleNamespace(
                    only=lambda *args, **kwargs: [
                        self._msg("m1", "[image]"),
                        self._msg("m2", "texto valido"),
                    ]
                )
            )
        )
        built = _build_text_transcript(conv, max_chars=1000)
        self.assertEqual(built.message_count, 1)
        self.assertIn("texto valido", built.content)
        self.assertNotIn("[image]", built.content)

    def test_build_transcript_deduplicates_same_message_id_and_content(self):
        conv = SimpleNamespace(
            messages=SimpleNamespace(
                all=lambda: SimpleNamespace(
                    only=lambda *args, **kwargs: [
                        self._msg("m1", "oi", message_id="ext-1"),
                        self._msg("m2", "oi", message_id="ext-1"),
                    ]
                )
            )
        )
        built = _build_text_transcript(conv, max_chars=1000)
        self.assertEqual(built.message_count, 1)

    @patch("apps.ai.services.dify_rag_memory_service.threading.Thread")
    @patch("apps.ai.services.dify_rag_memory_service.close_old_connections")
    @patch("apps.ai.services.dify_rag_memory_service.ingest_closed_conversation_transcript")
    def test_launch_ingest_wraps_worker_with_connection_hygiene(self, mock_ingest, mock_close_conn, mock_thread_cls):
        captured = {}

        def _thread_ctor(*args, **kwargs):
            captured["target"] = kwargs.get("target")
            return SimpleNamespace(start=lambda: None)

        mock_thread_cls.side_effect = _thread_ctor
        launch_ingest_closed_conversation("c-1")

        self.assertIn("target", captured)
        captured["target"]()
        self.assertEqual(mock_close_conn.call_count, 2)
        mock_ingest.assert_called_once_with("c-1")

    @patch("apps.ai.services.dify_rag_memory_service.AiKnowledgeDocument.objects.create")
    @patch("apps.ai.services.dify_rag_memory_service._should_use_rag_for_conversation", return_value=True)
    @patch("apps.ai.services.dify_rag_memory_service.Conversation.objects")
    def test_ingest_skips_when_hash_and_last_message_match(self, mock_conv_objects, _mock_rag_enabled, mock_create):
        msg = self._msg("m1", "oi")
        conversation = SimpleNamespace(
            id="c1",
            tenant=SimpleNamespace(id="t1"),
            tenant_id="t1",
            status="closed",
            metadata={},
            updated_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            contact_name="Contato",
            contact_phone="+5517999999999",
        )
        conversation.messages = SimpleNamespace(
            all=lambda: SimpleNamespace(only=lambda *args, **kwargs: [msg]),
            order_by=lambda *args, **kwargs: SimpleNamespace(only=lambda *a, **k: SimpleNamespace(first=lambda: msg)),
        )
        built = _build_text_transcript(conversation, max_chars=1000)
        import hashlib
        transcript_hash = hashlib.sha256((built.content or "").encode("utf-8", errors="ignore")).hexdigest()
        conversation.metadata = {
            "rag_last_ingested_message_id": str(msg.id),
            "rag_last_ingested_hash": transcript_hash,
        }

        mock_conv_objects.select_related.return_value.filter.return_value.first.return_value = conversation
        ingest_closed_conversation_transcript("c1")
        mock_create.assert_not_called()
