import requests
from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from django.utils import timezone
from .models import EvolutionConnection
from .serializers import EvolutionConnectionSerializer


class ConnectionListView(generics.ListAPIView):
    """List all connections for the current tenant."""
    
    serializer_class = EvolutionConnectionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # Return connections for the current user's tenant
        return EvolutionConnection.objects.filter(tenant=self.request.user.tenant)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def evolution_config(request):
    """
    Get Evolution API statistics and instances.
    
    ✅ REFATORADO (Out/2025):
    - Não retorna mais base_url e api_key (vêm do .env)
    - Busca instâncias da Evolution API usando settings
    - Retorna estatísticas: total, conectadas, desconectadas
    - Retorna lista de instâncias com nome e status
    """
    from django.conf import settings
    import logging
    
    logger = logging.getLogger(__name__)
    
    # ✅ Buscar configuração do .env (não do banco)
    base_url = settings.EVOLUTION_API_URL
    api_key = settings.EVOLUTION_API_KEY
    
    # Webhook URL
    try:
        webhook_url = f"{request.scheme}://{request.get_host()}/webhooks/evolution/"
    except Exception:
        base_url_setting = getattr(settings, 'BASE_URL', 'http://localhost:8000')
        webhook_url = f"{base_url_setting}/webhooks/evolution/"
    
    # ✅ Verificar se configuração existe no .env
    if not base_url or not api_key:
        logger.warning("⚠️ [EVOLUTION CONFIG] Variáveis de ambiente não configuradas")
        return Response({
            'status': 'inactive',
            'last_check': timezone.now().isoformat(),
            'last_error': 'Configuração não encontrada no .env (EVOLUTION_API_URL ou EVOLUTION_API_KEY)',
            'webhook_url': webhook_url,
            'statistics': {
                'total': 0,
                'connected': 0,
                'disconnected': 0,
            },
            'instances': [],
        })
    
    # ✅ Buscar instâncias da Evolution API
    connection_status = 'inactive'
    last_error = None
    instances_data = []
    stats = {'total': 0, 'connected': 0, 'disconnected': 0}
    
    try:
        headers = {
            'apikey': api_key,
            'Content-Type': 'application/json'
        }
        
        # Remove trailing slash
        base_url_clean = base_url.rstrip('/')
        fetch_url = f"{base_url_clean}/instance/fetchInstances"
        
        logger.info(f"🔍 [EVOLUTION CONFIG] Buscando instâncias em: {base_url_clean}")
        
        response = requests.get(fetch_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            instances = response.json()
            if not isinstance(instances, list):
                instances = getattr(instances, 'data', instances) or []
                if not isinstance(instances, list):
                    instances = []
            logger.info(f"✅ [EVOLUTION CONFIG] {len(instances)} instâncias encontradas")
            
            connection_status = 'active'
            
            # Processar cada instância (Evolution API v2: name, profileName, connectionStatus na raiz)
            for inst in instances:
                if not isinstance(inst, dict):
                    continue
                # v2: profileName (nome legível), name (id interno), connectionStatus ("open" = conectado)
                instance_name = (
                    inst.get('profileName') or
                    inst.get('instance', {}).get('instanceName') or
                    inst.get('instanceName') or
                    inst.get('name') or
                    'Unknown'
                )
                instance_status = (
                    inst.get('connectionStatus') or
                    inst.get('instance', {}).get('status') or
                    inst.get('status') or
                    'unknown'
                )
                is_connected = str(instance_status).lower() == 'open'
                
                instances_data.append({
                    'name': instance_name if isinstance(instance_name, str) else str(instance_name),
                    'status': 'connected' if is_connected else 'disconnected',
                    'raw_status': str(instance_status),
                })
                
                stats['total'] += 1
                if is_connected:
                    stats['connected'] += 1
                else:
                    stats['disconnected'] += 1
                    
        elif response.status_code == 401:
            connection_status = 'error'
            last_error = 'Erro de autenticação (401) - Verifique EVOLUTION_API_KEY no .env'
            logger.error(f"❌ [EVOLUTION CONFIG] {last_error}")
        else:
            connection_status = 'error'
            last_error = f'HTTP {response.status_code}: {response.text[:200]}'
            logger.error(f"❌ [EVOLUTION CONFIG] {last_error}")
            
    except requests.exceptions.Timeout:
        connection_status = 'error'
        last_error = 'Timeout na conexão com Evolution API (10s)'
        logger.error(f"❌ [EVOLUTION CONFIG] {last_error}")
    except requests.exceptions.ConnectionError:
        connection_status = 'error'
        last_error = f'Erro de conexão - servidor {base_url} não alcançável'
        logger.error(f"❌ [EVOLUTION CONFIG] {last_error}")
    except Exception as e:
        connection_status = 'error'
        last_error = f'Erro inesperado: {str(e)[:200]}'
        logger.error(f"❌ [EVOLUTION CONFIG] {last_error}", exc_info=True)
    
    return Response({
        'status': connection_status,
        'last_check': timezone.now().isoformat(),
        'last_error': last_error,
        'webhook_url': webhook_url,
        'statistics': stats,
        'instances': instances_data,
    })