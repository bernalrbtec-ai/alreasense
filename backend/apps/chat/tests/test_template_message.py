"""
Testes para mensagens de template oficial (Evolution API).

- evolution_template_to_display_text: extração de texto a partir do payload.
- template_body_to_display_text: placeholders {{1}}, {{2}} e edge cases.
"""
from django.test import TestCase

from apps.chat.utils.template_display import (
    evolution_template_to_display_text,
    template_body_to_display_text,
)


class TemplateBodyToDisplayTextTests(TestCase):
    """Testes para template_body_to_display_text."""

    def test_empty_body_returns_empty(self):
        self.assertEqual(template_body_to_display_text('', []), '')
        self.assertEqual(template_body_to_display_text('   ', None), '   ')

    def test_no_placeholders_returns_body(self):
        self.assertEqual(template_body_to_display_text('Olá mundo', []), 'Olá mundo')

    def test_single_placeholder(self):
        self.assertEqual(
            template_body_to_display_text('Olá {{1}}', ['Maria']),
            'Olá Maria',
        )

    def test_multiple_placeholders(self):
        self.assertEqual(
            template_body_to_display_text('{{1}} {{2}}', ['A', 'B']),
            'A B',
        )

    def test_missing_param_replaced_with_empty(self):
        self.assertEqual(
            template_body_to_display_text('Olá {{1}}', []),
            'Olá ',
        )

    def test_params_safe_str_non_string(self):
        self.assertEqual(
            template_body_to_display_text('Valor: {{1}}', [123]),
            'Valor: 123',
        )
        self.assertEqual(
            template_body_to_display_text('Valor: {{1}}', [None]),
            'Valor: ',
        )

    def test_order_descending_placeholder(self):
        self.assertEqual(
            template_body_to_display_text('{{1}} e {{2}}', ['a', 'b']),
            'a e b',
        )

    def test_param_dict_or_list_replaced_with_empty(self):
        self.assertEqual(
            template_body_to_display_text('Olá {{1}}', [{'x': 1}]),
            'Olá ',
        )
        self.assertEqual(
            template_body_to_display_text('Olá {{1}}', [[]]),
            'Olá ',
        )


class EvolutionTemplateToDisplayTextTests(TestCase):
    """Testes para evolution_template_to_display_text (payload Evolution)."""

    def test_none_returns_empty(self):
        self.assertEqual(evolution_template_to_display_text(None), '')

    def test_empty_dict_returns_empty(self):
        self.assertEqual(evolution_template_to_display_text({}), '')

    def test_not_dict_returns_empty(self):
        self.assertEqual(evolution_template_to_display_text([]), '')
        self.assertEqual(evolution_template_to_display_text('x'), '')

    def test_hydrated_content_at_top(self):
        payload = {'hydratedContent': '  Texto hidratado  '}
        self.assertEqual(evolution_template_to_display_text(payload), 'Texto hidratado')

    def test_hydrated_template_nested(self):
        payload = {'hydratedTemplate': {'hydratedContent': 'Nested'}}
        self.assertEqual(evolution_template_to_display_text(payload), 'Nested')

    def test_content_text_at_top(self):
        payload = {'contentText': '  Content text  '}
        self.assertEqual(evolution_template_to_display_text(payload), 'Content text')

    def test_template_message_content_text(self):
        payload = {'templateMessage': {'contentText': 'Via templateMessage'}}
        self.assertEqual(evolution_template_to_display_text(payload), 'Via templateMessage')

    def test_components_body_with_text_and_params(self):
        payload = {
            'templateMessage': {
                'components': [
                    {
                        'type': 'body',
                        'text': 'Olá {{1}}, seu pedido {{2}}.',
                        'parameters': [
                            {'type': 'text', 'text': 'Maria'},
                            {'type': 'text', 'text': '123'},
                        ],
                    },
                ],
            },
        }
        self.assertEqual(
            evolution_template_to_display_text(payload),
            'Olá Maria, seu pedido 123.',
        )

    def test_components_body_format_body(self):
        payload = {
            'templateMessage': {
                'components': [
                    {
                        'type': 'body',
                        'format': {'body': 'Hello {{1}}'},
                        'parameters': [{'type': 'text', 'text': 'World'}],
                    },
                ],
            },
        }
        self.assertEqual(evolution_template_to_display_text(payload), 'Hello World')

    def test_malformed_payload_returns_empty(self):
        payload = {'templateMessage': 'not-a-dict'}
        self.assertEqual(evolution_template_to_display_text(payload), '')

    def test_invalid_inner_type_returns_empty(self):
        payload = {'templateMessage': None}
        self.assertEqual(evolution_template_to_display_text(payload), '')
