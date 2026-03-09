"""
Testes para listas interativas Meta: provider, parsing Evolution (listMessage/listResponse) e consumer.
"""
import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch

from django.test import TestCase

from apps.chat.utils.evolution_list_parsing import (
    parse_list_message,
    parse_list_message_fallback,
    parse_list_response,
)
from apps.notifications.models import WhatsAppInstance
from apps.notifications.whatsapp_providers.evolution import EvolutionProvider
from apps.notifications.whatsapp_providers.meta_cloud import MetaCloudProvider


def _make_meta_instance():
    """Instância mock Meta para o provider (não chama API real)."""
    inst = Mock(spec=WhatsAppInstance)
    inst.id = 1
    inst.integration_type = WhatsAppInstance.INTEGRATION_TYPE_META_CLOUD
    inst.phone_number_id = "123456"
    inst.access_token = "token"
    return inst


class MetaSendInteractiveListValidationTests(TestCase):
    """Validações de send_interactive_list (rejeitar excedentes, não truncar)."""

    def setUp(self):
        self.instance = _make_meta_instance()
        self.provider = MetaCloudProvider(self.instance)

    def test_rejects_empty_body(self):
        ok, data = self.provider.send_interactive_list(
            "5511999999999",
            "",
            "Ver opções",
            [{"title": "S1", "rows": [{"id": "r1", "title": "Opção 1"}]}],
        )
        self.assertFalse(ok)
        self.assertIn("error", data)
        self.assertEqual(data.get("error_code"), "INVALID_BODY")

    def test_rejects_empty_button_text(self):
        ok, data = self.provider.send_interactive_list(
            "5511999999999",
            "Corpo da mensagem",
            "",
            [{"title": "S1", "rows": [{"id": "r1", "title": "Opção 1"}]}],
        )
        self.assertFalse(ok)
        self.assertEqual(data.get("error_code"), "INVALID_BUTTON")

    def test_rejects_empty_sections(self):
        ok, data = self.provider.send_interactive_list(
            "5511999999999",
            "Corpo",
            "Ver opções",
            [],
        )
        self.assertFalse(ok)
        self.assertEqual(data.get("error_code"), "INVALID_SECTIONS")

    def test_rejects_more_than_10_rows(self):
        sections = [{"title": "S", "rows": [{"id": f"r{i}", "title": f"Opção {i}"} for i in range(11)]}]
        ok, data = self.provider.send_interactive_list(
            "5511999999999",
            "Corpo",
            "Ver opções",
            sections,
        )
        self.assertFalse(ok)
        self.assertEqual(data.get("error_code"), "INVALID_ROWS")

    def test_rejects_duplicate_row_ids(self):
        ok, data = self.provider.send_interactive_list(
            "5511999999999",
            "Corpo",
            "Ver opções",
            [
                {"title": "S1", "rows": [{"id": "same", "title": "A"}, {"id": "same", "title": "B"}]},
            ],
        )
        self.assertFalse(ok)
        self.assertEqual(data.get("error_code"), "INVALID_ROW_IDS")

    def test_rejects_empty_row_title(self):
        ok, data = self.provider.send_interactive_list(
            "5511999999999",
            "Corpo",
            "Ver opções",
            [{"title": "S1", "rows": [{"id": "r1", "title": ""}]}],
        )
        self.assertFalse(ok)
        self.assertEqual(data.get("error_code"), "INVALID_ROW_TITLE")
        self.assertIn("título", data.get("error", ""))

    def test_rejects_whitespace_only_row_title(self):
        ok, data = self.provider.send_interactive_list(
            "5511999999999",
            "Corpo",
            "Ver opções",
            [{"title": "S1", "rows": [{"id": "r1", "title": "   "}]}],
        )
        self.assertFalse(ok)
        self.assertEqual(data.get("error_code"), "INVALID_ROW_TITLE")

    def test_rejects_row_title_over_24_chars(self):
        ok, data = self.provider.send_interactive_list(
            "5511999999999",
            "Corpo",
            "Ver opções",
            [{"title": "S1", "rows": [{"id": "r1", "title": "a" * 25}]}],
        )
        self.assertFalse(ok)
        self.assertEqual(data.get("error_code"), "INVALID_ROW_TITLE")

    def test_rejects_button_text_over_20_chars(self):
        ok, data = self.provider.send_interactive_list(
            "5511999999999",
            "Corpo",
            "a" * 21,
            [{"title": "S1", "rows": [{"id": "r1", "title": "Opção 1"}]}],
        )
        self.assertFalse(ok)
        self.assertEqual(data.get("error_code"), "INVALID_BUTTON")

    @patch.object(MetaCloudProvider, "_request")
    def test_accepts_valid_payload(self, mock_request):
        mock_request.return_value = (True, {"messages": [{"id": "wamid.xxx"}]})
        ok, data = self.provider.send_interactive_list(
            "5511999999999",
            "Escolha uma opção",
            "Ver opções",
            [{"title": "Seção", "rows": [{"id": "r1", "title": "Opção 1"}, {"id": "r2", "title": "Opção 2"}]}],
        )
        self.assertTrue(ok)
        mock_request.assert_called_once()
        payload = mock_request.call_args[0][0]
        self.assertEqual(payload["type"], "interactive")
        self.assertEqual(payload["interactive"]["type"], "list")
        self.assertEqual(len(payload["interactive"]["action"]["sections"][0]["rows"]), 2)


# --- Evolution listMessage / listResponseMessage parsing ---


class EvolutionListMessageParsingTests(TestCase):
    """Payload listMessage Evolution → content e interactive_list metadata esperada."""

    def test_list_message_full_payload(self):
        lm = {
            "description": "Escolha uma opção",
            "buttonText": "Ver opções",
            "sections": [
                {
                    "title": "Opções",
                    "rows": [
                        {"id": "opt1", "title": "Opção 1", "description": "Desc 1"},
                        {"id": "opt2", "title": "Opção 2"},
                    ],
                }
            ],
        }
        content, meta = parse_list_message(lm)
        self.assertEqual(content, "Escolha uma opção")
        self.assertIsNotNone(meta)
        self.assertEqual(meta["body_text"], "Escolha uma opção")
        self.assertEqual(meta["button_text"], "Ver opções")
        self.assertEqual(len(meta["sections"]), 1)
        self.assertEqual(len(meta["sections"][0]["rows"]), 2)
        self.assertEqual(meta["sections"][0]["rows"][0]["id"], "opt1")
        self.assertEqual(meta["sections"][0]["rows"][0]["title"], "Opção 1")
        self.assertEqual(meta["sections"][0]["rows"][0]["description"], "Desc 1")
        self.assertEqual(meta["sections"][0]["rows"][1]["title"], "Opção 2")

    def test_list_message_row_ids_as_strings(self):
        lm = {
            "description": "Lista",
            "buttonText": "Abrir",
            "sections": [{"title": "S1", "rowIds": ["id_a", "id_b"]}],
        }
        content, meta = parse_list_message(lm)
        self.assertEqual(content, "Lista")
        self.assertIsNotNone(meta)
        self.assertEqual(len(meta["sections"]), 1)
        self.assertEqual(len(meta["sections"][0]["rows"]), 2)
        self.assertEqual(meta["sections"][0]["rows"][0]["id"], "id_a")
        self.assertEqual(meta["sections"][0]["rows"][0]["title"], "id_a")
        self.assertEqual(meta["sections"][0]["rows"][1]["id"], "id_b")

    def test_list_message_caps_at_10_rows(self):
        lm = {
            "description": "Muitas",
            "buttonText": "Ver",
            "sections": [
                {"title": "S1", "rows": [{"id": f"r{i}", "title": f"Opção {i}"} for i in range(15)]}
            ],
        }
        content, meta = parse_list_message(lm)
        self.assertIsNotNone(meta)
        total = sum(len(sec["rows"]) for sec in meta["sections"])
        self.assertEqual(total, 10)

    def test_list_message_empty_dict_returns_none_metadata(self):
        content, meta = parse_list_message({})
        self.assertEqual(content, "Mensagem com lista")
        self.assertIsNone(meta)

    def test_list_message_fallback_sections_and_content(self):
        lm = {
            "description": "Corpo fallback",
            "sections": [{"title": "S", "rows": [{"id": "r1", "title": "T"}]}],
        }
        content, meta = parse_list_message_fallback(lm)
        self.assertEqual(content, "Corpo fallback")
        self.assertIsNotNone(meta)
        self.assertEqual(meta["body_text"], "Corpo fallback")
        self.assertEqual(meta["header_text"], "")
        self.assertEqual(len(meta["sections"][0]["rows"]), 1)


class EvolutionListResponseParsingTests(TestCase):
    """Payload listResponseMessage Evolution → content e list_reply metadata esperada."""

    def test_list_response_full(self):
        lrm = {"title": "Opção escolhida", "rowId": "opt_1", "description": "Desc da opção"}
        content, meta = parse_list_response(lrm)
        self.assertEqual(content, "Opção escolhida")
        self.assertEqual(meta["id"], "opt_1")
        self.assertEqual(meta["title"], "Opção escolhida")
        self.assertEqual(meta["description"], "Desc da opção")

    def test_list_response_title_fallback_to_row_id(self):
        lrm = {"rowId": "opt_2"}
        content, meta = parse_list_response(lrm)
        self.assertEqual(content, "opt_2")
        self.assertEqual(meta["id"], "opt_2")
        self.assertEqual(meta["title"], "opt_2")

    def test_list_response_empty_dict(self):
        content, meta = parse_list_response({})
        self.assertEqual(content, "Resposta de lista")
        self.assertEqual(meta["id"], "")
        self.assertEqual(meta["title"], "")


# --- Consumer: rejeição lista+template, não-Meta, flag desligada ---


class ConsumerInteractiveListRejectionTests(TestCase):
    """Consumer rejeita interactive_list quando: lista+template, não-Meta, flag desligada."""

    def _run_receive(self, consumer, payload):
        async def run():
            await consumer.receive(text_data=json.dumps(payload))

        return asyncio.run(run())

    def _build_send_message_with_list(self, conversation_id="00000000-0000-0000-0000-000000000001"):
        return {
            "type": "send_message",
            "conversation_id": conversation_id,
            "content": "",
            "include_signature": False,
            "is_internal": False,
            "interactive_list": {
                "body_text": "Corpo",
                "button_text": "Ver opções",
                "sections": [{"title": "S1", "rows": [{"id": "r1", "title": "Opção 1"}]}],
            },
        }

    @patch("apps.chat.consumers_v2.ChatConsumerV2.get_tenant_allow_meta_interactive_buttons", new_callable=AsyncMock)
    @patch("apps.chat.consumers_v2.ChatConsumerV2.check_conversation_access", new_callable=AsyncMock)
    def test_rejects_list_when_flag_disabled(self, mock_access, mock_allow):
        mock_access.return_value = True
        mock_allow.return_value = False
        from apps.chat.consumers_v2 import ChatConsumerV2

        scope = {"user": Mock(tenant_id="t1", email="u@t.com")}
        consumer = ChatConsumerV2(scope)
        consumer.send = AsyncMock()
        payload = self._build_send_message_with_list()
        self._run_receive(consumer, payload)
        consumer.send.assert_called_once()
        sent = json.loads(consumer.send.call_args[0][0])
        self.assertEqual(sent["type"], "error")
        self.assertEqual(sent["error_code"], "INTERACTIVE_BUTTONS_DISABLED")

    @patch("apps.chat.consumers_v2.ChatConsumerV2.get_conversation_supports_interactive_list", new_callable=AsyncMock)
    @patch("apps.chat.consumers_v2.ChatConsumerV2.get_conversation_type", new_callable=AsyncMock)
    @patch("apps.chat.consumers_v2.ChatConsumerV2.get_tenant_allow_meta_interactive_buttons", new_callable=AsyncMock)
    @patch("apps.chat.consumers_v2.ChatConsumerV2.check_conversation_access", new_callable=AsyncMock)
    def test_rejects_list_when_not_meta_nor_evolution(self, mock_access, mock_allow, mock_conv_type, mock_supports_list):
        mock_access.return_value = True
        mock_allow.return_value = True
        mock_conv_type.return_value = "individual"
        mock_supports_list.return_value = False
        from apps.chat.consumers_v2 import ChatConsumerV2

        scope = {"user": Mock(tenant_id="t1", email="u@t.com")}
        consumer = ChatConsumerV2(scope)
        consumer.send = AsyncMock()
        payload = self._build_send_message_with_list()
        self._run_receive(consumer, payload)
        consumer.send.assert_called_once()
        sent = json.loads(consumer.send.call_args[0][0])
        self.assertEqual(sent["type"], "error")
        self.assertEqual(sent["error_code"], "INTERACTIVE_LIST_NOT_SUPPORTED")

    @patch("apps.chat.consumers_v2.ChatConsumerV2.get_tenant_allow_meta_interactive_buttons", new_callable=AsyncMock)
    @patch("apps.chat.consumers_v2.ChatConsumerV2.check_conversation_access", new_callable=AsyncMock)
    def test_rejects_list_with_template(self, mock_access, mock_allow):
        mock_access.return_value = True
        mock_allow.return_value = True
        from apps.chat.consumers_v2 import ChatConsumerV2

        scope = {"user": Mock(tenant_id="t1", email="u@t.com")}
        consumer = ChatConsumerV2(scope)
        consumer.send = AsyncMock()
        payload = self._build_send_message_with_list()
        payload["wa_template_id"] = "template_123"
        self._run_receive(consumer, payload)
        consumer.send.assert_called_once()
        sent = json.loads(consumer.send.call_args[0][0])
        self.assertEqual(sent["type"], "error")
        self.assertEqual(sent["error_code"], "TEMPLATE_BUTTONS_AND_LIST")


# --- EvolutionProvider: validações send_interactive_list ---


def _make_evolution_instance():
    """Instância mock Evolution para o provider (não chama API real)."""
    inst = Mock(spec=WhatsAppInstance)
    inst.id = 1
    inst.integration_type = WhatsAppInstance.INTEGRATION_TYPE_EVOLUTION
    inst.instance_name = "evol_instance"
    return inst


class EvolutionSendInteractiveListValidationTests(TestCase):
    """Validações de EvolutionProvider.send_interactive_list (rejeitar inválidos)."""

    def setUp(self):
        self.instance = _make_evolution_instance()
        self.provider = EvolutionProvider(self.instance)

    def test_rejects_empty_body(self):
        ok, data = self.provider.send_interactive_list(
            "5511999999999",
            "",
            "Ver opções",
            [{"title": "S1", "rows": [{"id": "r1", "title": "Opção 1"}]}],
        )
        self.assertFalse(ok)
        self.assertIn("error", data)
        self.assertEqual(data.get("error_code"), "INVALID_BODY")

    def test_rejects_empty_button_text(self):
        ok, data = self.provider.send_interactive_list(
            "5511999999999",
            "Corpo",
            "",
            [{"title": "S1", "rows": [{"id": "r1", "title": "Opção 1"}]}],
        )
        self.assertFalse(ok)
        self.assertIn("error", data)
        self.assertEqual(data.get("error_code"), "INVALID_BUTTON")

    def test_rejects_more_than_10_rows(self):
        rows = [{"id": f"r{i}", "title": f"Opção {i}"} for i in range(11)]
        ok, data = self.provider.send_interactive_list(
            "5511999999999",
            "Corpo",
            "Ver opções",
            [{"title": "S1", "rows": rows}],
        )
        self.assertFalse(ok)
        self.assertIn("error", data)
        self.assertEqual(data.get("error_code"), "INVALID_ROWS")
