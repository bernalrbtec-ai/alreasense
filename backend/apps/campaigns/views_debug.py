from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.conf import settings
from .models import Campaign
import logging

logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])  # ✅ SECURITY FIX: Only admin users
def debug_campaigns(request):
    """Endpoint de debug para investigar problemas com campanhas"""
    user = request.user
    
    debug_info = {
        'user_id': user.id,
        'username': user.username,
        'email': user.email,
        'tenant_id': user.tenant.id if user.tenant else None,
        'tenant_name': user.tenant.name if user.tenant else None,
        'is_superuser': user.is_superuser,
        'request_tenant': getattr(request, 'tenant', None),
        'request_tenant_id': getattr(request, 'tenant_id', None),
    }
    
    # Buscar TODAS as campanhas (sem filtro de tenant)
    all_campaigns = Campaign.objects.all().values(
        'id', 'name', 'status', 'tenant_id', 'created_at'
    )
    
    debug_info['total_campaigns_in_db'] = all_campaigns.count()
    debug_info['all_campaigns'] = list(all_campaigns)
    
    # Buscar campanhas do tenant atual
    if user.tenant:
        tenant_campaigns = Campaign.objects.filter(tenant=user.tenant).values(
            'id', 'name', 'status', 'tenant_id', 'created_at'
        )
        debug_info['tenant_campaigns_count'] = tenant_campaigns.count()
        debug_info['tenant_campaigns'] = list(tenant_campaigns)
    else:
        debug_info['tenant_campaigns_count'] = 0
        debug_info['tenant_campaigns'] = []
        debug_info['error'] = 'User has no tenant associated'
    
    # Buscar campanhas sem tenant
    no_tenant_campaigns = Campaign.objects.filter(tenant__isnull=True).values(
        'id', 'name', 'status', 'tenant_id', 'created_at'
    )
    debug_info['no_tenant_campaigns_count'] = no_tenant_campaigns.count()
    debug_info['no_tenant_campaigns'] = list(no_tenant_campaigns)
    
    # Buscar campanhas de outros tenants
    other_tenants_campaigns = Campaign.objects.exclude(tenant=user.tenant).exclude(tenant__isnull=True).values(
        'id', 'name', 'status', 'tenant_id', 'created_at'
    )
    debug_info['other_tenants_campaigns_count'] = other_tenants_campaigns.count()
    debug_info['other_tenants_campaigns'] = list(other_tenants_campaigns)
    
    return Response(debug_info)

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])  # ✅ SECURITY FIX: Only admin users
def test_retry_endpoint(request, campaign_id):
    """Endpoint de teste para verificar se as rotas estão funcionando"""
    from django.utils import timezone
    return Response({
        'message': f'Endpoint de teste funcionando para campanha {campaign_id}',
        'campaign_id': campaign_id,
        'timestamp': timezone.now().isoformat()
    })
