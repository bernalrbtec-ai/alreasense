"""
Critérios de aprovação automática de resumos (RAG). Avaliação e reprovação por frases.
"""
import re
import unicodedata

# Frases que indicam ausência de mensagens/diálogo no resumo → reprovar automaticamente.
AUTO_REJECT_PHRASES = [
    "não há mensagens pré-existentes",
    "nao ha mensagens pre-existentes",
    "não há mensagens",
    "nao ha mensagens",
    "diálogo vazio",
    "dialogo vazio",
    "sem conteúdo",
    "sem conteudo",
    "nenhuma mensagem",
]

# Critérios: id -> { "type": "boolean" | "number", "default": value, "label": str }
CRITERION_DEFAULTS = {
    "min_words": {"type": "number", "default": 20, "label": "Mín. de palavras no resumo"},
    "max_words": {"type": "number", "default": 500, "label": "Máx. de palavras no resumo"},
    "has_subject": {"type": "boolean", "default": True, "label": "Ter assunto preenchido"},
    "sentiment_not_negative": {"type": "boolean", "default": True, "label": "Sentimento não negativo"},
    "satisfaction_min": {"type": "number", "default": 3, "label": "Satisfação mín. (1–5)"},
    "min_messages": {"type": "number", "default": 3, "label": "Mín. mensagens na conversa"},
    "no_placeholders": {"type": "boolean", "default": True, "label": "Sem placeholders no texto"},
    "confidence_min": {"type": "number", "default": 0.85, "label": "Confiança mín. (0–1)"},
}

# Termos que indicam sentimento negativo (case-insensitive).
NEGATIVE_SENTIMENT_TERMS = ("negativo", "negativa", "insatisfeito", "insatisfeita")

PLACEHOLDER_SUBSTRINGS = ("n/a", "nao disponivel", "não disponível", "...")


def _normalize_for_reject(text):
    """Lower + remove acentos para match de frases."""
    if not text or not isinstance(text, str):
        return ""
    s = text.strip().lower()
    nfd = unicodedata.normalize("NFD", s)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def should_auto_reject(content):
    """
    Retorna (True, reason) se o conteúdo indicar ausência de mensagens no diálogo;
    (False, None) caso contrário.
    """
    if not content or not isinstance(content, str):
        return False, None
    normalized = _normalize_for_reject(content)
    for phrase in AUTO_REJECT_PHRASES:
        # Normalizar a frase também para match com conteúdo sem acentos
        phrase_norm = _normalize_for_reject(phrase)
        if phrase_norm and phrase_norm in normalized:
            return True, "resumo indica ausência de mensagens no diálogo"
    return False, None


def _get_criterion_value(config, criterion_id):
    """Retorna o value do critério (com default se enabled e sem value)."""
    criteria = config.get("criteria") or {}
    c = criteria.get(criterion_id) or {}
    if not c.get("enabled"):
        return None
    default_spec = CRITERION_DEFAULTS.get(criterion_id)
    if not default_spec:
        return None
    if "value" in c:
        return c["value"]
    return default_spec.get("default")


def _word_count(text):
    if not text or not isinstance(text, str):
        return 0
    return len(text.strip().split())


def _parse_satisfaction(s):
    """Extrai número 1-5 de string (ex: '4', 'satisfaction: 4'). Retorna None se inválido."""
    if s is None:
        return None
    s = str(s).strip().lower()
    # Tenta número no final da linha (ex: "satisfaction: 4")
    m = re.search(r"[1-5]\s*$", s)
    if m:
        return int(m.group().strip())
    # Tenta só dígito 1-5
    for c in s:
        if c in "12345":
            return int(c)
    return None


def _is_negative_sentiment(sentiment):
    if not sentiment or not isinstance(sentiment, str):
        return False
    s = sentiment.strip().lower()
    return any(term in s for term in NEGATIVE_SENTIMENT_TERMS)


def _has_placeholders(content):
    if not content or not isinstance(content, str):
        return False
    normalized = content.strip().lower()
    normalized = unicodedata.normalize("NFD", normalized)
    normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    return any(ph in normalized for ph in PLACEHOLDER_SUBSTRINGS)


def evaluate_criteria(config, context):
    """
    Avalia critérios de aprovação automática.

    config: dict com "enabled" (bool) e "criteria" (dict id -> { enabled, value? }).
    context: dict com content (str), metadata (dict subject, sentiment, satisfaction),
             message_count (int), confidence (float, opcional).

    Retorna: { "approved": bool, "results": { criterion_id: { "passed": bool, "detail": str } } }
    """
    results = {}
    if not config or not config.get("enabled"):
        return {"approved": False, "results": results}

    criteria_cfg = config.get("criteria") or {}
    content = (context.get("content") or "").strip()
    metadata = context.get("metadata") or {}
    message_count = context.get("message_count", 0)
    confidence = context.get("confidence")

    subject = (metadata.get("subject") or "").strip()
    sentiment = (metadata.get("sentiment") or "").strip()
    satisfaction_raw = metadata.get("satisfaction")

    words = _word_count(content)

    def check(criterion_id, passed, detail):
        results[criterion_id] = {"passed": bool(passed), "detail": str(detail)}
        return passed

    # min_words
    v = _get_criterion_value(config, "min_words")
    if v is not None:
        threshold = int(v) if isinstance(v, (int, float)) else 20
        check("min_words", words >= threshold, f"palavras={words}, mínimo={threshold}")

    # max_words
    v = _get_criterion_value(config, "max_words")
    if v is not None:
        threshold = int(v) if isinstance(v, (int, float)) else 500
        check("max_words", words <= threshold, f"palavras={words}, máximo={threshold}")

    # has_subject
    v = _get_criterion_value(config, "has_subject")
    if v is not None:
        check("has_subject", bool(subject), f"subject={'preenchido' if subject else 'vazio'}")

    # sentiment_not_negative
    v = _get_criterion_value(config, "sentiment_not_negative")
    if v is not None:
        neg = _is_negative_sentiment(sentiment)
        check("sentiment_not_negative", not neg, f"sentiment={sentiment or 'vazio'}")

    # satisfaction_min
    v = _get_criterion_value(config, "satisfaction_min")
    if v is not None:
        threshold = int(v) if isinstance(v, (int, float)) else 3
        sat = _parse_satisfaction(satisfaction_raw)
        passed = sat is not None and sat >= threshold
        check("satisfaction_min", passed, f"satisfaction={satisfaction_raw} (parse={sat}), mínimo={threshold}")

    # min_messages
    v = _get_criterion_value(config, "min_messages")
    if v is not None:
        threshold = int(v) if isinstance(v, (int, float)) else 3
        check("min_messages", message_count >= threshold, f"mensagens={message_count}, mínimo={threshold}")

    # no_placeholders
    v = _get_criterion_value(config, "no_placeholders")
    if v is not None:
        has_ph = _has_placeholders(content)
        check("no_placeholders", not has_ph, "resumo sem placeholders" if not has_ph else "resumo contém placeholder")

    # confidence_min
    v = _get_criterion_value(config, "confidence_min")
    if v is not None:
        threshold = float(v) if isinstance(v, (int, float)) else 0.85
        if confidence is None:
            check("confidence_min", False, "confidence não retornada pelo n8n")
        else:
            c = float(confidence) if isinstance(confidence, (int, float)) else None
            passed = c is not None and 0 <= c <= 1 and c >= threshold
            check("confidence_min", passed, f"confidence={confidence}, mínimo={threshold}")

    # Aprovar só se todos os critérios ativados passaram
    enabled_ids = [cid for cid, c in criteria_cfg.items() if c.get("enabled")]
    all_passed = enabled_ids and all(results.get(cid, {}).get("passed", False) for cid in enabled_ids)

    return {"approved": all_passed, "results": results}
