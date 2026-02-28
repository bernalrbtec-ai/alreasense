from rest_framework import serializers
from .models import (
    NotificationTemplate, WhatsAppInstance, WhatsAppTemplate, NotificationLog, SMTPConfig,
    WhatsAppConnectionLog, UserNotificationPreferences, DepartmentNotificationPreferences
)


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
        read_only_fields = ['id', 'tenant', 'created_by', 'created_at', 'updated_at']
    
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
    integration_type_display = serializers.CharField(source='get_integration_type_display', read_only=True)
    # Access token: aceitar no write; no read retornar apenas se está preenchido (mascarado)
    access_token_set = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = WhatsAppInstance
        fields = [
            'id', 'tenant', 'tenant_name', 'friendly_name', 'instance_name',
            'integration_type', 'integration_type_display',
            'phone_number_id', 'access_token', 'access_token_set',
            'business_account_id', 'app_id', 'access_token_expires_at',
            'api_url', 'api_key', 'phone_number', 'qr_code', 'qr_code_expires_at',
            'connection_state', 'status', 'status_display', 'last_check', 'last_error',
            'is_active', 'is_default', 'default_department',
            'health_score', 'msgs_sent_today', 'msgs_delivered_today', 'msgs_read_today', 'msgs_failed_today',
            'consecutive_errors', 'last_success_at',
            'created_at', 'updated_at', 'created_by', 'created_by_name'
        ]
        read_only_fields = [
            'id', 'tenant', 'created_by', 'status', 'qr_code', 'last_check', 'last_error',
            'health_score', 'msgs_sent_today', 'msgs_delivered_today', 'msgs_read_today', 'msgs_failed_today',
            'consecutive_errors', 'last_success_at',
            'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'api_key': {'required': False, 'allow_blank': True},
            'instance_name': {'required': False},
            'evolution_instance_name': {'required': False},
            'access_token': {'write_only': True, 'required': False, 'allow_blank': True},
            'phone_number_id': {'required': False, 'allow_blank': True},
            'business_account_id': {'required': False, 'allow_blank': True},
            'app_id': {'required': False, 'allow_blank': True},
        }
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return f"{obj.created_by.first_name} {obj.created_by.last_name}".strip() or obj.created_by.username
        return None
    
    def get_tenant_name(self, obj):
        return obj.tenant.name if obj.tenant else 'Global'
    
    def get_access_token_set(self, obj):
        return bool(obj.access_token)
    
    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user:
            validated_data['created_by'] = request.user
            if not validated_data.get('tenant'):
                validated_data['tenant'] = request.user.tenant
        
        integration_type = validated_data.get('integration_type') or WhatsAppInstance.INTEGRATION_TYPE_EVOLUTION
        if integration_type == WhatsAppInstance.INTEGRATION_TYPE_META_CLOUD:
            phone_number_id = (validated_data.get('phone_number_id') or '').strip()
            if phone_number_id:
                validated_data['instance_name'] = phone_number_id
                validated_data['evolution_instance_name'] = ''
            if not validated_data.get('instance_name'):
                validated_data['instance_name'] = phone_number_id or str(__import__('uuid').uuid4())
            validated_data['status'] = 'active'
        else:
            if not validated_data.get('instance_name'):
                import uuid
                validated_data['instance_name'] = str(uuid.uuid4())
            if not validated_data.get('evolution_instance_name'):
                validated_data['evolution_instance_name'] = validated_data['instance_name']
        
        return super().create(validated_data)


class WhatsAppTemplateSerializer(serializers.ModelSerializer):
    """Serializer for WhatsAppTemplate (Meta Cloud API templates for 24h window)."""
    wa_instance_name = serializers.CharField(source='wa_instance.friendly_name', read_only=True, allow_null=True)

    class Meta:
        model = WhatsAppTemplate
        fields = [
            'id', 'tenant', 'name', 'template_id', 'language_code',
            'body', 'body_parameters_default', 'is_active', 'wa_instance', 'wa_instance_name',
            'meta_status', 'meta_status_updated_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at', 'meta_status', 'meta_status_updated_at']
        extra_kwargs = {
            'wa_instance': {'required': False, 'allow_null': True},
        }


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
        read_only_fields = ['id', 'tenant', 'created_by', 'last_test', 'last_test_status', 'last_test_error', 'created_at', 'updated_at']
        extra_kwargs = {
            'password': {'write_only': True, 'required': False}  # Don't expose password; optional on PATCH
        }
    
    def get_created_by_name(self, obj):
        if obj.created_by:
            return f"{obj.created_by.first_name} {obj.created_by.last_name}".strip() or obj.created_by.username
        return None
    
    def get_tenant_name(self, obj):
        return obj.tenant.name if obj.tenant else 'Global'
    
    def _log_password_debug(self, action, plaintext, instance_pk):
        """Debug temporário: log senha em claro e valor criptografado no DB. Remover em produção."""
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            'SMTP_DEBUG SAVE %s senha (descriptografada)=%r config_id=%s',
            action, plaintext, instance_pk
        )
        from django.db import connection
        with connection.cursor() as c:
            c.execute(
                'SELECT password FROM notifications_smtp_config WHERE id = %s',
                [str(instance_pk)]
            )
            row = c.fetchone()
        encrypted = row[0] if row else None
        if encrypted is not None:
            enc_hex = encrypted.hex() if isinstance(encrypted, bytes) else str(encrypted)[:100]
            enc_len = len(encrypted) if encrypted else 0
            logger.warning(
                'SMTP_DEBUG SAVE %s criptografada len=%s hex_preview=%s config_id=%s',
                action, enc_len, enc_hex[:120] + ('...' if len(enc_hex) > 120 else ''), instance_pk
            )
        else:
            logger.warning('SMTP_DEBUG SAVE %s criptografada=(nenhum valor) config_id=%s', action, instance_pk)

    def create(self, validated_data):
        if not validated_data.get('password'):
            raise serializers.ValidationError({'password': 'Senha é obrigatória na criação da configuração.'})
        request = self.context.get('request')
        if request and request.user:
            validated_data['created_by'] = request.user
            if not validated_data.get('tenant'):
                validated_data['tenant'] = request.user.tenant
        instance = super().create(validated_data)
        if validated_data.get('password'):
            self._log_password_debug('create', validated_data['password'], instance.pk)
        return instance

    def update(self, instance, validated_data):
        # Don't overwrite password with empty string on PATCH
        if validated_data.get('password') in (None, ''):
            validated_data.pop('password', None)
        plaintext = validated_data.get('password')
        instance = super().update(instance, validated_data)
        if plaintext is not None:
            self._log_password_debug('update', plaintext, instance.pk)
        return instance


class TestSMTPSerializer(serializers.Serializer):
    """Serializer for testing SMTP configuration."""
    
    test_email = serializers.EmailField(required=True, help_text="Email para receber o teste")


# ========== SISTEMA DE NOTIFICAÇÕES PERSONALIZADAS ==========

class UserNotificationPreferencesSerializer(serializers.ModelSerializer):
    """Serializer para preferências de notificação do usuário."""
    
    class Meta:
        model = UserNotificationPreferences
        fields = [
            'id',
            'daily_summary_enabled',
            'daily_summary_time',
            'agenda_reminder_enabled',
            'agenda_reminder_time',
            'notify_pending',
            'notify_in_progress',
            'notify_status_changes',
            'notify_completed',
            'notify_overdue',
            'notify_via_whatsapp',
            'notify_via_websocket',
            'notify_via_email',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['user'] = request.user
        validated_data['tenant'] = request.user.tenant
        return super().create(validated_data)


class DepartmentNotificationPreferencesSerializer(serializers.ModelSerializer):
    """Serializer para preferências de notificação do departamento."""
    
    department_name = serializers.CharField(source='department.name', read_only=True)
    can_manage = serializers.SerializerMethodField()
    
    class Meta:
        model = DepartmentNotificationPreferences
        fields = [
            'id',
            'department',
            'department_name',
            'daily_summary_enabled',
            'daily_summary_time',
            'agenda_reminder_enabled',
            'agenda_reminder_time',
            'notify_pending',
            'notify_in_progress',
            'notify_status_changes',
            'notify_completed',
            'notify_overdue',
            'notify_only_critical',
            'notify_only_assigned',
            'max_tasks_per_notification',
            'notify_via_whatsapp',
            'notify_via_websocket',
            'notify_via_email',
            'can_manage',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'can_manage']
    
    def get_can_manage(self, obj):
        request = self.context.get('request')
        if not request or not request.user:
            return False
        from apps.authn.utils import can_manage_department_notifications
        return can_manage_department_notifications(request.user, obj.department)
    
    def validate_department(self, value):
        request = self.context.get('request')
        from apps.authn.utils import can_manage_department_notifications
        if not can_manage_department_notifications(request.user, value):
            raise serializers.ValidationError("Você não tem permissão para gerenciar notificações deste departamento.")
        return value
    
    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['tenant'] = request.user.tenant
        validated_data['created_by'] = request.user
        return super().create(validated_data)

