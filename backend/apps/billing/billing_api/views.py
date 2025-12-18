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
)
from apps.billing.billing_api.services.billing_campaign_service import BillingCampaignService

logger = logging.getLogger(__name__)


class SendOverdueView(APIView):
    """
    Endpoint 1: Envia cobrança atrasada
    
    POST /api/v1/billing/send/overdue
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
                # Para mensagens de ciclo, pode não ter campaign_contact
                if contact.campaign_contact and contact.campaign_contact.contact:
                    phone = contact.campaign_contact.contact.phone
                    name = contact.campaign_contact.contact.name
                elif contact.billing_cycle:
                    # Mensagem de ciclo: usa dados do ciclo
                    phone = contact.billing_cycle.contact_phone
                    name = contact.billing_cycle.contact_name
                else:
                    phone = ''
                    name = ''
                
                contacts_data.append({
                    'contact_id': str(contact.id),
                    'phone': phone,
                    'name': name,
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


class SendBatchView(APIView):
    """
    Endpoint para envio em lote de cobranças com ciclo de mensagens
    
    POST /billing/v1/billing/send/batch
    {
        "contacts": [
            {
                "external_billing_id": "BILL-001",
                "contact_phone": "+5511999999999",
                "contact_name": "João Silva",
                "due_date": "2025-01-15",
                "billing_data": {
                    "value": 100.00,
                    "link_payment": "https://...",
                    "pix_code": "..."
                },
                "notify_before_due": true,
                "notify_after_due": true
            }
        ]
    }
    """
    authentication_classes = [BillingAPIKeyAuthentication]
    throttle_classes = [BillingAPIRateThrottle]
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Cria ciclos de mensagens em lote"""
        try:
            # Valida request
            contacts_data = request.data.get('contacts', [])
            
            if not contacts_data or not isinstance(contacts_data, list):
                return Response(
                    {
                        'success': False,
                        'message': 'Lista de contatos é obrigatória'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if len(contacts_data) > 10000:
                return Response(
                    {
                        'success': False,
                        'message': 'Máximo de 10000 contatos por requisição'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Pega tenant da API Key
            api_key = request.auth
            tenant = api_key.tenant
            
            # Importa service
            from apps.billing.billing_api.services.billing_cycle_service import BillingCycleService
            from datetime import datetime, date
            
            # Processa cada contato
            results = []
            errors = []
            
            for idx, contact_data in enumerate(contacts_data):
                try:
                    # Valida campos obrigatórios
                    external_id = contact_data.get('external_billing_id')
                    phone = contact_data.get('contact_phone')
                    name = contact_data.get('contact_name')
                    due_date_str = contact_data.get('due_date')
                    billing_data = contact_data.get('billing_data', {})
                    
                    # Valida campos obrigatórios
                    if not external_id or not isinstance(external_id, str) or len(external_id.strip()) == 0:
                        errors.append({
                            'index': idx,
                            'external_billing_id': external_id,
                            'error': 'external_billing_id é obrigatório e deve ser uma string não vazia'
                        })
                        continue
                    
                    if not phone or not isinstance(phone, str):
                        errors.append({
                            'index': idx,
                            'external_billing_id': external_id,
                            'error': 'contact_phone é obrigatório e deve ser uma string'
                        })
                        continue
                    
                    if not name or not isinstance(name, str) or len(name.strip()) == 0:
                        errors.append({
                            'index': idx,
                            'external_billing_id': external_id,
                            'error': 'contact_name é obrigatório e deve ser uma string não vazia'
                        })
                        continue
                    
                    if not due_date_str or not isinstance(due_date_str, str):
                        errors.append({
                            'index': idx,
                            'external_billing_id': external_id,
                            'error': 'due_date é obrigatório e deve ser uma string no formato YYYY-MM-DD'
                        })
                        continue
                    
                    # Valida billing_data
                    if billing_data and not isinstance(billing_data, dict):
                        errors.append({
                            'index': idx,
                            'external_billing_id': external_id,
                            'error': 'billing_data deve ser um objeto JSON'
                        })
                        continue
                    
                    if not billing_data:
                        billing_data = {}
                    
                    # Parse data com validação
                    try:
                        due_date = datetime.strptime(due_date_str.strip(), '%Y-%m-%d').date()
                        
                        # Valida se data não é muito antiga (mais de 1 ano) ou muito futura (mais de 1 ano)
                        from datetime import date as date_class
                        today = date_class.today()
                        one_year_ago = date_class(today.year - 1, today.month, today.day)
                        one_year_ahead = date_class(today.year + 1, today.month, today.day)
                        
                        if due_date < one_year_ago:
                            errors.append({
                                'index': idx,
                                'external_billing_id': external_id,
                                'error': f'Data de vencimento muito antiga: {due_date_str}'
                            })
                            continue
                        
                        if due_date > one_year_ahead:
                            errors.append({
                                'index': idx,
                                'external_billing_id': external_id,
                                'error': f'Data de vencimento muito futura: {due_date_str}'
                            })
                            continue
                            
                    except ValueError as e:
                        errors.append({
                            'index': idx,
                            'external_billing_id': external_id,
                            'error': f'Data inválida: {due_date_str}. Use formato YYYY-MM-DD. Erro: {str(e)}'
                        })
                        continue
                    
                    # Cria ciclo
                    cycle = BillingCycleService.create_cycle(
                        tenant=tenant,
                        external_billing_id=external_id,
                        contact_phone=phone,
                        contact_name=name,
                        due_date=due_date,
                        billing_data=billing_data,
                        notify_before_due=contact_data.get('notify_before_due', False),
                        notify_after_due=contact_data.get('notify_after_due', True)
                    )
                    
                    # Agenda mensagens
                    BillingCycleService.schedule_cycle_messages(cycle)
                    
                    results.append({
                        'external_billing_id': external_id,
                        'cycle_id': str(cycle.id),
                        'status': 'created',
                        'total_messages': cycle.total_messages
                    })
                    
                except Exception as e:
                    logger.error(
                        f"❌ Erro ao processar contato {idx}: {e}",
                        exc_info=True,
                        extra={'contact_data': contact_data}
                    )
                    errors.append({
                        'index': idx,
                        'external_billing_id': contact_data.get('external_billing_id'),
                        'error': str(e)
                    })
            
            # Resposta
            response_data = {
                'success': True,
                'total_processed': len(contacts_data),
                'created': len(results),
                'errors': len(errors),
                'results': results
            }
            
            if errors:
                response_data['error_details'] = errors
            
            logger.info(
                f"✅ [BILLING_API] Batch processado: {len(results)} criados, {len(errors)} erros",
                extra={'tenant_id': str(tenant.id), 'total': len(contacts_data)}
            )
            
            return Response(
                response_data,
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(
                f"❌ [BILLING_API] Erro ao processar batch: {e}",
                exc_info=True
            )
            return Response(
                {
                    'success': False,
                    'message': f'Erro interno: {str(e)}'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CancelCycleView(APIView):
    """
    Endpoint para cancelar ciclo de mensagens (pagamento ou cancelamento)
    
    POST /billing/v1/billing/cancel
    {
        "external_billing_id": "BILL-001",
        "reason": "paid"  // ou "cancelled"
    }
    """
    authentication_classes = [BillingAPIKeyAuthentication]
    throttle_classes = [BillingAPIRateThrottle]
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Cancela ciclo de mensagens"""
        try:
            # Valida request
            external_id = request.data.get('external_billing_id')
            reason = request.data.get('reason', 'cancelled')
            
            if not external_id:
                return Response(
                    {
                        'success': False,
                        'message': 'external_billing_id é obrigatório'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if reason not in ['paid', 'cancelled']:
                return Response(
                    {
                        'success': False,
                        'message': 'reason deve ser "paid" ou "cancelled"'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Pega tenant da API Key
            api_key = request.auth
            tenant = api_key.tenant
            
            # Importa service
            from apps.billing.billing_api.services.billing_cycle_service import BillingCycleService
            
            # Cancela ciclo
            cycle = BillingCycleService.cancel_cycle(
                tenant=tenant,
                external_billing_id=external_id,
                reason=reason
            )
            
            if not cycle:
                return Response(
                    {
                        'success': False,
                        'message': f'Ciclo não encontrado: {external_id}'
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
            
            logger.info(
                f"✅ [BILLING_API] Ciclo cancelado: {external_id} ({reason})",
                extra={'cycle_id': str(cycle.id), 'tenant_id': str(tenant.id)}
            )
            
            return Response(
                {
                    'success': True,
                    'message': f'Ciclo {reason} com sucesso',
                    'cycle_id': str(cycle.id),
                    'external_billing_id': external_id,
                    'status': cycle.status
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(
                f"❌ [BILLING_API] Erro ao cancelar ciclo: {e}",
                exc_info=True
            )
            return Response(
                {
                    'success': False,
                    'message': f'Erro interno: {str(e)}'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

