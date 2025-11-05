"""
Serializers para o módulo Flow Chat.
"""
from rest_framework import serializers
from apps.chat.models import Conversation, Message, MessageAttachment, MessageReaction
from apps.authn.serializers import UserSerializer
from apps.contacts.models import Contact


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
                    proxy_url = s3_manager.get_public_url(instance.file_path)
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
    user = serializers.UUIDField(read_only=True)
    user_data = UserSerializer(source='user', read_only=True)
    
    class Meta:
        model = MessageReaction
        fields = ['id', 'message', 'user', 'user_data', 'emoji', 'created_at']
        read_only_fields = ['id', 'message', 'user', 'user_data', 'created_at']


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
            'status', 'is_internal', 'attachments', 'reactions', 'reactions_summary', 'metadata', 'created_at'
        ]
        read_only_fields = ['id', 'conversation', 'sender', 'created_at', 'sender_data', 'attachments', 'reactions', 'reactions_summary']
    
    def get_reactions_summary(self, obj):
        """
        Retorna resumo das reações agrupadas por emoji.
        Formato: {'👍': {'count': 3, 'users': [user1, user2, user3]}, ...}
        """
        from django.db.models import Count
        from collections import defaultdict
        
        # Buscar reações com prefetch se disponível
        if hasattr(obj, 'reactions'):
            reactions = obj.reactions.all()
        else:
            reactions = MessageReaction.objects.filter(message=obj).select_related('user')
        
        summary = defaultdict(lambda: {'count': 0, 'users': []})
        
        for reaction in reactions:
            emoji = reaction.emoji
            summary[emoji]['count'] += 1
            # Adicionar dados do usuário (apenas ID e nome para economizar espaço)
            summary[emoji]['users'].append({
                'id': str(reaction.user.id),
                'email': reaction.user.email,
                'first_name': reaction.user.first_name,
                'last_name': reaction.user.last_name,
            })
        
        return dict(summary)


class MessageCreateSerializer(serializers.ModelSerializer):
    """Serializer para criação de mensagens (outgoing)."""
    
    attachment_urls = serializers.ListField(
        child=serializers.URLField(),
        required=False,
        write_only=True,
        help_text='Lista de URLs de anexos para enviar'
    )
    
    class Meta:
        model = Message
        fields = [
            'conversation', 'content', 'is_internal', 'attachment_urls'
        ]
    
    def validate(self, attrs):
        """Valida que há conteúdo ou anexos."""
        if not attrs.get('content') and not attrs.get('attachment_urls'):
            raise serializers.ValidationError(
                "Mensagem deve ter conteúdo de texto ou anexos."
            )
        return attrs
    
    def create(self, validated_data):
        """Cria mensagem outgoing."""
        attachment_urls = validated_data.pop('attachment_urls', [])
        validated_data['direction'] = 'outgoing'
        validated_data['sender'] = self.context['request'].user
        validated_data['status'] = 'pending'
        
        message = Message.objects.create(**validated_data)
        
        # attachment_urls será processado pela task RabbitMQ
        if attachment_urls:
            message.metadata = {'attachment_urls': attachment_urls}
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
        """Retorna nome amigável da instância (com cache)."""
        if not obj.instance_name:
            return None
        
        # ✅ PERFORMANCE: Cache de 5 minutos para evitar queries repetidas
        from django.core.cache import cache
        cache_key = f"instance_friendly_name:{obj.instance_name}"
        friendly_name = cache.get(cache_key)
        
        if friendly_name is None:
            # Buscar no banco
            from apps.notifications.models import WhatsAppInstance
            instance = WhatsAppInstance.objects.filter(
                instance_name=obj.instance_name,
                is_active=True
            ).values('friendly_name').first()
            
            friendly_name = instance['friendly_name'] if instance else obj.instance_name
            # Cache por 5 minutos (300 segundos)
            cache.set(cache_key, friendly_name, 300)
        
        return friendly_name
    
    def get_contact_tags(self, obj):
        """Busca as tags do contato pelo telefone (com cache)."""
        # ✅ PERFORMANCE: Cache de 10 minutos para evitar queries repetidas
        from django.core.cache import cache
        cache_key = f"contact_tags:{obj.tenant_id}:{obj.contact_phone}"
        tags = cache.get(cache_key)
        
        if tags is None:
            try:
                contact = Contact.objects.prefetch_related('tags').get(
                    tenant=obj.tenant,
                    phone=obj.contact_phone,
                    is_active=True
                )
                tags = [
                    {
                        'id': str(tag.id),
                        'name': tag.name,
                        'color': tag.color
                    }
                    for tag in contact.tags.all()
                ]
            except Contact.DoesNotExist:
                tags = []
            
            # Cache por 10 minutos (600 segundos)
            cache.set(cache_key, tags, 600)
        
        return tags


class ConversationDetailSerializer(ConversationSerializer):
    """Serializer detalhado para conversa (com mensagens)."""
    
    messages = MessageSerializer(many=True, read_only=True)
    
    class Meta(ConversationSerializer.Meta):
        fields = ConversationSerializer.Meta.fields + ['messages']

