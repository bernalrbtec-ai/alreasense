"""Testes leves para dify_whatsapp_aux (mocks, sem DB quando possível)."""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings


class DifyWhatsappAuxTests(SimpleTestCase):
    @override_settings(DIFY_MARK_INBOUND_READ=False)
    @patch("apps.chat.webhooks.send_read_receipt")
    def test_mark_read_skipped_when_disabled(self, mock_send):
        from apps.ai.services.dify_whatsapp_aux import dify_mark_inbound_messages_read

        conv = MagicMock()
        msg = MagicMock(direction="incoming", is_deleted=False, message_id="mid1")
        dify_mark_inbound_messages_read(conv, [msg])
        mock_send.assert_not_called()

    @override_settings(DIFY_MARK_INBOUND_READ=True)
    @patch("apps.chat.webhooks.send_read_receipt")
    def test_mark_read_skips_outgoing(self, mock_send):
        from apps.ai.services.dify_whatsapp_aux import dify_mark_inbound_messages_read

        conv = MagicMock()
        msg = MagicMock(direction="outgoing", is_deleted=False, message_id="mid1")
        dify_mark_inbound_messages_read(conv, [msg])
        mock_send.assert_not_called()

    @override_settings(DIFY_PRE_SEND_TYPING=False)
    @patch("time.sleep")
    def test_pre_send_pause_skipped_when_typing_disabled(self, mock_sleep):
        from apps.ai.services.dify_whatsapp_aux import dify_pre_send_outbound_pause

        conv = MagicMock(contact_phone="+5511999999999")
        wa = MagicMock()
        dify_pre_send_outbound_pause(conv, wa)
        mock_sleep.assert_not_called()

    @override_settings(
        DIFY_MARK_INBOUND_READ=True,
        DIFY_MARK_INBOUND_READ_MAX_MESSAGES=2,
    )
    @patch("time.sleep")
    @patch("apps.chat.webhooks.send_read_receipt")
    def test_mark_read_caps_to_last_n(self, mock_send, _sleep):
        from apps.ai.services.dify_whatsapp_aux import dify_mark_inbound_messages_read

        conv = MagicMock()
        msgs = [
            MagicMock(direction="incoming", is_deleted=False, message_id=f"m{i}")
            for i in range(5)
        ]
        dify_mark_inbound_messages_read(conv, msgs)
        self.assertEqual(mock_send.call_count, 2)
        passed = [c.args[1].message_id for c in mock_send.call_args_list]
        self.assertEqual(passed, ["m3", "m4"])

    @override_settings(DIFY_MARK_INBOUND_READ=True, DIFY_MARK_INBOUND_READ_MAX_MESSAGES=0)
    @patch("time.sleep")
    @patch("apps.chat.webhooks.send_read_receipt")
    def test_mark_read_no_cap_when_zero(self, mock_send, _sleep):
        from apps.ai.services.dify_whatsapp_aux import dify_mark_inbound_messages_read

        conv = MagicMock()
        msgs = [
            MagicMock(direction="incoming", is_deleted=False, message_id=f"m{i}")
            for i in range(3)
        ]
        dify_mark_inbound_messages_read(conv, msgs)
        self.assertEqual(mock_send.call_count, 3)

    @override_settings(DIFY_MARK_INBOUND_READ=True, DIFY_MARK_INBOUND_READ_MAX_MESSAGES=0)
    @patch("time.sleep")
    @patch("apps.chat.webhooks.send_read_receipt")
    def test_preferred_wa_instance_forwarded(self, mock_send, _sleep):
        from apps.ai.services.dify_whatsapp_aux import dify_mark_inbound_messages_read

        conv = MagicMock()
        msg = MagicMock(direction="incoming", is_deleted=False, message_id="mid")
        pref = MagicMock()
        dify_mark_inbound_messages_read(conv, [msg], preferred_wa_instance=pref)
        mock_send.assert_called_once()
        self.assertIs(mock_send.call_args.kwargs.get("preferred_wa_instance"), pref)
