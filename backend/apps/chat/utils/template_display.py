"""
Utilitários para exibição de mensagens de template no chat.
Substitui placeholders {{1}}, {{2}}, ... pelos parâmetros na ordem (decrescente para evitar literais).
"""
import re
from typing import Any, Dict, List, Optional, Union


def _safe_str(value: Any) -> str:
    """Converte valor para string de forma segura (evita bytes/dict/list no texto)."""
    if value is None:
        return ''
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='replace')
    if isinstance(value, (dict, list)):
        return ''  # não injetar repr no corpo da mensagem
    return str(value)


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
            value = _safe_str(val)
        body = body.replace(f'{{{{{n}}}}}', value)
    return body


def evolution_template_to_display_text(payload: Optional[Dict[str, Any]] = None) -> str:
    """
    Extrai texto para exibição a partir do payload de template recebido (Evolution API).
    Suporta hydratedTemplate, contentText e components (body + parameters).
    Retorna string vazia em caso de erro ou payload inválido.
    """
    if not payload or not isinstance(payload, dict):
        return ''
    try:
        # 0) Texto no topo (payload já é o objeto interno)
        if payload.get('hydratedContent') and isinstance(payload.get('hydratedContent'), str):
            return payload['hydratedContent'].strip()
        # 1) Texto já hidratado (hydratedTemplate.hydratedContent)
        hydrated = payload.get('hydratedTemplate')
        if isinstance(hydrated, dict):
            text = hydrated.get('hydratedContent') or hydrated.get('contentText') or ''
            if text and isinstance(text, str):
                return text.strip()
        # 2) contentText no primeiro nível (algumas APIs)
        content_text = payload.get('contentText')
        if content_text and isinstance(content_text, str):
            return content_text.strip()
        # 3) templateMessage aninhado
        _tm = payload.get('templateMessage')
        tm = _tm if isinstance(_tm, dict) else {}
        if isinstance(tm, dict):
            inner = tm.get('hydratedTemplate') or tm
            if isinstance(inner, dict):
                text = inner.get('hydratedContent') or inner.get('contentText') or ''
                if text and isinstance(text, str):
                    return text.strip()
            content_text = tm.get('contentText')
            if content_text and isinstance(content_text, str):
                return content_text.strip()
            # 4) components: body + parameters
            components = tm.get('components') or (payload.get('components') if isinstance(payload.get('components'), list) else [])
            if isinstance(components, list):
                for comp in components:
                    if not isinstance(comp, dict) or comp.get('type') != 'body':
                        continue
                    body_params_raw = comp.get('parameters') or []
                    params_safe = []
                    for p in body_params_raw:
                        if isinstance(p, dict):
                            params_safe.append(_safe_str(p.get('text', '')))
                        else:
                            params_safe.append(_safe_str(p))
                    body_text = (comp.get('text') or '').strip()
                    if not body_text and isinstance(comp.get('format'), dict):
                        body_text = (comp.get('format', {}).get('body') or '').strip()
                    if body_text:
                        return template_body_to_display_text(body_text, params_safe)
                    if params_safe:
                        return ' '.join(params_safe).strip()
                    break
        return ''
    except Exception:
        return ''
