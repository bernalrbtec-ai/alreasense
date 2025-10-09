"""
Decorators para controle de acesso baseado em produtos
Baseado na estratégia definida em ALREA_PRODUCTS_STRATEGY.md
"""

from functools import wraps
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from rest_framework import status


def require_product(product_slug):
    """
    Decorator que valida acesso ao produto
    
    Uso:
    @require_product('flow')
    class CampaignViewSet(viewsets.ModelViewSet):
        ...
    """
    def decorator(cls):
        original_dispatch = cls.dispatch
        
        @wraps(original_dispatch)
        def new_dispatch(self, request, *args, **kwargs):
            # Verificar se o tenant tem acesso ao produto
            if not hasattr(request, 'tenant') or not request.tenant:
                raise PermissionDenied('Tenant não encontrado')
            
            if not request.tenant.can_access_product(product_slug):
                # Retornar erro específico para API
                if hasattr(request, 'accepted_renderer'):
                    return JsonResponse({
                        'error': f'Produto {product_slug} não disponível no seu plano',
                        'code': 'PRODUCT_NOT_AVAILABLE',
                        'product': product_slug,
                        'current_plan': request.tenant.current_plan.name if request.tenant.current_plan else 'Sem Plano',
                        'available_products': request.tenant.active_product_slugs
                    }, status=status.HTTP_403_FORBIDDEN)
                else:
                    raise PermissionDenied(
                        f'Produto {product_slug} não disponível no seu plano'
                    )
            
            return original_dispatch(self, request, *args, **kwargs)
        
        cls.dispatch = new_dispatch
        return cls
    
    return decorator


def require_ui_access(cls):
    """
    Decorator que valida acesso à UI
    
    Uso:
    @require_ui_access
    class DashboardViewSet(viewsets.ModelViewSet):
        ...
    """
    original_dispatch = cls.dispatch
    
    @wraps(original_dispatch)
    def new_dispatch(self, request, *args, **kwargs):
        # Verificar se o tenant tem acesso à UI
        if not hasattr(request, 'tenant') or not request.tenant:
            raise PermissionDenied('Tenant não encontrado')
        
        if not request.tenant.ui_access:
            # Retornar erro específico para API
            if hasattr(request, 'accepted_renderer'):
                return JsonResponse({
                    'error': 'Acesso à interface não disponível no seu plano',
                    'code': 'UI_ACCESS_DENIED',
                    'current_plan': request.tenant.current_plan.name if request.tenant.current_plan else 'API Only',
                    'suggestion': 'Considere fazer upgrade para um plano com acesso à interface'
                }, status=status.HTTP_403_FORBIDDEN)
            else:
                raise PermissionDenied(
                    'Acesso à interface não disponível no seu plano'
                )
        
        return original_dispatch(self, request, *args, **kwargs)
    
    cls.dispatch = new_dispatch
    return cls


def require_api_key(product_slug):
    """
    Decorator que valida API key específica do produto
    
    Uso:
    @require_api_key('api_public')
    def public_api_view(request):
        ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Verificar se o tenant tem o produto
            if not hasattr(request, 'tenant') or not request.tenant:
                return JsonResponse({
                    'error': 'Tenant não encontrado'
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            if not request.tenant.has_product(product_slug):
                return JsonResponse({
                    'error': f'Produto {product_slug} não disponível no seu plano',
                    'code': 'PRODUCT_NOT_AVAILABLE'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Verificar API key
            api_key = request.headers.get('X-API-Key') or request.GET.get('api_key')
            if not api_key:
                return JsonResponse({
                    'error': 'API Key é obrigatória',
                    'code': 'API_KEY_REQUIRED'
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            # Verificar se a API key é válida para o produto
            tenant_api_key = request.tenant.get_product_api_key(product_slug)
            if not tenant_api_key or api_key != tenant_api_key:
                return JsonResponse({
                    'error': 'API Key inválida',
                    'code': 'INVALID_API_KEY'
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def check_product_limit(product_slug, limit_type, current_usage):
    """
    Decorator que verifica limites de produto
    
    Uso:
    @check_product_limit('sense', 'analyses_per_month', current_analyses)
    def analyze_sentiment(request):
        ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Verificar se o tenant tem o produto
            if not hasattr(request, 'tenant') or not request.tenant:
                return JsonResponse({
                    'error': 'Tenant não encontrado'
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            if not request.tenant.has_product(product_slug):
                return JsonResponse({
                    'error': f'Produto {product_slug} não disponível no seu plano',
                    'code': 'PRODUCT_NOT_AVAILABLE'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Verificar limites
            try:
                from apps.billing.models import PlanProduct
                plan_product = PlanProduct.objects.get(
                    plan=request.tenant.current_plan,
                    product__slug=product_slug,
                    is_included=True
                )
                
                # Se tem limite definido
                if plan_product.limit_value and current_usage >= plan_product.limit_value:
                    return JsonResponse({
                        'error': f'Limite de {plan_product.limit_unit} atingido',
                        'code': 'LIMIT_EXCEEDED',
                        'limit': plan_product.limit_value,
                        'current_usage': current_usage,
                        'limit_unit': plan_product.limit_unit
                    }, status=status.HTTP_429_TOO_MANY_REQUESTS)
                
            except PlanProduct.DoesNotExist:
                return JsonResponse({
                    'error': f'Produto {product_slug} não configurado no plano',
                    'code': 'PRODUCT_NOT_CONFIGURED'
                }, status=status.HTTP_403_FORBIDDEN)
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator
