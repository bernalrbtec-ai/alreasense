"""
Views para o sistema de billing
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Product, Plan, TenantProduct, BillingHistory
from .serializers import (
    ProductSerializer,
    PlanSerializer,
    PlanCreateUpdateSerializer,
    TenantProductSerializer,
    BillingHistorySerializer,
    TenantBillingInfoSerializer
)
from apps.common.permissions import IsTenantMember, IsAdminUser
from apps.common.cache_manager import CacheManager
from django.contrib.auth import get_user_model

User = get_user_model()


class ProductViewSet(viewsets.ModelViewSet):
    """ViewSet para produtos"""
    
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    queryset = Product.objects.all()
    
    def get_queryset(self):
        """Filtrar produtos baseado no usuário (COM CACHE)"""
        user = self.request.user
        
        # Cache key baseado no tipo de usuário usando CacheManager
        cache_key = CacheManager.make_key(
            CacheManager.PREFIX_PRODUCT,
            'all' if (user.is_superuser or user.is_staff) else 'active'
        )
        
        def fetch_products():
            """Função para buscar produtos do banco"""
            if user.is_superuser or user.is_staff:
                return list(Product.objects.all().values_list('id', flat=True))
            else:
                return list(Product.objects.filter(is_active=True).values_list('id', flat=True))
        
        # Usar CacheManager para get_or_set (TTL de 24 horas)
        product_ids = CacheManager.get_or_set(
            cache_key,
            fetch_products,
            ttl=CacheManager.TTL_DAY
        )
        
        # Retornar queryset completo
        return Product.objects.filter(id__in=product_ids)

    def list(self, request, *args, **kwargs):
        """Listar produtos com cache de resposta"""
        user = request.user
        scope = 'all' if (user.is_superuser or user.is_staff) else 'active'
        page = request.query_params.get('page', '1')
        page_size = request.query_params.get('page_size', 'default')

        cache_key = CacheManager.make_key(
            CacheManager.PREFIX_PRODUCT,
            'list',
            scope=scope,
            page=page,
            page_size=page_size
        )

        def fetch_list():
            queryset = self.filter_queryset(self.get_queryset())
            page_obj = self.paginate_queryset(queryset)
            if page_obj is not None:
                serializer = self.get_serializer(page_obj, many=True)
                return self.get_paginated_response(serializer.data).data
            serializer = self.get_serializer(queryset, many=True)
            return serializer.data

        data = CacheManager.get_or_set(
            cache_key,
            fetch_list,
            ttl=CacheManager.TTL_HOUR
        )

        return Response(data)

    def perform_create(self, serializer):
        product = serializer.save()
        CacheManager.invalidate_pattern(f"{CacheManager.PREFIX_PRODUCT}:*")
        return product

    def perform_update(self, serializer):
        product = serializer.save()
        CacheManager.invalidate_pattern(f"{CacheManager.PREFIX_PRODUCT}:*")
        return product

    def perform_destroy(self, instance):
        instance.delete()
        CacheManager.invalidate_pattern(f"{CacheManager.PREFIX_PRODUCT}:*")
    
    @action(detail=False, methods=['get'])
    def available(self, request):
        """Lista produtos disponíveis para o tenant como add-on (COM CACHE)"""
        tenant = request.user.tenant
        
        # Cache key por tenant
        cache_key = CacheManager.make_key(
            CacheManager.PREFIX_PRODUCT,
            'available',
            tenant_id=tenant.id
        )
        
        def fetch_available_products():
            """Função para buscar produtos disponíveis do banco"""
            # Produtos já ativos
            active_product_ids = tenant.active_products.values_list('product_id', flat=True)
            
            # Produtos disponíveis como add-on (têm addon_price definido)
            available_products = Product.objects.filter(
                is_active=True,
                addon_price__isnull=False
            ).exclude(id__in=active_product_ids)
            
            # Serializar dados para cache
            serializer = self.get_serializer(available_products, many=True)
            return serializer.data
        
        # Usar CacheManager para get_or_set (TTL de 5 minutos - dados podem mudar quando add-on é adicionado)
        data = CacheManager.get_or_set(
            cache_key,
            fetch_available_products,
            ttl=CacheManager.TTL_MINUTE * 5
        )
        
        return Response(data)


class PlanViewSet(viewsets.ModelViewSet):
    """ViewSet para planos"""
    
    permission_classes = [IsAuthenticated]
    queryset = Plan.objects.all()
    
    def get_serializer_class(self):
        """Usar serializer diferente para create/update"""
        if self.action in ['create', 'update', 'partial_update']:
            return PlanCreateUpdateSerializer
        return PlanSerializer
    
    def get_queryset(self):
        """Filtrar planos baseado no usuário (COM CACHE)"""
        user = self.request.user
        
        # Cache key baseado no tipo de usuário usando CacheManager
        cache_key = CacheManager.make_key(
            CacheManager.PREFIX_PLAN,
            'all' if (user.is_superuser or user.is_staff) else 'active'
        )
        
        def fetch_plans():
            """Função para buscar planos do banco"""
            if user.is_superuser or user.is_staff:
                return list(Plan.objects.all().order_by('sort_order').values_list('id', flat=True))
            else:
                return list(Plan.objects.filter(is_active=True).order_by('sort_order').values_list('id', flat=True))
        
        # Usar CacheManager para get_or_set (TTL de 12 horas)
        plan_ids = CacheManager.get_or_set(
            cache_key,
            fetch_plans,
            ttl=CacheManager.TTL_HOUR * 12
        )
        
        # Retornar queryset completo
        return Plan.objects.filter(id__in=plan_ids).order_by('sort_order')

    def list(self, request, *args, **kwargs):
        """Listar planos com cache de resposta"""
        user = request.user
        scope = 'all' if (user.is_superuser or user.is_staff) else 'active'
        page = request.query_params.get('page', '1')
        page_size = request.query_params.get('page_size', 'default')

        cache_key = CacheManager.make_key(
            CacheManager.PREFIX_PLAN,
            'list',
            scope=scope,
            page=page,
            page_size=page_size
        )

        def fetch_list():
            queryset = self.filter_queryset(self.get_queryset())
            page_obj = self.paginate_queryset(queryset)
            if page_obj is not None:
                serializer = self.get_serializer(page_obj, many=True)
                return self.get_paginated_response(serializer.data).data
            serializer = self.get_serializer(queryset, many=True)
            return serializer.data

        data = CacheManager.get_or_set(
            cache_key,
            fetch_list,
            ttl=CacheManager.TTL_HOUR
        )

        return Response(data)

    def perform_create(self, serializer):
        plan = serializer.save()
        CacheManager.invalidate_pattern(f"{CacheManager.PREFIX_PLAN}:*")
        return plan

    def perform_update(self, serializer):
        plan = serializer.save()
        CacheManager.invalidate_pattern(f"{CacheManager.PREFIX_PLAN}:*")
        return plan

    def perform_destroy(self, instance):
        instance.delete()
        CacheManager.invalidate_pattern(f"{CacheManager.PREFIX_PLAN}:*")
    
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
        
        # ✅ INVALIDAR CACHE: Limpar cache de produtos do tenant e planos
        CacheManager.invalidate_pattern(f"{CacheManager.PREFIX_TENANT_PRODUCT}:*")
        CacheManager.invalidate_pattern(f"{CacheManager.PREFIX_PLAN}:*")
        CacheManager.invalidate_pattern(f"{CacheManager.PREFIX_TENANT}:billing_summary:*")
        
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
        """Get tenant products (COM CACHE)"""
        tenant = self.request.user.tenant
        if not tenant:
            return TenantProduct.objects.none()
        
        # Cache key por tenant usando CacheManager
        cache_key = CacheManager.make_key(
            CacheManager.PREFIX_TENANT_PRODUCT,
            tenant_id=tenant.id
        )
        
        def fetch_tenant_products():
            """Função para buscar produtos do tenant do banco"""
            return list(
                TenantProduct.objects.filter(
                    tenant=tenant,
                    is_active=True
                ).select_related('product').values_list('id', flat=True)
            )
        
        # Usar CacheManager para get_or_set (TTL de 5 minutos)
        tenant_product_ids = CacheManager.get_or_set(
            cache_key,
            fetch_tenant_products,
            ttl=CacheManager.TTL_MINUTE * 5
        )
        
        # Retornar queryset completo
        return TenantProduct.objects.filter(
            id__in=tenant_product_ids
        ).select_related('product')
    
    def perform_create(self, serializer):
        """Adiciona um produto (add-on) ao tenant"""
        from rest_framework import serializers as drf_serializers
        
        tenant = self.request.user.tenant
        product = serializer.validated_data['product']
        
        # Validar se o produto pode ser add-on
        if not product.is_addon_available:
            raise drf_serializers.ValidationError('Este produto não está disponível como add-on')
        
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
        
        # ✅ INVALIDAR CACHE: Limpar cache de produtos do tenant e produtos disponíveis
        CacheManager.invalidate_pattern(f"{CacheManager.PREFIX_TENANT_PRODUCT}:*")
        CacheManager.invalidate_pattern(f"{CacheManager.PREFIX_PRODUCT}:available:*")
    
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
        
        # ✅ INVALIDAR CACHE: Limpar cache de produtos do tenant e produtos disponíveis
        CacheManager.invalidate_pattern(f"{CacheManager.PREFIX_TENANT_PRODUCT}:*")
        CacheManager.invalidate_pattern(f"{CacheManager.PREFIX_PRODUCT}:available:*")
        
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
        """Resumo de billing (COM CACHE)"""
        tenant = request.user.tenant
        
        # Cache key por tenant
        cache_key = CacheManager.make_key(
            CacheManager.PREFIX_TENANT,
            'billing_summary',
            tenant_id=tenant.id
        )
        
        def fetch_summary():
            """Função para buscar resumo do banco"""
            # Contar produtos ativos
            active_products_count = tenant.active_products.count()
            
            # Calcular total mensal
            monthly_total = tenant.monthly_total
            
            # Histórico recente
            recent_history = BillingHistory.objects.filter(
                tenant=tenant
            ).order_by('-created_at')[:5]
            
            return {
                'plan': {
                    'name': tenant.current_plan.name if tenant.current_plan else 'Nenhum',
                    'price': tenant.current_plan.price if tenant.current_plan else 0
                },
                'active_products_count': active_products_count,
                'monthly_total': monthly_total,
                'next_billing_date': tenant.next_billing_date,
                'recent_history': BillingHistorySerializer(recent_history, many=True).data
            }
        
        # Usar CacheManager para get_or_set (TTL de 1 minuto - dados podem mudar frequentemente)
        data = CacheManager.get_or_set(
            cache_key,
            fetch_summary,
            ttl=CacheManager.TTL_MINUTE
        )
        
        return Response(data)
