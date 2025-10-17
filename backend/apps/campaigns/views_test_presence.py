"""
Views para testar envio de presença (digitando) via Evolution API
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import requests
import logging

from apps.notifications.models import WhatsAppInstance
from apps.common.permissions import IsTenantMember

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTenantMember])
def test_send_presence(request):
    """
    Testa envio de presença (status digitando) via Evolution API
    
    Body:
    {
        "instance_id": "uuid-da-instancia",
        "phone": "+5517999999999",
        "typing_seconds": 3.5
    }
    """
    try:
        # Pegar dados do request
        instance_id = request.data.get('instance_id')
        phone = request.data.get('phone')
        typing_seconds = request.data.get('typing_seconds', 3.0)
        
        if not instance_id or not phone:
            return Response({
                'success': False,
                'error': 'instance_id e phone são obrigatórios'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Buscar instância
        try:
            instance = WhatsAppInstance.objects.get(
                id=instance_id,
                tenant=request.user.tenant
            )
        except WhatsAppInstance.DoesNotExist:
            return Response({
                'success': False,
                'error': f'Instância {instance_id} não encontrada'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Preparar URL e dados
        presence_url = f"{instance.api_url}/chat/sendPresence/{instance.instance_name}"
        presence_data = {
            "number": phone,
            "options": {
                "delay": int(typing_seconds * 1000),  # Converter para milissegundos
                "presence": "composing"
            }
        }
        headers = {
            "Content-Type": "application/json",
            "apikey": instance.api_key
        }
        
        logger.info("="*80)
        logger.info(f"🧪 [TEST PRESENCE] Iniciando teste de presença")
        logger.info(f"📍 URL: {presence_url}")
        logger.info(f"📤 Headers: {headers}")
        logger.info(f"📦 Body: {presence_data}")
        logger.info("="*80)
        
        # Enviar request
        response = requests.post(
            presence_url,
            json=presence_data,
            headers=headers,
            timeout=10
        )
        
        # Log da resposta
        logger.info("="*80)
        logger.info(f"📥 [TEST PRESENCE] Resposta recebida")
        logger.info(f"🔢 Status Code: {response.status_code}")
        logger.info(f"📄 Response Headers: {dict(response.headers)}")
        logger.info(f"📦 Response Body: {response.text}")
        logger.info("="*80)
        
        # Preparar resposta
        result = {
            'success': True,
            'request': {
                'url': presence_url,
                'method': 'POST',
                'headers': {
                    'Content-Type': headers['Content-Type'],
                    'apikey': '***' + instance.api_key[-4:] if len(instance.api_key) > 4 else '***'
                },
                'body': presence_data
            },
            'response': {
                'status_code': response.status_code,
                'headers': dict(response.headers),
                'body': response.text
            }
        }
        
        # Tentar parsear JSON
        try:
            result['response']['body_json'] = response.json()
        except:
            pass
        
        return Response(result, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"❌ [TEST PRESENCE] Erro ao testar presença: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        return Response({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTenantMember])
def list_instances_for_test(request):
    """Lista instâncias disponíveis para teste"""
    instances = WhatsAppInstance.objects.filter(
        tenant=request.user.tenant,
        is_active=True
    ).values('id', 'friendly_name', 'instance_name', 'status')
    
    return Response({
        'success': True,
        'instances': list(instances)
    })

