"""
Views Django puras (não DRF) para endpoints públicos.

Endpoints:
- media_proxy: Proxy universal para mídia (fotos, áudios, docs)
"""
import httpx
import logging
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["GET", "HEAD", "OPTIONS"])
def media_proxy(request):
    """
    Proxy universal para servir mídia (fotos, áudios, documentos).
    
    IMPORTANTE: Este endpoint é PÚBLICO (não requer autenticação)!
    
    Volume de requisições: listas (contatos, conversas) carregam uma imagem por item
    via este proxy; dezenas de GET em sequência são esperados, não indicam ataque.
    
    Query params:
        url: URL da mídia (WhatsApp, etc) - para URLs externas
        s3_path: Caminho no S3 (ex: chat/{tenant_id}/attachments/{uuid}.jpg) - para nosso S3
    
    Headers de resposta:
        X-Cache: DIRECT (Download direto - sem cache)
        Cache-Control: public, max-age=604800 (7 dias)
        Content-Type: Detectado automaticamente
    
    Fluxo:
        1. Baixa direto da URL original (S3, WhatsApp, etc)
        2. Retorna conteúdo
    """
    # ✅ CORS Preflight: Responder OPTIONS com headers CORS
    if request.method == 'OPTIONS':
        response = HttpResponse()
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, HEAD, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type'
        response['Access-Control-Max-Age'] = '86400'  # 24 horas
        return response
    
    # ✅ CORREÇÃO: Verificar se é S3 nosso ou URL externa
    s3_path = request.GET.get('s3_path')
    media_url = request.GET.get('url')
    
    if not s3_path and not media_url:
        logger.warning('📦 [MEDIA PROXY] Parâmetro não fornecido (s3_path ou url)')
        return JsonResponse({'error': 's3_path ou url é obrigatório'}, status=400)
    
    # ✅ Se for S3 nosso, acessar diretamente usando boto3
    if s3_path:
        logger.info(f'📦 [MEDIA PROXY] Acessando S3 diretamente: {s3_path}')
        try:
            from apps.chat.utils.s3 import get_s3_manager
            s3_manager = get_s3_manager()
            
            # ✅ NOVO: Verificar se arquivo existe no S3 antes de tentar baixar
            if not s3_manager.file_exists(s3_path):
                logger.warning(f'⚠️ [MEDIA PROXY] Arquivo não existe no S3: {s3_path}')
                return JsonResponse({
                    'error': 'Arquivo indisponível',
                    'message': 'O anexo não está mais disponível no servidor. Pode ter sido removido ou expirado.',
                    's3_path': s3_path
                }, status=404)
            
            # Baixar do S3 usando boto3 (com credenciais do Django)
            success, content, msg = s3_manager.download_from_s3(s3_path)
            
            if not success:
                logger.error(f'❌ [MEDIA PROXY] Erro ao baixar do S3: {msg}')
                return JsonResponse({
                    'error': 'Arquivo indisponível',
                    'message': 'O anexo não está mais disponível no servidor. Pode ter sido removido ou expirado.',
                    's3_path': s3_path
                }, status=404)
            
            # Detectar Content-Type baseado na extensão
            from urllib.parse import unquote
            import mimetypes
            
            filename = s3_path.split('/')[-1]
            if '.' in filename:
                ext = filename.split('.')[-1].lower()
                detected_type, _ = mimetypes.guess_type(f'file.{ext}')
                if detected_type:
                    content_type = detected_type
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
                elif ext == 'xlsx':
                    content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                elif ext == 'xls':
                    content_type = 'application/vnd.ms-excel'
                elif ext == 'docx':
                    content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                elif ext == 'doc':
                    content_type = 'application/msword'
                elif ext == 'pptx':
                    content_type = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
                elif ext == 'ppt':
                    content_type = 'application/vnd.ms-powerpoint'
                else:
                    content_type = 'application/octet-stream'
            else:
                content_type = 'application/octet-stream'
            
            # Detectar pelo magic number se ainda for genérico
            if content_type == 'application/octet-stream' and len(content) > 4:
                if content[:2] == b'\xff\xd8':
                    content_type = 'image/jpeg'
                elif content[:8] == b'\x89PNG\r\n\x1a\n':
                    content_type = 'image/png'
                elif content[:6] in [b'GIF87a', b'GIF89a']:
                    content_type = 'image/gif'
                elif content[:4] == b'RIFF' and content[8:12] == b'WEBP':
                    content_type = 'image/webp'
            
            logger.info(f'✅ [MEDIA PROXY] Download do S3 concluído!')
            logger.info(f'   📦 [MEDIA PROXY] S3 Path: {s3_path}')
            logger.info(f'   📄 [MEDIA PROXY] Content-Type: {content_type}')
            logger.info(f'   📏 [MEDIA PROXY] Size: {len(content)} bytes ({len(content) / 1024:.2f} KB)')
            
            # ✅ CRUCIAL: Validar que o conteúdo é bytes válido
            if not isinstance(content, bytes):
                logger.error(f'❌ [MEDIA PROXY] Content não é bytes! Tipo: {type(content)}')
                return JsonResponse({'error': 'Erro ao processar conteúdo do S3'}, status=500)
            
            # ✅ Validar que o conteúdo não está vazio
            if len(content) == 0:
                logger.error(f'❌ [MEDIA PROXY] Content está vazio!')
                return JsonResponse({'error': 'Arquivo vazio no S3'}, status=404)
            
            # ✅ Validar magic numbers para imagens (primeiros bytes)
            if content_type.startswith('image/'):
                if len(content) < 4:
                    logger.error(f'❌ [MEDIA PROXY] Content muito pequeno para ser uma imagem!')
                    return JsonResponse({'error': 'Arquivo corrompido'}, status=500)
                logger.info(f'   🔍 [MEDIA PROXY] Primeiros bytes (hex): {content[:16].hex()}')
            
        except Exception as e:
            logger.error(f'❌ [MEDIA PROXY] Erro ao acessar S3: {e}', exc_info=True)
            return JsonResponse({'error': f'Erro ao acessar S3: {str(e)}'}, status=500)
    
    # ✅ Se for URL externa (WhatsApp, etc), baixar via HTTP
    else:
        from urllib.parse import unquote
        
        # ✅ Garantir que URL está decodificada (pode vir duplo-encoded)
        try:
            if '%' in media_url:
                media_url = unquote(media_url)
            if '%' in media_url:
                media_url = unquote(media_url)
        except Exception as e:
            logger.warning(f'⚠️ [MEDIA PROXY] Erro ao decodificar URL: {e}, usando original')
        
        logger.info(f'🔄 [MEDIA PROXY] Baixando mídia externa:')
        logger.info(f'   🔗 [MEDIA PROXY] URL completa: {media_url}')
        logger.info(f'   📌 [MEDIA PROXY] Método: {request.method}')
        logger.info(f'   📌 [MEDIA PROXY] User-Agent: {request.META.get("HTTP_USER_AGENT", "N/A")[:100]}')
        
        try:
            # ✅ CORREÇÃO CRÍTICA: Headers para URLs do WhatsApp (pps.whatsapp.net)
            # URLs do WhatsApp exigem headers específicos para evitar 403 Forbidden
            headers = {}
            
            # Detectar se é URL do WhatsApp
            is_whatsapp_url = 'pps.whatsapp.net' in media_url or 'whatsapp.net' in media_url
            
            if is_whatsapp_url:
                # Headers que simulam um navegador real acessando WhatsApp
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Referer': 'https://web.whatsapp.com/',
                    'Origin': 'https://web.whatsapp.com',
                    'Sec-Fetch-Dest': 'image',
                    'Sec-Fetch-Mode': 'no-cors',
                    'Sec-Fetch-Site': 'cross-site',
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache',
                }
                logger.info(f'📱 [MEDIA PROXY] Detectada URL do WhatsApp - usando headers específicos')
            else:
                # Para outras URLs, usar headers mais simples
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': '*/*',
                }
            
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                http_response = client.get(media_url, headers=headers)
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
                    elif ext == 'xlsx':
                        content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    elif ext == 'xls':
                        content_type = 'application/vnd.ms-excel'
                    elif ext == 'docx':
                        content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                    elif ext == 'doc':
                        content_type = 'application/msword'
                    elif ext == 'pptx':
                        content_type = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
                    elif ext == 'ppt':
                        content_type = 'application/vnd.ms-powerpoint'
                
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
            
            logger.info(f'✅ [MEDIA PROXY] Download externo concluído!')
            logger.info(f'   🔗 [MEDIA PROXY] URL original: {media_url}')
            logger.info(f'   📄 [MEDIA PROXY] Content-Type: {content_type}')
            logger.info(f'   📏 [MEDIA PROXY] Size: {len(content)} bytes ({len(content) / 1024:.2f} KB)')
            logger.info(f'   ✅ [MEDIA PROXY] Status: 200 OK')
            
        except httpx.HTTPStatusError as e:
            # 403/404 do upstream (ex.: WhatsApp bloqueia requests de servidor) = tratar como
            # "mídia indisponível" e retornar 404 para o frontend exibir placeholder (não 502).
            if e.response.status_code in (403, 404):
                logger.warning(
                    '⚠️ [MEDIA PROXY] Mídia indisponível (upstream %s): %s...',
                    e.response.status_code,
                    media_url[:80],
                )
                return JsonResponse(
                    {'error': 'Imagem indisponível', 'code': 'upstream_forbidden'},
                    status=404,
                )
            logger.error(
                f'❌ [MEDIA PROXY] Erro HTTP {e.response.status_code}: {media_url[:80]}...'
            )
            return JsonResponse(
                {'error': f'Erro ao buscar mídia: {e.response.status_code}'},
                status=502,
            )
        except httpx.TimeoutException:
            logger.error(f'⏱️ [MEDIA PROXY] Timeout ao baixar: {media_url[:80]}...')
            return JsonResponse({'error': 'Timeout ao baixar mídia'}, status=504)
        except Exception as e:
            logger.error(f'❌ [MEDIA PROXY] Erro ao baixar URL externa: {e}', exc_info=True)
            return JsonResponse({'error': f'Erro ao buscar mídia: {str(e)}'}, status=500)
    
    # ✅ Resposta comum para S3 e URL externa (após ambos os blocos)
    try:
        # ✅ DEBUG: Log detalhado dos headers sendo enviados (usar WARNING para garantir visibilidade)
        logger.warning(f'📤 [MEDIA PROXY] Preparando resposta HTTP:')
        logger.warning(f'   Content-Type: {content_type}')
        logger.warning(f'   Content-Length: {len(content)}')
        logger.warning(f'   Method: {request.method}')
        logger.warning(f'   User-Agent: {request.META.get("HTTP_USER_AGENT", "N/A")[:100]}')
        
        # ✅ CRUCIAL: Usar HttpResponse direto (simples e eficiente)
        # StreamingHttpResponse pode causar problemas com CORS em alguns browsers
        # Para HEAD requests, retornar HttpResponse vazio
        if request.method == 'HEAD':
            response = HttpResponse(status=200, content_type=content_type)
        else:
            # ✅ CRUCIAL: Usar HttpResponse com content como bytes explicitamente
            # Garante que o conteúdo binário seja enviado corretamente sem encoding
            # IMPORTANTE: Não usar str() ou .encode() no content - já é bytes!
            response = HttpResponse(
                content,  # ✅ Já é bytes do S3
                content_type=content_type,
                status=200
            )
            # ✅ CRUCIAL: Garantir que não há charset sendo aplicado (imagens são binárias)
            if 'charset' in response.get('Content-Type', ''):
                # Remover charset se foi adicionado automaticamente
                response['Content-Type'] = content_type
        
        # ✅ CRUCIAL: Definir headers na ordem correta para evitar problemas de CORS
        # 1. Content-Type primeiro (pode ser sobrescrito, então definir duas vezes)
        response['Content-Type'] = content_type
        
        # 2. CORS headers (OBRIGATÓRIOS para evitar OpaqueResponseBlocking)
        # ✅ IMPORTANTE: Não usar '*' com credenciais, mas este endpoint não usa credenciais
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, HEAD, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Accept, Range'
        response['Access-Control-Expose-Headers'] = 'Content-Type, Content-Length, X-Cache, X-Content-Size, Accept-Ranges'
        # ✅ CRUCIAL: Não definir Access-Control-Allow-Credentials se usar '*'
        # response['Access-Control-Allow-Credentials'] = 'true'  # NÃO USAR com '*'
        
        # 3. Cache headers
        response['Cache-Control'] = 'public, max-age=604800'
        
        # 4. Content-Disposition para documentos (forçar download)
        # ✅ NOVO: Adicionar Content-Disposition para arquivos que devem ser baixados
        # Extrair nome do arquivo do s3_path ou media_url
        filename = None
        if s3_path:
            filename = s3_path.split('/')[-1]
        elif media_url:
            from urllib.parse import urlparse, unquote
            parsed = urlparse(unquote(media_url))
            filename = parsed.path.split('/')[-1]
        
        # Se for documento (não imagem/vídeo/áudio), adicionar Content-Disposition
        is_document = (
            content_type.startswith('application/') and 
            not content_type.startswith('application/json') and
            content_type not in ['application/xml', 'application/javascript']
        )
        
        if is_document and filename:
            # ✅ IMPORTANTE: Usar filename* com encoding UTF-8 para caracteres especiais
            from urllib.parse import quote
            # Filtrar caracteres problemáticos do nome do arquivo
            safe_filename = filename.encode('utf-8', errors='ignore').decode('utf-8')
            # Usar RFC 5987 para suportar caracteres especiais
            response['Content-Disposition'] = f'attachment; filename="{safe_filename}"; filename*=UTF-8\'\'{quote(safe_filename)}'
            logger.info(f'📎 [MEDIA PROXY] Content-Disposition adicionado: {safe_filename}')
        
        # 5. Custom headers
        response['X-Cache'] = 'DIRECT'  # ✅ Sem cache - download direto
        response['X-Content-Size'] = str(len(content))
        if request.method != 'HEAD':
            response['Content-Length'] = str(len(content))
            response['Accept-Ranges'] = 'bytes'
        
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
        
    except Exception as e:
        logger.error(f'❌ [MEDIA PROXY] Erro geral: {e}', exc_info=True)
        return JsonResponse({'error': f'Erro ao processar mídia: {str(e)}'}, status=500)


# Alias para compatibilidade (pode ser removido depois)
profile_pic_proxy_django_view = media_proxy
