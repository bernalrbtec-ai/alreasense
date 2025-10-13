"""
Endpoint de teste para verificar se o webhook está funcionando
"""

import json
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from datetime import datetime

logger = logging.getLogger(__name__)


class TestWebhookEndpointView(APIView):
    """
    Endpoint para testar se o webhook está funcionando
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Testa se o endpoint está acessível"""
        try:
            # Verificar se é superuser
            if not request.user.is_superuser:
                return Response({
                    'error': 'Apenas administradores podem acessar esta funcionalidade'
                }, status=status.HTTP_403_FORBIDDEN)
            
            return Response({
                'status': 'success',
                'message': 'Endpoint de webhook está funcionando!',
                'timestamp': timezone.now().isoformat(),
                'webhook_url': f"{request.scheme}://{request.get_host()}/webhooks/evolution/",
                'test_endpoint': f"{request.scheme}://{request.get_host()}/api/connections/webhooks/test/"
            })
            
        except Exception as e:
            logger.error(f"❌ Erro no teste de webhook: {str(e)}")
            return Response({
                'error': 'Erro no teste de webhook',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request):
        """Simula um webhook para teste"""
        try:
            # Verificar se é superuser
            if not request.user.is_superuser:
                return Response({
                    'error': 'Apenas administradores podem acessar esta funcionalidade'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Dados de teste
            test_data = {
                'event': 'test.webhook',
                'instance': 'test_instance',
                'server_url': f"{request.scheme}://{request.get_host()}",
                'data': {
                    'test': True,
                    'timestamp': timezone.now().isoformat(),
                    'message': 'Este é um teste de webhook'
                }
            }
            
            # Log do teste
            logger.info(f"🧪 Teste de webhook executado: {test_data}")
            
            return Response({
                'status': 'success',
                'message': 'Webhook de teste executado com sucesso!',
                'test_data': test_data,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"❌ Erro no teste de webhook: {str(e)}")
            return Response({
                'error': 'Erro no teste de webhook',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
