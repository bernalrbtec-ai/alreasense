"""
Testes para instruções Typebot no texto: parsing de #{"chave": valor},
remoção de trechos, closeTicket e transferTo (mocks e integração).
"""
from unittest.mock import Mock, patch

from django.test import TestCase

from apps.chat.services.typebot_flow_service import (
    _find_matching_brace,
    _process_instructions_in_texts,
)


class FindMatchingBraceTests(TestCase):
    """Testes para _find_matching_brace (suporte a } dentro de strings)."""

    def test_simple_object_returns_closing_brace_index(self):
        text = '#{"closeTicket": true}'
        open_pos = text.index("{")
        self.assertEqual(_find_matching_brace(text, open_pos), text.index("}"))

    def test_brace_inside_string_value_ignored(self):
        text = '#{"transferTo": "Dept } algo"}'
        open_pos = text.index("{")
        end = _find_matching_brace(text, open_pos)
        self.assertGreater(end, 0)
        self.assertEqual(text[end], "}")

    def test_brace_only_in_string_returns_final_brace(self):
        text = '#{"x": "}"}'
        open_pos = text.index("{")
        self.assertEqual(_find_matching_brace(text, open_pos), len(text) - 1)

    def test_escaped_quote_inside_string_does_not_end_string(self):
        text = r'#{"key": "val\"ue}"}'
        open_pos = text.index("{")
        end = _find_matching_brace(text, open_pos)
        self.assertEqual(end, len(text) - 1)

    def test_invalid_no_closing_returns_minus_one(self):
        text = '#{"open": true'
        open_pos = text.index("{")
        self.assertEqual(_find_matching_brace(text, open_pos), -1)


@patch("apps.chat.services.typebot_flow_service._execute_transfer_by_department_name")
@patch("apps.chat.services.typebot_flow_service.close_conversation_from_typebot")
class ProcessInstructionsInTextsTests(TestCase):
    """Testes de parse/comportamento de _process_instructions_in_texts com mocks."""

    def _conv(self, tenant_id=1):
        c = Mock()
        c.id = 99
        c.tenant_id = tenant_id
        return c

    def test_process_instructions_returns_identical_when_no_instruction(
        self, mock_close, mock_transfer
    ):
        texts = ["Olá!", "Tudo bem?"]
        conv = self._conv()
        result = _process_instructions_in_texts(conv, texts)
        self.assertEqual(result, ["Olá!", "Tudo bem?"])
        mock_close.assert_not_called()
        mock_transfer.assert_not_called()

    def test_process_instructions_removes_close_ticket(self, mock_close, mock_transfer):
        conv = self._conv()
        result = _process_instructions_in_texts(
            conv, ['Obrigado!\n#{"closeTicket": true}']
        )
        self.assertEqual(result, ["Obrigado!"])
        mock_close.assert_called_once_with(conv)
        mock_transfer.assert_not_called()

    def test_process_instructions_removes_transfer_to(self, mock_close, mock_transfer):
        conv = self._conv()
        result = _process_instructions_in_texts(
            conv, ['Transfere?\n#{"transferTo": "Comercial"}']
        )
        self.assertEqual(result, ["Transfere?"])
        mock_transfer.assert_called_once_with(conv, "Comercial")
        mock_close.assert_not_called()

    def test_process_instructions_unknown_key_not_removed(
        self, mock_close, mock_transfer
    ):
        conv = self._conv()
        texts = ['Texto #{"outra": true} fim']
        result = _process_instructions_in_texts(conv, texts)
        self.assertEqual(result, texts)
        mock_close.assert_not_called()
        mock_transfer.assert_not_called()

    def test_process_instructions_invalid_json_not_removed(
        self, mock_close, mock_transfer
    ):
        conv = self._conv()
        texts = ['Texto #{ invalid } fim']
        result = _process_instructions_in_texts(conv, texts)
        self.assertEqual(result, texts)
        mock_close.assert_not_called()
        mock_transfer.assert_not_called()

    def test_process_instructions_empty_or_invalid_input(
        self, mock_close, mock_transfer
    ):
        conv = self._conv()
        self.assertEqual(_process_instructions_in_texts(conv, None), [])
        self.assertEqual(_process_instructions_in_texts(conv, "not a list"), [])
        conv_none = None
        result = _process_instructions_in_texts(conv_none, ["hello"])
        self.assertEqual(result, [])
        mock_close.assert_not_called()
        mock_transfer.assert_not_called()

    def test_process_instructions_after_close_skips_transfer(
        self, mock_close, mock_transfer
    ):
        conv = self._conv()
        text = 'Fim.\n#{"closeTicket": true}\n#{"transferTo": "Suporte"}'
        result = _process_instructions_in_texts(conv, [text])
        self.assertEqual(result, ["Fim."])
        mock_close.assert_called_once_with(conv)
        mock_transfer.assert_not_called()

    def test_process_instructions_brace_in_string_value_removed(
        self, mock_close, mock_transfer
    ):
        conv = self._conv()
        result = _process_instructions_in_texts(
            conv, ['Ok #{"transferTo": "Dept } algo"} fim']
        )
        self.assertEqual(result, ["Ok  fim"])
        mock_transfer.assert_called_once_with(conv, "Dept } algo")


class ProcessInstructionsIntegrationTests(TestCase):
    """Testes de integração opcionais: close e transfer com DB real."""

    def test_close_conversation_from_typebot_updates_db(self):
        from apps.chat.models import Conversation
        from apps.chat.models_flow import ConversationFlowState, Flow
        from apps.chat.services.typebot_flow_service import close_conversation_from_typebot
        from apps.tenancy.models import Tenant

        tenant = Tenant.objects.create(name="T Typebot")
        flow = Flow.objects.create(tenant=tenant, name="Flow Typebot Test")
        conv = Conversation.objects.create(
            tenant_id=tenant.id,
            contact_phone="5511999999999",
            status="open",
        )
        ConversationFlowState.objects.create(
            conversation=conv,
            flow=flow,
            typebot_session_id="s1",
        )
        close_conversation_from_typebot(conv)
        conv.refresh_from_db()
        self.assertEqual(conv.status, "closed")
        self.assertFalse(
            ConversationFlowState.objects.filter(conversation_id=conv.id).exists()
        )
        tenant.delete()

    def test_execute_transfer_by_department_name(self):
        from apps.authn.models import Department
        from apps.chat.models import Conversation, Message
        from apps.chat.services.typebot_flow_service import (
            _execute_transfer_by_department_name,
        )
        from apps.tenancy.models import Tenant

        tenant = Tenant.objects.create(name="T Typebot 2")
        dept_orig = Department.objects.create(tenant=tenant, name="Vendas")
        dept_dest = Department.objects.create(tenant=tenant, name="Comercial")
        conv = Conversation.objects.create(
            tenant_id=tenant.id,
            contact_phone="5511888888888",
            department_id=dept_orig.id,
            status="open",
        )
        ok = _execute_transfer_by_department_name(conv, "Comercial")
        self.assertTrue(ok)
        conv.refresh_from_db()
        self.assertEqual(conv.department_id, dept_dest.id)
        internal = Message.objects.filter(
            conversation=conv, direction="internal", text__icontains="Comercial"
        ).first()
        self.assertIsNotNone(internal)
        tenant.delete()
