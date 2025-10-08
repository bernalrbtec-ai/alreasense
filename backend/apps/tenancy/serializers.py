from rest_framework import serializers
from .models import Tenant


class TenantSerializer(serializers.ModelSerializer):
    """Serializer for Tenant model."""
    
    plan_limits = serializers.ReadOnlyField()
    is_active = serializers.ReadOnlyField()
    
    class Meta:
        model = Tenant
        fields = [
            'id', 'name', 'plan', 'status', 'next_billing_date',
            'created_at', 'updated_at', 'plan_limits', 'is_active'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TenantMetricsSerializer(serializers.Serializer):
    """Serializer for tenant metrics."""
    
    total_messages = serializers.IntegerField()
    avg_sentiment = serializers.FloatField()
    avg_satisfaction = serializers.FloatField()
    positive_messages_pct = serializers.FloatField()
    messages_today = serializers.IntegerField()
    active_connections = serializers.IntegerField()
    avg_latency_ms = serializers.FloatField()
