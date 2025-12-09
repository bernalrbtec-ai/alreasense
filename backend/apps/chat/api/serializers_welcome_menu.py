"""
Serializers para Menu de Boas-Vindas
"""
from rest_framework import serializers
from apps.chat.models_welcome_menu import WelcomeMenuConfig
from apps.authn.models import Department


class DepartmentOptionSerializer(serializers.ModelSerializer):
    """Serializer simplificado para departamentos no menu"""
    
    class Meta:
        model = Department
        fields = ['id', 'name', 'color']
        read_only_fields = ['id', 'name', 'color']


class WelcomeMenuConfigSerializer(serializers.ModelSerializer):
    """Serializer para configuração do menu de boas-vindas"""
    
    departments = DepartmentOptionSerializer(many=True, read_only=True)
    department_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Department.objects.all(),
        write_only=True,
        required=False,
        source='departments'
    )
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    
    class Meta:
        model = WelcomeMenuConfig
        fields = [
            'id',
            'tenant',
            'tenant_name',
            'enabled',
            'welcome_message',
            'departments',
            'department_ids',
            'show_close_option',
            'close_option_text',
            'send_to_new_conversations',
            'send_to_closed_conversations',
            'ai_enabled',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at', 'ai_enabled']
    
    def validate(self, data):
        """Validação customizada"""
        # Se enabled=True, deve ter pelo menos 1 departamento
        if data.get('enabled', False):
            departments = data.get('departments', [])
            if not departments or len(departments) == 0:
                raise serializers.ValidationError({
                    'departments': 'É necessário selecionar pelo menos um departamento quando o menu está habilitado.'
                })
        
        return data
    
    def create(self, validated_data):
        """Criar configuração"""
        tenant = self.context['request'].user.tenant
        departments = validated_data.pop('departments', [])
        
        config = WelcomeMenuConfig.objects.create(
            tenant=tenant,
            **validated_data
        )
        
        if departments:
            config.departments.set(departments)
        
        return config
    
    def update(self, instance, validated_data):
        """Atualizar configuração"""
        departments = validated_data.pop('departments', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        
        if departments is not None:
            instance.departments.set(departments)
        
        return instance

