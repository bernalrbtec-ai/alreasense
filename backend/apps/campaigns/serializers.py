from rest_framework import serializers
from .models import Campaign, CampaignMessage, CampaignContact, CampaignLog, CampaignNotification
from apps.notifications.models import WhatsAppInstance
from apps.contacts.models import Contact, ContactList


class CampaignMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampaignMessage
        fields = ['id', 'content', 'order', 'times_used', 'media_url', 'media_type']


class CampaignInstanceSerializer(serializers.ModelSerializer):
    """Serializer simplificado para instâncias dentro de campanhas"""
    class Meta:
        model = WhatsAppInstance
        fields = ['id', 'friendly_name', 'phone_number', 'connection_state', 'health_score', 'msgs_sent_today']


class CampaignSerializer(serializers.ModelSerializer):
    """Serializer principal para campanhas"""
    
    messages = CampaignMessageSerializer(many=True, required=False)
    instances = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=WhatsAppInstance.objects.all()
    )
    instances_detail = CampaignInstanceSerializer(source='instances', many=True, read_only=True)
    
    # Campos calculados
    success_rate = serializers.FloatField(read_only=True)
    read_rate = serializers.FloatField(read_only=True)
    progress_percentage = serializers.FloatField(read_only=True)
    
    # Modo de rotação com descrição
    rotation_mode_display = serializers.CharField(source='get_rotation_mode_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Campaign
        fields = [
            'id', 'name', 'description', 'rotation_mode', 'rotation_mode_display',
            'instances', 'instances_detail', 'contact_list', 'messages',
            'interval_min', 'interval_max', 'daily_limit_per_instance', 'pause_on_health_below',
            'scheduled_at', 'started_at', 'completed_at',
            'status', 'status_display', 'total_contacts', 'messages_sent',
            'messages_delivered', 'messages_read', 'messages_failed',
            'success_rate', 'read_rate', 'progress_percentage',
            'last_message_sent_at', 'next_message_scheduled_at',
            'next_contact_name', 'next_contact_phone', 'next_instance_name',
            'last_contact_name', 'last_contact_phone', 'last_instance_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'total_contacts', 'messages_sent', 'messages_delivered',
            'messages_read', 'messages_failed', 'started_at', 'completed_at',
            'created_at', 'updated_at'
        ]
    
    def to_representation(self, instance):
        """Atualiza informações do próximo contato antes de serializar"""
        # Atualizar informações do próximo contato para campanhas em execução
        if instance.status == 'running':
            instance.update_next_contact_info()
        
        return super().to_representation(instance)
    
    def create(self, validated_data):
        messages_data = validated_data.pop('messages', [])
        instances_data = validated_data.pop('instances', [])
        tag_id = self.context.get('tag_id')
        contact_ids = self.context.get('contact_ids', [])
        
        # Criar campanha
        campaign = Campaign.objects.create(**validated_data)
        
        # Adicionar instâncias
        campaign.instances.set(instances_data)
        
        # Criar mensagens
        for msg_data in messages_data:
            CampaignMessage.objects.create(campaign=campaign, **msg_data)
        
        # Adicionar contatos
        contacts_to_add = []
        
        # Priorizar contact_ids se fornecidos (permite seleção manual mesmo com tag)
        if contact_ids:
            # Usar contatos específicos (podem vir de uma tag ou avulsos)
            contacts_to_add = Contact.objects.filter(
                tenant=campaign.tenant,
                id__in=contact_ids,
                is_active=True,
                opted_out=False
            )
            if tag_id:
                print(f"📊 Tag {tag_id}: {contacts_to_add.count()} contatos selecionados manualmente")
            else:
                print(f"📊 Contatos avulsos: {contacts_to_add.count()} selecionados")
        elif tag_id:
            # Buscar TODOS os contatos por tag (fallback se contact_ids não fornecido)
            contacts_to_add = Contact.objects.filter(
                tenant=campaign.tenant,
                tags__id=tag_id,
                is_active=True,
                opted_out=False
            ).distinct()
            print(f"📊 Tag {tag_id}: {contacts_to_add.count()} contatos encontrados (todos da tag)")
        
        # Criar CampaignContact para cada contato
        campaign_contacts = []
        for contact in contacts_to_add:
            campaign_contacts.append(
                CampaignContact(
                    campaign=campaign,
                    contact=contact,
                    status='pending'
                )
            )
        
        CampaignContact.objects.bulk_create(campaign_contacts)
        
        # Atualizar contador
        campaign.total_contacts = len(campaign_contacts)
        campaign.save()
        
        print(f"✅ Campanha criada com {campaign.total_contacts} contatos")
        
        return campaign
    
    def update(self, instance, validated_data):
        messages_data = validated_data.pop('messages', None)
        instances_data = validated_data.pop('instances', None)
        
        # Atualizar campos da campanha
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Atualizar instâncias
        if instances_data is not None:
            instance.instances.set(instances_data)
        
        # Atualizar mensagens
        if messages_data is not None:
            # Deletar mensagens antigas
            instance.messages.all().delete()
            # Criar novas
            for msg_data in messages_data:
                CampaignMessage.objects.create(campaign=instance, **msg_data)
        
        return instance


class CampaignContactSerializer(serializers.ModelSerializer):
    """Serializer para contatos da campanha"""
    
    contact_name = serializers.CharField(source='contact.name', read_only=True)
    contact_phone = serializers.CharField(source='contact.phone', read_only=True)
    instance_name = serializers.CharField(source='instance_used.friendly_name', read_only=True, allow_null=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = CampaignContact
        fields = [
            'id', 'contact', 'contact_name', 'contact_phone',
            'instance_used', 'instance_name', 'message_used',
            'status', 'status_display', 'scheduled_at', 'sent_at',
            'delivered_at', 'read_at', 'failed_at', 'error_message',
            'whatsapp_message_id', 'retry_count'
        ]


class CampaignLogSerializer(serializers.ModelSerializer):
    """Serializer para logs da campanha"""
    
    log_type_display = serializers.CharField(source='get_log_type_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    instance_name = serializers.CharField(source='instance.friendly_name', read_only=True, allow_null=True)
    contact_name = serializers.CharField(source='contact.name', read_only=True, allow_null=True)
    
    class Meta:
        model = CampaignLog
        fields = [
            'id', 'log_type', 'log_type_display', 'severity', 'severity_display',
            'message', 'details', 'instance', 'instance_name',
            'contact', 'contact_name', 'duration_ms',
            'campaign_progress', 'instance_health_score', 'created_at'
        ]


class CampaignStatsSerializer(serializers.Serializer):
    """Serializer para estatísticas da campanha"""
    
    total_campaigns = serializers.IntegerField()
    active_campaigns = serializers.IntegerField()
    completed_campaigns = serializers.IntegerField()
    total_messages_sent = serializers.IntegerField()
    total_messages_delivered = serializers.IntegerField()
    avg_success_rate = serializers.FloatField()
    campaigns_by_status = serializers.DictField()


class CampaignNotificationSerializer(serializers.ModelSerializer):
    """Serializer para notificações de campanhas"""
    campaign_name = serializers.CharField(source='campaign.name', read_only=True)
    contact_name = serializers.CharField(source='contact.name', read_only=True)
    contact_phone = serializers.CharField(source='contact.phone', read_only=True)
    instance_name = serializers.CharField(source='instance.friendly_name', read_only=True)
    sent_by_name = serializers.CharField(source='sent_by.email', read_only=True)
    
    class Meta:
        model = CampaignNotification
        fields = [
            'id', 'tenant', 'campaign', 'contact', 'campaign_contact', 'instance',
            'notification_type', 'status', 'received_message', 'received_timestamp',
            'sent_reply', 'sent_timestamp', 'sent_by', 'whatsapp_message_id',
            'details', 'created_at', 'updated_at',
            # Campos calculados
            'campaign_name', 'contact_name', 'contact_phone', 'instance_name', 'sent_by_name'
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at', 'received_timestamp']
    
    def create(self, validated_data):
        """Criar notificação com tenant do usuário"""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['tenant'] = request.user.tenant
        return super().create(validated_data)


class NotificationMarkReadSerializer(serializers.Serializer):
    """Serializer para marcar notificação como lida"""
    notification_id = serializers.UUIDField()


class NotificationReplySerializer(serializers.Serializer):
    """Serializer para responder notificação"""
    notification_id = serializers.UUIDField()
    message = serializers.CharField(max_length=4000, help_text="Mensagem de resposta")
    
    def validate_message(self, value):
        """Validar mensagem não vazia"""
        if not value.strip():
            raise serializers.ValidationError("Mensagem não pode estar vazia")
        return value.strip()

