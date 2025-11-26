"""
Serializers para horários de atendimento.
"""
from rest_framework import serializers
from apps.chat.models_business_hours import (
    BusinessHours,
    AfterHoursMessage,
    AfterHoursTaskConfig
)


class BusinessHoursSerializer(serializers.ModelSerializer):
    """Serializer para horários de atendimento."""
    
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True, allow_null=True)
    
    class Meta:
        model = BusinessHours
        fields = [
            'id',
            'tenant',
            'tenant_name',
            'department',
            'department_name',
            'timezone',
            'monday_enabled', 'monday_start', 'monday_end',
            'tuesday_enabled', 'tuesday_start', 'tuesday_end',
            'wednesday_enabled', 'wednesday_start', 'wednesday_end',
            'thursday_enabled', 'thursday_start', 'thursday_end',
            'friday_enabled', 'friday_start', 'friday_end',
            'saturday_enabled', 'saturday_start', 'saturday_end',
            'sunday_enabled', 'sunday_start', 'sunday_end',
            'holidays',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class AfterHoursMessageSerializer(serializers.ModelSerializer):
    """Serializer para mensagens fora de horário."""
    
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True, allow_null=True)
    
    class Meta:
        model = AfterHoursMessage
        fields = [
            'id',
            'tenant',
            'tenant_name',
            'department',
            'department_name',
            'message_template',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class AfterHoursTaskConfigSerializer(serializers.ModelSerializer):
    """Serializer para configuração de tarefas fora de horário."""
    
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True, allow_null=True)
    auto_assign_to_agent_name = serializers.CharField(
        source='auto_assign_to_agent.email',
        read_only=True,
        allow_null=True
    )
    
    class Meta:
        model = AfterHoursTaskConfig
        fields = [
            'id',
            'tenant',
            'tenant_name',
            'department',
            'department_name',
            'create_task_enabled',
            'task_title_template',
            'task_description_template',
            'task_priority',
            'task_due_date_offset_hours',
            'task_type',
            'auto_assign_to_department',
            'auto_assign_to_agent',
            'auto_assign_to_agent_name',
            'include_message_preview',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

