"""
Serializers para o sistema de billing
"""

from rest_framework import serializers
from .models import Product, Plan, PlanProduct, TenantProduct, BillingHistory


class ProductSerializer(serializers.ModelSerializer):
    """Serializer para produtos"""
    
    class Meta:
        model = Product
        fields = [
            'id', 'slug', 'name', 'description', 'is_active',
            'requires_ui_access', 'addon_price', 'icon', 'color',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PlanProductSerializer(serializers.ModelSerializer):
    """Serializer para produtos de um plano"""
    product = ProductSerializer(read_only=True)
    
    class Meta:
        model = PlanProduct
        fields = ['id', 'product', 'is_included', 'limit_value', 'limit_unit']


class PlanSerializer(serializers.ModelSerializer):
    """Serializer para planos"""
    products = PlanProductSerializer(source='plan_products', many=True, read_only=True)
    product_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Plan
        fields = [
            'id', 'slug', 'name', 'description', 'price', 
            'is_active', 'sort_order', 'products', 'product_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_product_count(self, obj):
        return obj.plan_products.count()


class TenantProductSerializer(serializers.ModelSerializer):
    """Serializer para produtos ativos do tenant"""
    product = ProductSerializer(read_only=True)
    product_id = serializers.UUIDField(write_only=True)
    
    class Meta:
        model = TenantProduct
        fields = [
            'id', 'product', 'product_id', 'is_addon', 'addon_price',
            'api_key', 'is_active', 'activated_at', 'deactivated_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'activated_at', 'deactivated_at', 'created_at', 'updated_at']


class BillingHistorySerializer(serializers.ModelSerializer):
    """Serializer para histórico de billing"""
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    
    class Meta:
        model = BillingHistory
        fields = [
            'id', 'action', 'action_display', 'amount', 'description',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class TenantBillingInfoSerializer(serializers.Serializer):
    """Informações de billing do tenant"""
    plan = PlanSerializer(source='current_plan', read_only=True)
    active_products = TenantProductSerializer(many=True, read_only=True)
    monthly_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    next_billing_date = serializers.DateField(read_only=True)
    ui_access = serializers.BooleanField(read_only=True)
