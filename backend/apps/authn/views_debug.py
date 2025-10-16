from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from apps.tenancy.models import Tenant
import logging

logger = logging.getLogger(__name__)

User = get_user_model()

@api_view(['GET'])
@permission_classes([AllowAny])
def debug_user_tenant(request):
    """Endpoint público para debug de usuários e tenants"""
    
    debug_info = {
        'total_users': User.objects.count(),
        'users_without_tenant': User.objects.filter(tenant__isnull=True).count(),
        'total_tenants': Tenant.objects.count(),
    }
    
    # Listar usuários sem tenant
    users_without_tenant = User.objects.filter(tenant__isnull=True).values(
        'id', 'username', 'email', 'first_name', 'last_name'
    )
    debug_info['users_without_tenant_list'] = list(users_without_tenant)
    
    # Listar todos os tenants
    tenants = Tenant.objects.all().values('id', 'name', 'status')
    debug_info['tenants_list'] = list(tenants)
    
    # Listar usuários com tenant
    users_with_tenant = User.objects.filter(tenant__isnull=False).values(
        'id', 'username', 'email', 'tenant_id', 'tenant__name'
    )
    debug_info['users_with_tenant_list'] = list(users_with_tenant)
    
    return Response(debug_info)

@api_view(['POST'])
@permission_classes([AllowAny])
def fix_user_tenant(request):
    """Endpoint para corrigir usuários sem tenant"""
    email = request.data.get('email')
    tenant_id = request.data.get('tenant_id')
    
    if not email or not tenant_id:
        return Response({
            'error': 'Email e tenant_id são obrigatórios'
        }, status=400)
    
    try:
        user = User.objects.get(email=email)
        tenant = Tenant.objects.get(id=tenant_id)
        
        user.tenant = tenant
        user.save()
        
        return Response({
            'success': True,
            'message': f'Usuário {email} associado ao tenant {tenant.name}',
            'user_id': user.id,
            'tenant_id': tenant.id
        })
        
    except User.DoesNotExist:
        return Response({
            'error': f'Usuário com email {email} não encontrado'
        }, status=404)
    except Tenant.DoesNotExist:
        return Response({
            'error': f'Tenant com ID {tenant_id} não encontrado'
        }, status=404)
