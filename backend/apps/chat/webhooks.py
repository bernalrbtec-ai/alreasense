"""
Webhook handler para Evolution API.
Recebe eventos de mensagens e atualiza o banco.
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
# download_attachment removido - agora usa process_incoming_media diretamente (S3 + cache Redis)
from apps.tenancy.models import Tenant
from apps.connections.models import EvolutionConnection
from apps.notifications.models import WhatsAppInstance

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([AllowAny])
def evolution_webhook(request):
    """
    Webhook para receber eventos da Evolution API.
    
    Eventos suportados:
    - messages.upsert: Nova mensagem recebida
    - messages.update: Atualização de status (delivered/read)
    """
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
        
        # ✅ CORREÇÃO: Buscar WhatsAppInstance pelo instance_name (UUID) primeiro
        # O webhook envia UUID (ex: "9afdad84-5411-4754-8f63-2599a6b9142c")
        # EvolutionConnection.name é nome amigável, não UUID
        wa_instance = None
        connection = None
        
        try:
            # Buscar WhatsAppInstance pelo instance_name (UUID do webhook)
            wa_instance = WhatsAppInstance.objects.select_related('tenant').filter(
                instance_name=instance_name,
                is_active=True,
                status='active'
            ).first()
            
            if wa_instance:
                logger.info(f"✅ [WEBHOOK] WhatsAppInstance encontrada: {wa_instance.friendly_name} ({wa_instance.instance_name})")
                logger.info(f"   📌 Tenant: {wa_instance.tenant.name if wa_instance.tenant else 'Global'}")
                
                # Buscar EvolutionConnection (servidor Evolution) para usar api_url/api_key
                # Se WhatsAppInstance tem api_url/api_key próprios, usar deles
                # Se não, usar do EvolutionConnection
                connection = EvolutionConnection.objects.filter(
                    is_active=True
                ).select_related('tenant').first()
                
                if not connection:
                    logger.warning(f"⚠️ [WEBHOOK] EvolutionConnection não encontrada, mas WhatsAppInstance encontrada")
                    # Continuar mesmo assim (WhatsAppInstance pode ter api_url/api_key próprios)
        except Exception as e:
            logger.warning(f"⚠️ [WEBHOOK] Erro ao buscar WhatsAppInstance: {e}")
        
        # ✅ FALLBACK: Se não encontrou WhatsAppInstance, tentar buscar EvolutionConnection pelo name
        # (pode ser que instance_name seja nome amigável em alguns casos)
        if not wa_instance:
            try:
                connection = EvolutionConnection.objects.select_related('tenant').get(
                    name=instance_name,
                    is_active=True
                )
                logger.info(f"✅ [WEBHOOK] EvolutionConnection encontrada pelo name: {connection.name} - Tenant: {connection.tenant.name}")
            except EvolutionConnection.DoesNotExist:
                logger.warning(f"⚠️ [WEBHOOK] Nenhuma conexão encontrada para instance: {instance_name}")
                logger.warning(f"   Tentando buscar qualquer conexão ativa...")
                
                # Fallback final: buscar qualquer conexão ativa
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
        
        # ✅ Determinar tenant: usar do wa_instance se tiver, senão usar do connection
        if wa_instance and wa_instance.tenant:
            tenant = wa_instance.tenant
        elif connection:
            tenant = connection.tenant
        else:
            logger.error(f"❌ [WEBHOOK] Nenhum tenant encontrado!")
            return Response(
                {'error': 'Tenant não encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Roteamento por tipo de evento
        # ✅ Passar wa_instance também para handler (pode ter api_url/api_key próprios)
        if event_type == 'messages.upsert':
            handle_message_upsert(data, tenant, connection=connection, wa_instance=wa_instance)
        elif event_type == 'messages.update':
            handle_message_update(data, tenant)
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
def handle_message_upsert(data, tenant, connection=None, wa_instance=None):
    """
    Processa evento de nova mensagem (messages.upsert).
    
    Cria ou atualiza:
    - Conversation
    - Message
    - MessageAttachment (se houver)
    
    Args:
        data: Dados do webhook
        tenant: Tenant da mensagem
        connection: EvolutionConnection (opcional)
        wa_instance: WhatsAppInstance (opcional, tem instance_name UUID)
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
        logger.info(f"🔍 [DEBUG] fromMe={from_me}, conversation_type={conversation_type}, remoteJid={remote_jid}")
        
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
                        endpoint = f"{base_url}/chat/fetchProfilePictureUrl/{instance_name}"
                        
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
                            endpoint = f"{base_url}/chat/whatsappNumbers/{instance_name}"
                            
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
                from apps.chat.utils.serialization import serialize_conversation_for_ws
                
                conv_data_serializable = serialize_conversation_for_ws(conversation)
                
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
                logger.error(f"❌ [WEBSOCKET] Error broadcasting new conversation: {e}", exc_info=True)
        else:
            # ✅ CONVERSAS EXISTENTES: Se conversa estava fechada, reabrir automaticamente
            status_changed = False
            if conversation.status == 'closed':
                old_status = conversation.status
                conversation.status = 'pending' if not from_me else 'open'
                conversation.save(update_fields=['status'])
                status_str = "Inbox" if not from_me else "Aberta"
                status_changed = True
                logger.info(f"🔄 [WEBHOOK] Conversa {phone} reaberta automaticamente: {old_status} → {conversation.status} ({status_str})")
            
            # ✅ IMPORTANTE: Para conversas existentes, ainda precisamos atualizar last_message_at
            # Isso garante que a conversa aparece no topo da lista
            conversation.update_last_message()
            
        # Atualiza nome e foto se mudaram
        update_fields = []
        name_or_pic_changed = False
        if push_name and conversation.contact_name != push_name:
            conversation.contact_name = push_name
            update_fields.append('contact_name')
            name_or_pic_changed = True
        
        if profile_pic_url and conversation.profile_pic_url != profile_pic_url:
            conversation.profile_pic_url = profile_pic_url
            update_fields.append('profile_pic_url')
            name_or_pic_changed = True
            logger.info(f"📸 [WEBHOOK] Foto de perfil atualizada: {profile_pic_url[:50]}...")
        
        if update_fields:
            conversation.save(update_fields=update_fields)
        
        # ✅ IMPORTANTE: Fazer broadcast UMA VEZ apenas se algo mudou (status OU nome/foto)
        # Isso evita duplicação de eventos e múltiplos toasts
        if status_changed or name_or_pic_changed:
            try:
                from apps.chat.utils.serialization import serialize_conversation_for_ws
                # ✅ Usar imports globais (linhas 12-13) ao invés de import local
                # from channels.layers import get_channel_layer  # ❌ REMOVIDO: causava UnboundLocalError
                # from asgiref.sync import async_to_sync  # ❌ REMOVIDO: causava UnboundLocalError
                
                # ✅ Recarregar do banco para garantir dados atualizados
                conversation.refresh_from_db()
                conv_data_serializable = serialize_conversation_for_ws(conversation)
                
                channel_layer = get_channel_layer()  # ✅ Usa import global (linha 12)
                tenant_group = f"chat_tenant_{tenant.id}"
                
                async_to_sync(channel_layer.group_send)(
                    tenant_group,
                    {
                        'type': 'conversation_updated',
                        'conversation': conv_data_serializable
                    }
                )
                
                change_type = "status mudou" if status_changed else "nome/foto atualizado"
                logger.info(f"📡 [WEBSOCKET] Broadcast de conversa atualizada ({change_type}) enviado")
            except Exception as e:
                logger.error(f"❌ [WEBSOCKET] Erro ao fazer broadcast de conversa atualizada: {e}", exc_info=True)
        
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
        
        logger.info(f"💾 [WEBHOOK] Tentando salvar mensagem no banco...")
        logger.info(f"   message_id={message_id}")
        logger.info(f"   direction={direction} (fromMe={from_me})")
        logger.info(f"   conversation_id={conversation.id}")
        logger.info(f"   content={content[:100]}...")
        
        message, msg_created = Message.objects.get_or_create(
            message_id=message_id,
            defaults=message_defaults
        )
        
        if msg_created:
            logger.info(f"✅ [WEBHOOK] MENSAGEM NOVA CRIADA NO BANCO!")
            logger.info(f"   ID interno: {message.id}")
            logger.info(f"   Message ID: {message_id}")
            logger.info(f"   Direction: {direction}")
            logger.info(f"   Conversa: {conversation.id} | Phone: {conversation.contact_phone}")
            
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
                # Determinar media_type baseado no message_type
                if message_type == 'imageMessage':
                    incoming_media_type = 'image'
                elif message_type == 'videoMessage':
                    incoming_media_type = 'video'
                elif message_type == 'audioMessage':
                    incoming_media_type = 'audio'
                elif message_type == 'documentMessage':
                    incoming_media_type = 'document'
                else:
                    incoming_media_type = 'document'
                
                # Usar transaction para garantir que o anexo seja salvo antes de enfileirar
                from django.db import transaction
                with transaction.atomic():
                    # Criar placeholder (sem file_url ainda, será preenchido após processamento)
                    attachment = MessageAttachment.objects.create(
                        message=message,
                        tenant=tenant,
                        original_filename=filename,
                        mime_type=mime_type,
                        file_path='',  # Será preenchido após processamento S3
                        file_url='',  # Será preenchido com URL proxy após processamento
                        storage_type='s3',  # Direto para S3 (sem storage local)
                        size_bytes=0,  # Será preenchido após download
                        metadata={'processing': True, 'media_type': incoming_media_type}  # Flag para frontend mostrar loading
                    )
                    
                    attachment_id_str = str(attachment.id)
                    message_id_str = str(message.id)
                    tenant_id_str = str(tenant.id)
                    
                    logger.info(f"📎 [WEBHOOK] Criado anexo placeholder ID={attachment_id_str}, mime={mime_type}, type={incoming_media_type}")
                    logger.info(f"📎 [WEBHOOK] URL temporária: {attachment_url[:100]}...")
                    
                    # Força commit antes de enfileirar processamento direto (S3 direto - sem cache)
                    # ✅ MELHORIA: Usar conexão Evolution já encontrada no webhook para descriptografar arquivos
                    instance_name_for_media = None
                    api_key_for_media = None
                    evolution_api_url_for_media = None
                    
                    # ✅ CORREÇÃO: Usar WhatsAppInstance (tem instance_name UUID) ou EvolutionConnection
                    # Prioridade: wa_instance > connection > fallback
                    instance_name_for_media = None
                    api_key_for_media = None
                    evolution_api_url_for_media = None
                    
                    # ✅ OPÇÃO 1: Usar WhatsAppInstance (tem instance_name UUID do webhook)
                    if wa_instance:
                        instance_name_for_media = wa_instance.instance_name  # UUID da instância
                        api_key_for_media = wa_instance.api_key or (connection.api_key if connection else None)
                        evolution_api_url_for_media = wa_instance.api_url or (connection.base_url if connection else None)
                        
                        logger.info(f"✅ [WEBHOOK] Usando WhatsAppInstance para descriptografar mídia:")
                        logger.info(f"   📌 Instance (UUID): {instance_name_for_media}")
                        logger.info(f"   📌 Friendly Name: {wa_instance.friendly_name}")
                        logger.info(f"   📌 API URL: {evolution_api_url_for_media}")
                        logger.info(f"   📌 API Key: {'Configurada' if api_key_for_media else 'Não configurada'}")
                    
                    # ✅ OPÇÃO 2: Usar EvolutionConnection (fallback)
                    elif connection:
                        instance_name_for_media = instance_name  # Usar instance_name do webhook (pode ser UUID ou nome)
                        api_key_for_media = connection.api_key
                        evolution_api_url_for_media = connection.api_url or connection.base_url
                        
                        logger.info(f"✅ [WEBHOOK] Usando EvolutionConnection para descriptografar mídia:")
                        logger.info(f"   📌 Instance: {instance_name_for_media}")
                        logger.info(f"   📌 API URL: {evolution_api_url_for_media}")
                        logger.info(f"   📌 Connection: {connection.name}")
                    
                    # ✅ OPÇÃO 3: Fallback - buscar conexão diretamente
                    else:
                        logger.warning(f"⚠️ [WEBHOOK] Nenhuma conexão disponível, tentando buscar diretamente...")
                        
                        try:
                            # Tentar buscar WhatsAppInstance pelo instance_name (UUID)
                            from apps.notifications.models import WhatsAppInstance
                            from apps.connections.models import EvolutionConnection
                            
                            fallback_wa_instance = WhatsAppInstance.objects.filter(
                                instance_name=instance_name,
                                tenant=tenant,
                                is_active=True,
                                status='active'
                            ).first()
                            
                            if fallback_wa_instance:
                                instance_name_for_media = fallback_wa_instance.instance_name
                                api_key_for_media = fallback_wa_instance.api_key
                                evolution_api_url_for_media = fallback_wa_instance.api_url
                                
                                # Se não tem api_url/api_key próprios, buscar EvolutionConnection
                                if not evolution_api_url_for_media or not api_key_for_media:
                                    fallback_connection = EvolutionConnection.objects.filter(
                                        is_active=True
                                    ).first()
                                    if fallback_connection:
                                        evolution_api_url_for_media = evolution_api_url_for_media or fallback_connection.base_url
                                        api_key_for_media = api_key_for_media or fallback_connection.api_key
                                
                                logger.info(f"✅ [WEBHOOK] WhatsAppInstance encontrada via fallback:")
                                logger.info(f"   📌 Instance (UUID): {instance_name_for_media}")
                                logger.info(f"   📌 Friendly Name: {fallback_wa_instance.friendly_name}")
                                logger.info(f"   📌 API URL: {evolution_api_url_for_media}")
                            else:
                                # Último fallback: buscar EvolutionConnection
                                fallback_connection = EvolutionConnection.objects.filter(
                                    tenant=tenant,
                                    is_active=True
                                ).first()
                                
                                if fallback_connection:
                                    instance_name_for_media = instance_name
                                    api_key_for_media = fallback_connection.api_key
                                    evolution_api_url_for_media = fallback_connection.api_url or fallback_connection.base_url
                                    
                                    logger.info(f"✅ [WEBHOOK] EvolutionConnection encontrada via fallback:")
                                    logger.info(f"   📌 Instance: {instance_name_for_media}")
                                    logger.info(f"   📌 API URL: {evolution_api_url_for_media}")
                                    logger.info(f"   📌 Connection: {fallback_connection.name}")
                                else:
                                    logger.warning(f"⚠️ [WEBHOOK] Nenhuma conexão encontrada via fallback")
                                    logger.warning(f"   🔍 [WEBHOOK] Tentou buscar por: instance_name={instance_name}, tenant={tenant.name}")
                        except Exception as e:
                            logger.warning(f"⚠️ [WEBHOOK] Erro ao buscar conexão via fallback: {e}", exc_info=True)
                    
                    def enqueue_process():
                        logger.info(f"🔄 [WEBHOOK] Enfileirando processamento direto (S3) do anexo {attachment_id_str}...")
                        logger.info(f"   📌 tenant_id: {tenant_id_str}")
                        logger.info(f"   📌 message_id: {message_id_str}")
                        logger.info(f"   📌 media_url: {attachment_url[:100]}...")
                        logger.info(f"   📌 media_type: {incoming_media_type}")
                        try:
                            from apps.chat.tasks import process_incoming_media
                            process_incoming_media.delay(
                                tenant_id=tenant_id_str,
                                message_id=message_id_str,
                                media_url=attachment_url,
                                media_type=incoming_media_type,
                                instance_name=instance_name_for_media,
                                api_key=api_key_for_media,
                                evolution_api_url=evolution_api_url_for_media
                            )
                            logger.info(f"✅ [WEBHOOK] Processamento enfileirado com sucesso na fila chat_process_incoming_media!")
                        except Exception as e:
                            logger.error(f"❌ [WEBHOOK] ERRO ao enfileirar processamento: {e}", exc_info=True)
                            raise  # ✅ Re-raise para não silenciar erro
                    
                    transaction.on_commit(enqueue_process)
                
                logger.info(f"📎 [WEBHOOK] Anexo {filename} preparado para processamento direto (S3+cache)")
            
            # Broadcast via WebSocket (mensagem específica)
            logger.info(f"📡 [WEBHOOK] Enviando para WebSocket da conversa...")
            broadcast_message_to_websocket(message, conversation)
            
            # 🔔 IMPORTANTE: Se for mensagem recebida (não enviada por nós)
            if not from_me:
                # ❌ REMOVIDO: Não marcar como lida automaticamente
                # O read receipt só deve ser enviado quando usuário REALMENTE abrir a conversa
                # Isso é feito via /mark_as_read/ quando frontend abre a conversa (após 2.5s)
                
                # 1. Notificar tenant sobre nova mensagem (toast)
                logger.info(f"📬 [WEBHOOK] Notificando tenant sobre nova mensagem...")
                try:
                    from apps.chat.utils.serialization import serialize_conversation_for_ws
                    # ✅ Usar imports globais (linhas 12-13) ao invés de import local
                    # from asgiref.sync import async_to_sync  # ❌ REMOVIDO: causava UnboundLocalError
                    
                    conv_data_serializable = serialize_conversation_for_ws(conversation)
                    
                    # Broadcast para todo o tenant (notificação de nova mensagem)
                    channel_layer = get_channel_layer()  # ✅ Usa import global (linha 12)
                    tenant_group = f"chat_tenant_{tenant.id}"
                    
                    # 📱 Para GRUPOS: Nome do grupo + quem enviou
                    if is_group:
                        group_name = conversation.group_metadata.get('group_name', 'Grupo WhatsApp') if conversation.group_metadata else 'Grupo WhatsApp'
                        # Pegar nome de quem enviou (sender_name já foi extraído no início)
                        sender_display = sender_name if sender_name else 'Alguém'
                        notification_text = f"📱 {group_name}\n{sender_display} enviou uma mensagem"
                    else:
                        notification_text = content[:100]  # Primeiros 100 caracteres para contatos individuais
                    
                    async_to_sync(channel_layer.group_send)(  # ✅ Usa import global (linha 13)
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
                    logger.error(f"❌ [WEBSOCKET] Error broadcasting notification: {e}", exc_info=True)
        
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
            # 🔇 Reduzir ruído: Evolution envia updates parciais de contato/chat sem status/mensagem
            logger.debug(f"🔇 [WEBHOOK UPDATE] Ignorando update sem message_id/status (contacts.update/chat.update)")
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
        
        logger.info(f"📡 [WEBSOCKET] Preparando broadcast...")
        logger.info(f"   Room: {room_group_name}")
        logger.info(f"   Direction: {message.direction}")
        
        # ✅ Usar utilitário centralizado para serialização
        from apps.chat.utils.serialization import serialize_message_for_ws
        message_data_serializable = serialize_message_for_ws(message)
        
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
        logger.error(f"❌ [WEBSOCKET] Error broadcasting message: {e}", exc_info=True)


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

