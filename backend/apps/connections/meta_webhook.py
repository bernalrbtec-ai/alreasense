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
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from datetime import timedelta
from django.db import transaction
from django.utils import timezone as django_timezone
from apps.notifications.models import WhatsAppInstance
from apps.chat.models import Conversation, Message, MessageAttachment, MessageReaction
from apps.chat.utils.websocket import (
    broadcast_conversation_updated,
    broadcast_message_received,
    broadcast_message_reaction_update,
    broadcast_message_status_update,
)

logger = logging.getLogger(__name__)

# Mapeamento status Meta webhook -> nosso Message.status (só para mensagens enviadas por nós)
META_STATUS_TO_INTERNAL = {
    'sent': 'sent',
    'delivered': 'delivered',
    'read': 'seen',
}


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
                    _log_meta_instance_diagnostic(phone_number_id)
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


def _log_meta_instance_diagnostic(phone_number_id: str) -> None:
    """
    Quando a instância não é encontrada, consulta o banco só por phone_number_id + meta_cloud
    e loga status/is_active para diagnóstico (ex.: status=inactive).
    """
    try:
        candidates = WhatsAppInstance.objects.filter(
            phone_number_id=str(phone_number_id).strip(),
            integration_type=WhatsAppInstance.INTEGRATION_TYPE_META_CLOUD,
        ).values('id', 'status', 'is_active', 'tenant_id')[:5]
        candidates = list(candidates)
        if not candidates:
            logger.info(
                "[META WEBHOOK] Diagnóstico: nenhuma instância com phone_number_id=%s e integration_type=meta_cloud no banco",
                _mask_phone_id(phone_number_id),
            )
            return
        for row in candidates:
            logger.warning(
                "[META WEBHOOK] Diagnóstico: instância id=%s tenant_id=%s status=%s is_active=%s (webhook exige status=active e is_active=True)",
                row['id'],
                row['tenant_id'],
                row['status'],
                row['is_active'],
            )
    except Exception as e:
        logger.debug("[META WEBHOOK] Diagnóstico falhou: %s", e)
    

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
        from_phone = msg.get('from', '')
        timestamp = msg.get('timestamp')
        msg_type = msg.get('type', 'text')
        contact_name = contacts.get(from_phone) or (msg.get('profile', {}).get('name')) or ''
        normalized_phone = _normalize_phone(from_phone)
        if not normalized_phone:
            continue

        # Reação: não criar nova Message; criar/atualizar MessageReaction na mensagem original
        if msg_type == 'reaction':
            reaction_obj = msg.get('reaction') or {}
            reaction_message_id = reaction_obj.get('message_id')
            emoji = (reaction_obj.get('emoji') or '').strip()
            if not reaction_message_id:
                logger.warning("[META WEBHOOK] Reação sem message_id, ignorando (wamid=%s)", wamid[:20] + "...")
                continue
            original_message = Message.objects.filter(
                message_id=reaction_message_id,
                conversation__tenant=tenant,
            ).select_related('conversation').first()
            if not original_message:
                logger.warning(
                    "[META WEBHOOK] Reação: mensagem original não encontrada message_id=%s (provider=meta)",
                    reaction_message_id[:24] + "...",
                )
                continue
            try:
                if not emoji:
                    deleted = MessageReaction.objects.filter(
                        message=original_message,
                        external_sender=normalized_phone,
                    ).delete()[0]
                    if deleted:
                        logger.info(
                            "[META WEBHOOK] Reação removida message_id=%s external_sender=%s (provider=meta)",
                            reaction_message_id[:24],
                            normalized_phone[:16],
                        )
                else:
                    reaction, created = MessageReaction.objects.update_or_create(
                        message=original_message,
                        external_sender=normalized_phone,
                        defaults={'emoji': emoji},
                    )
                    logger.info(
                        "[META WEBHOOK] Reação %s message_id=%s emoji=%s external_sender=%s (provider=meta)",
                        "criada" if created else "atualizada",
                        reaction_message_id[:24],
                        emoji,
                        normalized_phone[:16],
                    )
                original_message = Message.objects.prefetch_related('reactions__user').get(id=original_message.id)
                broadcast_message_reaction_update(original_message)
            except Exception as e:
                logger.exception("[META WEBHOOK] Erro ao processar reação: %s", e)
            continue

        # Idempotência: não criar mensagem duplicada por wamid
        if Message.objects.filter(message_id=wamid).exists():
            logger.info("[META WEBHOOK] Mensagem já existente (wamid=%s), ignorando (provider=meta)", wamid[:20] + "...")
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

        # Reabrir conversa fechada quando chega mensagem inbound (alinhado ao Evolution).
        # Janela de despedida: não reabrir se fechou há menos de 2 min (mensagem de fechamento do menu).
        if conversation.status == 'closed':
            last_close_message = Message.objects.filter(
                conversation=conversation,
                direction='outgoing',
                metadata__welcome_menu_close_confirmation=True,
            ).order_by('-created_at').first()
            in_farewell_window = False
            if last_close_message:
                time_since_closure = (django_timezone.now() - last_close_message.created_at).total_seconds() / 60
                if time_since_closure < 2:
                    in_farewell_window = True
                    logger.info(
                        "[META WEBHOOK] Janela de despedida ativa (%.1f min < 2 min) - conversa permanece fechada",
                        time_since_closure,
                    )
            if not in_farewell_window:
                old_status = conversation.status
                old_dept = conversation.department.name if conversation.department else 'Nenhum'
                # Alinhado ao Evolution: se BIA ativa, reabrir no Inbox; senão respeitar default_department
                from apps.ai.models import TenantAiSettings, TenantSecretaryProfile
                secretary_responds = (
                    TenantAiSettings.objects.filter(tenant=tenant).filter(secretary_enabled=True).exists()
                    and TenantSecretaryProfile.objects.filter(tenant=tenant).filter(is_active=True).exists()
                )
                if secretary_responds:
                    conversation.department = None
                    conversation.status = 'pending'
                    logger.info(
                        "[META WEBHOOK] Conversa %s reaberta no Inbox (BIA ativa, secretária pode responder)",
                        normalized_phone[:16],
                    )
                elif default_department:
                    conversation.department = default_department
                    conversation.status = 'open'
                    logger.info(
                        "[META WEBHOOK] Conversa %s reaberta no departamento %s (instância com departamento padrão)",
                        normalized_phone[:16],
                        default_department.name,
                    )
                else:
                    conversation.department = None
                    conversation.status = 'pending'
                    logger.info(
                        "[META WEBHOOK] Conversa %s reaberta no Inbox (sem departamento padrão)",
                        normalized_phone[:16],
                    )
                conversation.assigned_to = None
                conversation.save(update_fields=['status', 'department', 'assigned_to'])
                logger.info(
                    "[META WEBHOOK] Conversa reaberta: %s -> %s (dept: %s -> %s)",
                    old_status,
                    conversation.status,
                    old_dept,
                    conversation.department.name if conversation.department else 'Inbox',
                )

        content = ''
        metadata_extra = {}
        if msg_type == 'text':
            content = (msg.get('text') or {}).get('body', '')
        elif msg_type == 'interactive':
            # Resposta a botão ou lista (reply button / list_reply): exibir título como conteúdo
            interactive_obj = msg.get('interactive') or {}
            itype = interactive_obj.get('type')
            if itype == 'button_reply':
                button_reply = interactive_obj.get('button_reply') or {}
                title = (button_reply.get('title') or button_reply.get('id') or '').strip()
                content = title or 'Resposta de botão'
                metadata_extra['button_reply'] = {'id': button_reply.get('id'), 'title': title}
            elif itype == 'list_reply':
                list_reply = interactive_obj.get('list_reply') or {}
                title = (list_reply.get('title') or list_reply.get('id') or '').strip()
                content = title or 'Resposta de lista'
                metadata_extra['list_reply'] = {'id': list_reply.get('id'), 'title': title}
                if list_reply.get('description'):
                    metadata_extra['list_reply']['description'] = (list_reply.get('description') or '')[:72]
                logger.info(
                    "[META WEBHOOK] list_reply processado conversation_id=%s title=%s (provider=meta)",
                    str(conversation.id),
                    (title or list_reply.get('id') or '')[:50],
                )
            else:
                content = '[interactive]'
        elif msg_type == 'contacts':
            # Mensagem de contato (vCard) recebida pela Meta Cloud.
            contacts_payload = msg.get('contacts') or []
            if isinstance(contacts_payload, dict):
                contacts_payload = [contacts_payload]
            parsed_contacts = []
            for c in contacts_payload:
                if not isinstance(c, dict):
                    continue
                name_obj = c.get('name') or {}
                formatted_name = ''
                if isinstance(name_obj, dict):
                    formatted_name = (name_obj.get('formatted_name') or '').strip()
                formatted_name = formatted_name or 'Contato'
                phone_e164 = ''
                phones = c.get('phones') or []
                if isinstance(phones, list) and phones:
                    first_phone = phones[0]
                    if isinstance(first_phone, dict):
                        raw_phone = first_phone.get('phone') or first_phone.get('wa_id') or ''
                        phone_e164 = _normalize_phone(raw_phone) if raw_phone else ''
                if not phone_e164 and c.get('wa_id'):
                    phone_e164 = _normalize_phone(str(c.get('wa_id', '')))
                parsed_contacts.append(
                    {
                        'display_name': formatted_name,
                        'name': formatted_name,
                        'phone': phone_e164,
                    }
                )
            if parsed_contacts:
                if len(parsed_contacts) == 1:
                    cm = parsed_contacts[0]
                    metadata_extra['contact_message'] = cm
                    display_name = cm.get('display_name') or cm.get('phone') or 'Contato'
                    content = f"📇 Compartilhou contato: {display_name}"
                else:
                    metadata_extra['contact_message'] = {'contacts': parsed_contacts}
                    content = f"📇 Compartilhou {len(parsed_contacts)} contatos"
            else:
                content = "📇 Contato compartilhado"
            logger.info(
                "[META WEBHOOK] contacts processados conversation_id=%s n=%s (provider=meta)",
                str(conversation.id),
                len(parsed_contacts),
            )
        elif msg_type in ('image', 'video', 'document', 'audio'):
            media = msg.get('image') or msg.get('video') or msg.get('document') or msg.get('audio') or {}
            media_id = media.get('id')
            content = (media.get('caption') or '').strip()
            mime_type_meta = media.get('mime_type') or ''
            if media_id:
                metadata_extra['meta_media_id'] = media_id
        else:
            # Debug: tipo de mensagem Meta não mapeado explicitamente
            try:
                msg_keys = list(msg.keys()) if isinstance(msg, dict) else []
            except Exception:
                msg_keys = []
            logger.warning(
                "[META WEBHOOK] Tipo de mensagem não mapeado type=%s keys=%s (provider=meta)",
                msg_type,
                msg_keys,
            )
            content = f'[{msg_type}]'

        # Reply: Meta envia context.id (wamid da mensagem respondida); reply_to_message_id é usado ao enviar
        context = msg.get('context') or {}
        reply_to_wamid = context.get('id') or context.get('reply_to_message_id')
        if reply_to_wamid:
            original_message = Message.objects.filter(
                message_id=reply_to_wamid,
                conversation=conversation,
            ).first()
            if original_message:
                metadata_extra['reply_to'] = str(original_message.id)
                logger.info(
                    "[META WEBHOOK] Reply detectado: reply_to_message_id=%s -> UUID interno=%s (provider=meta)",
                    reply_to_wamid[:24] + "...",
                    metadata_extra['reply_to'],
                )
            else:
                metadata_extra['reply_to_meta_message_id'] = reply_to_wamid
                logger.warning(
                    "[META WEBHOOK] Reply: mensagem original não encontrada reply_to_message_id=%s (provider=meta)",
                    reply_to_wamid[:24] + "...",
                )

        # Idempotência por wamid já evita duplicata quando a Meta reenvia o mesmo evento.
        # Não deduplicar por (conversation, content, tempo) para não descartar uma segunda mensagem legítima com mesmo texto.

        # Para mídia sem legenda: não usar placeholder [document]/[image] (evita texto redundante no chat)
        message_defaults = {
            'conversation': conversation,
            'content': (content or '') if msg_type in ('image', 'video', 'document', 'audio') else (content or f'[{msg_type}]'),
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
                "[META WEBHOOK] Message criada type=%s conversation_id=%s message_id=%s (provider=meta instance_id=%s)",
                msg_type,
                str(conversation.id),
                wamid[:24],
                str(wa_instance.id),
            )
            # Fase 6: notificar apenas APÓS o commit, para evitar race (agente responde antes da inbound persistida)
            def _broadcast_after_commit():
                try:
                    broadcast_conversation_updated(conversation, message_id=str(new_msg.id))
                except Exception as e:
                    logger.exception("[META WEBHOOK] Erro ao broadcast conversation_updated: %s", e)
                try:
                    broadcast_message_received(new_msg)
                except Exception as e:
                    logger.exception("[META WEBHOOK] Erro ao broadcast message_received: %s", e)
            transaction.on_commit(_broadcast_after_commit)

            # BIA (Secretária IA): disparar quando mensagem incoming no Inbox e secretária ativa (inclui conversas reabertas).
            # Callback roda após commit; dispatch_secretary_async revalida condições e ignora grupos no worker.
            if conversation.department_id is None:
                _conv_id, _msg_id, _tenant_id = conversation.id, new_msg.id, tenant.id

                def _dispatch_bia_after_commit():
                    try:
                        from apps.ai.models import TenantAiSettings, TenantSecretaryProfile
                        from apps.ai.secretary_service import dispatch_secretary_async
                        if (
                            TenantAiSettings.objects.filter(tenant_id=_tenant_id).filter(secretary_enabled=True).exists()
                            and TenantSecretaryProfile.objects.filter(tenant_id=_tenant_id).filter(is_active=True).exists()
                        ):
                            conv = Conversation.objects.filter(pk=_conv_id).first()
                            msg = Message.objects.filter(pk=_msg_id).first()
                            if conv and msg:
                                dispatch_secretary_async(conv, msg)
                                logger.info(
                                    "[META WEBHOOK] BIA disparada para conversation_id=%s message_id=%s (provider=meta)",
                                    str(_conv_id),
                                    str(_msg_id),
                                )
                    except Exception as e:
                        logger.exception("[META WEBHOOK] Erro ao disparar BIA: %s", e)
                transaction.on_commit(_dispatch_bia_after_commit)

            # Mídia Meta: criar placeholder (se possível) e sempre enfileirar download via Graph API
            if msg_type in ('image', 'video', 'document', 'audio') and metadata_extra.get('meta_media_id'):
                media_id = metadata_extra['meta_media_id']
                mime = (mime_type_meta or '').strip() or {
                    'image': 'image/jpeg',
                    'video': 'video/mp4',
                    'document': 'application/octet-stream',
                    'audio': 'audio/ogg',
                }.get(msg_type, 'application/octet-stream')
                filename = {'image': 'image', 'video': 'video', 'document': 'document', 'audio': 'audio'}.get(msg_type, 'file')
                try:
                    MessageAttachment.objects.create(
                        message=new_msg,
                        tenant=tenant,
                        original_filename=filename,
                        mime_type=mime,
                        file_path='',
                        file_url='',
                        storage_type='s3',
                        size_bytes=0,
                        expires_at=django_timezone.now() + timedelta(days=365),
                        processing_status='processing',
                        metadata={'meta_media_id': media_id},
                    )
                except Exception as e:
                    logger.exception("[META WEBHOOK] Erro ao criar MessageAttachment (wamid=%s): %s", wamid, e)
                # Enfileirar mesmo se o placeholder falhou: o worker pode criar o attachment ao concluir o download
                def _enqueue_meta_media_after_commit():
                    try:
                        from apps.chat.tasks import process_incoming_media
                        process_incoming_media.delay(
                            tenant_id=str(tenant.id),
                            message_id=str(new_msg.id),
                            media_url='',
                            media_type=msg_type,
                            meta_media_id=media_id,
                            mime_type=mime or None,
                        )
                        logger.info("[META WEBHOOK] process_incoming_media enfileirado (meta_media_id=%s)", media_id[:24] + "...")
                    except Exception as e:
                        logger.exception("[META WEBHOOK] Erro ao enfileirar process_incoming_media: %s", e)
                transaction.on_commit(_enqueue_meta_media_after_commit)
        except Exception as e:
            logger.exception("[META WEBHOOK] Erro ao criar Message (wamid=%s): %s", wamid, e)

    for st in statuses_list:
        wamid = st.get('id')
        meta_status = (st.get('status') or '').strip().lower()
        if not wamid or not meta_status:
            continue
        new_status = META_STATUS_TO_INTERNAL.get(meta_status)
        if not new_status:
            logger.debug("[META WEBHOOK] Status ignorado (não mapeado): %s", meta_status)
            continue
        try:
            message = Message.objects.select_related('conversation').filter(message_id=wamid).first()
            if not message:
                logger.debug("[META WEBHOOK] Mensagem não encontrada para wamid=%s", wamid[:24] + "...")
                continue
            # Só atualizar status de mensagens enviadas por nós (outgoing)
            if message.direction != 'outgoing':
                continue
            # Não rebaixar: se já está seen, não voltar para delivered/sent
            if message.status == 'seen' and new_status != 'seen':
                continue
            if message.status == new_status:
                continue
            old_status = message.status
            message.status = new_status
            message.evolution_status = meta_status
            message.save(update_fields=['status', 'evolution_status'])

            # Sincronizar health da instância Meta com base nos status de entrega/leitura
            try:
                if new_status == 'delivered':
                    wa_instance.record_message_delivered()
                elif new_status == 'seen':
                    # Meta às vezes envia só 'seen' sem 'delivered'; contar delivered também nesse caso
                    if old_status not in ('delivered', 'seen'):
                        wa_instance.record_message_delivered()
                    wa_instance.record_message_read()
            except Exception as e_health:
                logger.exception(
                    "[META WEBHOOK] Erro ao atualizar health da instância para wamid=%s: %s",
                    wamid[:24] + "...",
                    e_health,
                )

            broadcast_message_status_update(message)
            logger.info(
                "[META WEBHOOK] Status atualizado wamid=%s -> %s (provider=meta)",
                wamid[:24] + "...",
                new_status,
            )
        except Exception as e:
            logger.exception("[META WEBHOOK] Erro ao processar status (wamid=%s): %s", wamid[:24] if wamid else "", e)


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


