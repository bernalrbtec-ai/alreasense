"""
Parsing de listMessage e listResponseMessage (Evolution API) para metadata de listas interativas.
Usado pelo webhook Evolution; lógica extraída para permitir testes unitários.
"""
from typing import Any, Dict, List, Optional, Tuple


def parse_list_message(lm: Dict[str, Any]) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Extrai body, buttonText, header/footer e sections/rows de um payload Evolution listMessage.
    Retorna (content, interactive_list_metadata ou None).
    Limita a 10 rows no total; suporta rowIds como lista de strings.
    """
    if not lm or not isinstance(lm, dict):
        return ("Mensagem com lista", None)
    try:
        raw_body = (
            lm.get("description") or lm.get("contentText") or lm.get("content")
            or lm.get("text") or lm.get("title") or ""
        )
        if isinstance(raw_body, bytes):
            raw_body = raw_body.decode("utf-8", errors="replace")
        body_text = (
            (raw_body or "").strip().replace("\x00", "")[:1024]
            if isinstance(raw_body, str)
            else str(raw_body or "").strip()[:1024]
        )
        content = body_text or "Mensagem com lista"
        button_text = lm.get("buttonText") or ""
        if isinstance(button_text, dict):
            button_text = (button_text.get("displayText") or button_text.get("text") or "").strip()
        else:
            button_text = (button_text or "").strip() if isinstance(button_text, str) else ""
        header_text = (lm.get("header") or lm.get("headerText") or "").strip() if isinstance(lm.get("header"), str) else ""
        if not header_text and isinstance(lm.get("header"), dict):
            header_text = (lm.get("header", {}).get("title") or "").strip()
        footer_text = (lm.get("footer") or lm.get("footerText") or "").strip() if isinstance(lm.get("footer"), str) else ""
        values = lm.get("sections") or lm.get("values") or lm.get("listSections") or []
        if not isinstance(values, list):
            values = []
        sections: List[Dict[str, Any]] = []
        total_rows_cap = 0
        for sec in values[:10]:
            if total_rows_cap >= 10:
                break
            if not isinstance(sec, dict):
                continue
            sec_title = (
                (sec.get("title") or "").strip()
                if isinstance(sec.get("title"), str)
                else str(sec.get("title") or "").strip()
            )
            rows_raw = sec.get("rows") or sec.get("rowIds") or []
            if not isinstance(rows_raw, list):
                rows_raw = []
            rows: List[Dict[str, Any]] = []
            for r in rows_raw[:10]:
                if total_rows_cap >= 10:
                    break
                if isinstance(r, dict):
                    row_id = (r.get("rowId") or r.get("id") or "").strip() or str(len(rows))
                    row_title = (
                        (r.get("title") or r.get("displayText") or "").strip()
                        if isinstance(r.get("title"), str)
                        else str(r.get("title") or "").strip()
                    )
                    if not row_title and isinstance(r.get("title"), str):
                        row_title = (r.get("title") or "").strip()
                    row_desc = (
                        (r.get("description") or "").strip()[:72]
                        if isinstance(r.get("description"), str)
                        else ""
                    )
                    rows.append(
                        {
                            "id": str(row_id)[:100],
                            "title": row_title[:24] if row_title else row_id[:24],
                            "description": row_desc,
                        }
                    )
                    total_rows_cap += 1
                elif r is not None:
                    raw = str(r).strip()[:100]
                    if raw:
                        rows.append({"id": raw, "title": raw[:24], "description": ""})
                        total_rows_cap += 1
            if rows:
                sections.append(
                    {"title": sec_title[:24] if sec_title else "Seção", "rows": rows}
                )
        if not sections and not body_text and not button_text:
            return (content, None)
        interactive_list_metadata = {
            "body_text": body_text or content,
            "button_text": button_text[:20] if button_text else "Ver opções",
            "header_text": header_text[:60] if header_text else "",
            "footer_text": footer_text[:60] if footer_text else "",
            "sections": sections[:10],
        }
        return (content, interactive_list_metadata)
    except Exception:
        return ("Mensagem com lista", None)


def parse_list_message_fallback(lm: Dict[str, Any]) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Versão simplificada para fallback (outro messageType): sem header/footer do payload.
    Limita a 10 rows; suporta rowIds como lista de strings.
    """
    if not lm or not isinstance(lm, dict):
        return ("Mensagem com lista", None)
    if not (lm.get("sections") or lm.get("values") or lm.get("description")):
        return ("Mensagem com lista", None)
    try:
        body_text = (lm.get("description") or lm.get("contentText") or lm.get("content") or "").strip()[:1024]
        if isinstance(body_text, bytes):
            body_text = body_text.decode("utf-8", errors="replace").strip()[:1024]
        button_text = lm.get("buttonText") or ""
        if isinstance(button_text, dict):
            button_text = (button_text.get("displayText") or button_text.get("text") or "").strip()
        values = lm.get("sections") or lm.get("values") or []
        sections = []
        total_rows_fb = 0
        for sec in (values if isinstance(values, list) else [])[:10]:
            if total_rows_fb >= 10:
                break
            if not isinstance(sec, dict):
                continue
            rows = []
            for r in (sec.get("rows") or sec.get("rowIds") or [])[:10]:
                if total_rows_fb >= 10:
                    break
                if isinstance(r, dict):
                    row_id = (r.get("rowId") or r.get("id") or str(len(rows))).strip()
                    row_title = (r.get("title") or r.get("displayText") or "").strip()[:24]
                    rows.append(
                        {
                            "id": row_id[:100],
                            "title": row_title or row_id[:24],
                            "description": (r.get("description") or "")[:72],
                        }
                    )
                    total_rows_fb += 1
                elif r is not None:
                    raw = str(r).strip()[:100]
                    if raw:
                        rows.append({"id": raw, "title": raw[:24], "description": ""})
                        total_rows_fb += 1
            if rows:
                sections.append(
                    {"title": (sec.get("title") or "Seção").strip()[:24], "rows": rows}
                )
        if not sections and not body_text:
            return (body_text or "Mensagem com lista", None)
        metadata = {
            "body_text": body_text or "Mensagem com lista",
            "button_text": (button_text or "Ver opções")[:20],
            "header_text": "",
            "footer_text": "",
            "sections": sections[:10],
        }
        content = body_text or "Mensagem com lista"
        return (content, metadata)
    except Exception:
        return ("Mensagem com lista", None)


def parse_list_response(lrm: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """
    Extrai título e id da opção escolhida de um payload Evolution listResponseMessage.
    Retorna (content, list_reply_metadata).
    """
    if not lrm or not isinstance(lrm, dict):
        return ("Resposta de lista", {"id": "", "title": ""})
    try:
        title = (
            lrm.get("title")
            or lrm.get("selectedDisplayText")
            or lrm.get("selectedRowId")
            or lrm.get("selectedId")
            or ""
        ).strip()
        if isinstance(title, bytes):
            title = title.decode("utf-8", errors="replace").strip()
        row_id = (lrm.get("rowId") or lrm.get("selectedId") or lrm.get("id") or "").strip()
        description = (
            (lrm.get("description") or "").strip()[:72]
            if isinstance(lrm.get("description"), str)
            else ""
        )
        content = title or row_id or "Resposta de lista"
        content = (content or "").replace("\x00", "")[:65536]
        list_reply_metadata = {"id": row_id or title, "title": title or row_id}
        if description:
            list_reply_metadata["description"] = description
        return (content, list_reply_metadata)
    except Exception:
        return ("Resposta de lista", {"id": "", "title": ""})
