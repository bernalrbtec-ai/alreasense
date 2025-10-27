"""
Webhook handler para Evolution API.
Recebe eventos de mensagens e atualiza o banco.

✅ SEGURANÇA (Out/2025):
- Validação de token obrigatória (query string)
- Rate limiting por IP (1000 req/min)
- Logs de auditoria de tentativas inválidas
"""
import logging
import httpx
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from apps.chat.models import Conversation, Message, MessageAttachment
from apps.chat.tasks import download_attachment
from apps.tenancy.models import Tenant
from apps.connections.models import EvolutionConnection
from apps.notifications.models import WhatsAppInstance
from apps.common.rate_limiting import rate_limit_by_ip

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([AllowAny])
@rate_limit_by_ip(rate='1000/m', method='POST')  # 1000 webhooks por minuto por IP
def evolution_webhook(request):
    """
    Webhook para receber eventos da Evolution API.
    
    ✅ SEGURANÇA (Out/2025):
    - Validação de token obrigatória (query string)
    - Rate limiting por IP
    - Logs de auditoria
    
    Eventos suportados:
    - messages.upsert: Nova mensagem recebida
    - messages.update: Atualização de status (delivered/read)
    """
    from django.conf import settings
    
    # ========================================
    # 🔐 VALIDAÇÃO DE TOKEN (OBRIGATÓRIA)
    # ========================================
    token = request.GET.get('token')
    
    if not token:
        logger.warning(f"🚨 [WEBHOOK SECURITY] Tentativa sem token!")
        logger.warning(f"   IP: {request.META.get('REMOTE_ADDR')}")
        logger.warning(f"   User-Agent: {request.META.get('HTTP_USER_AGENT', 'Unknown')}")
        return Response(
            {'error': 'Token required'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    # Validar token
    expected_token = getattr(settings, 'EVOLUTION_WEBHOOK_SECRET', None)
    
    if not expected_token:
        logger.error(f"❌ [WEBHOOK SECURITY] EVOLUTION_WEBHOOK_SECRET não configurado no .env!")
        return Response(
            {'error': 'Server configuration error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    if token != expected_token:
        logger.warning(f"🚨 [WEBHOOK SECURITY] Token inválido!")
        logger.warning(f"   IP: {request.META.get('REMOTE_ADDR')}")
        logger.warning(f"   Token recebido: {token[:10]}... (truncado)")
        logger.warning(f"   Token esperado: {expected_token[:10]}... (truncado)")
        return Response(
            {'error': 'Invalid token'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    # ✅ Token válido!
    logger.info(f"✅ [WEBHOOK SECURITY] Token válido - processando webhook")
    
    # ========================================
    # 📥 PROCESSAR WEBHOOK
    # ========================================
    try:
        data = request.data
        event_type = data.get('event')
        instance_name = data.get('instance')
        
        logger.info(f"📥 [WEBHOOK] Evento recebido: {event_type} - {instance_name}")
        
        if not instance_name:
            return Response(
                {'error': 'instance é obrigatório'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Busca conexão pelo nome da instância (field 'name' no modelo)
        try:
            connection = EvolutionConnection.objects.select_related('tenant').get(
                name=instance_name,
                is_active=True
            )
            logger.info(f"✅ [WEBHOOK] Conexão encontrada: {connection.name} - Tenant: {connection.tenant.name}")
        except EvolutionConnection.DoesNotExist:
            logger.warning(f"⚠️ [WEBHOOK] Conexão não encontrada ou inativa: {instance_name}")
            logger.warning(f"   Tentando buscar qualquer conexão ativa do tenant...")
            
            # Fallback: buscar qualquer conexão ativa (se o instance_name não for exato)
            connection = EvolutionConnection.objects.filter(
                is_active=True
            ).select_related('tenant').first()
            
            if not connection:
                logger.error(f"❌ [WEBHOOK] Nenhuma conexão ativa encontrada!")
                return Response(
                    {'error': 'Conexão não encontrada'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            logger.info(f"✅ [WEBHOOK] Usando conexão ativa encontrada: {connection.name} - Tenant: {connection.tenant.name}")
        
        # Roteamento por tipo de evento
        if event_type == 'messages.upsert':
            handle_message_upsert(data, connection.tenant)
        elif event_type == 'messages.update':
            handle_message_update(data, connection.tenant)
        else:
            logger.info(f"ℹ️ [WEBHOOK] Evento não tratado: {event_type}")
        
        return Response({'status': 'ok'}, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"❌ [WEBHOOK] Erro ao processar webhook: {e}", exc_info=True)
        return Response(
            {'error': 'Erro interno'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@transaction.atomic
def handle_message_upsert(data, tenant, connection=None):
    """
    Processa evento de nova mensagem (messages.upsert).
    
    Cria ou atualiza:
    - Conversation
    - Message
    - MessageAttachment (se houver)
    """
    logger.info(f"📥 [WEBHOOK UPSERT] ====== INICIANDO PROCESSAMENTO ======")
    logger.info(f"📥 [WEBHOOK UPSERT] Tenant: {tenant.name} (ID: {tenant.id})")
    logger.info(f"📥 [WEBHOOK UPSERT] Dados recebidos: {data}")
    
    # Nome da instância (ex: "Comercial", "Suporte")
    instance_name = data.get('instance', '')
    logger.info(f"📱 [WEBHOOK UPSERT] Instância: {instance_name}")
    
    try:
        message_data = data.get('data', {})
        key = message_data.get('key', {})
        message_info = message_data.get('message', {})
        
        # Extrai dados
        remote_jid = key.get('remoteJid', '')  # Ex: 5517999999999@s.whatsapp.net ou 120363123456789012@g.us (grupo)
        from_me = key.get('fromMe', False)
        message_id = key.get('id')
        participant = key.get('participant', '')  # Quem enviou no grupo (apenas em grupos)
        
        # 🔍 Detectar tipo de conversa
        # ⚠️ IMPORTANTE: @lid é o novo formato de ID de PARTICIPANTE, não tipo de grupo!
        # Apenas @g.us indica grupos normais do WhatsApp
        is_group = remote_jid.endswith('@g.us')  # @g.us = grupos
        is_broadcast = remote_jid.endswith('@broadcast')
        
        if is_group:
            conversation_type = 'group'
        elif is_broadcast:
            conversation_type = 'broadcast'
        else:
            conversation_type = 'individual'
        
        logger.info(f"🔍 [TIPO] Conversa: {conversation_type} | RemoteJID: {remote_jid}")
        
        # Telefone/ID (depende do tipo)
        if is_group:
            # 👥 GRUPOS: Usar ID completo
            # Evolution API retorna: 5517991106338-1396034900@g.us ou 120363295648424210@g.us
            # Precisamos manter o formato completo (@g.us) para usar na API depois
            phone = remote_jid  # Mantém formato completo: xxx@g.us
        else:
            # 👤 INDIVIDUAIS: Extrair número e adicionar +
            phone = remote_jid.split('@')[0]
            if not phone.startswith('+'):
                phone = '+' + phone
        
        # Para grupos, extrair quem enviou
        sender_phone = ''
        sender_name = ''
        if is_group and participant:
            # 🆕 Usar participantAlt se disponível (formato @s.whatsapp.net = número real)
            # Caso contrário, usar participant (pode ser @lid = novo formato de ID)
            participant_to_use = key.get('participantAlt', participant)
            sender_phone = participant_to_use.split('@')[0]
            if not sender_phone.startswith('+'):
                sender_phone = '+' + sender_phone
            sender_name = message_data.get('pushName', '')  # Nome de quem enviou
            logger.info(f"👥 [GRUPO] Enviado por: {sender_name} ({sender_phone})")
        
        # Tipo de mensagem
        message_type = message_data.get('messageType', 'text')
        
        # Conteúdo
        if message_type == 'conversation':
            content = message_info.get('conversation', '')
        elif message_type == 'extendedTextMessage':
            content = message_info.get('extendedTextMessage', {}).get('text', '')
        elif message_type == 'imageMessage':
            content = message_info.get('imageMessage', {}).get('caption', '')
        elif message_type == 'videoMessage':
            content = message_info.get('videoMessage', {}).get('caption', '')
        elif message_type == 'documentMessage':
            content = message_info.get('documentMessage', {}).get('caption', '')
        elif message_type == 'audioMessage':
            content = ''  # Player de áudio já é auto-explicativo, não precisa de texto
        else:
            content = f'[{message_type}]'
        
        # Nome do contato
        push_name = message_data.get('pushName', '')
        
        # Foto de perfil (se disponível)
        profile_pic_url = message_data.get('profilePicUrl', '')
        
        # Log da mensagem recebida
        direction_str = "📤 ENVIADA" if from_me else "📥 RECEBIDA"
        logger.info(f"{direction_str} [WEBHOOK] {phone}: {content[:50]}...")
        logger.info(f"   Tenant: {tenant.name} | Message ID: {message_id}")
        logger.info(f"   👤 Nome: {push_name} | 📸 Foto de Perfil: {profile_pic_url[:100] if profile_pic_url else 'NÃO ENVIADA'}")
        
        # Busca ou cria conversa
        # Nova conversa vai para INBOX (pending) sem departamento
        
        # 🔧 FIX: Só usar pushName se mensagem veio do contato (not from_me)
        # Se você enviou a primeira mensagem, deixar vazio e buscar via API
        contact_name_to_save = push_name if not from_me else ''
        
        # Para grupos, usar o ID do grupo como identificador único
        defaults = {
            'department': None,  # Inbox: sem departamento
            'contact_name': contact_name_to_save,
            'profile_pic_url': profile_pic_url if profile_pic_url else None,
            'instance_name': instance_name,  # Salvar instância de origem
            'status': 'pending',  # Pendente para classificação
            'conversation_type': conversation_type,
        }
        
        # Para grupos, adicionar metadados
        # ⚠️ pushName é de quem ENVIOU, não do grupo! Nome real virá da API
        if is_group:
            defaults['contact_name'] = 'Grupo WhatsApp'  # Placeholder até buscar da API
            defaults['group_metadata'] = {
                'group_id': remote_jid,
                'group_name': 'Grupo WhatsApp',  # Placeholder - será atualizado pela API
                'is_group': True,
            }
        
        conversation, created = Conversation.objects.get_or_create(
            tenant=tenant,
            contact_phone=phone,
            defaults=defaults
        )
        
        logger.info(f"📋 [CONVERSA] {'NOVA' if created else 'EXISTENTE'}: {phone} | Tipo: {conversation_type}")
        
        if created:
            logger.info(f"✅ [WEBHOOK] Nova conversa criada: {phone} (Inbox)")
            
            # 📸 Buscar foto de perfil SÍNCRONAMENTE (é rápida)
            logger.info(f"📸 [FOTO] Iniciando busca... | Tipo: {conversation_type} | É grupo: {is_group}")
            try:
                import httpx
                
                # Buscar instância WhatsApp ativa do tenant
                wa_instance = WhatsAppInstance.objects.filter(
                    tenant=tenant,
                    is_active=True,
                    status='active'
                ).first()
                
                # Buscar servidor Evolution
                evolution_server = EvolutionConnection.objects.filter(is_active=True).first()
                
                if wa_instance and evolution_server:
                    logger.info(f"📸 [WEBHOOK] Buscando foto de perfil...")
                    
                    base_url = (wa_instance.api_url or evolution_server.base_url).rstrip('/')
                    api_key = wa_instance.api_key or evolution_server.api_key
                    instance_name = wa_instance.instance_name
                    
                    headers = {
                        'apikey': api_key,
                        'Content-Type': 'application/json'
                    }
                    
                    # 👥 Para GRUPOS: usar endpoint /group/findGroupInfos
                    if is_group:
                        group_jid = remote_jid
                        logger.info(f"👥 [GRUPO NOVO] Buscando informações com Group JID: {group_jid}")
                        
                        endpoint = f"{base_url}/group/findGroupInfos/{instance_name}"
                        
                        with httpx.Client(timeout=5.0) as client:
                            response = client.get(
                                endpoint,
                                params={'groupJid': group_jid},
                                headers=headers
                            )
                            
                            if response.status_code == 200:
                                group_info = response.json()
                                logger.info(f"✅ [GRUPO NOVO] Informações recebidas!")
                                
                                # Extrair dados
                                group_name = group_info.get('subject', '')
                                group_pic_url = group_info.get('pictureUrl')
                                participants_count = group_info.get('size', 0)
                                group_desc = group_info.get('desc', '')
                                
                                # Atualizar conversa
                                update_fields = []
                                
                                if group_name:
                                    conversation.contact_name = group_name
                                    update_fields.append('contact_name')
                                    logger.info(f"✅ [GRUPO NOVO] Nome: {group_name}")
                                
                                if group_pic_url:
                                    conversation.profile_pic_url = group_pic_url
                                    update_fields.append('profile_pic_url')
                                    logger.info(f"✅ [GRUPO NOVO] Foto: {group_pic_url[:50]}...")
                                
                                # Atualizar metadados
                                conversation.group_metadata = {
                                    'group_id': remote_jid,
                                    'group_name': group_name,
                                    'group_pic_url': group_pic_url,
                                    'participants_count': participants_count,
                                    'description': group_desc,
                                    'is_group': True,
                                }
                                update_fields.append('group_metadata')
                                
                                if update_fields:
                                    conversation.save(update_fields=update_fields)
                            else:
                                logger.warning(f"⚠️ [GRUPO NOVO] Erro ao buscar: {response.status_code}")
                    
                    # 👤 Para INDIVIDUAIS: buscar foto E nome do contato via API
                    else:
                        clean_phone = phone.replace('+', '').replace('@s.whatsapp.net', '')
                        logger.info(f"👤 [INDIVIDUAL] Buscando informações do contato: {clean_phone}")
                        
                        update_fields = []
                        
                        # 1️⃣ Buscar foto de perfil
                        endpoint = f"{base_url}/chat/fetchProfilePictureUrl/{instance.name}"
                        
                        with httpx.Client(timeout=5.0) as client:
                            response = client.get(
                                endpoint,
                                params={'number': clean_phone},
                                headers=headers
                            )
                            
                            if response.status_code == 200:
                                data = response.json()
                                profile_url = (
                                    data.get('profilePictureUrl') or
                                    data.get('profilePicUrl') or
                                    data.get('url') or
                                    data.get('picture')
                                )
                                
                                if profile_url:
                                    conversation.profile_pic_url = profile_url
                                    update_fields.append('profile_pic_url')
                                    logger.info(f"✅ [INDIVIDUAL] Foto encontrada: {profile_url[:50]}...")
                                else:
                                    logger.info(f"ℹ️ [INDIVIDUAL] Foto não disponível")
                            else:
                                logger.warning(f"⚠️ [INDIVIDUAL] Erro ao buscar foto: {response.status_code}")
                        
                        # 2️⃣ Buscar nome do contato (se não tiver)
                        if not conversation.contact_name:
                            logger.info(f"👤 [INDIVIDUAL] Nome vazio, buscando na API...")
                            endpoint = f"{base_url}/chat/whatsappNumbers/{instance.name}"
                            
                            with httpx.Client(timeout=5.0) as client:
                                try:
                                    response = client.post(
                                        endpoint,
                                        json={'numbers': [clean_phone]},
                                        headers=headers
                                    )
                                    
                                    if response.status_code == 200:
                                        data = response.json()
                                        # Resposta: [{"jid": "...", "exists": true, "name": "..."}]
                                        if data and len(data) > 0:
                                            contact_info = data[0]
                                            contact_name = contact_info.get('name') or contact_info.get('pushname', '')
                                            
                                            if contact_name:
                                                conversation.contact_name = contact_name
                                                update_fields.append('contact_name')
                                                logger.info(f"✅ [INDIVIDUAL] Nome encontrado via API: {contact_name}")
                                            else:
                                                # Fallback: usar o número
                                                conversation.contact_name = clean_phone
                                                update_fields.append('contact_name')
                                                logger.info(f"ℹ️ [INDIVIDUAL] Nome não disponível, usando número")
                                    else:
                                        logger.warning(f"⚠️ [INDIVIDUAL] Erro ao buscar nome: {response.status_code}")
                                        # Fallback: usar o número
                                        conversation.contact_name = clean_phone
                                        update_fields.append('contact_name')
                                except Exception as e:
                                    logger.error(f"❌ [INDIVIDUAL] Erro ao buscar nome: {e}")
                                    # Fallback: usar o número
                                    conversation.contact_name = clean_phone
                                    update_fields.append('contact_name')
                        
                        # Salvar atualizações
                        if update_fields:
                            conversation.save(update_fields=update_fields)
                            logger.info(f"✅ [INDIVIDUAL] Conversa atualizada: {', '.join(update_fields)}")
                else:
                    logger.info(f"ℹ️ [WEBHOOK] Nenhuma instância Evolution ativa para buscar foto")
            except Exception as e:
                logger.error(f"❌ [WEBHOOK] Erro ao buscar foto de perfil: {e}")
        
        # 📸 Para conversas EXISTENTES de GRUPO: atualizar APENAS se falta dados
        # (Atualização on-demand acontece quando usuário ABRE o grupo no frontend)
        elif is_group and (not conversation.profile_pic_url or not conversation.group_metadata.get('group_name')):
            logger.info(f"📸 [GRUPO] Falta dados básicos → buscando agora")
            if True:  # Manter indentação do bloco try/except abaixo
                logger.info(f"📸 [GRUPO INFO] Buscando informações completas do grupo...")
                try:
                    import httpx
                    
                    # Buscar instância WhatsApp ativa do tenant
                    wa_instance = WhatsAppInstance.objects.filter(
                        tenant=tenant,
                        is_active=True,
                        status='active'
                    ).first()
                    
                    # Buscar servidor Evolution
                    evolution_server = EvolutionConnection.objects.filter(is_active=True).first()
                    
                    if wa_instance and evolution_server:
                        group_jid = remote_jid
                        logger.info(f"👥 [GRUPO INFO] Buscando com Group JID: {group_jid}")
                        
                        base_url = (wa_instance.api_url or evolution_server.base_url).rstrip('/')
                        api_key = wa_instance.api_key or evolution_server.api_key
                        instance_name = wa_instance.instance_name
                        
                        # ✅ Endpoint CORRETO para grupos: /group/findGroupInfos
                        endpoint = f"{base_url}/group/findGroupInfos/{instance_name}"
                        
                        headers = {
                            'apikey': api_key,
                            'Content-Type': 'application/json'
                        }
                        
                        with httpx.Client(timeout=5.0) as client:
                            response = client.get(
                                endpoint,
                                params={'groupJid': group_jid},
                                headers=headers
                            )
                            
                            if response.status_code == 200:
                                group_info = response.json()
                                logger.info(f"✅ [GRUPO INFO] Informações recebidas: {group_info}")
                                
                                # Extrair dados do grupo
                                group_name = group_info.get('subject', '')
                                group_pic_url = group_info.get('pictureUrl')
                                participants_count = group_info.get('size', 0)
                                group_desc = group_info.get('desc', '')
                                
                                # Atualizar conversa
                                update_fields = []
                                
                                if group_name:
                                    conversation.contact_name = group_name
                                    update_fields.append('contact_name')
                                    logger.info(f"✅ [GRUPO INFO] Nome do grupo: {group_name}")
                                
                                if group_pic_url:
                                    conversation.profile_pic_url = group_pic_url
                                    update_fields.append('profile_pic_url')
                                    logger.info(f"✅ [GRUPO INFO] Foto do grupo: {group_pic_url[:50]}...")
                                
                                # Atualizar metadados
                                conversation.group_metadata = {
                                    'group_id': remote_jid,
                                    'group_name': group_name,
                                    'group_pic_url': group_pic_url,
                                    'participants_count': participants_count,
                                    'description': group_desc,
                                    'is_group': True,
                                }
                                update_fields.append('group_metadata')
                                
                                if update_fields:
                                    conversation.save(update_fields=update_fields)
                                    logger.info(f"✅ [GRUPO INFO] Conversa atualizada com {len(update_fields)} campos")
                            else:
                                logger.warning(f"⚠️ [GRUPO INFO] Erro ao buscar: {response.status_code}")
                                logger.warning(f"   Response: {response.text[:200]}")
                except Exception as e:
                    logger.error(f"❌ [GRUPO INFO] Erro ao buscar informações: {e}", exc_info=True)
            
            # 📡 Broadcast nova conversa para o tenant (todos os departamentos veem Inbox)
            try:
                from apps.chat.api.serializers import ConversationSerializer
                conv_data = ConversationSerializer(conversation).data
                
                # Converter UUIDs para string
                def convert_uuids_to_str(obj):
                    import uuid
                    if isinstance(obj, uuid.UUID):
                        return str(obj)
                    elif isinstance(obj, dict):
                        return {k: convert_uuids_to_str(v) for k, v in obj.items()}
                    elif isinstance(obj, list):
                        return [convert_uuids_to_str(item) for item in obj]
                    return obj
                
                conv_data_serializable = convert_uuids_to_str(conv_data)
                
                # Broadcast para todo o tenant (Inbox é visível para todos)
                channel_layer = get_channel_layer()
                tenant_group = f"chat_tenant_{tenant.id}"
                
                logger.info(f"🚀 [WEBSOCKET] Enviando broadcast de NOVA CONVERSA...")
                logger.info(f"   Tenant ID: {tenant.id}")
                logger.info(f"   Tenant Group: {tenant_group}")
                logger.info(f"   Conversation ID: {conversation.id}")
                logger.info(f"   Contact: {conversation.contact_name or phone}")
                
                async_to_sync(channel_layer.group_send)(
                    tenant_group,
                    {
                        'type': 'new_conversation',
                        'conversation': conv_data_serializable
                    }
                )
                
                logger.info(f"✅ [WEBSOCKET] Broadcast de nova conversa enviado com sucesso!")
            except Exception as e:
                logger.error(f"❌ [WEBSOCKET] Erro ao fazer broadcast de nova conversa: {e}", exc_info=True)
        else:
            # Se conversa estava fechada, reabrir automaticamente
            if conversation.status == 'closed':
                conversation.status = 'pending' if not from_me else 'open'
                conversation.save(update_fields=['status'])
                status_str = "Inbox" if not from_me else "Aberta"
                logger.info(f"🔄 [WEBHOOK] Conversa {phone} reaberta automaticamente ({status_str})")
        
        # Atualiza nome e foto se mudaram
        update_fields = []
        if push_name and conversation.contact_name != push_name:
            conversation.contact_name = push_name
            update_fields.append('contact_name')
        
        if profile_pic_url and conversation.profile_pic_url != profile_pic_url:
            conversation.profile_pic_url = profile_pic_url
            update_fields.append('profile_pic_url')
            logger.info(f"📸 [WEBHOOK] Foto de perfil atualizada: {profile_pic_url[:50]}...")
        
        if update_fields:
            conversation.save(update_fields=update_fields)
            
            # 📡 Broadcast atualização via WebSocket
            try:
                from apps.chat.api.serializers import ConversationSerializer
                conv_data = ConversationSerializer(conversation).data
                
                # Converter UUIDs para string
                def convert_uuids_to_str(obj):
                    import uuid
                    if isinstance(obj, uuid.UUID):
                        return str(obj)
                    elif isinstance(obj, dict):
                        return {k: convert_uuids_to_str(v) for k, v in obj.items()}
                    elif isinstance(obj, list):
                        return [convert_uuids_to_str(item) for item in obj]
                    return obj
                
                conv_data_serializable = convert_uuids_to_str(conv_data)
                
                channel_layer = get_channel_layer()
                tenant_group = f"chat_tenant_{tenant.id}"
                
                async_to_sync(channel_layer.group_send)(
                    tenant_group,
                    {
                        'type': 'conversation_updated',
                        'conversation': conv_data_serializable
                    }
                )
                
                logger.info(f"📡 [WEBSOCKET] Atualização de conversa broadcast (nome/foto)")
            except Exception as e:
                logger.error(f"❌ [WEBSOCKET] Erro ao broadcast atualização: {e}", exc_info=True)
        
        # Cria mensagem
        direction = 'outgoing' if from_me else 'incoming'
        
        message_defaults = {
            'conversation': conversation,
            'content': content,
            'direction': direction,
            'status': 'sent',
            'evolution_status': 'sent'
        }
        
        # Para grupos, adicionar quem enviou
        if is_group and sender_phone:
            message_defaults['sender_name'] = sender_name
            message_defaults['sender_phone'] = sender_phone
        
        message, msg_created = Message.objects.get_or_create(
            message_id=message_id,
            defaults=message_defaults
        )
        
        if msg_created:
            logger.info(f"✅ [WEBHOOK] Mensagem {direction} salva no banco")
            logger.info(f"   ID: {message.id} | Conversa: {conversation.id}")
            
            # Se tiver anexo, processa
            attachment_url = None
            mime_type = None
            filename = ''
            
            if message_type == 'imageMessage':
                attachment_url = message_info.get('imageMessage', {}).get('url')
                mime_type = message_info.get('imageMessage', {}).get('mimetype', 'image/jpeg')
                filename = f"{message.id}.jpg"
            elif message_type == 'videoMessage':
                attachment_url = message_info.get('videoMessage', {}).get('url')
                mime_type = message_info.get('videoMessage', {}).get('mimetype', 'video/mp4')
                filename = f"{message.id}.mp4"
            elif message_type == 'documentMessage':
                attachment_url = message_info.get('documentMessage', {}).get('url')
                mime_type = message_info.get('documentMessage', {}).get('mimetype', 'application/octet-stream')
                filename = message_info.get('documentMessage', {}).get('fileName', f"{message.id}.bin")
            elif message_type == 'audioMessage':
                attachment_url = message_info.get('audioMessage', {}).get('url')
                mime_type = message_info.get('audioMessage', {}).get('mimetype', 'audio/ogg')
                filename = f"{message.id}.ogg"
            
            if attachment_url:
                # Usar transaction para garantir que o anexo seja salvo antes de enfileirar
                from django.db import transaction
                with transaction.atomic():
                    attachment = MessageAttachment.objects.create(
                        message=message,
                        tenant=tenant,
                        original_filename=filename,
                        mime_type=mime_type,
                        file_path='',  # Será preenchido após download
                        file_url=attachment_url,
                        storage_type='local'
                    )
                    # Força commit antes de enfileirar
                    transaction.on_commit(
                        lambda: download_attachment.delay(str(attachment.id), attachment_url)
                    )
                logger.info(f"📎 [WEBHOOK] Anexo enfileirado para download: {filename}")
            
            # Broadcast via WebSocket (mensagem específica)
            logger.info(f"📡 [WEBHOOK] Enviando para WebSocket da conversa...")
            broadcast_message_to_websocket(message, conversation)
            
            # 🔔 IMPORTANTE: Se for mensagem recebida (não enviada por nós)
            if not from_me:
                # 1. Enviar ACK de entrega automático para o WhatsApp
                logger.info(f"📬 [WEBHOOK] Enviando ACK de entrega automático...")
                try:
                    send_delivery_receipt(conversation, message)
                except Exception as ack_error:
                    logger.error(f"❌ [WEBHOOK] Erro ao enviar ACK de entrega: {ack_error}", exc_info=True)
                
                # 2. Notificar tenant sobre nova mensagem (toast)
                logger.info(f"📬 [WEBHOOK] Notificando tenant sobre nova mensagem...")
                try:
                    from apps.chat.api.serializers import ConversationSerializer
                    conv_data = ConversationSerializer(conversation).data
                    
                    # Converter UUIDs para string
                    def convert_uuids_to_str(obj):
                        import uuid
                        if isinstance(obj, uuid.UUID):
                            return str(obj)
                        elif isinstance(obj, dict):
                            return {k: convert_uuids_to_str(v) for k, v in obj.items()}
                        elif isinstance(obj, list):
                            return [convert_uuids_to_str(item) for item in obj]
                        return obj
                    
                    conv_data_serializable = convert_uuids_to_str(conv_data)
                    
                    # Broadcast para todo o tenant (notificação de nova mensagem)
                    channel_layer = get_channel_layer()
                    tenant_group = f"chat_tenant_{tenant.id}"
                    
                    # 📱 Para GRUPOS: Nome do grupo + quem enviou
                    if is_group:
                        group_name = conversation.group_metadata.get('group_name', 'Grupo WhatsApp') if conversation.group_metadata else 'Grupo WhatsApp'
                        # Pegar nome de quem enviou (sender_name já foi extraído no início)
                        sender_display = sender_name if sender_name else 'Alguém'
                        notification_text = f"📱 {group_name}\n{sender_display} enviou uma mensagem"
                    else:
                        notification_text = content[:100]  # Primeiros 100 caracteres para contatos individuais
                    
                    async_to_sync(channel_layer.group_send)(
                        tenant_group,
                        {
                            'type': 'new_message_notification',
                            'conversation': conv_data_serializable,
                            'message': {
                                'content': notification_text,
                                'created_at': message.created_at.isoformat(),
                                'is_group': is_group
                            }
                        }
                    )
                    
                    logger.info(f"📡 [WEBSOCKET] Notificação de nova mensagem broadcast para tenant {tenant.name}")
                except Exception as e:
                    logger.error(f"❌ [WEBSOCKET] Erro ao fazer broadcast de notificação: {e}", exc_info=True)
        
        else:
            logger.info(f"ℹ️ [WEBHOOK] Mensagem já existe no banco: {message_id}")
    
    except Exception as e:
        logger.error(f"❌ [WEBHOOK] Erro ao processar messages.upsert: {e}", exc_info=True)


def handle_message_update(data, tenant):
    """
    Processa evento de atualização de status (messages.update).
    Atualiza status: delivered, read
    """
    logger.info(f"🔄 [WEBHOOK UPDATE] Iniciando processamento...")
    
    try:
        # 🔧 Evolution API pode enviar 'data' como LISTA ou DICT
        raw_data = data.get('data', {})
        
        # Se for lista, pegar o primeiro item
        if isinstance(raw_data, list):
            if len(raw_data) == 0:
                logger.warning(f"⚠️ [WEBHOOK UPDATE] data está vazio")
                return
            message_data = raw_data[0]
            logger.info(f"📋 [WEBHOOK UPDATE] data é LISTA, usando primeiro item")
        else:
            message_data = raw_data
            logger.info(f"📋 [WEBHOOK UPDATE] data é DICT")
        
        # Estrutura pode variar: key.id ou messageId direto
        # IMPORTANTE: Usar keyId (ID real) ao invés de messageId (ID interno Evolution)
        key = message_data.get('key', {}) if isinstance(message_data, dict) else {}
        key_id = message_data.get('keyId') if isinstance(message_data, dict) else None
        message_id_evo = message_data.get('messageId') if isinstance(message_data, dict) else None
        message_id = key.get('id') if isinstance(key, dict) else None
        
        if not message_id:
            message_id = key_id or message_id_evo
        
        # Status: delivered, read
        update = message_data.get('update', {})
        status_value = update.get('status') or message_data.get('status', '').upper()
        
        logger.info(f"🔍 [WEBHOOK UPDATE] Buscando mensagem...")
        logger.info(f"   key.id: {key.get('id')}")
        logger.info(f"   keyId: {key_id}")
        logger.info(f"   messageId (evo): {message_id_evo}")
        logger.info(f"   Status recebido: {status_value}")
        
        if not message_id or not status_value:
            logger.warning(f"⚠️ [WEBHOOK UPDATE] Dados insuficientes!")
            logger.warning(f"   message_id: {message_id}")
            logger.warning(f"   status: {status_value}")
            return
        
        # Busca mensagem - tentar com keyId primeiro
        message = None
        
        # Tentar com keyId
        if key_id:
            try:
                message = Message.objects.select_related('conversation').get(message_id=key_id)
                logger.info(f"✅ [WEBHOOK UPDATE] Mensagem encontrada via keyId!")
            except Message.DoesNotExist:
                pass
        
        # Se não encontrou, tentar com key.id
        if not message and key.get('id'):
            try:
                message = Message.objects.select_related('conversation').get(message_id=key.get('id'))
                logger.info(f"✅ [WEBHOOK UPDATE] Mensagem encontrada via key.id!")
            except Message.DoesNotExist:
                pass
        
        # Se não encontrou, tentar com messageId do Evolution
        if not message and message_id_evo:
            try:
                message = Message.objects.select_related('conversation').get(message_id=message_id_evo)
                logger.info(f"✅ [WEBHOOK UPDATE] Mensagem encontrada via messageId!")
            except Message.DoesNotExist:
                pass
        
        if not message:
            logger.warning(f"⚠️ [WEBHOOK UPDATE] Mensagem não encontrada no banco!")
            logger.warning(f"   Tentou: keyId={key_id}, key.id={key.get('id')}, messageId={message_id_evo}")
            return
        
        logger.info(f"✅ [WEBHOOK UPDATE] Mensagem encontrada!")
        logger.info(f"   ID no banco: {message.id}")
        logger.info(f"   Conversa: {message.conversation.contact_phone}")
        logger.info(f"   Status atual: {message.status}")
        
        # Mapeia status (aceita múltiplos formatos)
        status_map = {
            'PENDING': 'pending',
            'SERVER_ACK': 'sent',
            'DELIVERY_ACK': 'delivered',
            'READ': 'seen',
            # Formatos alternativos
            'delivered': 'delivered',
            'delivery_ack': 'delivered',
            'read': 'seen',
            'read_ack': 'seen',
            'sent': 'sent'
        }
        
        new_status = status_map.get(status_value.lower()) or status_map.get(status_value)
        
        if not new_status:
            logger.warning(f"⚠️ [WEBHOOK UPDATE] Status não mapeado: {status_value}")
            return
        
        if message.status != new_status:
            old_status = message.status
            
            # ✅ CORREÇÃO CRÍTICA: Ignorar status READ para mensagens INCOMING
            # Mensagens incoming são marcadas como lidas pelo USUÁRIO via mark_as_read(),
            # não pelo WhatsApp via webhook. WhatsApp envia READ apenas para mensagens
            # OUTGOING (quando o destinatário lê nossa mensagem).
            if new_status == 'seen' and message.direction == 'incoming':
                logger.info(f"⏸️ [WEBHOOK UPDATE] Ignorando status READ para mensagem INCOMING")
                logger.info(f"   Direction: {message.direction}")
                logger.info(f"   Mensagens incoming são marcadas como lidas pelo USUÁRIO")
                logger.info(f"   WhatsApp não controla status de leitura de mensagens que ELE enviou para NÓS")
                return
            
            message.status = new_status
            message.evolution_status = status_value
            message.save(update_fields=['status', 'evolution_status'])
            
            logger.info(f"✅ [WEBHOOK UPDATE] Status atualizado!")
            logger.info(f"   Direction: {message.direction}")
            logger.info(f"   {old_status} → {new_status}")
            logger.info(f"   Evolution status: {status_value}")
            
            # Broadcast via WebSocket
            logger.info(f"📡 [WEBHOOK UPDATE] Enviando atualização via WebSocket...")
            broadcast_status_update(message)
        else:
            logger.info(f"ℹ️ [WEBHOOK UPDATE] Status já está como '{new_status}', sem alteração")
    
    except Exception as e:
        logger.error(f"❌ [WEBHOOK] Erro ao processar messages.update: {e}", exc_info=True)


def broadcast_message_to_websocket(message, conversation):
    """Envia nova mensagem via WebSocket para o grupo da conversa."""
    try:
        channel_layer = get_channel_layer()
        room_group_name = f"chat_tenant_{conversation.tenant_id}_conversation_{conversation.id}"
        
        from apps.chat.api.serializers import MessageSerializer
        message_data = MessageSerializer(message).data
        
        logger.info(f"📡 [WEBSOCKET] Preparando broadcast...")
        logger.info(f"   Room: {room_group_name}")
        logger.info(f"   Direction: {message.direction}")
        
        # Converter UUIDs para string para serialização msgpack
        def convert_uuids_to_str(obj):
            """Recursivamente converte UUIDs para string."""
            import uuid
            if isinstance(obj, uuid.UUID):
                return str(obj)
            elif isinstance(obj, dict):
                return {k: convert_uuids_to_str(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_uuids_to_str(item) for item in obj]
            return obj
        
        message_data_serializable = convert_uuids_to_str(message_data)
        
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'message_received',
                'message': message_data_serializable
            }
        )
        
        logger.info(f"✅ [WEBSOCKET] Mensagem broadcast com sucesso!")
        logger.info(f"   Message ID: {message.id} | Content: {message.content[:30]}...")
    
    except Exception as e:
        logger.error(f"❌ [WEBSOCKET] Erro ao fazer broadcast: {e}", exc_info=True)


def broadcast_status_update(message):
    """
    Envia atualização de status via WebSocket.
    
    ✅ REFATORADO: Usa função centralizada de utils/websocket.py
    """
    from apps.chat.utils.websocket import broadcast_message_status_update
    broadcast_message_status_update(message)


def send_delivery_receipt(conversation: Conversation, message: Message):
    """
    Envia ACK de ENTREGA (delivered) para Evolution API.
    Isso fará com que o remetente veja ✓✓ cinza no WhatsApp dele.
    """
    try:
        # Buscar instância WhatsApp ativa do tenant
        wa_instance = WhatsAppInstance.objects.filter(
            tenant=conversation.tenant,
            is_active=True,
            status='active'
        ).first()
        
        if not wa_instance:
            logger.warning(f"⚠️ [DELIVERY ACK] Nenhuma instância WhatsApp ativa para tenant {conversation.tenant.name}")
            return
        
        # Buscar servidor Evolution
        evolution_server = EvolutionConnection.objects.filter(is_active=True).first()
        if not evolution_server:
            logger.warning(f"⚠️ [DELIVERY ACK] Servidor Evolution não configurado")
            return
        
        # Endpoint da Evolution API para enviar ACK de entrega
        base_url = (wa_instance.api_url or evolution_server.base_url).rstrip('/')
        api_key = wa_instance.api_key or evolution_server.api_key
        instance_name = wa_instance.instance_name
        
        url = f"{base_url}/chat/markMessageAsRead/{instance_name}"
        
        # Payload para ACK de entrega (só marca como delivered, não como read)
        # Na Evolution API, geralmente o endpoint é o mesmo, mas há diferença no payload
        payload = {
            "readMessages": [
                {
                    "remoteJid": f"{conversation.contact_phone.replace('+', '')}@s.whatsapp.net",
                    "id": message.message_id,
                    "fromMe": False
                }
            ]
        }
        
        headers = {
            "Content-Type": "application/json",
            "apikey": api_key
        }
        
        logger.info(f"📬 [DELIVERY ACK] Enviando ACK de entrega...")
        logger.info(f"   URL: {url}")
        logger.info(f"   Message ID: {message.message_id}")
        logger.info(f"   Contact: {conversation.contact_phone}")
        
        # Enviar request de forma síncrona
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=payload, headers=headers)
            
            if response.status_code == 200 or response.status_code == 201:
                logger.info(f"✅ [DELIVERY ACK] ACK de entrega enviado!")
                logger.info(f"   Response: {response.text[:200]}")
                
                # Atualizar status local da mensagem
                message.status = 'delivered'
                message.save(update_fields=['status'])
            else:
                logger.warning(f"⚠️ [DELIVERY ACK] Resposta não esperada: {response.status_code}")
                logger.warning(f"   Response: {response.text[:300]}")
    
    except Exception as e:
        logger.error(f"❌ [DELIVERY ACK] Erro ao enviar ACK de entrega: {e}", exc_info=True)


def send_read_receipt(conversation: Conversation, message: Message):
    """
    Envia confirmação de LEITURA (read) para Evolution API.
    Isso fará com que o remetente veja ✓✓ azul no WhatsApp dele.
    """
    try:
        # Buscar instância WhatsApp ativa do tenant
        wa_instance = WhatsAppInstance.objects.filter(
            tenant=conversation.tenant,
            is_active=True,
            status='active'
        ).first()
        
        if not wa_instance:
            logger.warning(f"⚠️ [READ RECEIPT] Nenhuma instância WhatsApp ativa para tenant {conversation.tenant.name}")
            return
        
        # Buscar servidor Evolution
        evolution_server = EvolutionConnection.objects.filter(is_active=True).first()
        if not evolution_server:
            logger.warning(f"⚠️ [READ RECEIPT] Servidor Evolution não configurado")
            return
        
        # Endpoint da Evolution API para marcar como lida
        # Formato: POST /chat/markMessageAsRead/{instance}
        base_url = (wa_instance.api_url or evolution_server.base_url).rstrip('/')
        api_key = wa_instance.api_key or evolution_server.api_key
        instance_name = wa_instance.instance_name
        
        url = f"{base_url}/chat/markMessageAsRead/{instance_name}"
        
        # Payload para marcar mensagem como lida
        payload = {
            "readMessages": [
                {
                    "remoteJid": f"{conversation.contact_phone.replace('+', '')}@s.whatsapp.net",
                    "id": message.message_id,
                    "fromMe": False
                }
            ]
        }
        
        headers = {
            "Content-Type": "application/json",
            "apikey": api_key
        }
        
        logger.info(f"📖 [READ RECEIPT] Enviando confirmação de leitura...")
        logger.info(f"   URL: {url}")
        logger.info(f"   Message ID: {message.message_id}")
        logger.info(f"   Contact: {conversation.contact_phone}")
        
        # Enviar request de forma síncrona
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=payload, headers=headers)
            
            if response.status_code == 200 or response.status_code == 201:
                logger.info(f"✅ [READ RECEIPT] Confirmação enviada com sucesso!")
                logger.info(f"   Response: {response.text[:200]}")
            else:
                logger.warning(f"⚠️ [READ RECEIPT] Resposta não esperada: {response.status_code}")
                logger.warning(f"   Response: {response.text[:300]}")
    
    except Exception as e:
        logger.error(f"❌ [READ RECEIPT] Erro ao enviar confirmação de leitura: {e}", exc_info=True)

