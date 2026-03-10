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
    """Serializer para produtos de um plano (inclui limite secundário ex: usuários para ALREA Chat)"""
    product = ProductSerializer(read_only=True)
    product_id = serializers.UUIDField(write_only=True, required=False)
    
    class Meta:
        model = PlanProduct
        fields = [
            'id', 'product', 'product_id', 'is_included',
            'limit_value', 'limit_unit',
            'limit_value_secondary', 'limit_unit_secondary',
        ]


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


class PlanCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer para criar/editar planos com produtos. Flow é add-on do Chat: só pode ser incluído se Chat estiver no plano."""
    plan_products = PlanProductSerializer(many=True, required=False)

    class Meta:
        model = Plan
        fields = [
            'id', 'slug', 'name', 'description', 'price',
            'is_active', 'sort_order', 'plan_products',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def _validate_flow_requires_chat(self, plan_products_data):
        """Flow só pode ser adquirido se o Chat já estiver no plano."""
        if not plan_products_data:
            return
        product_ids = []
        for p in plan_products_data:
            pid = p.get('product_id')
            if not pid and p.get('product'):
                prod = p['product']
                pid = getattr(prod, 'id', None) or (prod.get('id') if isinstance(prod, dict) else None)
            if pid:
                product_ids.append(pid)
        if not product_ids:
            return
        slugs = set(
            Product.objects.filter(id__in=product_ids).values_list('slug', flat=True)
        )
        if 'flow' in slugs and 'chat' not in slugs:
            raise serializers.ValidationError({
                'plan_products': 'O produto ALREA Flow é um add-on do ALREA Chat. Inclua o produto ALREA Chat no plano antes de adicionar o Flow.'
            })

    def create(self, validated_data):
        plan_products_data = validated_data.pop('plan_products', [])
        self._validate_flow_requires_chat(plan_products_data)
        plan = Plan.objects.create(**validated_data)

        for product_data in plan_products_data:
            data = dict(product_data)
            if 'product_id' not in data and data.get('product'):
                data['product_id'] = getattr(data['product'], 'id', None) or data['product'].get('id')
            data.pop('product', None)
            data.pop('id', None)  # não definir PK na criação
            product_id = data.pop('product_id', None)
            if product_id:
                PlanProduct.objects.create(plan=plan, product_id=product_id, **data)
        return plan
    
    def update(self, instance, validated_data):
        plan_products_data = validated_data.pop('plan_products', [])
        if plan_products_data:
            self._validate_flow_requires_chat(plan_products_data)

        # Atualizar dados do plano
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Atualizar produtos do plano (usa cópia dos dados para não mutar validated_data)
        if plan_products_data:
            instance.plan_products.all().delete()
            for product_data in plan_products_data:
                data = dict(product_data)
                if 'product_id' not in data and data.get('product'):
                    prod = data['product']
                    data['product_id'] = getattr(prod, 'id', None) or (prod.get('id') if isinstance(prod, dict) else None)
                data.pop('product', None)
                data.pop('id', None)  # não reutilizar PK ao recriar
                product_id = data.pop('product_id', None)
                if product_id:
                    PlanProduct.objects.create(plan=instance, product_id=product_id, **data)
        return instance


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
