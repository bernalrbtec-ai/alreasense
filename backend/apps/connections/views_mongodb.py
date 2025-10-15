from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import datetime, timedelta
import logging
from .webhook_views import mongodb_client

logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def webhook_events_stats(request):
    """Retorna estatísticas dos eventos salvos no MongoDB"""
    try:
        stats = mongodb_client.get_event_stats()
        
        return Response({
            'success': True,
            'stats': stats,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"❌ [MONGODB_STATS] Erro: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def webhook_events_list(request):
    """Lista eventos salvos no MongoDB"""
    try:
        # Parâmetros de filtro
        event_type = request.GET.get('event_type')
        status_filter = request.GET.get('status', 'processed')
        limit = int(request.GET.get('limit', 50))
        
        # Buscar eventos
        query = {}
        if event_type:
            query['event_type'] = event_type
        if status_filter:
            query['status'] = status_filter
        
        try:
            events = list(mongodb_client.collection.find(query)
                         .sort('created_at', -1)
                         .limit(limit))
            
            # Converter ObjectId para string
            for event in events:
                event['_id'] = str(event['_id'])
                if 'created_at' in event:
                    event['created_at'] = event['created_at'].isoformat()
                if 'processed_at' in event and event['processed_at']:
                    event['processed_at'] = event['processed_at'].isoformat()
            
            return Response({
                'success': True,
                'events': events,
                'count': len(events),
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"❌ [MONGODB_QUERY] Erro na consulta: {e}")
            return Response({
                'success': False,
                'error': f'Erro na consulta MongoDB: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except Exception as e:
        logger.error(f"❌ [MONGODB_LIST] Erro: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reprocess_webhook_event(request):
    """Reprocessa um evento específico do MongoDB"""
    try:
        event_id = request.data.get('event_id')
        if not event_id:
            return Response({
                'success': False,
                'error': 'event_id é obrigatório'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Buscar evento no MongoDB
        event = mongodb_client.collection.find_one({'event_id': event_id})
        if not event:
            return Response({
                'success': False,
                'error': 'Evento não encontrado'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Reprocessar evento (simular chamada do webhook)
        from .webhook_views import EvolutionWebhookView
        webhook_view = EvolutionWebhookView()
        
        # Processar baseado no tipo de evento
        event_type = event.get('event_type')
        raw_payload = event.get('raw_payload', {})
        
        if event_type == 'messages.update':
            # Reprocessar atualização de status
            result = webhook_view.handle_message_update(raw_payload)
            logger.info(f"✅ [REPROCESS] Evento {event_id} reprocessado: {event_type}")
            
        elif event_type == 'messages.upsert':
            # Reprocessar mensagem
            result = webhook_view.handle_message_upsert(raw_payload)
            logger.info(f"✅ [REPROCESS] Evento {event_id} reprocessado: {event_type}")
            
        else:
            logger.info(f"ℹ️ [REPROCESS] Tipo de evento não suportado para reprocessamento: {event_type}")
            result = {'status': 'ignored', 'reason': 'tipo_nao_suportado'}
        
        return Response({
            'success': True,
            'message': f'Evento {event_id} reprocessado com sucesso',
            'event_type': event_type,
            'result': result
        })
        
    except Exception as e:
        logger.error(f"❌ [REPROCESS] Erro: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
