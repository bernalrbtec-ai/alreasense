"""
Variantes de telefone (apenas dígitos) para matching BR / E.164 no mesmo contato.
"""
from __future__ import annotations

from apps.chat.utils.contact_phone import normalize_contact_phone_for_rag


def digit_variants_for_match(raw: str) -> set[str]:
    """
    Ex.: 17991253112 -> {17991253112, 5517991253112}
    Ex.: 5517991253112 -> {5517991253112, 17991253112}
    """
    d = normalize_contact_phone_for_rag(raw or "")
    if not d:
        return set()
    variants = {d}
    if d.startswith("55") and len(d) >= 12:
        variants.add(d[2:])
    elif len(d) >= 10 and not d.startswith("55"):
        variants.add("55" + d)
    return variants


def conversation_phone_in_variants(contact_phone: str, variants: set[str]) -> bool:
    return normalize_contact_phone_for_rag(contact_phone or "") in variants


def contact_model_phone_in_variants(phone_e164: str, variants: set[str]) -> bool:
    return normalize_contact_phone_for_rag(phone_e164 or "") in variants
