"""
Views para o sistema de billing
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q

from .models import Product, Plan, TenantProduct, BillingHistory
from .serializers import (
    ProductSerializer,
    PlanSerializer,
    TenantProductSerializer,
    BillingHistorySerializer,
    TenantBillingInfoSerializer
)
from apps.common.permissions import IsTenantMember, IsAdminUser


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet para produtos (somente leitura)"""
    
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    queryset = Product.objects.filter(is_active=True)
    
    @action(detail=False, methods=['get'])
    def available(self, request):
        """Lista produtos disponíveis para o tenant"""
        tenant = request.user.tenant
        
        # Produtos já ativos
        active_product_ids = tenant.active_products.values_list('product_id', flat=True)
        
        # Produtos disponíveis como add-on
        available_products = Product.objects.filter(
            is_active=True,
            is_addon_available=True
        ).exclude(id__in=active_product_ids)
        
        serializer = self.get_serializer(available_products, many=True)
        return Response(serializer.data)


class PlanViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet para planos (somente leitura)"""
    
    serializer_class = PlanSerializer
    permission_classes = [IsAuthenticated]
    queryset = Plan.objects.filter(is_active=True).order_by('sort_order')
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsTenantMember, IsAdminUser])
    def select(self, request, pk=None):
        """Seleciona um plano para o tenant"""
        plan = self.get_object()
        tenant = request.user.tenant
        
        # Validar se o tenant pode mudar de plano
        if not tenant.is_active:
            return Response(
                {'error': 'Tenant não está ativo'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        old_plan = tenant.current_plan
        
        # Atualizar plano
        tenant.current_plan = plan
        tenant.save()
        
        # Registrar no histórico
        BillingHistory.objects.create(
            tenant=tenant,
            action='plan_change',
            amount=plan.price,
            description=f'Mudança de plano: {old_plan.name if old_plan else "Nenhum"} → {plan.name}'
        )
        
        # Sincronizar produtos do plano
        self._sync_plan_products(tenant, plan)
        
        return Response({
            'success': True,
            'message': f'Plano alterado para {plan.name}'
        })
    
    def _sync_plan_products(self, tenant, plan):
        """Sincroniza produtos do plano com o tenant"""
        # Desativar produtos que não estão mais no plano
        tenant.tenant_products.exclude(
            product__in=plan.plan_products.values_list('product', flat=True)
        ).filter(is_addon=False).update(is_active=False)
        
        # Ativar produtos do plano
        for plan_product in plan.plan_products.all():
            TenantProduct.objects.update_or_create(
                tenant=tenant,
                product=plan_product.product,
                defaults={
                    'is_addon': False,
                    'is_active': True
                }
            )


class TenantProductViewSet(viewsets.ModelViewSet):
    """ViewSet para produtos do tenant"""
    
    serializer_class = TenantProductSerializer
    permission_classes = [IsAuthenticated, IsTenantMember]
    
    def get_queryset(self):
        return TenantProduct.objects.filter(
            tenant=self.request.user.tenant
        ).select_related('product')
    
    def perform_create(self, serializer):
        """Adiciona um produto (add-on) ao tenant"""
        tenant = self.request.user.tenant
        product = serializer.validated_data['product']
        
        # Validar se o produto pode ser add-on
        if not product.is_addon_available:
            raise serializers.ValidationError('Este produto não está disponível como add-on')
        
        # Criar tenant_product
        tenant_product = serializer.save(
            tenant=tenant,
            is_addon=True,
            addon_price=product.addon_price
        )
        
        # Registrar no histórico
        BillingHistory.objects.create(
            tenant=tenant,
            action='addon_add',
            amount=product.addon_price or 0,
            description=f'Add-on adicionado: {product.name}'
        )
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Desativa um produto/add-on"""
        tenant_product = self.get_object()
        
        if not tenant_product.is_addon:
            return Response(
                {'error': 'Não é possível desativar produtos incluídos no plano'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        tenant_product.is_active = False
        tenant_product.save()
        
        # Registrar no histórico
        BillingHistory.objects.create(
            tenant=tenant_product.tenant,
            action='addon_remove',
            amount=0,
            description=f'Add-on removido: {tenant_product.product.name}'
        )
        
        return Response({'success': True, 'message': 'Produto desativado'})


class BillingHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet para histórico de billing"""
    
    serializer_class = BillingHistorySerializer
    permission_classes = [IsAuthenticated, IsTenantMember]
    
    def get_queryset(self):
        return BillingHistory.objects.filter(
            tenant=self.request.user.tenant
        ).order_by('-created_at')


class TenantBillingViewSet(viewsets.ViewSet):
    """ViewSet para informações de billing do tenant"""
    
    permission_classes = [IsAuthenticated, IsTenantMember]
    
    def list(self, request):
        """Retorna informações de billing do tenant"""
        tenant = request.user.tenant
        serializer = TenantBillingInfoSerializer(tenant)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Resumo de billing"""
        tenant = request.user.tenant
        
        # Contar produtos ativos
        active_products_count = tenant.active_products.count()
        
        # Calcular total mensal
        monthly_total = tenant.monthly_total
        
        # Histórico recente
        recent_history = BillingHistory.objects.filter(
            tenant=tenant
        ).order_by('-created_at')[:5]
        
        return Response({
            'plan': {
                'name': tenant.current_plan.name if tenant.current_plan else 'Nenhum',
                'price': tenant.current_plan.price if tenant.current_plan else 0
            },
            'active_products_count': active_products_count,
            'monthly_total': monthly_total,
            'next_billing_date': tenant.next_billing_date,
            'recent_history': BillingHistorySerializer(recent_history, many=True).data
        })
