"""
Views Django puras (não DRF) para endpoints públicos.

Endpoints:
- media_proxy: Proxy universal para mídia (fotos, áudios, docs)
"""
import httpx
import logging
import hashlib
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.cache import cache

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["GET", "HEAD"])
def media_proxy(request):
    """
    Proxy universal para servir mídia (fotos, áudios, documentos).
    
    IMPORTANTE: Este endpoint é PÚBLICO (não requer autenticação)!
    
    Query params:
        url: URL da mídia (S3, WhatsApp, etc)
    
    Headers de resposta:
        X-Cache: HIT (Redis) ou MISS (Download)
        Cache-Control: public, max-age=604800 (7 dias)
        Content-Type: Detectado automaticamente
    
    Fluxo:
        1. Tenta buscar no Redis cache
        2. Se não encontrar, baixa da URL original
        3. Cacheia no Redis (7 dias)
        4. Retorna conteúdo
    """
    # ✅ IMPORTANTE: Django já decodifica URL automaticamente, mas garantir que está correta
    from urllib.parse import unquote
    
    media_url = request.GET.get('url')
    
    if not media_url:
        logger.warning('📦 [MEDIA PROXY] URL não fornecida')
        return JsonResponse({'error': 'URL é obrigatória'}, status=400)
    
    # ✅ Garantir que URL está decodificada (pode vir duplo-encoded)
    try:
        # Se ainda estiver encoded, decodificar
        if '%' in media_url:
            media_url = unquote(media_url)
        # Se ainda tiver caracteres encoded, tentar mais uma vez
        if '%' in media_url:
            media_url = unquote(media_url)
    except Exception as e:
        logger.warning(f'⚠️ [MEDIA PROXY] Erro ao decodificar URL: {e}, usando original')
    
    logger.debug(f'🔍 [MEDIA PROXY] URL recebida (decodificada): {media_url[:100]}...')
    
    # Cache key (hash da URL)
    cache_key = f"media:{hashlib.md5(media_url.encode()).hexdigest()}"
    cached_data = cache.get(cache_key)
    
    # Cache HIT
    if cached_data:
        logger.info(f'✅ [MEDIA PROXY CACHE] Servido do Redis: {media_url[:80]}...')
        
        # Para HEAD request, retornar só headers
        content = b'' if request.method == 'HEAD' else cached_data['content']
        
        response = HttpResponse(
            content,
            content_type=cached_data['content_type']
        )
        response['Cache-Control'] = 'public, max-age=604800'  # 7 dias
        response['Access-Control-Allow-Origin'] = '*'
        response['X-Cache'] = 'HIT'
        response['X-Content-Size'] = len(cached_data['content'])
        response['Content-Length'] = len(cached_data['content'])
        return response
    
    # Cache MISS - Download
    logger.info(f'🔄 [MEDIA PROXY] Baixando mídia: {media_url[:80]}...')
    
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            http_response = client.get(media_url)
            http_response.raise_for_status()
            
            content_type = http_response.headers.get('content-type', 'application/octet-stream')
            content = http_response.content
            
            logger.info(
                f'✅ [MEDIA PROXY] Download concluído! '
                f'Content-Type: {content_type} | Size: {len(content)} bytes'
            )
            
            # Cachear no Redis (7 dias)
            cache.set(
                cache_key,
                {'content': content, 'content_type': content_type},
                timeout=604800  # 7 dias
            )
            logger.info(f'💾 [MEDIA PROXY] Cacheado no Redis: {cache_key}')
            
            # Para HEAD request, retornar só headers
            response_content = b'' if request.method == 'HEAD' else content
            
            response = HttpResponse(response_content, content_type=content_type)
            response['Cache-Control'] = 'public, max-age=604800'
            response['Access-Control-Allow-Origin'] = '*'
            response['X-Cache'] = 'MISS'
            response['X-Content-Size'] = len(content)
            response['Content-Length'] = len(content)
            return response
            
    except httpx.HTTPStatusError as e:
        logger.error(
            f'❌ [MEDIA PROXY] Erro HTTP {e.response.status_code}: {media_url[:80]}...'
        )
        return JsonResponse(
            {'error': f'Erro ao buscar mídia: {e.response.status_code}'},
            status=502
        )
    except httpx.TimeoutException:
        logger.error(f'⏱️ [MEDIA PROXY] Timeout ao baixar: {media_url[:80]}...')
        return JsonResponse({'error': 'Timeout ao baixar mídia'}, status=504)
    except Exception as e:
        logger.error(
            f'❌ [MEDIA PROXY] Erro: {str(e)} | URL: {media_url[:80]}...',
            exc_info=True
        )
        return JsonResponse({'error': f'Erro ao buscar mídia: {str(e)}'}, status=500)


# Alias para compatibilidade (pode ser removido depois)
profile_pic_proxy_django_view = media_proxy
