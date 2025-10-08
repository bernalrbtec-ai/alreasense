import requests
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from django.utils import timezone
from .models import EvolutionConnection
from .serializers import EvolutionConnectionSerializer


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def evolution_config(request):
    """Get or update Evolution API configuration."""
    
    if request.method == 'GET':
        # Return default configuration (without database dependency)
        return Response({
            'id': None,
            'name': 'Default Evolution API',
            'base_url': 'https://evo.rbtec.com.br',
            'api_key': '584B4A4A-0815-AC86-DC39-C38FC27E8E17',
            'webhook_url': f"{request.scheme}://{request.get_host()}/api/webhooks/evolution/",
            'is_active': True,
            'status': 'inactive',
            'last_check': None,
            'last_error': None,
            'created_at': None,
            'updated_at': None,
        })
    
    elif request.method == 'POST':
        # For now, just return success (without database dependency)
        data = request.data
        return Response({
            'id': 'temp-id',
            'name': data.get('name', 'Default Evolution API'),
            'base_url': data.get('base_url', 'https://evo.rbtec.com.br'),
            'api_key': data.get('api_key', '584B4A4A-0815-AC86-DC39-C38FC27E8E17'),
            'webhook_url': data.get('webhook_url', f"{request.scheme}://{request.get_host()}/api/webhooks/evolution/"),
            'is_active': data.get('is_active', True),
            'status': 'active',
            'last_check': timezone.now().isoformat(),
            'last_error': None,
            'created_at': timezone.now().isoformat(),
            'updated_at': timezone.now().isoformat(),
        }, status=status.HTTP_200_OK)


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