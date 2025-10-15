from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
import logging
from .webhook_views import mongodb_client

logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["GET"])
def test_mongodb_connection(request):
    """Testa conexão MongoDB - endpoint público para debug"""
    try:
        # Testar conexão
        mongo_status = mongodb_client.connect()
        
        if mongo_status:
            # Tentar buscar estatísticas
            stats = mongodb_client.get_event_stats()
            
            # Tentar inserir um documento de teste
            test_doc = {
                "test": True,
                "timestamp": timezone.now(),
                "source": "test_endpoint",
                "message": "Teste de conexão MongoDB"
            }
            
            test_id = mongodb_client.insert_webhook_event(test_doc)
            
            return JsonResponse({
                "status": "success",
                "message": "MongoDB conectado com sucesso!",
                "connection": "ok",
                "stats": stats,
                "test_insert_id": str(test_id) if test_id else None,
                "timestamp": timezone.now().isoformat()
            })
        else:
            return JsonResponse({
                "status": "error",
                "message": "Erro na conexão MongoDB",
                "connection": "failed",
                "timestamp": timezone.now().isoformat()
            }, status=500)
            
    except Exception as e:
        logger.error(f"❌ [MONGO_TEST] Erro: {e}")
        return JsonResponse({
            "status": "error",
            "message": f"Erro ao testar MongoDB: {str(e)}",
            "connection": "error",
            "timestamp": timezone.now().isoformat()
        }, status=500)

@csrf_exempt
@require_http_methods(["GET"])
def test_mongodb_events(request):
    """Lista eventos MongoDB - endpoint público para debug"""
    try:
        # Buscar últimos 10 eventos
        events = list(mongodb_client.collection.find({})
                     .sort('created_at', -1)
                     .limit(10))
        
        # Converter ObjectId para string
        for event in events:
            event['_id'] = str(event['_id'])
            if 'created_at' in event:
                event['created_at'] = event['created_at'].isoformat()
            if 'processed_at' in event and event['processed_at']:
                event['processed_at'] = event['processed_at'].isoformat()
        
        return JsonResponse({
            "status": "success",
            "message": f"Encontrados {len(events)} eventos",
            "events": events,
            "timestamp": timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"❌ [MONGO_EVENTS] Erro: {e}")
        return JsonResponse({
            "status": "error",
            "message": f"Erro ao buscar eventos: {str(e)}",
            "timestamp": timezone.now().isoformat()
        }, status=500)
