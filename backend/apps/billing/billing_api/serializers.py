"""
Serializers para Billing API
"""
from rest_framework import serializers
from django.utils import timezone
from typing import Dict, Any, List

from apps.billing.billing_api import (
    BillingConfig, BillingAPIKey, BillingTemplate, BillingTemplateVariation,
    BillingCampaign, BillingQueue, BillingContact
)
from apps.tenancy.models import Tenant


class BillingConfigSerializer(serializers.ModelSerializer):
    """Serializer para BillingConfig"""
    
    class Meta:
        model = BillingConfig
        fields = [
            'id', 'tenant', 'api_enabled', 'messages_per_minute',
            'max_messages_per_day', 'max_batch_size', 'max_retry_attempts',
            'retry_delay_minutes', 'close_conversation_after_send',
            'notify_on_instance_down', 'notify_on_resume', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class BillingAPIKeySerializer(serializers.ModelSerializer):
    """Serializer para BillingAPIKey"""
    
    key_masked = serializers.SerializerMethodField()
    
    class Meta:
        model = BillingAPIKey
        fields = [
            'id', 'tenant', 'name', 'key_masked', 'key_set',
            'is_active', 'expires_at', 'allowed_ips', 'allowed_template_types',
            'total_requests', 'last_used_at', 'last_used_ip', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'key_masked', 'key_set', 'total_requests', 
                           'last_used_at', 'last_used_ip', 'created_at', 'updated_at']
    
    def get_key_masked(self, obj):
        """Retorna API key mascarada"""
        if obj.key:
            return '****' + obj.key[-4:] if len(obj.key) > 4 else '****'
        return None
    
    def get_key_set(self, obj):
        """Indica se a key está configurada"""
        return bool(obj.key)


class BillingTemplateVariationSerializer(serializers.ModelSerializer):
    """Serializer para variação de template"""
    
    class Meta:
        model = BillingTemplateVariation
        fields = [
            'id', 'template', 'name', 'template_text', 'order',
            'is_active', 'times_used', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'times_used', 'created_at', 'updated_at']


class BillingTemplateSerializer(serializers.ModelSerializer):
    """Serializer para BillingTemplate"""
    
    variations = BillingTemplateVariationSerializer(many=True, read_only=True)
    
    class Meta:
        model = BillingTemplate
        fields = [
            'id', 'tenant', 'name', 'template_type', 'description',
            'is_active', 'total_uses', 'variations',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'total_uses', 'created_at', 'updated_at']


class BillingContactSerializer(serializers.ModelSerializer):
    """Serializer para BillingContact"""
    
    contact_name = serializers.CharField(source='campaign_contact.contact.name', read_only=True)
    contact_phone = serializers.CharField(source='campaign_contact.contact.phone', read_only=True)
    
    class Meta:
        model = BillingContact
        fields = [
            'id', 'billing_campaign', 'campaign_contact', 'template_variation',
            'status', 'rendered_message', 'billing_data', 'contact_name', 'contact_phone',
            'scheduled_at', 'sent_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class BillingQueueSerializer(serializers.ModelSerializer):
    """Serializer para BillingQueue"""
    
    campaign_name = serializers.CharField(source='billing_campaign.campaign.name', read_only=True)
    progress_percentage = serializers.ReadOnlyField()
    
    class Meta:
        model = BillingQueue
        fields = [
            'id', 'billing_campaign', 'campaign_name', 'status',
            'total_contacts', 'processed_contacts', 'sent_contacts', 'failed_contacts',
            'progress_percentage', 'processing_by', 'last_heartbeat',
            'scheduled_for', 'started_at', 'completed_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'progress_percentage', 'created_at', 'updated_at']


class BillingCampaignSerializer(serializers.ModelSerializer):
    """Serializer para BillingCampaign"""
    
    campaign_name = serializers.CharField(source='campaign.name', read_only=True)
    template_name = serializers.CharField(source='template.name', read_only=True)
    queue = BillingQueueSerializer(read_only=True)
    
    class Meta:
        model = BillingCampaign
        fields = [
            'id', 'tenant', 'campaign', 'campaign_name', 'template', 'template_name',
            'external_id', 'billing_type', 'callback_url', 'callback_events',
            'metadata', 'queue', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ========== REQUEST/RESPONSE SERIALIZERS PARA API ==========

class ContactDataSerializer(serializers.Serializer):
    """Serializer para dados de contato na requisição"""
    nome = serializers.CharField(required=True, help_text="Nome do cliente")
    telefone = serializers.CharField(required=True, help_text="Telefone (formato E.164 ou nacional)")
    valor = serializers.CharField(required=False, help_text="Valor da cobrança (ex: 'R$ 150,00')")
    data_vencimento = serializers.CharField(required=False, help_text="Data de vencimento (YYYY-MM-DD)")
    valor_total = serializers.CharField(required=False, help_text="Valor total (para overdue)")
    codigo_pix = serializers.CharField(required=False, help_text="Código PIX")
    link_pagamento = serializers.URLField(required=False, help_text="Link de pagamento")
    titulo = serializers.CharField(required=False, help_text="Título (para notifications)")
    mensagem = serializers.CharField(required=False, help_text="Mensagem (para notifications)")
    
    # Campos opcionais extras
    metadata = serializers.DictField(required=False, help_text="Dados extras em formato JSON")


class SendBillingRequestSerializer(serializers.Serializer):
    """Serializer para requisição de envio de billing"""
    template_type = serializers.ChoiceField(
        choices=['overdue', 'upcoming', 'notification'],
        required=True,
        help_text="Tipo de template: 'overdue', 'upcoming' ou 'notification'"
    )
    contacts = ContactDataSerializer(many=True, required=True, help_text="Lista de contatos")
    external_id = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="ID externo da campanha (opcional, para rastreamento)"
    )
    instance_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="ID da instância WhatsApp a usar (opcional)"
    )
    
    def validate_contacts(self, value):
        """Valida lista de contatos"""
        if not value or len(value) == 0:
            raise serializers.ValidationError("A lista de contatos não pode estar vazia")
        
        # Valida limite máximo (será verificado no service)
        if len(value) > 1000:
            raise serializers.ValidationError("Máximo de 1000 contatos por requisição")
        
        return value
    
    def validate_template_type(self, value):
        """Valida campos obrigatórios baseado no tipo"""
        contacts = self.initial_data.get('contacts', [])
        
        if value == 'overdue':
            required_fields = ['nome', 'telefone', 'valor', 'data_vencimento']
        elif value == 'upcoming':
            required_fields = ['nome', 'telefone', 'valor', 'data_vencimento']
        elif value == 'notification':
            required_fields = ['nome', 'telefone', 'titulo', 'mensagem']
        else:
            return value
        
        for i, contact in enumerate(contacts):
            missing = [field for field in required_fields if not contact.get(field)]
            if missing:
                raise serializers.ValidationError(
                    f"Contato {i+1} está faltando campos obrigatórios para '{value}': {', '.join(missing)}"
                )
        
        return value


class SendBillingResponseSerializer(serializers.Serializer):
    """Serializer para resposta de envio de billing"""
    success = serializers.BooleanField(help_text="Se a requisição foi processada com sucesso")
    message = serializers.CharField(help_text="Mensagem de status")
    campaign_id = serializers.UUIDField(required=False, help_text="ID da campanha criada")
    queue_id = serializers.UUIDField(required=False, help_text="ID da queue criada")
    total_contacts = serializers.IntegerField(required=False, help_text="Total de contatos processados")
    errors = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        help_text="Lista de erros (se houver)"
    )


class BillingCampaignStatusSerializer(serializers.Serializer):
    """Serializer para status de campanha"""
    campaign_id = serializers.UUIDField(help_text="ID da campanha")
    external_id = serializers.CharField(required=False, help_text="ID externo")
    status = serializers.CharField(help_text="Status da campanha")
    total_contacts = serializers.IntegerField(help_text="Total de contatos")
    sent_contacts = serializers.IntegerField(help_text="Contatos enviados")
    failed_contacts = serializers.IntegerField(help_text="Contatos com falha")
    progress_percentage = serializers.IntegerField(help_text="Porcentagem de progresso")
    started_at = serializers.DateTimeField(required=False, help_text="Quando começou")
    completed_at = serializers.DateTimeField(required=False, help_text="Quando completou")


class BillingContactStatusSerializer(serializers.Serializer):
    """Serializer para status de contato"""
    contact_id = serializers.UUIDField(help_text="ID do contato")
    phone = serializers.CharField(help_text="Telefone")
    name = serializers.CharField(help_text="Nome")
    status = serializers.CharField(help_text="Status do envio")
    sent_at = serializers.DateTimeField(required=False, help_text="Quando foi enviado")
    error_message = serializers.CharField(required=False, allow_blank=True, help_text="Mensagem de erro (se houver)")

