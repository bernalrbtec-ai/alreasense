from rest_framework import serializers
from apps.campaigns.models import (
    Campaign, CampaignMessage, CampaignContact, CampaignLog, Holiday
)
from apps.contacts.serializers import ContactSerializer


class CampaignMessageSerializer(serializers.ModelSerializer):
    response_rate = serializers.ReadOnlyField()
    
    class Meta:
        model = CampaignMessage
        fields = [
            'id', 'message_text', 'order', 'is_active',
            'times_sent', 'response_count', 'response_rate',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'times_sent', 'response_count', 'created_at', 'updated_at']


class CampaignContactSerializer(serializers.ModelSerializer):
    contact = ContactSerializer(read_only=True)
    message_sent_preview = serializers.SerializerMethodField()
    
    class Meta:
        model = CampaignContact
        fields = [
            'id', 'contact', 'status', 'message_sent', 'message_sent_preview',
            'sent_at', 'delivered_at', 'read_at', 'responded_at',
            'error_message', 'retry_count'
        ]
        read_only_fields = ['id']
    
    def get_message_sent_preview(self, obj):
        if obj.message_sent:
            return obj.message_sent.message_text[:100]
        return None


class CampaignLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampaignLog
        fields = ['id', 'level', 'event_type', 'message', 'metadata', 'created_at']
        read_only_fields = ['id', 'created_at']


class CampaignSerializer(serializers.ModelSerializer):
    progress_percentage = serializers.ReadOnlyField()
    response_rate = serializers.ReadOnlyField()
    can_be_started = serializers.ReadOnlyField()
    
    # Nested (read-only)
    messages = CampaignMessageSerializer(many=True, read_only=True)
    instance_name = serializers.CharField(source='instance.friendly_name', read_only=True)
    
    # Write-only
    instance_id = serializers.UUIDField(write_only=True)
    contact_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False
    )
    message_texts = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = Campaign
        fields = [
            'id', 'name', 'description', 'status', 'is_paused',
            'instance', 'instance_id', 'instance_name',
            'schedule_type', 'morning_start', 'morning_end',
            'afternoon_start', 'afternoon_end', 'skip_weekends', 'skip_holidays',
            'total_contacts', 'sent_messages', 'failed_messages', 'responded_count',
            'progress_percentage', 'response_rate', 'can_be_started',
            'messages', 'contact_ids', 'message_texts',
            'next_scheduled_send', 'last_send_at',
            'created_at', 'updated_at', 'started_at', 'paused_at', 'completed_at',
            'last_error', 'auto_pause_reason'
        ]
        read_only_fields = [
            'id', 'status', 'sent_messages', 'failed_messages', 'responded_count',
            'next_scheduled_send', 'last_send_at', 'created_at', 'updated_at',
            'started_at', 'paused_at', 'completed_at'
        ]
    
    def validate_instance_id(self, value):
        from apps.notifications.models import WhatsAppInstance
        try:
            instance = WhatsAppInstance.objects.get(
                id=value,
                tenant=self.context['request'].tenant
            )
        except WhatsAppInstance.DoesNotExist:
            raise serializers.ValidationError("Instância não encontrada")
        
        if instance.connection_state != 'open':
            raise serializers.ValidationError("Instância não está conectada")
        
        # Verificar se já tem campanha ativa
        if Campaign.objects.filter(
            instance=instance,
            status=Campaign.Status.ACTIVE
        ).exists():
            raise serializers.ValidationError(
                f"Instância já tem uma campanha ativa"
            )
        
        return value
    
    def validate_contact_ids(self, value):
        from apps.contacts.models import Contact
        if not value:
            return value
        
        contacts = Contact.objects.filter(
            id__in=value,
            tenant=self.context['request'].tenant
        )
        
        if contacts.count() != len(value):
            raise serializers.ValidationError("Um ou mais contatos não foram encontrados")
        
        return value
    
    def validate(self, attrs):
        if attrs.get('schedule_type') == Campaign.ScheduleType.CUSTOM_PERIOD:
            required_fields = ['morning_start', 'morning_end', 'afternoon_start', 'afternoon_end']
            for field in required_fields:
                if not attrs.get(field):
                    raise serializers.ValidationError({
                        field: f"Campo obrigatório para agendamento personalizado"
                    })
        
        return attrs


class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = ['id', 'date', 'name', 'is_national', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']

