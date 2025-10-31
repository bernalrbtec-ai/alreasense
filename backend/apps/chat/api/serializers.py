"""
Serializers para o módulo Flow Chat.
"""
from rest_framework import serializers
from apps.chat.models import Conversation, Message, MessageAttachment
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
            if instance.storage_type == 's3' and instance.file_path:
                file_url = (data.get('file_url') or '').strip()
                # Se file_url está vazio OU não é URL do proxy, gerar URL do proxy
                if not file_url or '/api/chat/media-proxy' not in file_url:
                    from apps.chat.utils.s3 import S3Manager
                    s3_manager = S3Manager()
                    
                    # ✅ Verificar se arquivo existe no S3 antes de gerar URL
                    if not s3_manager.file_exists(instance.file_path):
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"⚠️ [SERIALIZER] Arquivo não encontrado no S3: {instance.file_path}")
                        # Se arquivo não existe, manter URL vazia ou retornar URL vazia
                        data['file_url'] = ''
                        return data
                    
                    proxy_url = s3_manager.get_public_url(instance.file_path)
                    data['file_url'] = proxy_url
                    # Log para debug
                    import logging
                    logger = logging.getLogger(__name__)
                    if not file_url:
                        logger.debug(f"📎 [SERIALIZER] file_url vazio, gerado proxy: {proxy_url[:50]}...")
                    else:
                        logger.debug(f"📎 [SERIALIZER] file_url não era proxy, convertido: {proxy_url[:50]}...")
        except Exception as e:
            # Em caso de erro, logar mas manter o original para não quebrar a resposta
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"⚠️ [SERIALIZER] Erro ao gerar URL do proxy: {e}", exc_info=True)
        return data


class MessageSerializer(serializers.ModelSerializer):
    """Serializer para mensagens."""
    
    # Serializar UUIDs como strings
    id = serializers.UUIDField(read_only=True)
    conversation = serializers.UUIDField(read_only=True)
    sender = serializers.UUIDField(read_only=True)
    
    sender_data = UserSerializer(source='sender', read_only=True)
    attachments = MessageAttachmentSerializer(many=True, read_only=True)
    
    class Meta:
        model = Message
        fields = [
            'id', 'conversation', 'sender', 'sender_data', 'sender_name', 'sender_phone',
            'content', 'direction', 'message_id', 'evolution_status', 'error_message',
            'status', 'is_internal', 'attachments', 'metadata', 'created_at'
        ]
        read_only_fields = ['id', 'conversation', 'sender', 'created_at', 'sender_data', 'attachments']


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
    unread_count = serializers.ReadOnlyField()
    department_name = serializers.CharField(source='department.name', read_only=True)
    contact_tags = serializers.SerializerMethodField()
    instance_friendly_name = serializers.SerializerMethodField()
    
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
    
    def get_last_message(self, obj):
        """Retorna a última mensagem da conversa."""
        last_message = obj.messages.order_by('-created_at').first()
        if last_message:
            return MessageSerializer(last_message).data
        return None
    
    def get_instance_friendly_name(self, obj):
        """Retorna nome amigável da instância."""
        if not obj.instance_name:
            return None
        
        # Buscar no banco
        from apps.notifications.models import WhatsAppInstance
        instance = WhatsAppInstance.objects.filter(
            instance_name=obj.instance_name,
            is_active=True
        ).values('friendly_name').first()
        
        if instance:
            return instance['friendly_name']
        
        return obj.instance_name  # Fallback para UUID
    
    def get_contact_tags(self, obj):
        """Busca as tags do contato pelo telefone."""
        try:
            contact = Contact.objects.prefetch_related('tags').get(
                tenant=obj.tenant,
                phone=obj.contact_phone,
                is_active=True
            )
            return [
                {
                    'id': str(tag.id),
                    'name': tag.name,
                    'color': tag.color
                }
                for tag in contact.tags.all()
            ]
        except Contact.DoesNotExist:
            return []


class ConversationDetailSerializer(ConversationSerializer):
    """Serializer detalhado para conversa (com mensagens)."""
    
    messages = MessageSerializer(many=True, read_only=True)
    
    class Meta(ConversationSerializer.Meta):
        fields = ConversationSerializer.Meta.fields + ['messages']

