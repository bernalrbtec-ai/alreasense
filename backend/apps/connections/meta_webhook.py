"""
Webhook para WhatsApp Cloud API (Meta).
GET: verificação do hub (hub.verify_token, hub.challenge).
POST: mensagens e status; validação de assinatura; idempotência por wamid.
Em erro ou instância não encontrada: logar e retornar 200 (evitar retentativas da Meta).
"""
import hashlib
import hmac
import json
import logging
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from django.db import transaction
from apps.notifications.models import WhatsAppInstance
from apps.chat.models import Conversation, Message
from apps.chat.utils.websocket import broadcast_conversation_updated, broadcast_message_received

logger = logging.getLogger(__name__)


def get_whatsapp_instance_for_meta(phone_number_id: str):
    """
    Retorna WhatsAppInstance ativa para o phone_number_id da Meta (Cloud API).
    phone_number_id é o ID do número de telefone no Meta Business (string).
    """
    if not phone_number_id:
        return None
    return WhatsAppInstance.objects.select_related(
        'tenant',
        'default_department',
    ).filter(
        phone_number_id=str(phone_number_id).strip(),
        integration_type=WhatsAppInstance.INTEGRATION_TYPE_META_CLOUD,
        is_active=True,
        status='active',
    ).first()


def _verify_meta_signature(payload_body: bytes, signature_header: str) -> bool:
    """Valida X-Hub-Signature-256 (HMAC SHA256). Em produção, APP_SECRET deve estar configurado."""
    app_secret = getattr(settings, 'WHATSAPP_CLOUD_APP_SECRET', None) or ''
    app_secret = (app_secret or '').strip()
    if not signature_header or not signature_header.startswith('sha256='):
        return False
    if not app_secret:
        logger.error(
            "[META WEBHOOK] WHATSAPP_CLOUD_APP_SECRET não configurado; "
            "rejeitando POST com assinatura (configure em produção)"
        )
        return False
    expected = signature_header.split('sha256=')[-1].strip().lower()
    computed = hmac.new(
        app_secret.encode('utf-8'),
        payload_body,
        hashlib.sha256,
    ).hexdigest().lower()
    return hmac.compare_digest(computed, expected)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def meta_webhook_view(request):
    """
    Rota /webhooks/meta/
    GET: hub.verify_token == WHATSAPP_CLOUD_VERIFY_TOKEN -> retorna hub.challenge.
    POST: valida assinatura; processa entry[].changes[].value; idempotência por wamid; cria Conversation/Message.
    Sempre retorna 200 em caso de erro/instância não encontrada (evitar retentativas).
    """
    if request.method == 'GET':
        config_token = getattr(settings, 'WHATSAPP_CLOUD_VERIFY_TOKEN', '') or ''
        token = request.GET.get('hub.verify_token', '')
        challenge = request.GET.get('hub.challenge', '')
        if token and challenge and config_token and token == config_token:
            logger.info("[META WEBHOOK] GET verificação OK, retornando challenge")
            return HttpResponse(challenge, content_type='text/plain')
        logger.warning("[META WEBHOOK] GET verificação falhou (token ou challenge)")
        return HttpResponse('Forbidden', status=403)

    # POST
    try:
        body = request.body
        signature = request.META.get('HTTP_X_HUB_SIGNATURE_256', '')
        if not _verify_meta_signature(body, signature):
            logger.warning("[META WEBHOOK] Assinatura inválida")
            return HttpResponse(status=200)

        data = json.loads(body) if body else {}
        obj = data.get('object', '')
        entries = data.get('entry') or []
        logger.info(
            "[META WEBHOOK] Webhook recebido da Meta object=%s entries=%s",
            obj,
            len(entries),
        )
        if obj != 'whatsapp_business_account':
            logger.info("[META WEBHOOK] object não é whatsapp_business_account, ignorando")
            return HttpResponse(status=200)

        for entry in entries:
            for change in entry.get('changes') or []:
                value = change.get('value') or {}
                if change.get('field') != 'messages':
                    # statuses, etc. podem ser tratados depois
                    continue
                phone_number_id = (value.get('metadata') or {}).get('phone_number_id')
                if not phone_number_id:
                    logger.warning("[META WEBHOOK] phone_number_id ausente em value.metadata")
                    continue
                phone_number_id = str(phone_number_id)
                wa_instance = get_whatsapp_instance_for_meta(phone_number_id)
                if not wa_instance:
                    logger.warning(
                        "[META WEBHOOK] Instância não encontrada para phone_number_id=%s (provider=meta)",
                        _mask_phone_id(phone_number_id),
                    )
                    continue
                if not wa_instance.tenant_id:
                    logger.warning("[META WEBHOOK] Instância sem tenant, phone_number_id=%s", _mask_phone_id(phone_number_id))
                    continue

                _process_meta_value(
                    value=value,
                    wa_instance=wa_instance,
                    instance_name=phone_number_id,
                )
        return HttpResponse(status=200)
    except json.JSONDecodeError as e:
        logger.exception("[META WEBHOOK] JSON inválido: %s", e)
        return HttpResponse(status=200)
    except Exception as e:
        logger.exception("[META WEBHOOK] Erro ao processar POST: %s", e)
        return HttpResponse(status=200)


def _mask_phone_id(pid: str) -> str:
    if not pid or len(pid) <= 4:
        return "***"
    return f"***{pid[-4:]}"
    

def _normalize_phone(phone: str) -> str:
    """Normaliza número para E.164 (só dígitos com +)."""
    if not phone:
        return ""
    digits = "".join(c for c in str(phone) if c.isdigit())
    if not digits:
        return phone.strip()
    if not digits.startswith("55") and len(digits) <= 11:
        digits = "55" + digits
    return "+" + digits


@transaction.atomic
def _process_meta_value(value: dict, wa_instance: WhatsAppInstance, instance_name: str):
    """
    Processa value do webhook Meta: mensagens recebidas e statuses.
    instance_name para Meta = phone_number_id em string (usado em Conversation.instance_name).
    Idempotência por wamid antes de criar Message.
    """
    tenant = wa_instance.tenant
    default_department = wa_instance.default_department
    contacts = {c.get('wa_id'): c.get('profile', {}).get('name') for c in (value.get('contacts') or []) if c.get('wa_id')}
    messages_list = value.get('messages') or []
    statuses_list = value.get('statuses') or []

    for msg in messages_list:
        wamid = msg.get('id')
        if not wamid:
            continue
        # Idempotência: não criar mensagem duplicada
        if Message.objects.filter(message_id=wamid).exists():
            logger.info("[META WEBHOOK] Mensagem já existente (wamid=%s), ignorando (provider=meta)", wamid[:20] + "...")
            continue

        from_phone = msg.get('from', '')
        timestamp = msg.get('timestamp')
        msg_type = msg.get('type', 'text')
        contact_name = contacts.get(from_phone) or (msg.get('profile', {}).get('name')) or ''

        # Apenas mensagens recebidas (não from_me; na API Cloud, mensagens recebidas vêm em 'messages')
        normalized_phone = _normalize_phone(from_phone)
        if not normalized_phone:
            continue

        conversation = _get_or_create_conversation_meta(
            tenant=tenant,
            contact_phone=normalized_phone,
            contact_name=contact_name,
            instance_name=instance_name,
            instance_friendly_name=wa_instance.friendly_name or '',
            default_department=default_department,
        )
        if not conversation:
            continue

        content = ''
        metadata_extra = {}
        if msg_type == 'text':
            content = (msg.get('text') or {}).get('body', '')
        elif msg_type in ('image', 'video', 'document', 'audio'):
            media = msg.get('image') or msg.get('video') or msg.get('document') or msg.get('audio') or {}
            media_id = media.get('id')
            content = (media.get('caption') or '').strip()
            if media_id:
                metadata_extra['meta_media_id'] = media_id
            # Mídia: download via Graph API com Bearer (não usar getBase64FromMediaMessage)
        else:
            content = f'[{msg_type}]'

        message_defaults = {
            'conversation': conversation,
            'content': content or f'[{msg_type}]',
            'direction': 'incoming',
            'status': 'sent',
            'evolution_status': 'received',
            'sender': None,
            'sender_phone': from_phone,
            'sender_name': contact_name or from_phone,
            'metadata': metadata_extra,
        }
        try:
            new_msg = Message.objects.create(
                message_id=wamid,
                **message_defaults,
            )
            logger.info(
                "[META WEBHOOK] Message criada conversation_id=%s message_id=%s (provider=meta instance_id=%s)",
                str(conversation.id),
                wamid[:24],
                str(wa_instance.id),
            )
            # Fase 6: notificar apenas APÓS o commit, para evitar race (agente responde antes da inbound persistida)
            def _broadcast_after_commit():
                try:
                    broadcast_message_received(new_msg)
                except Exception as e:
                    logger.exception("[META WEBHOOK] Erro ao broadcast message_received: %s", e)
            transaction.on_commit(_broadcast_after_commit)
        except Exception as e:
            logger.exception("[META WEBHOOK] Erro ao criar Message (wamid=%s): %s", wamid, e)

    for st in statuses_list:
        # Status updates (delivered, read, etc.) podem ser mapeados depois para Message.status
        logger.debug("[META WEBHOOK] Status recebido: %s (provider=meta)", st.get('id'))


def _get_or_create_conversation_meta(
    tenant,
    contact_phone: str,
    contact_name: str,
    instance_name: str,
    instance_friendly_name: str,
    default_department,
):
    """Get or create Conversation para Meta; instance_name = phone_number_id (string)."""
    existing = Conversation.objects.filter(
        tenant=tenant,
        contact_phone=contact_phone,
        instance_name=instance_name,
    ).first()
    if existing:
        return existing
    defaults = {
        'department': default_department,
        'contact_name': contact_name or contact_phone,
        'instance_name': instance_name,
        'instance_friendly_name': instance_friendly_name,
        'status': 'pending' if not default_department else 'open',
        'conversation_type': 'individual',
    }
    try:
        conv = Conversation.objects.create(
            tenant=tenant,
            contact_phone=contact_phone,
            **defaults,
        )
        try:
            broadcast_conversation_updated(conv)
        except Exception:
            pass
        return conv
    except Exception as e:
        logger.exception("[META WEBHOOK] Erro ao criar Conversation: %s", e)
        return Conversation.objects.filter(
            tenant=tenant,
            contact_phone=contact_phone,
            instance_name=instance_name,
        ).first()


