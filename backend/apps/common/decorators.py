"""
Decorators para controle de acesso e validações
"""

from functools import wraps
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from rest_framework.response import Response
from rest_framework import status


def require_product(product_slug):
    """
    Decorator que valida acesso ao produto
    
    Uso:
    @require_product('flow')
    class CampaignViewSet(viewsets.ModelViewSet):
        ...
    
    @require_product('sense')
    def my_view(request):
        ...
    """
    def decorator(view_func_or_class):
        if hasattr(view_func_or_class, 'dispatch'):
            # É uma classe (ViewSet)
            original_dispatch = view_func_or_class.dispatch
            
            @wraps(original_dispatch)
            def new_dispatch(self, request, *args, **kwargs):
                # Verificar se tenant tem acesso ao produto
                if not hasattr(request, 'tenant') or not request.tenant:
                    raise PermissionDenied('Tenant não encontrado')
                
                if not request.tenant.has_product(product_slug):
                    if request.accepted_renderer.format == 'json' or 'application/json' in request.META.get('CONTENT_TYPE', ''):
                        return Response({
                            'success': False,
                            'error': f'Produto "{product_slug}" não disponível no seu plano',
                            'required_product': product_slug,
                            'current_plan': request.tenant.current_plan.name if request.tenant.current_plan else None
                        }, status=status.HTTP_403_FORBIDDEN)
                    else:
                        raise PermissionDenied(f'Produto "{product_slug}" não disponível no seu plano')
                
                return original_dispatch(self, request, *args, **kwargs)
            
            view_func_or_class.dispatch = new_dispatch
            return view_func_or_class
        else:
            # É uma função
            @wraps(view_func_or_class)
            def wrapper(request, *args, **kwargs):
                # Verificar se tenant tem acesso ao produto
                if not hasattr(request, 'tenant') or not request.tenant:
                    raise PermissionDenied('Tenant não encontrado')
                
                if not request.tenant.has_product(product_slug):
                    if request.accepted_renderer.format == 'json' or 'application/json' in request.META.get('CONTENT_TYPE', ''):
                        return JsonResponse({
                            'success': False,
                            'error': f'Produto "{product_slug}" não disponível no seu plano',
                            'required_product': product_slug,
                            'current_plan': request.tenant.current_plan.name if request.tenant.current_plan else None
                        }, status=403)
                    else:
                        raise PermissionDenied(f'Produto "{product_slug}" não disponível no seu plano')
                
                return view_func_or_class(request, *args, **kwargs)
            
            return wrapper
    
    return decorator


def require_plan(plan_slug):
    """
    Decorator que valida se tenant tem plano específico
    
    Uso:
    @require_plan('enterprise')
    def admin_only_view(request):
        ...
    """
    def decorator(view_func_or_class):
        if hasattr(view_func_or_class, 'dispatch'):
            # É uma classe (ViewSet)
            original_dispatch = view_func_or_class.dispatch
            
            @wraps(original_dispatch)
            def new_dispatch(self, request, *args, **kwargs):
                if not hasattr(request, 'tenant') or not request.tenant:
                    raise PermissionDenied('Tenant não encontrado')
                
                if not request.tenant.current_plan or request.tenant.current_plan.slug != plan_slug:
                    if request.accepted_renderer.format == 'json' or 'application/json' in request.META.get('CONTENT_TYPE', ''):
                        return Response({
                            'success': False,
                            'error': f'Plano "{plan_slug}" necessário para acessar este recurso',
                            'required_plan': plan_slug,
                            'current_plan': request.tenant.current_plan.slug if request.tenant.current_plan else None
                        }, status=status.HTTP_403_FORBIDDEN)
                    else:
                        raise PermissionDenied(f'Plano "{plan_slug}" necessário para acessar este recurso')
                
                return original_dispatch(self, request, *args, **kwargs)
            
            view_func_or_class.dispatch = new_dispatch
            return view_func_or_class
        else:
            # É uma função
            @wraps(view_func_or_class)
            def wrapper(request, *args, **kwargs):
                if not hasattr(request, 'tenant') or not request.tenant:
                    raise PermissionDenied('Tenant não encontrado')
                
                if not request.tenant.current_plan or request.tenant.current_plan.slug != plan_slug:
                    if request.accepted_renderer.format == 'json' or 'application/json' in request.META.get('CONTENT_TYPE', ''):
                        return JsonResponse({
                            'success': False,
                            'error': f'Plano "{plan_slug}" necessário para acessar este recurso',
                            'required_plan': plan_slug,
                            'current_plan': request.tenant.current_plan.slug if request.tenant.current_plan else None
                        }, status=403)
                    else:
                        raise PermissionDenied(f'Plano "{plan_slug}" necessário para acessar este recurso')
                
                return view_func_or_class(request, *args, **kwargs)
            
            return wrapper
    
    return decorator


def require_api_key():
    """
    Decorator para endpoints que requerem API Key (API Pública)
    
    Uso:
    @require_api_key()
    def public_api_endpoint(request):
        ...
    """
    def decorator(view_func_or_class):
        if hasattr(view_func_or_class, 'dispatch'):
            # É uma classe (ViewSet)
            original_dispatch = view_func_or_class.dispatch
            
            @wraps(original_dispatch)
            def new_dispatch(self, request, *args, **kwargs):
                # Verificar API Key no header
                api_key = request.META.get('HTTP_X_API_KEY') or request.META.get('HTTP_API_KEY')
                
                if not api_key:
                    return Response({
                        'success': False,
                        'error': 'API Key necessária',
                        'required_header': 'X-API-Key'
                    }, status=status.HTTP_401_UNAUTHORIZED)
                
                # Verificar se API Key é válida e tem acesso ao produto
                from apps.billing.models import TenantProduct
                try:
                    tenant_product = TenantProduct.objects.get(
                        api_key=api_key,
                        is_active=True,
                        product__slug='api_public'
                    )
                    request.tenant = tenant_product.tenant
                    request.tenant_product = tenant_product
                except TenantProduct.DoesNotExist:
                    return Response({
                        'success': False,
                        'error': 'API Key inválida ou produto não ativo'
                    }, status=status.HTTP_401_UNAUTHORIZED)
                
                return original_dispatch(self, request, *args, **kwargs)
            
            view_func_or_class.dispatch = new_dispatch
            return view_func_or_class
        else:
            # É uma função
            @wraps(view_func_or_class)
            def wrapper(request, *args, **kwargs):
                # Verificar API Key no header
                api_key = request.META.get('HTTP_X_API_KEY') or request.META.get('HTTP_API_KEY')
                
                if not api_key:
                    return JsonResponse({
                        'success': False,
                        'error': 'API Key necessária',
                        'required_header': 'X-API-Key'
                    }, status=401)
                
                # Verificar se API Key é válida
                from apps.billing.models import TenantProduct
                try:
                    tenant_product = TenantProduct.objects.get(
                        api_key=api_key,
                        is_active=True,
                        product__slug='api_public'
                    )
                    request.tenant = tenant_product.tenant
                    request.tenant_product = tenant_product
                except TenantProduct.DoesNotExist:
                    return JsonResponse({
                        'success': False,
                        'error': 'API Key inválida ou produto não ativo'
                    }, status=401)
                
                return view_func_or_class(request, *args, **kwargs)
            
            return wrapper
    
    return decorator
