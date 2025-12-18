"""
Views da API de Billing
5 endpoints principais para envio e consulta de campanhas
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.shortcuts import get_object_or_404
from django.db.models import Q
import logging

from apps.billing.billing_api.authentication import BillingAPIKeyAuthentication
from apps.billing.billing_api.throttling import BillingAPIRateThrottle
from apps.billing.billing_api.serializers import (
    SendBillingRequestSerializer,
    SendBillingResponseSerializer,
    BillingCampaignStatusSerializer,
    BillingContactStatusSerializer,
    BillingQueueSerializer
)
from apps.billing.billing_api.services.billing_campaign_service import BillingCampaignService
from apps.billing.billing_api import (
    BillingQueue, BillingCampaign, BillingContact
)

logger = logging.getLogger(__name__)


class SendOverdueView(APIView):
    """
    Endpoint 1: Envia cobrança atrasada
    
    POST /api/v1/billing/send/overdue
    Headers: X-Billing-API-Key: <api_key>
    Body: {
        "template_type": "overdue",
        "contacts": [...],
        "external_id": "fatura-12345",
        "instance_id": "uuid" (opcional)
    }
    """
    
    authentication_classes = [BillingAPIKeyAuthentication]
    throttle_classes = [BillingAPIRateThrottle]
    permission_classes = [AllowAny]  # Autenticação via API Key
    
    def post(self, request):
        """Envia cobrança atrasada"""
        try:
            # Valida request
            serializer = SendBillingRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {
                        'success': False,
                        'message': 'Dados inválidos',
                        'errors': serializer.errors
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Pega tenant da API Key
            api_key = request.auth
            tenant = api_key.tenant
            
            # Verifica se API Key pode usar este tipo
            if not api_key.can_use_template_type('overdue'):
                return Response(
                    {
                        'success': False,
                        'message': 'API Key não autorizada para este tipo de template'
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Cria campanha
            service = BillingCampaignService(tenant)
            success, billing_campaign, message = service.create_billing_campaign(
                template_type='overdue',
                contacts_data=serializer.validated_data['contacts'],
                external_id=serializer.validated_data.get('external_id'),
                instance_id=str(serializer.validated_data.get('instance_id')) if serializer.validated_data.get('instance_id') else None
            )
            
            if not success:
                return Response(
                    {
                        'success': False,
                        'message': message
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Busca queue
            queue = billing_campaign.queue
            
            # Resposta
            response_data = {
                'success': True,
                'message': message,
                'campaign_id': str(billing_campaign.id),
                'queue_id': str(queue.id),
                'total_contacts': queue.total_contacts
            }
            
            logger.info(
                f"✅ [BILLING_API] Campanha overdue criada: {billing_campaign.id} "
                f"({queue.total_contacts} contatos) para tenant {tenant.name}"
            )
            
            return Response(
                response_data,
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(
                f"❌ [BILLING_API] Erro ao criar campanha overdue: {e}",
                exc_info=True
            )
            return Response(
                {
                    'success': False,
                    'message': f'Erro interno: {str(e)}'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SendUpcomingView(APIView):
    """
    Endpoint 2: Envia cobrança a vencer
    
    POST /api/v1/billing/send/upcoming
    """
    
    authentication_classes = [BillingAPIKeyAuthentication]
    throttle_classes = [BillingAPIRateThrottle]
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Envia cobrança a vencer"""
        try:
            serializer = SendBillingRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {
                        'success': False,
                        'message': 'Dados inválidos',
                        'errors': serializer.errors
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            api_key = request.auth
            tenant = api_key.tenant
            
            if not api_key.can_use_template_type('upcoming'):
                return Response(
                    {
                        'success': False,
                        'message': 'API Key não autorizada'
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
            
            service = BillingCampaignService(tenant)
            success, billing_campaign, message = service.create_billing_campaign(
                template_type='upcoming',
                contacts_data=serializer.validated_data['contacts'],
                external_id=serializer.validated_data.get('external_id'),
                instance_id=str(serializer.validated_data.get('instance_id')) if serializer.validated_data.get('instance_id') else None
            )
            
            if not success:
                return Response(
                    {
                        'success': False,
                        'message': message
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            queue = billing_campaign.queue
            
            response_data = {
                'success': True,
                'message': message,
                'campaign_id': str(billing_campaign.id),
                'queue_id': str(queue.id),
                'total_contacts': queue.total_contacts
            }
            
            logger.info(
                f"✅ [BILLING_API] Campanha upcoming criada: {billing_campaign.id} "
                f"({queue.total_contacts} contatos)"
            )
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"❌ [BILLING_API] Erro ao criar campanha upcoming: {e}", exc_info=True)
            return Response(
                {
                    'success': False,
                    'message': f'Erro interno: {str(e)}'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SendNotificationView(APIView):
    """
    Endpoint 3: Envia notificação/aviso
    
    POST /api/v1/billing/send/notification
    """
    
    authentication_classes = [BillingAPIKeyAuthentication]
    throttle_classes = [BillingAPIRateThrottle]
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Envia notificação/aviso (24/7, sem respeitar horário comercial)"""
        try:
            serializer = SendBillingRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {
                        'success': False,
                        'message': 'Dados inválidos',
                        'errors': serializer.errors
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            api_key = request.auth
            tenant = api_key.tenant
            
            if not api_key.can_use_template_type('notification'):
                return Response(
                    {
                        'success': False,
                        'message': 'API Key não autorizada'
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
            
            service = BillingCampaignService(tenant)
            success, billing_campaign, message = service.create_billing_campaign(
                template_type='notification',
                contacts_data=serializer.validated_data['contacts'],
                external_id=serializer.validated_data.get('external_id'),
                instance_id=str(serializer.validated_data.get('instance_id')) if serializer.validated_data.get('instance_id') else None
            )
            
            if not success:
                return Response(
                    {
                        'success': False,
                        'message': message
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            queue = billing_campaign.queue
            
            response_data = {
                'success': True,
                'message': message,
                'campaign_id': str(billing_campaign.id),
                'queue_id': str(queue.id),
                'total_contacts': queue.total_contacts
            }
            
            logger.info(
                f"✅ [BILLING_API] Campanha notification criada: {billing_campaign.id} "
                f"({queue.total_contacts} contatos)"
            )
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"❌ [BILLING_API] Erro ao criar campanha notification: {e}", exc_info=True)
            return Response(
                {
                    'success': False,
                    'message': f'Erro interno: {str(e)}'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class QueueStatusView(APIView):
    """
    Endpoint 4: Consulta status da fila
    
    GET /api/v1/billing/queue/{queue_id}/status
    """
    
    authentication_classes = [BillingAPIKeyAuthentication]
    throttle_classes = [BillingAPIRateThrottle]
    permission_classes = [AllowAny]
    
    def get(self, request, queue_id):
        """Consulta status de uma fila de envio"""
        try:
            api_key = request.auth
            tenant = api_key.tenant
            
            queue = get_object_or_404(
                BillingQueue.objects.select_related(
                    'billing_campaign',
                    'billing_campaign__tenant'
                ),
                id=queue_id,
                billing_campaign__tenant=tenant
            )
            
            serializer = BillingQueueSerializer(queue)
            
            return Response(
                {
                    'success': True,
                    'queue': serializer.data
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"❌ [BILLING_API] Erro ao consultar status da queue {queue_id}: {e}", exc_info=True)
            return Response(
                {
                    'success': False,
                    'message': f'Erro ao consultar status: {str(e)}'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CampaignContactsView(APIView):
    """
    Endpoint 5: Lista contatos de uma campanha
    
    GET /api/v1/billing/campaign/{campaign_id}/contacts
    Query params: ?status=sent&page=1&page_size=50
    """
    
    authentication_classes = [BillingAPIKeyAuthentication]
    throttle_classes = [BillingAPIRateThrottle]
    permission_classes = [AllowAny]
    
    def get(self, request, campaign_id):
        """Lista contatos de uma campanha"""
        try:
            api_key = request.auth
            tenant = api_key.tenant
            
            # Busca campanha
            campaign = get_object_or_404(
                BillingCampaign.objects.select_related('tenant'),
                id=campaign_id,
                tenant=tenant
            )
            
            # Filtros
            status_filter = request.query_params.get('status')
            page = int(request.query_params.get('page', 1))
            page_size = min(int(request.query_params.get('page_size', 50)), 100)
            
            # Query
            contacts_query = BillingContact.objects.filter(
                billing_campaign=campaign
            ).select_related(
                'campaign_contact',
                'campaign_contact__contact',
                'template_variation'
            )
            
            if status_filter:
                contacts_query = contacts_query.filter(status=status_filter)
            
            # Paginação
            total = contacts_query.count()
            start = (page - 1) * page_size
            end = start + page_size
            
            contacts = contacts_query[start:end]
            
            # Serializa
            contacts_data = []
            for contact in contacts:
                contacts_data.append({
                    'contact_id': str(contact.id),
                    'phone': contact.campaign_contact.contact.phone if contact.campaign_contact.contact else '',
                    'name': contact.campaign_contact.contact.name if contact.campaign_contact.contact else '',
                    'status': contact.status,
                    'sent_at': contact.sent_at.isoformat() if contact.sent_at else None,
                    'error_message': contact.billing_data.get('last_error', '') if isinstance(contact.billing_data, dict) else ''
                })
            
            return Response(
                {
                    'success': True,
                    'campaign_id': str(campaign.id),
                    'total': total,
                    'page': page,
                    'page_size': page_size,
                    'contacts': contacts_data
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(
                f"❌ [BILLING_API] Erro ao listar contatos da campanha {campaign_id}: {e}",
                exc_info=True
            )
            return Response(
                {
                    'success': False,
                    'message': f'Erro ao listar contatos: {str(e)}'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

