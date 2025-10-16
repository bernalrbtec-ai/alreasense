from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
import os

@csrf_exempt
@require_http_methods(["GET"])
def debug_mongodb_env(request):
    """Debug das variáveis de ambiente MongoDB - endpoint público"""
    try:
        # Verificar variáveis de ambiente
        env_vars = {
            'MONGOHOST': os.getenv('MONGOHOST', 'NOT_SET'),
            'MONGOPORT': os.getenv('MONGOPORT', 'NOT_SET'),
            'MONGOUSER': os.getenv('MONGOUSER', 'NOT_SET'),
            'MONGOPASSWORD': os.getenv('MONGOPASSWORD', 'NOT_SET'),
            'MONGO_URL': os.getenv('MONGO_URL', 'NOT_SET'),
            'MONGO_INITDB_ROOT_PASSWORD': os.getenv('MONGO_INITDB_ROOT_PASSWORD', 'NOT_SET'),
        }
        
        # Verificar configuração Django
        django_config = {
            'MONGO_CONFIG': getattr(settings, 'MONGO_CONFIG', 'NOT_SET'),
            'MONGO_URL': getattr(settings, 'MONGO_URL', 'NOT_SET'),
        }
        
        # Construir URL manualmente
        manual_url = f"mongodb://{env_vars['MONGOUSER']}:{env_vars['MONGOPASSWORD']}@{env_vars['MONGOHOST']}:{env_vars['MONGOPORT']}/alreasense_webhooks"
        
        return JsonResponse({
            "status": "success",
            "environment_variables": env_vars,
            "django_settings": django_config,
            "manual_url": manual_url,
            "password_length": len(env_vars['MONGOPASSWORD']) if env_vars['MONGOPASSWORD'] != 'NOT_SET' else 0,
            "message": "Variáveis de ambiente MongoDB"
        })
        
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": f"Erro ao verificar variáveis: {str(e)}"
        }, status=500)
