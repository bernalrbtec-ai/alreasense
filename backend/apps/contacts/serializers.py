"""
Serializers para o módulo de contatos
"""

from rest_framework import serializers
from .models import Contact, Tag, ContactList, ContactImport, ContactHistory
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
        import logging
        logger = logging.getLogger(__name__)
        
        logger.debug(f"🔍 [SERIALIZER] VALIDATE DATA: {data}")
        logger.debug(f"🔍 [SERIALIZER] Instance: {self.instance}")
        logger.debug(f"🔍 [SERIALIZER] Instance PK: {self.instance.pk if self.instance else None}")
        
        # Verificar duplicata de telefone
        # ✅ CORREÇÃO: Verificar por tenant (correto)
        # Telefones são únicos por tenant, mas podem se repetir entre tenants diferentes
        # Usuários do mesmo tenant compartilham a mesma lista de contatos
        phone = data.get('phone')
        if phone:
            user = self.context['request'].user
            tenant = user.tenant
            instance_pk = self.instance.pk if self.instance else None
            
            logger.debug(f"🔍 [SERIALIZER] Verificando duplicata. Phone: {phone}, Tenant: {tenant}, Instance PK: {instance_pk}")
            
            # ✅ NOVA VALIDAÇÃO: Verificar se telefone pertence a uma instância WhatsApp do tenant
            from apps.notifications.models import WhatsAppInstance
            
            # Normalizar telefone para comparação (remover + e espaços)
            phone_normalized = phone.replace('+', '').replace(' ', '').strip()
            
            # Verificar se existe instância WhatsApp com esse telefone no mesmo tenant
            instance_with_phone = WhatsAppInstance.objects.filter(
                tenant=tenant,
                phone_number__isnull=False
            ).exclude(phone_number='')
            
            for instance in instance_with_phone:
                if instance.phone_number:
                    instance_phone_normalized = instance.phone_number.replace('+', '').replace(' ', '').strip()
                    if instance_phone_normalized == phone_normalized:
                        logger.warning(f"⚠️ [SERIALIZER] Telefone pertence a instância WhatsApp: {instance.friendly_name}")
                        raise serializers.ValidationError({
                            'phone': f'Este telefone pertence à instância WhatsApp "{instance.friendly_name}". Não é possível criar contato com telefone de instância.'
                        })
            
            # Verificar duplicatas no mesmo tenant, excluindo o próprio contato se estiver atualizando
            existing = Contact.objects.filter(
                tenant=tenant,
                phone=phone
            )
            
            # ✅ CORREÇÃO CRÍTICA: Se está atualizando, excluir o próprio contato da verificação
            if instance_pk:
                existing = existing.exclude(pk=instance_pk)
            
            logger.debug(f"🔍 [SERIALIZER] Contatos existentes com mesmo telefone no tenant: {existing.count()}")
            if existing.exists():
                logger.warning(f"⚠️ [SERIALIZER] Telefone duplicado encontrado no tenant {tenant}: {phone}")
                raise serializers.ValidationError({
                    'phone': 'Telefone já cadastrado neste tenant'
                })
        
        logger.debug(f"✅ [SERIALIZER] Validação passou")
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
        import logging
        logger = logging.getLogger(__name__)
        
        logger.debug(f"🔄 [SERIALIZER UPDATE] Iniciando update. Instance: {instance.id}, Data: {validated_data}")
        
        # Extrair tags
        tag_ids = validated_data.pop('tag_ids', None)
        logger.debug(f"🔄 [SERIALIZER UPDATE] Tag IDs: {tag_ids}")
        
        # ✅ MELHORIA: Sempre verificar UF quando telefone for alterado
        phone_changed = 'phone' in validated_data and validated_data.get('phone') != instance.phone
        if phone_changed:
            phone = validated_data.get('phone')
            if phone:
                state = get_state_from_phone(phone)
                if state:
                    validated_data['state'] = state
                    ddd = extract_ddd_from_phone(phone)
                    logger.info(f"  ℹ️  Estado '{state}' recalculado pelo DDD {ddd} (telefone alterado)")
        # Se telefone não mudou mas estado não está definido, tentar inferir
        elif 'state' not in validated_data and not instance.state:
            phone = validated_data.get('phone', instance.phone)
            if phone:
                state = get_state_from_phone(phone)
                if state:
                    validated_data['state'] = state
                    ddd = extract_ddd_from_phone(phone)
                    logger.info(f"  ℹ️  Estado '{state}' inferido pelo DDD {ddd} (atualização via API)")
        
        # Atualizar campos
        logger.debug(f"🔄 [SERIALIZER UPDATE] Atualizando campos: {list(validated_data.keys())}")
        for attr, value in validated_data.items():
            logger.debug(f"🔄 [SERIALIZER UPDATE] Set {attr} = {value} (type: {type(value)})")
            try:
                setattr(instance, attr, value)
            except Exception as e:
                logger.error(f"❌ [SERIALIZER UPDATE] Erro ao setar {attr} = {value}: {e}")
                raise
        
        logger.debug(f"🔄 [SERIALIZER UPDATE] Salvando instância...")
        try:
            instance.save()
            logger.debug(f"✅ [SERIALIZER UPDATE] Instância salva com sucesso")
        except Exception as e:
            logger.error(f"❌ [SERIALIZER UPDATE] Erro ao salvar instância: {e}", exc_info=True)
            raise
        
        # Atualizar tags
        if tag_ids is not None:
            logger.debug(f"🔄 [SERIALIZER UPDATE] Atualizando tags: {tag_ids}")
            instance.tags.set(tag_ids)
        
        logger.info(f"✅ [SERIALIZER UPDATE] Update concluído com sucesso")
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


class ContactHistorySerializer(serializers.ModelSerializer):
    """Serializer para histórico de contatos"""
    
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)
    created_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = ContactHistory
        fields = [
            'id', 'event_type', 'event_type_display', 'title', 'description',
            'metadata', 'created_by', 'created_by_name', 'created_at',
            'is_editable', 'related_conversation', 'related_campaign',
            'related_message'
        ]
        read_only_fields = [
            'id', 'event_type', 'created_by', 'created_at',
            'related_conversation', 'related_campaign', 'related_message'
        ]
    
    def get_created_by_name(self, obj):
        """Retorna nome do usuário que criou o evento"""
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return None


class ContactHistoryCreateSerializer(serializers.ModelSerializer):
    """Serializer para criar anotações manuais no histórico"""
    
    class Meta:
        model = ContactHistory
        fields = ['title', 'description', 'metadata']
    
    def create(self, validated_data):
        """Cria anotação manual editável"""
        contact = self.context.get('contact')
        tenant = self.context.get('tenant')
        user = self.context.get('user')
        
        if not contact or not tenant:
            raise serializers.ValidationError('Contexto inválido: contact e tenant são obrigatórios')
        
        return ContactHistory.create_note(
            contact=contact,
            tenant=tenant,
            title=validated_data['title'],
            description=validated_data.get('description', ''),
            created_by=user,
            metadata=validated_data.get('metadata', {})
        )
