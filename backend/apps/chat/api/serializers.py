"""
Serializers para o módulo Flow Chat.
"""
from rest_framework import serializers
from apps.chat.models import Conversation, Message, MessageAttachment
from apps.authn.serializers import UserSerializer


class MessageAttachmentSerializer(serializers.ModelSerializer):
    """Serializer para anexos de mensagem."""
    
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
            'size_bytes', 'expires_at', 'created_at',
            'is_expired', 'is_image', 'is_video', 'is_audio', 'is_document'
        ]
        read_only_fields = [
            'id', 'tenant', 'created_at', 'is_expired',
            'is_image', 'is_video', 'is_audio', 'is_document'
        ]


class MessageSerializer(serializers.ModelSerializer):
    """Serializer para mensagens."""
    
    sender_data = UserSerializer(source='sender', read_only=True)
    attachments = MessageAttachmentSerializer(many=True, read_only=True)
    
    class Meta:
        model = Message
        fields = [
            'id', 'conversation', 'sender', 'sender_data', 'content',
            'direction', 'message_id', 'evolution_status', 'error_message',
            'status', 'is_internal', 'attachments', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'sender_data', 'attachments']


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
    participants_data = UserSerializer(source='participants', many=True, read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.ReadOnlyField()
    department_name = serializers.CharField(source='department.name', read_only=True)
    
    class Meta:
        model = Conversation
        fields = [
            'id', 'tenant', 'department', 'department_name',
            'contact_phone', 'contact_name', 'assigned_to', 'assigned_to_data',
            'status', 'last_message_at', 'metadata', 'participants',
            'participants_data', 'created_at', 'updated_at',
            'last_message', 'unread_count'
        ]
        read_only_fields = [
            'id', 'tenant', 'created_at', 'updated_at', 'last_message_at',
            'unread_count', 'assigned_to_data', 'participants_data', 'department_name'
        ]
    
    def get_last_message(self, obj):
        """Retorna a última mensagem da conversa."""
        last_message = obj.messages.order_by('-created_at').first()
        if last_message:
            return MessageSerializer(last_message).data
        return None


class ConversationDetailSerializer(ConversationSerializer):
    """Serializer detalhado para conversa (com mensagens)."""
    
    messages = MessageSerializer(many=True, read_only=True)
    
    class Meta(ConversationSerializer.Meta):
        fields = ConversationSerializer.Meta.fields + ['messages']

