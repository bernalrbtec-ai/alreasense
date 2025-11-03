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
@require_http_methods(["GET", "HEAD", "OPTIONS"])
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
    # ✅ CORS Preflight: Responder OPTIONS com headers CORS
    if request.method == 'OPTIONS':
        response = HttpResponse()
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, HEAD, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type'
        response['Access-Control-Max-Age'] = '86400'  # 24 horas
        return response
    
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
        content_type = cached_data['content_type']
        
        # ✅ CRUCIAL: Usar HttpResponse com content_type explicitamente
        response = HttpResponse(
            content,
            content_type=content_type,
            status=200
        )
        
        # ✅ CRUCIAL: Definir headers na ordem correta para evitar problemas de CORS
        # 1. Content-Type primeiro
        response['Content-Type'] = content_type
        
        # 2. CORS headers (OBRIGATÓRIOS para evitar OpaqueResponseBlocking)
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, HEAD, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Accept'
        response['Access-Control-Expose-Headers'] = 'Content-Type, Content-Length, X-Cache, X-Content-Size'
        
        # 3. Cache headers
        response['Cache-Control'] = 'public, max-age=604800'  # 7 dias
        
        # 4. Custom headers
        response['X-Cache'] = 'HIT'
        response['X-Content-Size'] = str(len(cached_data['content']))
        response['Content-Length'] = str(len(cached_data['content']))
        
        return response
    
    # Cache MISS - Download
    logger.info(f'🔄 [MEDIA PROXY] Baixando mídia: {media_url[:80]}...')
    
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            http_response = client.get(media_url)
            http_response.raise_for_status()
            
            content_type = http_response.headers.get('content-type', 'application/octet-stream')
            content = http_response.content
            
            # ✅ MELHORIA: Detectar Content-Type baseado na extensão se genérico
            # Isso resolve problema de OpaqueResponseBlocking quando S3 retorna application/octet-stream
            if content_type == 'application/octet-stream' or 'application/octet-stream' in content_type:
                import mimetypes
                from urllib.parse import urlparse, unquote
                
                # Tentar detectar pelo nome do arquivo na URL
                parsed_url = urlparse(unquote(media_url))
                filename = parsed_url.path.split('/')[-1]
                
                if '.' in filename:
                    ext = filename.split('.')[-1].lower()
                    detected_type, _ = mimetypes.guess_type(f'file.{ext}')
                    if detected_type:
                        content_type = detected_type
                        logger.info(f'🔍 [MEDIA PROXY] Content-Type detectado pela extensão: {content_type} (arquivo: {filename})')
                    elif ext in ['jpg', 'jpeg']:
                        content_type = 'image/jpeg'
                    elif ext == 'png':
                        content_type = 'image/png'
                    elif ext == 'gif':
                        content_type = 'image/gif'
                    elif ext == 'webp':
                        content_type = 'image/webp'
                    elif ext == 'mp4':
                        content_type = 'video/mp4'
                    elif ext == 'mp3':
                        content_type = 'audio/mpeg'
                    elif ext == 'pdf':
                        content_type = 'application/pdf'
                
                # Se ainda for genérico, tentar detectar pelo magic number (primeiros bytes)
                if content_type == 'application/octet-stream' and len(content) > 4:
                    if content[:2] == b'\xff\xd8':
                        content_type = 'image/jpeg'
                    elif content[:8] == b'\x89PNG\r\n\x1a\n':
                        content_type = 'image/png'
                    elif content[:6] in [b'GIF87a', b'GIF89a']:
                        content_type = 'image/gif'
                    elif content[:4] == b'RIFF' and content[8:12] == b'WEBP':
                        content_type = 'image/webp'
                    elif content[:4] == b'\x00\x00\x00 ftyp':
                        content_type = 'video/mp4'
                    elif content[:3] == b'\xff\xfb' or content[:2] == b'\xff\xf3':
                        content_type = 'audio/mpeg'
                    elif content[:4] == b'%PDF':
                        content_type = 'application/pdf'
                    
                    if content_type != 'application/octet-stream':
                        logger.info(f'🔍 [MEDIA PROXY] Content-Type detectado pelo magic number: {content_type}')
            
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
            
            # ✅ DEBUG: Log detalhado dos headers sendo enviados (usar WARNING para garantir visibilidade)
            logger.warning(f'📤 [MEDIA PROXY] Preparando resposta HTTP:')
            logger.warning(f'   Content-Type: {content_type}')
            logger.warning(f'   Content-Length: {len(content)}')
            logger.warning(f'   Method: {request.method}')
            logger.warning(f'   User-Agent: {request.META.get("HTTP_USER_AGENT", "N/A")[:100]}')
            
            # ✅ CRUCIAL: Usar HttpResponse com content_type explicitamente
            # Isso garante que o browser reconheça como imagem/vídeo/áudio válido
            response = HttpResponse(
                response_content,
                content_type=content_type,  # ✅ Definir no construtor
                status=200
            )
            
            # ✅ CRUCIAL: Definir headers na ordem correta para evitar problemas de CORS
            # 1. Content-Type primeiro (pode ser sobrescrito, então definir duas vezes)
            response['Content-Type'] = content_type
            
            # 2. CORS headers (OBRIGATÓRIOS para evitar OpaqueResponseBlocking)
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Methods'] = 'GET, HEAD, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Content-Type, Accept'
            response['Access-Control-Expose-Headers'] = 'Content-Type, Content-Length, X-Cache, X-Content-Size'
            
            # 3. Cache headers
            response['Cache-Control'] = 'public, max-age=604800'
            
            # 4. Custom headers
            response['X-Cache'] = 'MISS'
            response['X-Content-Size'] = str(len(content))
            response['Content-Length'] = str(len(content))
            
            # ✅ DEBUG: Verificar headers finais (usar WARNING para garantir visibilidade)
            logger.warning(f'📤 [MEDIA PROXY] Headers finais da resposta:')
            for key, value in response.items():
                if key.lower() in ['content-type', 'content-length', 'cache-control', 'access-control-allow-origin', 'access-control-expose-headers', 'access-control-allow-methods']:
                    logger.warning(f'   {key}: {value}')
            
            # ✅ CRUCIAL: Verificar se Content-Type foi definido corretamente
            if response.get('Content-Type') != content_type:
                logger.error(f'❌ [MEDIA PROXY] Content-Type não corresponde! Esperado: {content_type}, Atual: {response.get("Content-Type")}')
                # Forçar correção
                response['Content-Type'] = content_type
            
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
