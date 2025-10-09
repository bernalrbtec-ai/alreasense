from rest_framework import serializers
from .models import NotificationTemplate, WhatsAppInstance, NotificationLog, SMTPConfig, WhatsAppConnectionLog


class NotificationTemplateSerializer(serializers.ModelSerializer):
    """Serializer for NotificationTemplate."""
    
    created_by_name = serializers.SerializerMethodField()
    tenant_name = serializers.SerializerMethodField()
    
    class Meta:
        model = NotificationTemplate
        fields = [
            'id', 'tenant', 'tenant_name', 'name', 'type', 'category',
            'subject', 'content', 'html_content',
            'is_active', 'is_global',
            'created_at', 'updated_at', 'created_by', 'created_by_name'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return f"{obj.created_by.first_name} {obj.created_by.last_name}".strip() or obj.created_by.username
        return None
    
    def get_tenant_name(self, obj):
        return obj.tenant.name if obj.tenant else 'Global'
    
    def create(self, validated_data):
        # Set created_by from request user
        request = self.context.get('request')
        if request and request.user:
            validated_data['created_by'] = request.user
            # Set tenant from user if not provided
            if not validated_data.get('tenant') and not validated_data.get('is_global'):
                validated_data['tenant'] = request.user.tenant
        
        return super().create(validated_data)


class WhatsAppInstanceSerializer(serializers.ModelSerializer):
    """Serializer for WhatsAppInstance."""
    
    created_by_name = serializers.SerializerMethodField()
    tenant_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = WhatsAppInstance
        fields = [
            'id', 'tenant', 'tenant_name', 'friendly_name', 'instance_name',
            'api_url', 'api_key', 'phone_number', 'qr_code', 'qr_code_expires_at',
            'connection_state', 'status', 'status_display', 'last_check', 'last_error',
            'is_active', 'is_default',
            'created_at', 'updated_at', 'created_by', 'created_by_name'
        ]
        read_only_fields = ['id', 'status', 'qr_code', 'last_check', 'last_error', 'created_at', 'updated_at']
        extra_kwargs = {
            'api_key': {'write_only': True, 'required': False, 'allow_blank': True}  # Don't expose API key in responses
        }
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return f"{obj.created_by.first_name} {obj.created_by.last_name}".strip() or obj.created_by.username
        return None
    
    def get_tenant_name(self, obj):
        return obj.tenant.name if obj.tenant else 'Global'
    
    def create(self, validated_data):
        # Set created_by from request user
        request = self.context.get('request')
        if request and request.user:
            validated_data['created_by'] = request.user
            # Set tenant from user if not provided
            if not validated_data.get('tenant'):
                validated_data['tenant'] = request.user.tenant
        
        return super().create(validated_data)


class WhatsAppConnectionLogSerializer(serializers.ModelSerializer):
    """Serializer for WhatsAppConnectionLog."""
    
    instance_name = serializers.CharField(source='instance.friendly_name', read_only=True)
    user_name = serializers.SerializerMethodField()
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    
    class Meta:
        model = WhatsAppConnectionLog
        fields = [
            'id', 'instance', 'instance_name', 'action', 'action_display',
            'details', 'user', 'user_name', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_user_name(self, obj):
        if obj.user:
            return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.username
        return None


class NotificationLogSerializer(serializers.ModelSerializer):
    """Serializer for NotificationLog."""
    
    recipient_name = serializers.SerializerMethodField()
    tenant_name = serializers.SerializerMethodField()
    template_name = serializers.CharField(source='template.name', read_only=True)
    whatsapp_instance_name = serializers.CharField(source='whatsapp_instance.name', read_only=True)
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = NotificationLog
        fields = [
            'id', 'tenant', 'tenant_name', 'template', 'template_name',
            'whatsapp_instance', 'whatsapp_instance_name',
            'recipient', 'recipient_name', 'recipient_email', 'recipient_phone',
            'type', 'type_display', 'subject', 'content',
            'status', 'status_display', 'error_message', 'external_id',
            'created_at', 'sent_at', 'delivered_at', 'read_at',
            'metadata'
        ]
        read_only_fields = ['id', 'created_at', 'sent_at', 'delivered_at', 'read_at']
    
    def get_recipient_name(self, obj):
        return f"{obj.recipient.first_name} {obj.recipient.last_name}".strip() or obj.recipient.username
    
    def get_tenant_name(self, obj):
        return obj.tenant.name


class SendNotificationSerializer(serializers.Serializer):
    """Serializer for sending notifications."""
    
    template_id = serializers.UUIDField(required=True)
    recipient_id = serializers.IntegerField(required=True)
    context = serializers.JSONField(required=False, default=dict)
    scheduled_at = serializers.DateTimeField(required=False, allow_null=True)
    
    def validate_template_id(self, value):
        try:
            NotificationTemplate.objects.get(id=value, is_active=True)
        except NotificationTemplate.DoesNotExist:
            raise serializers.ValidationError("Template não encontrado ou inativo")
        return value
    
    def validate_recipient_id(self, value):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        try:
            User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("Usuário não encontrado")
        return value


class SMTPConfigSerializer(serializers.ModelSerializer):
    """Serializer for SMTPConfig."""
    
    created_by_name = serializers.SerializerMethodField()
    tenant_name = serializers.SerializerMethodField()
    last_test_status_display = serializers.CharField(source='get_last_test_status_display', read_only=True)
    
    class Meta:
        model = SMTPConfig
        fields = [
            'id', 'tenant', 'tenant_name', 'name',
            'host', 'port', 'username', 'password',
            'use_tls', 'use_ssl', 'verify_ssl', 'from_email', 'from_name',
            'is_active', 'is_default',
            'last_test', 'last_test_status', 'last_test_status_display', 'last_test_error',
            'created_at', 'updated_at', 'created_by', 'created_by_name'
        ]
        read_only_fields = ['id', 'last_test', 'last_test_status', 'last_test_error', 'created_at', 'updated_at']
        extra_kwargs = {
            'password': {'write_only': True}  # Don't expose password in responses
        }
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return f"{obj.created_by.first_name} {obj.created_by.last_name}".strip() or obj.created_by.username
        return None
    
    def get_tenant_name(self, obj):
        return obj.tenant.name if obj.tenant else 'Global'
    
    def create(self, validated_data):
        # Set created_by from request user
        request = self.context.get('request')
        if request and request.user:
            validated_data['created_by'] = request.user
            # Set tenant from user if not provided
            if not validated_data.get('tenant'):
                validated_data['tenant'] = request.user.tenant
        
        return super().create(validated_data)


class TestSMTPSerializer(serializers.Serializer):
    """Serializer for testing SMTP configuration."""
    
    test_email = serializers.EmailField(required=True, help_text="Email para receber o teste")

