import requests
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from django.utils import timezone
from .models import EvolutionConnection
from .serializers import EvolutionConnectionSerializer


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def evolution_config(request):
    """Get or update Evolution API configuration."""
    
    if request.method == 'GET':
        # Get current configuration
        try:
            config = EvolutionConnection.objects.first()
            if config:
                serializer = EvolutionConnectionSerializer(config)
                return Response(serializer.data)
            else:
                # Return default configuration
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
        except Exception as e:
            return Response(
                {'error': f'Erro ao buscar configuração: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'POST':
        # Update configuration
        try:
            data = request.data
            
            # Get or create configuration
            config, created = EvolutionConnection.objects.get_or_create(
                id=data.get('id'),
                defaults={
                    'name': data.get('name', 'Default Evolution API'),
                    'base_url': data.get('base_url'),
                    'api_key': data.get('api_key'),
                    'webhook_url': data.get('webhook_url'),
                    'is_active': data.get('is_active', True),
                }
            )
            
            if not created:
                # Update existing configuration
                config.name = data.get('name', config.name)
                config.base_url = data.get('base_url', config.base_url)
                config.api_key = data.get('api_key', config.api_key)
                config.webhook_url = data.get('webhook_url', config.webhook_url)
                config.is_active = data.get('is_active', config.is_active)
                config.save()
            
            serializer = EvolutionConnectionSerializer(config)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': f'Erro ao salvar configuração: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
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
            
            # Update or create configuration with success status
            config, created = EvolutionConnection.objects.get_or_create(
                defaults={
                    'name': 'Default Evolution API',
                    'base_url': base_url,
                    'api_key': api_key,
                    'webhook_url': f"{request.scheme}://{request.get_host()}/api/webhooks/evolution/",
                    'is_active': True,
                    'status': 'active',
                    'last_check': timezone.now(),
                    'last_error': None,
                }
            )
            
            if not created:
                config.base_url = base_url
                config.api_key = api_key
                config.update_status('active')
            
            return Response({
                'success': True,
                'message': f'Conexão estabelecida com sucesso! Encontradas {len(instances)} instâncias.',
                'instances': instances,
                'config': EvolutionConnectionSerializer(config).data
            })
            
        else:
            # Connection failed
            error_message = f'Falha na conexão: {response.status_code} - {response.text}'
            
            # Update configuration with error status
            config, created = EvolutionConnection.objects.get_or_create(
                defaults={
                    'name': 'Default Evolution API',
                    'base_url': base_url,
                    'api_key': api_key,
                    'webhook_url': f"{request.scheme}://{request.get_host()}/api/webhooks/evolution/",
                    'is_active': False,
                    'status': 'error',
                    'last_check': timezone.now(),
                    'last_error': error_message,
                }
            )
            
            if not created:
                config.update_status('error', error_message)
            
            return Response({
                'success': False,
                'message': error_message,
                'config': EvolutionConnectionSerializer(config).data
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