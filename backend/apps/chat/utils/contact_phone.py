"""
Normalização de contact_phone para uso consistente no RAG (BIA, summarize, rag-upsert).
Garante que salvar e consultar no pgvector usem o mesmo formato.
"""
import re


def normalize_contact_phone_for_rag(phone: str) -> str:
    """
    Normaliza o telefone para uso em RAG (payload BIA, summarize, rag-upsert).
    Remove sufixos @s.whatsapp.net, @g.us e caracteres não numéricos; retorna só dígitos.

    Uso: payload da BIA (conversation.contact_phone), pipeline de resumos (summarize/rag-upsert),
    e qualquer lugar que precise comparar ou enviar contact_phone para o pgvector.
    """
    if not phone or not isinstance(phone, str):
        return ""
    s = phone.strip()
    for suffix in ("@s.whatsapp.net", "@g.us", "@lid"):
        if s.lower().endswith(suffix):
            s = s[: -len(suffix)].strip()
        elif suffix in s.lower():
            s = s.split(suffix)[0].strip()
    return re.sub(r"\D", "", s)
