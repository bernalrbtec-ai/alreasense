"""
Serializers para o app tenancy
"""

from rest_framework import serializers
from .models import Tenant
from apps.billing.serializers import PlanSerializer


class TenantSerializer(serializers.ModelSerializer):
    """Serializer para Tenant"""
    
    # Plano completo com produtos
    current_plan = PlanSerializer(read_only=True)
    
    # Campos legados (manter compatibilidade)
    plan_name = serializers.CharField(source='current_plan.name', read_only=True)
    plan_slug = serializers.CharField(source='current_plan.slug', read_only=True)
    plan_price = serializers.DecimalField(source='current_plan.price', max_digits=10, decimal_places=2, read_only=True)
    active_products = serializers.SerializerMethodField()
    monthly_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    admin_user = serializers.SerializerMethodField()
    
    class Meta:
        model = Tenant
        fields = [
            'id', 'name', 'status', 'ui_access', 'next_billing_date',
            'current_plan', 'plan_name', 'plan_slug', 'plan_price', 'active_products',
            'monthly_total', 'admin_user', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_active_products(self, obj):
        """Retorna lista de produtos ativos"""
        return [
            {
                'slug': tp.product.slug,
                'name': tp.product.name,
                'is_addon': tp.is_addon,
                'addon_price': float(tp.addon_price) if tp.addon_price else None,
            }
            for tp in obj.active_products
        ]
    
    def get_admin_user(self, obj):
        """Retorna dados do usuário admin do tenant (OTIMIZADO com prefetch_related)"""
        # ✅ OTIMIZAÇÃO: Usar prefetch_related ao invés de query separada
        # obj.users já está prefetchado no ViewSet
        admin = next((u for u in obj.users.all() if u.role == 'admin'), None)
        if admin:
            return {
                'id': admin.id,
                'first_name': admin.first_name,
                'last_name': admin.last_name,
                'email': admin.email,
                'phone': admin.phone,
            }
        return None