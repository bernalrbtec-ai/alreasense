"""
Serializers para o módulo Flow Chat.
"""
import logging
from rest_framework import serializers
from django.db import models
from django.db.models import Q
from apps.chat.models import Conversation, Message, MessageAttachment, MessageReaction, QuickReply
from apps.authn.serializers import UserSerializer
from apps.contacts.models import Contact

logger = logging.getLogger(__name__)


class MessageAttachmentSerializer(serializers.ModelSerializer):
    """
    Serializer para anexos de mensagem.
    Inclui campos para IA (transcrição, resumo, tags, sentiment).
    """
    
    # Serializar UUIDs como strings
    id = serializers.UUIDField(read_only=True)
    message = serializers.UUIDField(read_only=True)
    tenant = serializers.UUIDField(read_only=True)
    
    is_expired = serializers.ReadOnlyField()
    is_image = serializers.ReadOnlyField()
    is_video = serializers.ReadOnlyField()
    is_audio = serializers.ReadOnlyField()
    is_document = serializers.ReadOnlyField()
    
    class Meta:
        model = MessageAttachment
        fields = [
            'id', 'message', 'tenant', 'original_filename', 'mime_type',
            'file_path', 'file_url', 'thumbnail_path', 'storage_type',
            'size_bytes', 'expires_at', 'created_at', 'metadata',
            'is_expired', 'is_image', 'is_video', 'is_audio', 'is_document',
            # ✨ Campos IA
            'transcription', 'transcription_language', 'ai_summary',
            'ai_tags', 'ai_sentiment', 'ai_metadata',
            'processing_status', 'processed_at'
        ]
        read_only_fields = [
            'id', 'message', 'tenant', 'created_at', 'is_expired',
            'is_image', 'is_video', 'is_audio', 'is_document',
            # IA fields são read-only (processados pelo backend)
            'transcription', 'transcription_language', 'ai_summary',
            'ai_tags', 'ai_sentiment', 'ai_metadata',
            'processing_status', 'processed_at'
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # ✅ SEMPRE forçar URL de proxy para anexos no S3
        # Isso garante que frontend sempre recebe URL válida e acessível
        try:
            if instance.storage_type == 's3' and instance.file_path and instance.file_path.strip():
                # ✅ IMPORTANTE: Só gerar URL se file_path está preenchido (não é placeholder)
                # Placeholders têm file_path vazio e devem manter file_url vazio até processamento
                file_url = (data.get('file_url') or '').strip()
                # Se file_url está vazio OU não é URL do proxy, gerar URL do proxy
                if not file_url or '/api/chat/media-proxy' not in file_url:
                    from apps.chat.utils.s3 import S3Manager
                    from django.core.cache import cache
                    import logging
                    
                    logger = logging.getLogger(__name__)
                    s3_manager = S3Manager()
                    
                    # ✅ PERFORMANCE: Gerar URL diretamente sem verificar existência
                    # Verificação é custosa e pode ser desatualizada
                    # Assumir que arquivo existe (otimista) - se não existir, erro será tratado no frontend
                    proxy_url = s3_manager.get_public_url(instance.file_path, use_presigned=False)
                    data['file_url'] = proxy_url
                    
                    # ✅ PERFORMANCE: Cachear URL gerada (10 minutos) para evitar regeneração
                    # URLs são estáveis enquanto arquivo existe no S3
                    url_cache_key = f"s3_proxy_url:{instance.file_path}"
                    cache.set(url_cache_key, proxy_url, 600)  # 10 minutos
                    
                    # ✅ DEBUG: Log detalhado das URLs geradas no serializer
                    logger.info(f"📎 [SERIALIZER] URLs para attachment {instance.id}:")
                    logger.info(f"   📦 [SERIALIZER] S3 Path: {instance.file_path}")
                    logger.info(f"   🌐 [SERIALIZER] URL Proxy (final): {proxy_url}")
                    logger.info(f"   📄 [SERIALIZER] MIME Type: {instance.mime_type}")
                    logger.info(f"   📝 [SERIALIZER] Filename: {instance.original_filename}")
                    logger.info(f"   📏 [SERIALIZER] Size: {instance.size_bytes} bytes ({instance.size_bytes / 1024:.2f} KB)" if instance.size_bytes else "   📏 [SERIALIZER] Size: N/A")
                
                # ✅ NORMALIZAR metadata: garantir que sempre seja dict
                from apps.chat.utils.serialization import normalize_metadata
                data['metadata'] = normalize_metadata(data.get('metadata'))
        except Exception as e:
            # Em caso de erro, logar mas manter o original para não quebrar a resposta
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"⚠️ [SERIALIZER] Erro ao gerar URL do proxy: {e}", exc_info=True)
        return data


class MessageReactionSerializer(serializers.ModelSerializer):
    """Serializer para reações de mensagens."""
    
    id = serializers.UUIDField(read_only=True)
    message = serializers.UUIDField(read_only=True)
    user = serializers.UUIDField(read_only=True, allow_null=True)
    user_data = UserSerializer(source='user', read_only=True, allow_null=True)
    external_sender = serializers.CharField(read_only=True, allow_blank=True)
    
    class Meta:
        model = MessageReaction
        fields = ['id', 'message', 'user', 'user_data', 'external_sender', 'emoji', 'created_at']
        read_only_fields = ['id', 'message', 'user', 'user_data', 'external_sender', 'created_at']


class MessageSerializer(serializers.ModelSerializer):
    """Serializer para mensagens."""
    
    # Serializar UUIDs como strings
    id = serializers.UUIDField(read_only=True)
    conversation = serializers.UUIDField(read_only=True)
    sender = serializers.UUIDField(read_only=True)
    
    sender_data = UserSerializer(source='sender', read_only=True)
    attachments = MessageAttachmentSerializer(many=True, read_only=True)
    reactions = MessageReactionSerializer(many=True, read_only=True)
    reactions_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = Message
        fields = [
            'id', 'conversation', 'sender', 'sender_data', 'sender_name', 'sender_phone',
            'content', 'direction', 'message_id', 'evolution_status', 'error_message',
            'status', 'is_internal', 'is_deleted', 'deleted_at', 'is_edited', 'attachments', 'reactions', 'reactions_summary', 'metadata', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'conversation', 'sender', 'created_at', 'sender_data', 'attachments', 'reactions', 'reactions_summary']
    
    def to_representation(self, instance):
        """
        Garante que conversation sempre seja serializado como UUID (string), não nome da conversa.
        Reprocessa menções para buscar nomes atualizados dos participantes.
        """
        data = super().to_representation(instance)

        if 'conversation' in data:
            if isinstance(instance.conversation, models.Model):
                data['conversation'] = str(instance.conversation.id)
            elif hasattr(instance, 'conversation_id') and instance.conversation_id:
                data['conversation'] = str(instance.conversation_id)

        # ✅ DEBUG: Normalizar metadata e logar reply_to se existir
        if 'metadata' in data:
            from apps.chat.utils.serialization import normalize_metadata
            data['metadata'] = normalize_metadata(data.get('metadata'))
            if data['metadata'].get('reply_to'):
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"💬 [SERIALIZER] Mensagem {instance.id} tem reply_to: {data['metadata'].get('reply_to')}")
            
            # ✅ CORREÇÃO: Reprocessar menções para buscar nomes atualizados
            if 'mentions' in data['metadata'] and instance.conversation:
                # ✅ CORREÇÃO CRÍTICA: Garantir que logger está definido
                import logging
                logger = logging.getLogger(__name__)
                
                mentions_saved = data['metadata'].get('mentions', [])
                if mentions_saved:
                    # ✅ IMPORTANTE: Recarregar conversa do banco para ter dados atualizados
                    # Isso garante que temos o group_metadata mais recente
                    try:
                        conversation = Conversation.objects.select_related('tenant').get(
                            id=instance.conversation.id
                        )
                    except Conversation.DoesNotExist:
                        conversation = instance.conversation
                    
                    # Extrair JIDs/phones das menções salvas
                    mentioned_jids = []
                    for mention in mentions_saved:
                        # ✅ CORREÇÃO CRÍTICA: Priorizar JID completo (mais confiável para @lid)
                        # Se temos JID salvo, usar ele (especialmente importante para @lid)
                        jid = mention.get('jid')
                        if not jid:
                            # Fallback para phone apenas se não temos JID
                            jid = mention.get('phone')
                        
                        if jid:
                            # Se é apenas phone (sem @), adicionar como está
                            # Se é JID completo (com @), usar diretamente
                            mentioned_jids.append(jid)
                            logger.debug(f"   📝 [SERIALIZER] Extraído JID da menção: {jid}")
                    
                    if mentioned_jids:
                        # Reprocessar com conversa atualizada
                        # ✅ IMPORTANTE: Importação lazy para evitar circular
                        try:
                            from apps.chat.webhooks import process_mentions_optimized
                            
                            logger.info(f"🔄 [SERIALIZER] Reprocessando {len(mentioned_jids)} menções para mensagem {instance.id}")
                            logger.info(f"   Conversa: {conversation.id} | Tipo: {conversation.conversation_type}")
                            logger.info(f"   Group metadata tem participantes: {len(conversation.group_metadata.get('participants', [])) if conversation.group_metadata else 0}")
                            
                            updated_mentions = process_mentions_optimized(
                                mentioned_jids, 
                                conversation.tenant,
                                conversation
                            )
                            
                            # Log das menções atualizadas
                            for i, mention in enumerate(updated_mentions):
                                old_name = mentions_saved[i].get('name', 'N/A') if i < len(mentions_saved) else 'N/A'
                                new_name = mention.get('name', 'N/A')
                                if old_name != new_name:
                                    logger.info(f"   ✅ Menção {i+1} atualizada: '{old_name}' → '{new_name}'")
                            
                            # Atualizar menções no metadata com nomes atualizados
                            data['metadata']['mentions'] = updated_mentions
                            logger.info(f"✅ [SERIALIZER] {len(updated_mentions)} menções reprocessadas para mensagem {instance.id}")
                        except ImportError as e:
                            logger.warning(f"⚠️ [SERIALIZER] Não foi possível importar process_mentions_optimized: {e}")
                            # Em caso de erro de importação, manter menções originais
                        except Exception as e:
                            logger.warning(f"⚠️ [SERIALIZER] Erro ao reprocessar menções: {e}", exc_info=True)
                            # Em caso de erro, manter menções originais

        return data

    def get_reactions_summary(self, obj):
        """
        Retorna resumo das reações agrupadas por emoji.
        Formato: {'👍': {'count': 3, 'users': [user1, user2, user3]}, ...}
        """
        from django.db.models import Count
        from collections import defaultdict
        
        # ✅ CORREÇÃO: Verificar se prefetch foi feito corretamente
        # hasattr sempre retorna True para campos do modelo, então verificar prefetch cache
        prefetch_cache = getattr(obj, '_prefetched_objects_cache', {})
        has_prefetched_reactions = 'reactions' in prefetch_cache
        
        if has_prefetched_reactions:
            # ✅ Usar reações prefetched (evita query adicional)
            reactions = prefetch_cache['reactions']
        else:
            # Fallback: buscar reações se não foram prefetched
            reactions = MessageReaction.objects.filter(message=obj).select_related('user')
        
        summary = defaultdict(lambda: {'count': 0, 'users': []})
        
        for reaction in reactions:
            emoji = reaction.emoji
            summary[emoji]['count'] += 1
            # ✅ CORREÇÃO: Adicionar dados do usuário ou contato externo
            if reaction.user:
                # Reação de usuário interno
                user = reaction.user
                summary[emoji]['users'].append({
                    'id': str(user.id),
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'external': False,
                })
            elif reaction.external_sender:
                # Reação de contato externo (WhatsApp)
                summary[emoji]['users'].append({
                    'id': None,
                    'email': None,
                    'first_name': reaction.external_sender,
                    'last_name': '',
                    'external': True,
                })
        
        return dict(summary)


class MessageCreateSerializer(serializers.ModelSerializer):
    """Serializer para criação de mensagens (outgoing)."""
    
    conversation = serializers.PrimaryKeyRelatedField(
        queryset=Conversation.objects.none()
    )
    attachment_urls = serializers.ListField(
        child=serializers.URLField(),
        required=False,
        write_only=True,
        help_text='Lista de URLs de anexos para enviar'
    )
    mentions = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        write_only=True,
        help_text='Lista de números de telefone mencionados (ex: ["5517999999999"])'
    )
    
    class Meta:
        model = Message
        fields = [
            'conversation', 'content', 'is_internal', 'attachment_urls'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            user = request.user
            queryset = Conversation.objects.filter(tenant=user.tenant)
            if not user.is_superuser and not user.is_admin:
                department_ids = user.departments.values_list('id', flat=True)
                queryset = queryset.filter(
                    Q(department__in=department_ids) |
                    Q(department__isnull=True, assigned_to=user)
                )
            self.fields['conversation'].queryset = queryset
        else:
            self.fields['conversation'].queryset = Conversation.objects.none()
    
    def validate(self, attrs):
        """Valida que há conteúdo ou anexos."""
        if not attrs.get('content') and not attrs.get('attachment_urls'):
            raise serializers.ValidationError(
                "Mensagem deve ter conteúdo de texto ou anexos."
            )
        
        request = self.context.get('request')
        conversation = attrs.get('conversation')
        if request and conversation:
            user = request.user
            
            if conversation.tenant_id != user.tenant_id:
                raise serializers.ValidationError({
                    'conversation': 'Conversa não pertence ao seu tenant.'
                })
            
            if not (user.is_superuser or user.is_admin):
                department_ids = set(user.departments.values_list('id', flat=True))
                if conversation.department_id:
                    if conversation.department_id not in department_ids:
                        raise serializers.ValidationError({
                            'conversation': 'Você não tem acesso a este departamento.'
                        })
                elif conversation.assigned_to_id != user.id:
                    raise serializers.ValidationError({
                        'conversation': 'Conversa não está atribuída a você.'
                    })
        
        return attrs
    
    def create(self, validated_data):
        """Cria mensagem outgoing."""
        import logging
        logger = logging.getLogger(__name__)
        
        # ✅ VALIDAÇÃO CRÍTICA DE SEGURANÇA: Validar conversation antes de criar mensagem
        conversation = validated_data.get('conversation')
        request = self.context.get('request')
        user = request.user if request else None
        
        logger.critical(f"🔒 [MESSAGE CREATE] ====== VALIDAÇÃO DE CONVERSA ======")
        logger.critical(f"   User: {user.email if user else 'N/A'}")
        logger.critical(f"   User Tenant: {user.tenant_id if user and user.tenant else 'N/A'}")
        logger.critical(f"   Conversation ID: {conversation.id if conversation else 'N/A'}")
        logger.critical(f"   Conversation Type: {conversation.conversation_type if conversation else 'N/A'}")
        logger.critical(f"   Conversation Phone: {conversation.contact_phone if conversation else 'N/A'}")
        logger.critical(f"   Conversation Tenant: {conversation.tenant_id if conversation else 'N/A'}")
        
        # ✅ VALIDAÇÃO CRÍTICA: Recarregar conversation do banco para garantir dados atualizados
        if conversation:
            conversation.refresh_from_db()
            logger.critical(f"   Conversation Type (após refresh): {conversation.conversation_type}")
            logger.critical(f"   Conversation Phone (após refresh): {conversation.contact_phone}")
            
            # ✅ VALIDAÇÃO CRÍTICA: Verificar tenant
            if user and user.tenant and conversation.tenant_id != user.tenant_id:
                logger.critical(f"❌ [SEGURANÇA] ERRO CRÍTICO: Conversation pertence a outro tenant!")
                logger.critical(f"   User Tenant: {user.tenant_id}")
                logger.critical(f"   Conversation Tenant: {conversation.tenant_id}")
                raise serializers.ValidationError({
                    'conversation': 'Conversa não pertence ao seu tenant.'
                })
            
            # ✅ VALIDAÇÃO CRÍTICA: Verificar se conversation_type corresponde ao formato do contact_phone
            contact_phone = (conversation.contact_phone or '').strip()
            if conversation.conversation_type == 'group' and not contact_phone.endswith('@g.us'):
                logger.critical(f"⚠️ [SEGURANÇA] AVISO: Conversation marcada como grupo mas contact_phone não termina com @g.us")
                logger.critical(f"   Contact Phone: {contact_phone}")
                logger.critical(f"   Isso pode causar envio para destinatário errado!")
            elif conversation.conversation_type == 'individual' and contact_phone.endswith('@g.us'):
                logger.critical(f"❌ [SEGURANÇA] ERRO CRÍTICO: Conversation marcada como individual mas contact_phone termina com @g.us!")
                logger.critical(f"   Contact Phone: {contact_phone}")
                logger.critical(f"   Isso causaria envio para grupo ao invés de individual!")
                raise serializers.ValidationError({
                    'conversation': 'Conversa marcada como individual mas contact_phone indica grupo. Contate o suporte.'
                })
        
        attachment_urls = validated_data.pop('attachment_urls', [])
        mentions = validated_data.pop('mentions', [])
        validated_data['direction'] = 'outgoing'
        validated_data['sender'] = self.context['request'].user
        validated_data['status'] = 'pending'
        
        message = Message.objects.create(**validated_data)
        
        logger.critical(f"✅ [MESSAGE CREATE] Mensagem criada:")
        logger.critical(f"   Message ID: {message.id}")
        logger.critical(f"   Conversation ID: {message.conversation_id}")
        logger.critical(f"   Conversation Type: {message.conversation.conversation_type}")
        logger.critical(f"   Conversation Phone: {message.conversation.contact_phone}")
        
        # ✅ NOVO: Processar menções e salvar no metadata
        metadata = {}
        if attachment_urls:
            metadata['attachment_urls'] = attachment_urls
        
        if mentions:
            # Validar que é grupo (menções só funcionam em grupos)
            conversation = message.conversation
            if conversation.conversation_type != 'group':
                # Ignorar menções em conversas individuais (não quebra, só não usa)
                pass
            else:
                # Processar menções: validar números e buscar nomes
                import logging
                logger = logging.getLogger(__name__)
                
                processed_mentions = []
                group_metadata = conversation.group_metadata or {}
                participants = group_metadata.get('participants', [])
                
                logger.info(f'🔍 [MENTIONS] Processando {len(mentions)} menção(ões) para grupo {conversation.id}')
                logger.info(f'   Participantes disponíveis: {len(participants)}')
                
                # Função auxiliar para formatar telefone (definida uma vez)
                def format_phone_for_display(phone: str) -> str:
                    """Formata telefone para exibição: (11) 99999-9999"""
                    import re
                    if not phone:
                        return phone
                    clean = re.sub(r'\D', '', phone)
                    digits = clean[2:] if clean.startswith('55') and len(clean) >= 12 else clean
                    if len(digits) == 11:
                        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
                    elif len(digits) == 10:
                        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
                    return phone
                
                # ✅ PRIORIDADE 1: Buscar CONTATOS CADASTRADOS primeiro (prioridade máxima)
                from apps.notifications.services import normalize_phone
                phone_to_contact = {}  # Telefone normalizado -> nome do contato cadastrado
                all_phones_to_check = []
                for identifier in mentions:
                    if '@' in identifier:
                        phone_raw = identifier.split('@')[0]
                    else:
                        phone_raw = identifier
                    normalized = normalize_phone(phone_raw.replace('+', '').replace(' ', '').strip())
                    if normalized:
                        all_phones_to_check.append(normalized)
                
                if all_phones_to_check:
                    contacts = Contact.objects.filter(
                        tenant=conversation.tenant,
                        phone__in=all_phones_to_check
                    ).values('phone', 'name')
                    
                    for contact in contacts:
                        normalized_contact_phone = normalize_phone(contact['phone'])
                        if normalized_contact_phone:
                            contact_name = contact.get('name', '').strip()
                            if contact_name:
                                phone_to_contact[normalized_contact_phone] = contact_name
                
                logger.info(f'   Contatos cadastrados encontrados: {len(phone_to_contact)}')
                
                # ✅ MELHORIA: Criar mapas otimizados para busca O(1) ao invés de O(n)
                # Normalizar telefones dos participantes para comparação (sem + e espaços)
                phone_to_name = {}
                phone_to_jid = {}  # Telefone -> JID original
                jid_to_name = {}  # ✅ NOVO: JID completo -> nome (para busca rápida)
                jid_clean_to_info = {}  # ✅ NOVO: JID limpo (sem @) -> {name, jid_full}
                
                for p in participants:
                    participant_phone = p.get('phone', '')
                    participant_jid = p.get('jid', '')
                    participant_name = p.get('name', '')
                    
                    # Normalizar telefone para comparação (remover + e espaços)
                    clean_participant_phone = participant_phone.replace('+', '').replace(' ', '').strip()
                    phone_to_name[clean_participant_phone] = participant_name
                    phone_to_jid[clean_participant_phone] = participant_jid
                    
                    # ✅ MELHORIA: Mapear JID completo e limpo para busca O(1)
                    if participant_jid:
                        jid_clean = participant_jid.split('@')[0]
                        jid_to_name[participant_jid] = participant_name  # JID completo -> nome
                        jid_clean_to_info[jid_clean] = {  # JID limpo -> info completa
                            'name': participant_name,
                            'jid': participant_jid,
                            'phone': clean_participant_phone
                        }
                        # Também mapear JID limpo no phone_to_name para compatibilidade
                        phone_to_name[jid_clean] = participant_name
                        phone_to_jid[jid_clean] = participant_jid
                
                for identifier in mentions:
                    # ✅ CORREÇÃO: O frontend pode enviar JID ou phone
                    # JID é mais confiável (ex: 52763740340435@lid ou 5517991253112@s.whatsapp.net)
                    # Phone pode ser o número do grupo em alguns casos
                    
                    is_jid = '@' in identifier
                    clean_identifier = identifier.replace('+', '').replace(' ', '').strip()
                    
                    if is_jid:
                        # ✅ MELHORIA: Busca O(1) usando mapas ao invés de loop O(n)
                        jid_full = clean_identifier
                        jid_clean = clean_identifier.split('@')[0]
                        
                        # Tentar buscar por JID completo primeiro, depois por JID limpo
                        name = jid_to_name.get(jid_full, '')
                        jid_info = jid_clean_to_info.get(jid_clean)
                        
                        if jid_info:
                            # Encontrou pelo JID limpo
                            name = jid_info['name']
                            jid_to_use = jid_info['jid']
                        else:
                            # Fallback: usar JID fornecido
                            jid_to_use = jid_full
                        
                        # ✅ PRIORIDADE: Buscar nome com prioridade CONTATOS CADASTRADOS > grupo > telefone
                        normalized_jid_phone = normalize_phone(jid_clean)
                        final_name = (
                            phone_to_contact.get(normalized_jid_phone) or  # 1. Contato cadastrado (PRIORIDADE)
                            name or  # 2. Nome do participante do grupo
                            format_phone_for_display(jid_clean)  # 3. Telefone formatado
                        )
                        
                        # ✅ VALIDAÇÃO: Garantir que name nunca seja LID
                        if final_name and ('@lid' in final_name.lower() or '@s.whatsapp.net' in final_name.lower() or len(final_name) > 20):
                            final_name = format_phone_for_display(jid_clean)
                        
                        # ✅ VALIDAÇÃO: Garantir que phone nunca seja LID
                        clean_phone = normalized_jid_phone or jid_clean
                        if len(clean_phone) > 15 or not clean_phone.replace('+', '').isdigit():
                            import re
                            digits_only = re.sub(r'\D', '', clean_phone)
                            if len(digits_only) >= 10:
                                clean_phone = digits_only
                            else:
                                clean_phone = format_phone_for_display(jid_clean) if jid_clean else ''
                        
                        processed_mentions.append({
                            'phone': clean_phone,  # ✅ Garantir que nunca seja LID
                            'jid': jid_to_use,  # JID completo (Evolution API precisa, mas não exibido)
                            'name': final_name  # ✅ Garantir que nunca seja LID
                        })
                        logger.info(f'✅ [MENTIONS] Processado JID: {jid_full} -> {jid_clean}')
                    else:
                        # É um phone - normalizar e buscar JID correspondente
                        clean_phone = clean_identifier
                        
                        # ✅ PRIORIDADE: Buscar nome com prioridade CONTATOS CADASTRADOS > grupo > telefone
                        normalized_clean_phone = normalize_phone(clean_phone)
                        name = (
                            phone_to_contact.get(normalized_clean_phone) or  # 1. Contato cadastrado (PRIORIDADE)
                            phone_to_name.get(clean_phone, '')  # 2. Nome do participante do grupo
                        )
                        jid_to_use = phone_to_jid.get(clean_phone, clean_phone)
                        
                        # ✅ VALIDAÇÃO: Se o phone não foi encontrado nos participantes,
                        # pode ser o número do grupo! Verificar se é o contact_phone da conversa
                        if not name and not jid_to_use:
                            group_phone = conversation.contact_phone.replace('+', '').replace(' ', '').strip()
                            if '@' in group_phone:
                                group_phone = group_phone.split('@')[0]
                            
                            if clean_phone == group_phone:
                                logger.warning(f'⚠️ [MENTIONS] Phone {clean_phone} parece ser o número do grupo, não do participante! Pulando...')
                                continue  # Pular menção se for o número do grupo
                        
                        # ✅ VALIDAÇÃO: Garantir que name nunca seja LID
                        final_name = name or format_phone_for_display(clean_phone)
                        if final_name and ('@lid' in final_name.lower() or '@s.whatsapp.net' in final_name.lower() or len(final_name) > 20):
                            final_name = format_phone_for_display(clean_phone)
                        
                        # ✅ VALIDAÇÃO: Garantir que phone nunca seja LID
                        final_phone = normalized_clean_phone or clean_phone
                        if len(final_phone) > 15 or not final_phone.replace('+', '').isdigit():
                            import re
                            digits_only = re.sub(r'\D', '', final_phone)
                            if len(digits_only) >= 10:
                                final_phone = digits_only
                            else:
                                final_phone = format_phone_for_display(clean_phone) if clean_phone else ''
                        
                        processed_mentions.append({
                            'phone': final_phone,  # ✅ Garantir que nunca seja LID
                            'jid': jid_to_use,  # JID original se disponível (não exibido)
                            'name': final_name  # ✅ Garantir que nunca seja LID
                        })
                        logger.info(f'✅ [MENTIONS] Processado phone: {clean_phone} -> JID: {jid_to_use}')
                
                metadata['mentions'] = processed_mentions
        
        if metadata:
            message.metadata = metadata
            message.save(update_fields=['metadata'])
        
        return message


class ConversationSerializer(serializers.ModelSerializer):
    """Serializer para conversas."""
    
    assigned_to_data = UserSerializer(source='assigned_to', read_only=True)
    participants_data = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()  # ✅ MUDADO: Agora usa get_unread_count
    department_name = serializers.SerializerMethodField()  # ✅ FIX: Mudado para SerializerMethodField para tratar null
    contact_tags = serializers.SerializerMethodField()
    instance_friendly_name = serializers.SerializerMethodField()
    
    # ✅ FIX: Garantir que department sempre retorne como UUID string (ou null)
    department = serializers.PrimaryKeyRelatedField(
        read_only=True,
        allow_null=True
    )
    
    def get_department_name(self, obj):
        """Retorna nome do departamento ou string vazia se não houver."""
        if obj.department:
            return obj.department.name
        return ''  # ✅ FIX: Retornar string vazia ao invés de None
    
    class Meta:
        model = Conversation
        fields = [
            'id', 'tenant', 'department', 'department_name',
            'contact_phone', 'contact_name', 'profile_pic_url', 'instance_name', 'instance_friendly_name',
            'assigned_to', 'assigned_to_data',
            'status', 'last_message_at', 'metadata', 'participants',
            'participants_data', 'created_at', 'updated_at',
            'conversation_type', 'group_metadata',
            'last_message', 'unread_count', 'contact_tags'
        ]
        read_only_fields = [
            'id', 'tenant', 'created_at', 'updated_at', 'last_message_at',
            'unread_count', 'assigned_to_data', 'participants_data', 'department_name', 
            'profile_pic_url', 'instance_name', 'instance_friendly_name', 'contact_tags'
        ]
    
    def get_participants_data(self, obj):
        """Retorna os participantes da conversa."""
        return UserSerializer(obj.participants.all(), many=True).data
    
    def get_unread_count(self, obj):
        """Retorna contagem de mensagens não lidas (otimizado em batch)."""
        # ✅ PERFORMANCE: Usar unread_count_annotated calculado em batch
        # Se não estiver disponível (fallback), usar property original
        if hasattr(obj, 'unread_count_annotated'):
            return obj.unread_count_annotated
        # Fallback para property original (caso não tenha annotate)
        return obj.unread_count
    
    def get_last_message(self, obj):
        """Retorna a última mensagem da conversa (otimizado com prefetch)."""
        # ✅ PERFORMANCE: Usar last_message_list do prefetch_related
        # Se não estiver disponível (fallback), buscar normalmente
        if hasattr(obj, 'last_message_list') and obj.last_message_list:
            return MessageSerializer(obj.last_message_list[0]).data
        
        # Fallback para query normal (caso não tenha prefetch)
        last_message = obj.messages.order_by('-created_at').first()
        if last_message:
            return MessageSerializer(last_message).data
        return None
    
    def get_instance_friendly_name(self, obj):
        """Retorna nome amigável da instância (com cache).
        Prioriza friendly_name; fallback para instance_name (UUID) só se instância não for encontrada.
        """
        if not obj.instance_name:
            return None
        
        # ✅ PERFORMANCE: Cache de 5 minutos para evitar queries repetidas
        from django.core.cache import cache
        from django.db.models import Q
        cache_key = f"instance_friendly_name:{obj.instance_name}"
        friendly_name = cache.get(cache_key)
        
        if friendly_name is None:
            # Buscar no banco - por instance_name OU evolution_instance_name (webhook pode enviar qualquer um)
            # Sem filtro is_active: mostrar nome amigável mesmo se instância foi desativada
            from apps.notifications.models import WhatsAppInstance
            instance = WhatsAppInstance.objects.filter(
                Q(instance_name=obj.instance_name) | Q(evolution_instance_name=obj.instance_name),
                tenant=obj.tenant
            ).values('friendly_name').first()
            
            friendly_name = instance['friendly_name'] if instance else obj.instance_name
            # Cache por 5 minutos (300 segundos)
            cache.set(cache_key, friendly_name, 300)
        
        return friendly_name
    
    def get_contact_tags(self, obj):
        """Busca as tags do contato pelo telefone (com cache)."""
        # ✅ PERFORMANCE: Cache de 10 minutos para evitar queries repetidas
        from django.core.cache import cache
        from apps.contacts.signals import normalize_phone_for_search
        
        # ✅ CORREÇÃO CRÍTICA: Normalizar telefone antes de buscar no cache
        # Isso garante que o cache seja encontrado mesmo se telefone estiver em formato diferente
        normalized_phone = normalize_phone_for_search(obj.contact_phone)
        cache_key = f"contact_tags:{obj.tenant_id}:{normalized_phone}"
        
        tags = cache.get(cache_key)
        
        if tags is None:
            try:
                # ✅ CORREÇÃO: Buscar contato usando telefone normalizado OU original
                # Isso garante que encontre o contato mesmo com diferenças de formatação
                from django.db.models import Q
                contact = Contact.objects.prefetch_related('tags').filter(
                    Q(tenant=obj.tenant) &
                    (Q(phone=normalized_phone) | Q(phone=obj.contact_phone)) &
                    Q(is_active=True)
                ).first()
                
                if contact:
                    tags = [
                        {
                            'id': str(tag.id),
                            'name': tag.name,
                            'color': tag.color
                        }
                        for tag in contact.tags.all()
                    ]
                else:
                    tags = []
            except Exception as e:
                logger.error(f"❌ [SERIALIZER] Erro ao buscar tags do contato: {e}", exc_info=True)
                tags = []
            
            # Cache por 10 minutos (600 segundos)
            cache.set(cache_key, tags, 600)
        
        return tags


class ConversationDetailSerializer(ConversationSerializer):
    """Serializer detalhado para conversa (com mensagens)."""
    
    messages = MessageSerializer(many=True, read_only=True)
    
    class Meta(ConversationSerializer.Meta):
        fields = ConversationSerializer.Meta.fields + ['messages']


class QuickReplySerializer(serializers.ModelSerializer):
    """Serializer para respostas rápidas."""
    
    class Meta:
        model = QuickReply
        fields = ['id', 'title', 'content', 'category', 'use_count', 'created_at', 'updated_at']
        read_only_fields = ['use_count', 'created_at', 'updated_at']
    
    def validate_content(self, value):
        """Validação: conteúdo não pode estar vazio."""
        if not value or not value.strip():
            raise serializers.ValidationError("Conteúdo não pode estar vazio.")
        if len(value) > 4000:  # Limite do WhatsApp
            raise serializers.ValidationError("Conteúdo muito longo (máximo 4000 caracteres).")
        return value.strip()
    
    def validate_title(self, value):
        """Validação: título não pode estar vazio."""
        if not value or not value.strip():
            raise serializers.ValidationError("Título não pode estar vazio.")
        return value.strip()

