"""
Utilitários para exibição de mensagens de template no chat.
Substitui placeholders {{1}}, {{2}}, ... pelos parâmetros na ordem (decrescente para evitar literais).
"""
import re
from typing import List, Optional, Union


def template_body_to_display_text(body: str, params: Optional[Union[List, tuple]] = None) -> str:
    """
    Substitui placeholders {{1}}, {{2}}, ... no texto do template pelos parâmetros.

    Ordem decrescente ({{10}}, {{9}}, ..., {{1}}) para que um valor de parâmetro
    que contenha literalmente "{{2}}" não seja interpretado como placeholder.

    - Parâmetro faltando (índice fora da lista) → string vazia.
    - Parâmetros excedentes → ignorados.
    """
    if not body or not body.strip():
        return body or ''
    params_list = list(params) if params is not None else []
    # Encontrar todos os {{n}} com n inteiro
    placeholders = set()
    for m in re.finditer(r'\{\{(\d+)\}\}', body):
        placeholders.add(int(m.group(1)))
    if not placeholders:
        return body
    # Ordenar decrescente para substituir {{10}} antes de {{1}}
    for n in sorted(placeholders, reverse=True):
        value = ''
        if 1 <= n <= len(params_list):
            val = params_list[n - 1]
            value = str(val) if val is not None else ''
        body = body.replace(f'{{{{{n}}}}}', value)
    return body
