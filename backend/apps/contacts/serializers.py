"""
Serializers para o módulo de contatos
"""

from rest_framework import serializers
from .models import Contact, Tag, ContactList, ContactImport
from .utils import normalize_phone, get_state_from_ddd, extract_ddd_from_phone, get_state_from_phone


class EmptyStringToNullDateField(serializers.DateField):
    """Campo de data que converte string vazia em None"""
    def to_internal_value(self, value):
        if value == '' or value == []:
            return None
        return super().to_internal_value(value)


class TagSerializer(serializers.ModelSerializer):
    contact_count = serializers.ReadOnlyField()
    
    class Meta:
        model = Tag
        fields = ['id', 'name', 'color', 'description', 'contact_count', 'created_at']
        read_only_fields = ['id', 'created_at']


class ContactListSerializer(serializers.ModelSerializer):
    contact_count = serializers.ReadOnlyField()
    opted_out_count = serializers.ReadOnlyField()
    
    class Meta:
        model = ContactList
        fields = [
            'id', 'name', 'description', 'is_active',
            'contact_count', 'opted_out_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ContactSerializer(serializers.ModelSerializer):
    # Computed fields
    age = serializers.ReadOnlyField()
    days_since_last_purchase = serializers.ReadOnlyField()
    days_until_birthday = serializers.ReadOnlyField()
    lifecycle_stage = serializers.ReadOnlyField()
    rfm_segment = serializers.ReadOnlyField()
    engagement_score = serializers.ReadOnlyField()
    
    # Override birth_date to allow empty string
    birth_date = EmptyStringToNullDateField(required=False, allow_null=True)
    
    # Relations
    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Tag.objects.all(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = Contact
        fields = [
            # IDs
            'id', 'tenant',
            
            # Básico
            'phone', 'name', 'email',
            
            # Demográficos
            'birth_date', 'gender', 'city', 'state', 'country', 'zipcode',
            
            # Comerciais
            'last_purchase_date', 'last_purchase_value', 'total_purchases',
            'average_ticket', 'lifetime_value', 'last_visit_date',
            
            # Engajamento
            'last_interaction_date', 'total_messages_received', 'total_messages_sent',
            'total_campaigns_participated', 'total_campaigns_responded',
            
            # Observações
            'notes', 'referred_by', 'custom_fields',
            
            # Segmentação
            'tags', 'tag_ids',
            
            # Controle
            'is_active', 'opted_out', 'opted_out_at', 'source',
            
            # Computed
            'age', 'days_since_last_purchase', 'days_until_birthday',
            'lifecycle_stage', 'rfm_segment', 'engagement_score',
            
            # Meta
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant', 'created_at', 'updated_at',
            'total_messages_received', 'total_messages_sent',
            'total_campaigns_participated', 'total_campaigns_responded',
            'opted_out_at'
        ]
    
    def validate_phone(self, value):
        """Normaliza e valida telefone"""
        return normalize_phone(value)
    
    def validate_birth_date(self, value):
        """Valida birth_date - aceita None ou string vazia"""
        if value == '' or value == []:
            return None
        return value
    
    def validate(self, data):
        """Validação customizada"""
        print(f"🔍 VALIDATE DATA: {data}")
        
        # Verificar duplicata de telefone
        phone = data.get('phone')
        if phone:
            tenant = self.context['request'].user.tenant
            existing = Contact.objects.filter(
                tenant=tenant,
                phone=phone
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing.exists():
                raise serializers.ValidationError({
                    'phone': 'Telefone já cadastrado neste tenant'
                })
        
        return data
    
    def create(self, validated_data):
        # Extrair tags
        tag_ids = validated_data.pop('tag_ids', [])
        
        # 🆕 Inferir estado pelo DDD se não fornecido
        if not validated_data.get('state'):
            phone = validated_data.get('phone')
            if phone:
                state = get_state_from_phone(phone)
                if state:
                    validated_data['state'] = state
                    ddd = extract_ddd_from_phone(phone)
                    print(f"  ℹ️  Estado '{state}' inferido pelo DDD {ddd} (cadastro individual via API)")
        
        # Criar contato
        contact = Contact.objects.create(**validated_data)
        
        # Associar tags
        if tag_ids:
            contact.tags.set(tag_ids)
        
        return contact
    
    def update(self, instance, validated_data):
        # Extrair tags
        tag_ids = validated_data.pop('tag_ids', None)
        
        # 🆕 Inferir estado pelo DDD se não fornecido E contato não tem estado
        if 'state' not in validated_data and not instance.state:
            phone = validated_data.get('phone', instance.phone)
            if phone:
                state = get_state_from_phone(phone)
                if state:
                    validated_data['state'] = state
                    ddd = extract_ddd_from_phone(phone)
                    print(f"  ℹ️  Estado '{state}' inferido pelo DDD {ddd} (atualização via API)")
        
        # Atualizar campos
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Atualizar tags
        if tag_ids is not None:
            instance.tags.set(tag_ids)
        
        return instance


class ContactImportSerializer(serializers.ModelSerializer):
    success_rate = serializers.ReadOnlyField()
    
    class Meta:
        model = ContactImport
        fields = [
            'id', 'file_name', 'status',
            'total_rows', 'processed_rows',
            'created_count', 'updated_count', 'skipped_count', 'error_count',
            'success_rate', 'errors',
            'update_existing', 'auto_tag',
            'created_at', 'completed_at'
        ]
        read_only_fields = [
            'id', 'status', 'total_rows', 'processed_rows',
            'created_count', 'updated_count', 'skipped_count', 'error_count',
            'errors', 'created_at', 'completed_at'
        ]
