"""
Views Django puras (sem DRF) para endpoints públicos.
"""
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.cache import cache
import httpx
import logging
import hashlib


logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["GET"])
def profile_pic_proxy_django_view(request):
    """
    Proxy PÚBLICO para fotos de perfil do WhatsApp com cache Redis.
    
    Esta é uma view Django PURA (não DRF) para evitar a autenticação global do DRF.
    
    Query params:
    - url: URL da foto de perfil do WhatsApp
    """
    profile_url = request.GET.get('url')
    
    if not profile_url:
        logger.warning('🖼️ [PROXY] URL não fornecida')
        return JsonResponse(
            {'error': 'URL é obrigatória'},
            status=400
        )
    
    # Gerar chave Redis baseada na URL
    cache_key = f"profile_pic:{hashlib.md5(profile_url.encode()).hexdigest()}"
    
    # Tentar buscar do cache Redis
    cached_data = cache.get(cache_key)
    
    if cached_data:
        logger.info(f'✅ [PROXY CACHE] Imagem servida do Redis: {profile_url[:80]}...')
        
        response = HttpResponse(
            cached_data['content'],
            content_type=cached_data['content_type']
        )
        response['Cache-Control'] = 'public, max-age=604800'  # 7 dias
        response['Access-Control-Allow-Origin'] = '*'
        response['X-Cache'] = 'HIT'
        
        return response
    
    # Não está no cache, buscar do WhatsApp
    logger.info(f'🔄 [PROXY] Baixando imagem do WhatsApp: {profile_url[:80]}...')
    
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            http_response = client.get(profile_url)
            http_response.raise_for_status()
            
            content_type = http_response.headers.get('content-type', 'image/jpeg')
            content = http_response.content
            
            logger.info(f'✅ [PROXY] Imagem baixada! Content-Type: {content_type} | Size: {len(content)} bytes')
            
            # Cachear no Redis por 7 dias
            cache.set(
                cache_key,
                {
                    'content': content,
                    'content_type': content_type
                },
                timeout=604800  # 7 dias
            )
            
            logger.info(f'💾 [PROXY] Imagem cacheada no Redis com chave: {cache_key}')
            
            # Retornar imagem
            response = HttpResponse(
                content,
                content_type=content_type
            )
            response['Cache-Control'] = 'public, max-age=604800'  # 7 dias
            response['Access-Control-Allow-Origin'] = '*'
            response['X-Cache'] = 'MISS'
            
            return response
    
    except httpx.HTTPStatusError as e:
        logger.error(f'❌ [PROXY] Erro HTTP {e.response.status_code}: {profile_url[:80]}...')
        return JsonResponse(
            {'error': f'Erro ao buscar imagem: {e.response.status_code}'},
            status=502
        )
    except Exception as e:
        logger.error(f'❌ [PROXY] Erro: {str(e)} | URL: {profile_url[:80]}...', exc_info=True)
        return JsonResponse(
            {'error': f'Erro ao buscar imagem: {str(e)}'},
            status=500
        )

