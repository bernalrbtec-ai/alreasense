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


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def evolution_config(request):
    """Get or update Evolution API configuration."""
    
    if request.method == 'GET':
        # Buscar configuração do tenant atual
        user = request.user
        print(f"🔍 Buscando configuração Evolution para usuário: {user.username} (superuser: {user.is_superuser})")
        
        if user.is_superuser:
            # Superadmin vê configuração global (primeira configuração ativa)
            print(f"🔍 Superuser - buscando conexões ativas...")
            all_connections = EvolutionConnection.objects.all()
            print(f"🔍 Superuser - total de conexões: {all_connections.count()}")
            for conn in all_connections:
                print(f"🔍 Superuser - conexão: id={conn.id}, is_active={conn.is_active}, tenant={conn.tenant.name}")
            
            connection = EvolutionConnection.objects.filter(is_active=True).first()
            print(f"🔍 Superuser - conexão encontrada: {connection is not None}")
            if connection:
                print(f"🔍 Superuser - tenant da conexão: {connection.tenant.name}")
                print(f"🔍 Superuser - dados da conexão: id={connection.id}, base_url={connection.base_url}, is_active={connection.is_active}")
        else:
            # Usuário comum NÃO PODE acessar configuração - apenas superuser
            return Response({
                'error': 'Apenas administradores podem acessar a configuração Evolution API'
            }, status=status.HTTP_403_FORBIDDEN)
        
        if not connection:
            # Se não existe, retornar configuração vazia
            return Response({
                'id': None,
                'name': '',
                'base_url': '',
                'api_key': '',
                'webhook_url': '',
                'is_active': False,
                'status': 'inactive',
                'last_check': None,
                'last_error': 'Configuração não encontrada - configure abaixo',
                'instance_count': 0,
                'created_at': None,
                'updated_at': None,
            })
        
        # Auto-test connection
        connection_status = 'inactive'
        last_error = None
        instance_count = 0
        
        # Só testar se tiver api_key e base_url
        if connection.api_key and connection.base_url:
            try:
                headers = {
                    'apikey': connection.api_key,
                    'Content-Type': 'application/json'
                }
                
                test_url = f"{connection.base_url}/instance/fetchInstances"
                response = requests.get(test_url, headers=headers, timeout=5)
                
                if response.status_code == 200:
                    instances = response.json()
                    instance_count = len(instances)
                    connection_status = 'active'
                    connection.update_status('active')
                else:
                    connection_status = 'error'
                    last_error = f'HTTP {response.status_code}: {response.text[:100]}'
                    connection.update_status('error', last_error)
                    
            except requests.exceptions.Timeout:
                connection_status = 'error'
                last_error = 'Timeout na conexão'
                connection.update_status('error', last_error)
            except requests.exceptions.ConnectionError:
                connection_status = 'error'
                last_error = 'Erro de conexão - servidor não alcançável'
                connection.update_status('error', last_error)
            except Exception as e:
                connection_status = 'error'
                last_error = str(e)[:100]
                connection.update_status('error', last_error)
        else:
            # Sem configuração ainda
            connection_status = 'inactive'
            last_error = 'Configuração incompleta - adicione URL e API Key'
        
        # Webhook URL seguro (não usa request.get_host que pode dar erro)
        try:
            webhook_url = f"{request.scheme}://{request.get_host()}/api/webhooks/evolution/"
        except Exception:
            # Fallback para Railway ou localhost
            from django.conf import settings
            base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
            webhook_url = f"{base_url}/api/webhooks/evolution/"
        
        # Tentar obter api_key, se falhar retornar string vazia
        try:
            api_key_value = connection.api_key or ''
        except Exception:
            api_key_value = ''
        
        return Response({
            'id': str(connection.id),
            'name': connection.name,
            'base_url': connection.base_url,
            'api_key': api_key_value,
            'webhook_url': webhook_url,
            'is_active': connection.is_active,
            'status': connection_status,
            'last_check': timezone.now().isoformat(),
            'last_error': last_error,
            'instance_count': instance_count,
            'created_at': connection.created_at.isoformat() if connection.created_at else None,
            'updated_at': connection.updated_at.isoformat() if connection.updated_at else None,
        })
    
    elif request.method == 'POST':
        # Atualizar configuração no banco de dados
        try:
            data = request.data
            
            # Buscar ou criar conexão para o tenant atual
            user = request.user
            
            if user.is_superuser:
                # Superadmin pode atualizar configuração global
                connection = EvolutionConnection.objects.filter(is_active=True).first()
                if not connection:
                    from apps.tenancy.models import Tenant
                    tenant = Tenant.objects.first()
                    if not tenant:
                        return Response({
                            'error': 'Nenhum tenant encontrado no sistema'
                        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                    
                    connection = EvolutionConnection.objects.create(
                        tenant=tenant,
                        name=data.get('name', 'Evolution RBTec'),
                        base_url=data.get('base_url', 'https://evo.rbtec.com.br'),
                        api_key=data.get('api_key', ''),
                        is_active=data.get('is_active', True),
                        status='inactive'
                    )
                    print(f"🔧 Superuser - criou nova conexão para tenant: {tenant.name}")
                else:
                    # Atualizar existente
                    print(f"🔧 Superuser - atualizando conexão existente: {connection.id} (tenant: {connection.tenant.name})")
                    print(f"🔧 Dados recebidos: base_url={data.get('base_url')}, api_key={'*' * 10 if data.get('api_key') else 'empty'}")
                    
                    connection.name = data.get('name', connection.name)
                    connection.base_url = data.get('base_url', connection.base_url)
                    
                    # API Key: só atualizar se vier nova (não vazia)
                    new_api_key = data.get('api_key', '')
                    if new_api_key and new_api_key.strip():
                        connection.api_key = new_api_key
                        print(f"🔧 Superuser - API key atualizada")
                    
                    connection.is_active = data.get('is_active', connection.is_active)
                    connection.save()
                    
                    print(f"🔧 Superuser - conexão salva: id={connection.id}, base_url={connection.base_url}, is_active={connection.is_active}")
            else:
                # Usuário comum NÃO PODE configurar - apenas superuser
                return Response({
                    'error': 'Apenas administradores podem configurar o servidor Evolution API'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Webhook URL seguro
            try:
                webhook_url = f"{request.scheme}://{request.get_host()}/api/webhooks/evolution/"
            except Exception:
                from django.conf import settings
                base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
                webhook_url = f"{base_url}/api/webhooks/evolution/"
            
            # Tentar obter api_key, se falhar (criptografia corrompida) retornar string vazia
            try:
                api_key_value = connection.api_key or ''
            except Exception:
                api_key_value = ''
            
            return Response({
                'id': str(connection.id),
                'name': connection.name,
                'base_url': connection.base_url,
                'api_key': api_key_value,
                'webhook_url': webhook_url,
                'is_active': connection.is_active,
                'status': connection.status,
                'last_check': connection.last_check.isoformat() if connection.last_check else None,
                'last_error': connection.last_error,
                'created_at': connection.created_at.isoformat() if connection.created_at else None,
                'updated_at': connection.updated_at.isoformat() if connection.updated_at else None,
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({
                'error': f'Erro ao salvar configuração: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_evolution_connection(request):
    """Test connection with Evolution API."""
    
    try:
        data = request.data
        base_url = data.get('base_url')
        api_key = data.get('api_key')
        
        if not base_url or not api_key:
            return Response(
                {'error': 'URL base e API Key são obrigatórios'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Test connection by fetching instances
        headers = {
            'apikey': api_key,
            'Content-Type': 'application/json'
        }
        
        # Remove trailing slash from base_url
        base_url = base_url.rstrip('/')
        test_url = f"{base_url}/instance/fetchInstances"
        
        response = requests.get(test_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            # Connection successful
            instances = response.json()
            
            return Response({
                'success': True,
                'message': f'Conexão estabelecida com sucesso! Encontradas {len(instances)} instâncias.',
                'instances': instances,
                'config': {
                    'id': 'temp-id',
                    'name': 'Default Evolution API',
                    'base_url': base_url,
                    'api_key': api_key,
                    'webhook_url': f"{request.scheme}://{request.get_host()}/api/webhooks/evolution/",
                    'is_active': True,
                    'status': 'active',
                    'last_check': timezone.now().isoformat(),
                    'last_error': None,
                }
            })
            
        else:
            # Connection failed
            error_message = f'Falha na conexão: {response.status_code} - {response.text}'
            
            return Response({
                'success': False,
                'message': error_message,
                'config': {
                    'id': 'temp-id',
                    'name': 'Default Evolution API',
                    'base_url': base_url,
                    'api_key': api_key,
                    'webhook_url': f"{request.scheme}://{request.get_host()}/api/webhooks/evolution/",
                    'is_active': False,
                    'status': 'error',
                    'last_check': timezone.now().isoformat(),
                    'last_error': error_message,
                }
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except requests.exceptions.Timeout:
        return Response({
            'success': False,
            'message': 'Timeout na conexão com Evolution API. Verifique a URL e conectividade.'
        }, status=status.HTTP_408_REQUEST_TIMEOUT)
        
    except requests.exceptions.ConnectionError:
        return Response({
            'success': False,
            'message': 'Erro de conexão com Evolution API. Verifique a URL e se o servidor está online.'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Erro inesperado: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)