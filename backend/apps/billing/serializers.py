from rest_framework import serializers
from .models import Plan, PaymentAccount, BillingEvent


class PlanSerializer(serializers.ModelSerializer):
    """Serializer for Plan model."""
    
    # Ensure price is returned as float, not string
    price = serializers.FloatField()
    
    class Meta:
        model = Plan
        fields = [
            'id', 'name', 'description', 'price', 'billing_cycle_days', 'is_free',
            'max_connections', 'max_messages_per_month', 'features', 'is_active',
            'stripe_price_id', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PaymentAccountSerializer(serializers.ModelSerializer):
    """Serializer for PaymentAccount model."""
    
    class Meta:
        model = PaymentAccount
        fields = [
            'id', 'stripe_customer_id', 'status', 
            'current_period_start', 'current_period_end',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class BillingEventSerializer(serializers.ModelSerializer):
    """Serializer for BillingEvent model."""
    
    class Meta:
        model = BillingEvent
        fields = [
            'id', 'event_type', 'stripe_event_id', 
            'processed', 'data', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class BillingInfoSerializer(serializers.Serializer):
    """Serializer for billing information."""
    
    current_plan = serializers.CharField()
    plan_limits = serializers.DictField()
    next_billing_date = serializers.DateField()
    status = serializers.CharField()
    has_payment_method = serializers.BooleanField()
    current_period_end = serializers.DateTimeField(allow_null=True)
