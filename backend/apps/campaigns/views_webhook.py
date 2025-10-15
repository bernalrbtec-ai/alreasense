from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.conf import settings
import json
import logging
from .mongodb_client import mongodb_client
from .rabbitmq_webhook import send_webhook_to_rabbitmq

logger = logging.getLogger(__name__)

@csrf_exempt
@require_POST
def whatsapp_webhook(request):
    """Recebe webhooks do WhatsApp e salva no MongoDB + envia para RabbitMQ"""
    try:
        # Parse do payload
        payload = json.loads(request.body)
        logger.info(f"📡 [WEBHOOK] Recebido: {payload}")
        
        # Extrair dados do webhook
        event_data = {
            "timestamp": timezone.now(),
            "tenant_id": getattr(request, 'tenant', {}).get('id') if hasattr(request, 'tenant') else None,
            "campaign_id": None,  # Será preenchido no processamento
            "contact_phone": None,
            "whatsapp_message_id": None,
            "event_type": None,
            "status": "pending",
            "raw_payload": payload,
            "processed_at": None,
            "created_at": timezone.now(),
            "retry_count": 0,
            "error_message": None
        }
        
        # Processar diferentes tipos de webhook
        events_created = []
        
        if 'entry' in payload:
            for entry in payload['entry']:
                if 'changes' in entry:
                    for change in entry['changes']:
                        if 'value' in change:
                            value = change['value']
                            
                            # Status de mensagem
                            if 'statuses' in value:
                                for status in value['statuses']:
                                    event_data.update({
                                        "contact_phone": status.get('recipient_id'),
                                        "whatsapp_message_id": status.get('id'),
                                        "event_type": status.get('status')
                                    })
                                    
                                    # Salvar no MongoDB
                                    event_id = mongodb_client.insert_webhook_event(event_data.copy())
                                    if event_id:
                                        events_created.append(event_id)
                                        
                                        # Enviar para RabbitMQ para processamento
                                        send_webhook_to_rabbitmq({
                                            '_id': str(event_id),
                                            **event_data
                                        })
        
        logger.info(f"✅ [WEBHOOK] {len(events_created)} eventos criados")
        
        return JsonResponse({
            "status": "success", 
            "message": f"{len(events_created)} eventos processados",
            "events_created": len(events_created)
        })
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ [WEBHOOK] Erro no JSON: {e}")
        return JsonResponse({"status": "error", "message": "JSON inválido"}, status=400)
        
    except Exception as e:
        logger.error(f"❌ [WEBHOOK] Erro ao processar: {e}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

@csrf_exempt
@require_POST
def webhook_health(request):
    """Endpoint de saúde para webhooks"""
    try:
        # Testar conexão MongoDB
        mongo_status = mongodb_client.connect()
        
        # Testar RabbitMQ (implementar depois)
        rabbitmq_status = True  # TODO: implementar teste
        
        return JsonResponse({
            "status": "healthy" if mongo_status and rabbitmq_status else "unhealthy",
            "mongodb": "connected" if mongo_status else "disconnected",
            "rabbitmq": "connected" if rabbitmq_status else "disconnected",
            "timestamp": timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"❌ [WEBHOOK_HEALTH] Erro: {e}")
        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=500)
