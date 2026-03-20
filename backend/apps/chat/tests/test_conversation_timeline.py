"""Testes do módulo conversation_timeline (merge, dedup, fechamento)."""
from datetime import datetime

from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone

from apps.authn.models import Department
from apps.chat.models import Conversation, Message
from apps.chat.services.conversation_timeline import (
    EV_CONVERSATION_REOPENED,
    TIMELINE_KEY,
    build_merged_timeline_items,
    merge_conversation_closed_on_instance,
    merge_timeline_event,
    render_timeline_plaintext,
    should_skip_timeline_for_conversation,
)
from apps.tenancy.models import Tenant


class ConversationTimelineTests(TestCase):
    def test_should_skip_group_jid(self):
        c = Conversation(contact_phone="120363123@g.us")
        self.assertTrue(should_skip_timeline_for_conversation(c))

    def test_merge_event_persists_on_save(self):
        tenant = Tenant.objects.create(name="TL1")
        conv = Conversation.objects.create(
            tenant=tenant,
            contact_phone="+5511999999001",
            status="open",
        )
        merge_timeline_event(conv, "conversation_opened", {"channel": "whatsapp"})
        conv.save(update_fields=["metadata", "updated_at"])
        conv.refresh_from_db()
        evs = (conv.metadata or {}).get(TIMELINE_KEY) or []
        self.assertEqual(len(evs), 1)
        self.assertEqual(evs[0]["type"], "conversation_opened")

    def test_dedup_duplicate_message_id_and_content(self):
        tenant = Tenant.objects.create(name="TL2")
        conv = Conversation.objects.create(
            tenant=tenant,
            contact_phone="+5511999999002",
            status="open",
        )
        ts = datetime(2026, 2, 1, 10, 0, 0, tzinfo=timezone.utc)
        for _ in range(2):
            Message.objects.create(
                conversation=conv,
                direction="incoming",
                content="oi",
                message_id="ext-dup",
                status="delivered",
                created_at=ts,
            )
        merged = build_merged_timeline_items(conv)
        msg_lines = [x for x in merged if x[2] == "message"]
        self.assertEqual(len(msg_lines), 1)

    def test_closed_snapshot_before_clear(self):
        tenant = Tenant.objects.create(name="TL3")
        dept = Department.objects.create(tenant=tenant, name="Suporte")
        conv = Conversation.objects.create(
            tenant=tenant,
            contact_phone="+5511999999003",
            status="open",
            department=dept,
        )
        merge_conversation_closed_on_instance(conv, close_source="test", closed_by_user=None)
        conv.status = "closed"
        conv.department = None
        conv.assigned_to = None
        conv.save(update_fields=["status", "department", "assigned_to", "metadata", "updated_at"])
        conv.refresh_from_db()
        evs = (conv.metadata or {}).get(TIMELINE_KEY) or []
        closed = [e for e in evs if e.get("type") == "conversation_closed"]
        self.assertEqual(len(closed), 1)
        self.assertEqual(closed[0]["data"].get("department_name"), "Suporte")

    def test_render_includes_events_and_messages(self):
        tenant = Tenant.objects.create(name="TL4")
        conv = Conversation.objects.create(
            tenant=tenant,
            contact_phone="+5511999999004",
            status="open",
        )
        merge_timeline_event(conv, "conversation_reopened", {"source": "api"})
        conv.save(update_fields=["metadata", "updated_at"])
        Message.objects.create(
            conversation=conv,
            direction="incoming",
            content="olá",
            status="delivered",
        )
        text, total, n_msg, n_ev = render_timeline_plaintext(conv, max_chars=10000)
        self.assertGreaterEqual(n_ev, 1)
        self.assertGreaterEqual(n_msg, 1)
        self.assertIn("olá", text)
        self.assertIn("reaberta", text.lower())

    @override_settings(CHAT_CONVERSATION_TIMELINE_ENABLED=False)
    def test_writes_disabled_skips_merge_in_memory(self):
        tenant = Tenant.objects.create(name="TL5")
        conv = Conversation.objects.create(
            tenant=tenant,
            contact_phone="+5511999999005",
            status="open",
        )
        merge_timeline_event(conv, "conversation_opened", {"channel": "whatsapp"})
        self.assertIsNone((conv.metadata or {}).get(TIMELINE_KEY))

    @override_settings(CHAT_TIMELINE_RAG_RENDER_ENABLED=False)
    def test_rag_render_disabled_omits_events_in_plaintext(self):
        tenant = Tenant.objects.create(name="TL6")
        conv = Conversation.objects.create(
            tenant=tenant,
            contact_phone="+5511999999006",
            status="open",
        )
        merge_timeline_event(conv, EV_CONVERSATION_REOPENED, {"source": "api"})
        conv.save(update_fields=["metadata", "updated_at"])
        Message.objects.create(
            conversation=conv,
            direction="incoming",
            content="só isso",
            status="delivered",
        )
        text, _total, _n_msg, n_ev = render_timeline_plaintext(conv, max_chars=10000)
        self.assertEqual(n_ev, 0)
        self.assertIn("só isso", text)
        self.assertNotIn("reaberta", text.lower())
