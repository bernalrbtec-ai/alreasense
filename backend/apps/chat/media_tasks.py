"""
Handlers RabbitMQ para processamento de mídia.

Handlers:
- handle_process_profile_pic: Processa foto de perfil
- handle_process_incoming_media: Processa mídia recebida do WhatsApp
- handle_process_uploaded_file: Processa arquivo enviado pelo usuário
"""
import logging
import asyncio
import httpx
import base64
from asgiref.sync import sync_to_async
from django.core.cache import cache
from apps.chat.utils.s3 import (
    get_s3_manager,
    generate_media_path,
    get_public_url
)
from apps.chat.utils.image_processing import process_image, is_valid_image

logger = logging.getLogger(__name__)


async def handle_process_profile_pic(tenant_id: str, phone: str, profile_url: str):
    """
    Handler: Processa foto de perfil do WhatsApp.
    
    Fluxo:
        1. Baixa foto do WhatsApp
        2. Valida que é imagem
        3. Cria thumbnail (150x150)
        4. Faz upload para S3 (original + thumbnail)
        5. Invalida cache Redis da URL antiga
        6. Atualiza conversation.profile_pic_url
    
    Args:
        tenant_id: UUID do tenant
        phone: Telefone do contato
        profile_url: URL da foto no WhatsApp
    """
    from apps.chat.models import Conversation
    
    logger.info(f"🖼️ [PROFILE PIC] Processando foto: {phone}")
    
    try:
        # 1. Baixar do WhatsApp
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(profile_url)
            response.raise_for_status()
            image_data = response.content
        
        logger.info(f"✅ [PROFILE PIC] Baixado: {len(image_data)} bytes")
        
        # 2. Validar e processar
        if not is_valid_image(image_data):
            logger.error(f"❌ [PROFILE PIC] Não é uma imagem válida: {phone}")
            return
        
        result = process_image(image_data, create_thumb=True, resize=False, optimize=True)
        
        if not result['success']:
            logger.error(f"❌ [PROFILE PIC] Erro ao processar: {result['errors']}")
            return
        
        # 3. Paths no S3
        s3_manager = get_s3_manager()
        
        original_path = generate_media_path(tenant_id, 'profile_pics', f"{phone}_original.jpg")
        thumb_path = generate_media_path(tenant_id, 'profile_pics', f"{phone}_thumb.jpg")
        
        # 4. Upload para S3
        success, msg = s3_manager.upload_to_s3(
            result['processed_data'],
            original_path,
            content_type='image/jpeg'
        )
        
        if not success:
            logger.error(f"❌ [PROFILE PIC] Erro no upload original: {msg}")
            return
        
        if result['thumbnail_data']:
            s3_manager.upload_to_s3(
                result['thumbnail_data'],
                thumb_path,
                content_type='image/jpeg'
            )
        
        # 5. URL pública via proxy
        public_url = get_public_url(original_path)
        
        # 6. Invalidar cache Redis da URL antiga
        import hashlib
        old_cache_key = f"media:{hashlib.md5(profile_url.encode()).hexdigest()}"
        cache.delete(old_cache_key)
        
        # 7. Atualizar conversas
        conversations = await sync_to_async(list)(
            Conversation.objects.filter(
                tenant_id=tenant_id,
                contact_phone=phone
            )
        )
        
        for conv in conversations:
            conv.profile_pic_url = public_url
            await sync_to_async(conv.save)(update_fields=['profile_pic_url'])
        
        logger.info(
            f"✅ [PROFILE PIC] Processamento completo: {phone} - "
            f"{len(conversations)} conversas atualizadas"
        )
        
    except Exception as e:
        logger.error(f"❌ [PROFILE PIC] Erro: {e}", exc_info=True)


async def handle_process_incoming_media(
    tenant_id: str,
    message_id: str,
    media_url: str,
    media_type: str
):
    """
    Handler: Processa mídia recebida do WhatsApp.
    
    Fluxo:
        1. Baixa mídia da URL temporária do WhatsApp
        2. Se for imagem: processa (thumbnail, resize, optimize)
        3. Faz upload para S3
        4. Cria MessageAttachment
        5. Invalida cache Redis
        6. Broadcast via WebSocket
    
    Args:
        tenant_id: UUID do tenant
        message_id: UUID da mensagem
        media_url: URL temporária do WhatsApp
        media_type: Tipo de mídia (image, audio, document, video)
    """
    from apps.chat.models import Message, MessageAttachment
    
    logger.info(f"📦 [INCOMING MEDIA] Processando: {media_type} - {media_url[:80]}...")
    
    # ✅ RETRY: Tentar até 3 vezes em caso de falha de rede
    max_retries = 3
    retry_count = 0
    media_data = None
    content_type = 'application/octet-stream'
    
    while retry_count < max_retries:
        try:
            # 1. Baixar do WhatsApp
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(media_url)
                response.raise_for_status()
                media_data = response.content
                content_type = response.headers.get('content-type', 'application/octet-stream')
            
            logger.info(f"✅ [INCOMING MEDIA] Baixado: {len(media_data)} bytes (tentativa {retry_count + 1}/{max_retries})")
            break  # Sucesso, sair do loop
            
        except (httpx.TimeoutException, httpx.NetworkError) as e:
            retry_count += 1
            if retry_count < max_retries:
                wait_time = retry_count * 2  # Backoff exponencial: 2s, 4s, 6s
                logger.warning(f"⚠️ [INCOMING MEDIA] Erro de rede (tentativa {retry_count}/{max_retries}): {e}. Aguardando {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"❌ [INCOMING MEDIA] Falhou após {max_retries} tentativas: {e}")
                raise
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ [INCOMING MEDIA] Erro HTTP ao baixar: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"❌ [INCOMING MEDIA] Erro inesperado ao baixar: {e}", exc_info=True)
            raise
    
    if not media_data:
        logger.error(f"❌ [INCOMING MEDIA] Não foi possível baixar mídia após {max_retries} tentativas")
        return
    
    try:
        
        # 2. Processar imagem e padronizar áudio
        processed_data = media_data
        thumbnail_data = None
        
        if media_type == 'image' and is_valid_image(media_data):
            result = process_image(media_data, create_thumb=True, resize=True, optimize=True)
            if result['success']:
                processed_data = result['processed_data']
                thumbnail_data = result['thumbnail_data']
                logger.info(f"✅ [INCOMING MEDIA] Imagem processada")
            # Forçar content-type seguro se vier genérico
            if not content_type or content_type.startswith('application/octet-stream'):
                content_type = 'image/jpeg'
        
        # Áudio: converter OGG/WEBM → MP3 para compatibilidade universal
        if media_type == 'audio':
            from apps.chat.utils.audio_converter import should_convert_audio, convert_ogg_to_mp3, get_converted_filename
            # Inferir filename e checar se precisa converter
            from urllib.parse import urlparse
            inferred_filename = urlparse(media_url).path.split('/')[-1] or f"audio_{message_id}"
            if should_convert_audio(content_type or '', inferred_filename):
                source_format = "webm" if ('webm' in (content_type or '').lower() or inferred_filename.lower().endswith('.webm')) else "ogg"
                success_conv, mp3_data, conv_msg = convert_ogg_to_mp3(processed_data, source_format=source_format)
                if success_conv and mp3_data:
                    processed_data = mp3_data
                    content_type = 'audio/mpeg'
                    inferred_filename = get_converted_filename(inferred_filename)
                    logger.info(f"✅ [AUDIO] Incoming convertido para MP3")
                else:
                    logger.warning(f"⚠️ [AUDIO] Conversão falhou: {conv_msg}. Seguindo com formato original")
        
        # 3. Path no S3
        from urllib.parse import urlparse
        filename = urlparse(media_url).path.split('/')[-1] or f"media_{message_id}"
        # Se convertemos áudio, o nome pode ter sido ajustado acima
        if media_type == 'audio':
            # usar inferred_filename se disponível no escopo
            try:
                filename = inferred_filename or filename
            except NameError:
                pass
        s3_path = generate_media_path(tenant_id, f'chat_{media_type}s', filename)
        
        # 4. Upload para S3 (com retry)
        s3_manager = get_s3_manager()
        upload_success = False
        upload_retries = 0
        max_upload_retries = 2
        
        while upload_retries <= max_upload_retries and not upload_success:
            success, msg = s3_manager.upload_to_s3(
                processed_data,
                s3_path,
                content_type=content_type
            )
            
            if success:
                upload_success = True
                logger.info(f"✅ [INCOMING MEDIA] Upload para S3 concluído: {s3_path}")
            else:
                upload_retries += 1
                if upload_retries <= max_upload_retries:
                    wait_time = upload_retries * 1  # Backoff: 1s, 2s
                    logger.warning(f"⚠️ [INCOMING MEDIA] Erro no upload (tentativa {upload_retries}/{max_upload_retries}): {msg}. Aguardando {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"❌ [INCOMING MEDIA] Falha no upload após {max_upload_retries + 1} tentativas: {msg}")
                    return
        
        # Upload thumbnail se houver (com tratamento de erro)
        thumb_s3_path = None
        if thumbnail_data:
            thumb_s3_path = generate_media_path(tenant_id, f'chat_{media_type}s', f"thumb_{filename}")
            thumb_success, thumb_msg = s3_manager.upload_to_s3(thumbnail_data, thumb_s3_path, 'image/jpeg')
            if thumb_success:
                logger.info(f"✅ [INCOMING MEDIA] Thumbnail enviado para S3: {thumb_s3_path}")
            else:
                logger.warning(f"⚠️ [INCOMING MEDIA] Erro ao enviar thumbnail: {thumb_msg}. Continuando sem thumbnail.")
                thumb_s3_path = None  # Não usar path se upload falhou
        
        # 5. URL pública
        public_url = get_public_url(s3_path)
        thumb_url = get_public_url(thumb_s3_path) if thumb_s3_path else None
        
        # 6. Criar/atualizar MessageAttachment
        # Tentar encontrar attachment placeholder criado no webhook
        existing = await sync_to_async(lambda: MessageAttachment.objects.filter(message__id=message_id).order_by('-created_at').first())()
        
        # Buscar message
        message = await sync_to_async(Message.objects.get)(id=message_id)
        if existing and (not existing.file_url or existing.storage_type != 's3'):
            existing.file_url = public_url
            # Atualizar thumbnail_path se houver thumbnail
            if thumb_s3_path:
                existing.thumbnail_path = thumb_s3_path
            existing.size_bytes = len(processed_data)
            existing.mime_type = content_type
            existing.original_filename = filename
            existing.file_path = s3_path
            existing.storage_type = 's3'
            # Remover flag de processing (mídia está pronta)
            import json
            # ✅ NORMALIZAR metadata: garantir que sempre seja dict
            metadata = existing.metadata if existing.metadata else {}
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata) if metadata else {}
                except (json.JSONDecodeError, ValueError):
                    metadata = {}
            elif not isinstance(metadata, dict):
                metadata = {}
            
            metadata.pop('processing', None)
            # Manter media_type se existir
            if 'media_type' not in metadata and media_type:
                metadata['media_type'] = media_type
            
            existing.metadata = metadata
            await sync_to_async(existing.save)(update_fields=['file_url', 'thumbnail_path', 'size_bytes', 'mime_type', 'original_filename', 'file_path', 'storage_type', 'metadata'])
            attachment = existing
            logger.info(f"✅ [INCOMING MEDIA] Attachment atualizado: {attachment.id}, file_url={public_url[:50]}...")
        else:
            # ✅ Criar novo attachment se placeholder não existir
            # Normalizar metadata ao criar
            import json
            new_metadata = {'media_type': media_type}
            attachment = await sync_to_async(MessageAttachment.objects.create)(
                message=message,
                tenant=message.conversation.tenant,
                original_filename=filename,
                mime_type=content_type,
                file_path=s3_path,
                file_url=public_url,
                storage_type='s3',
                size_bytes=len(processed_data),
                thumbnail_path=thumb_s3_path or '',
                metadata=new_metadata  # ✅ Metadata normalizado como dict
            )
            logger.info(f"✅ [INCOMING MEDIA] Novo attachment criado: {attachment.id}")
        
        # 7. Cache no Redis (alinhado com envio: 30 dias por padrão)
        # Gerar hash único para cache (usar file_path como base)
        import hashlib
        from django.conf import settings
        media_hash = hashlib.md5(s3_path.encode()).hexdigest()[:12]
        cache_key = f"media:{media_hash}"
        
        # Cachear dados do arquivo processado (TTL configurável)
        cache_ttl = int(getattr(settings, 'ATTACHMENTS_REDIS_TTL_DAYS', 30)) * 24 * 60 * 60
        try:
            cache_data = {
                'data': processed_data,
                'content_type': content_type,
            }
            cache.set(cache_key, cache_data, cache_ttl)
            logger.info(f"✅ [INCOMING MEDIA] Cacheado no Redis por {cache_ttl}s (hash: {media_hash})")
            
            # ✅ PERFORMANCE: Invalidar cache de verificação de existência no S3
            # Quando arquivo é processado, garantir que cache de "existe" está atualizado
            exists_cache_key = f"s3_exists:{s3_path}"
            cache.set(exists_cache_key, True, 300)  # 5 minutos
            if thumb_s3_path:
                thumb_exists_cache_key = f"s3_exists:{thumb_s3_path}"
                cache.set(thumb_exists_cache_key, True, 300)
        except Exception as cache_error:
            # Se cache falhar, não quebrar o processamento
            logger.warning(f"⚠️ [INCOMING MEDIA] Erro ao cachear no Redis: {cache_error}. Continuando...")
        
        # 8. Broadcast via WebSocket
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        
        # Gerar thumbnail_url a partir do thumbnail_path se houver
        thumbnail_url_for_ws = None
        if thumb_s3_path:
            thumbnail_url_for_ws = get_public_url(thumb_s3_path)
        
        # ✅ Garantir que metadata está serializado corretamente para WebSocket
        # NORMALIZAR: sempre retornar dict, nunca string
        metadata_for_ws = attachment.metadata if attachment.metadata else {}
        if isinstance(metadata_for_ws, str):
            try:
                import json
                metadata_for_ws = json.loads(metadata_for_ws) if metadata_for_ws else {}
            except (json.JSONDecodeError, ValueError):
                metadata_for_ws = {}
        elif not isinstance(metadata_for_ws, dict):
            metadata_for_ws = {}
        
        # Garantir que não tem flag processing (já foi removido acima)
        metadata_for_ws.pop('processing', None)
        
        await channel_layer.group_send(
            f'chat_tenant_{tenant_id}_conversation_{message.conversation_id}',
            {
                'type': 'attachment_updated',
                'data': {
                    'message_id': str(message_id),
                    'attachment_id': str(attachment.id),
                    'file_url': public_url,  # ✅ URL do proxy (via get_public_url)
                    'thumbnail_url': thumbnail_url_for_ws,
                    'mime_type': content_type,
                    'file_type': media_type,
                    'metadata': metadata_for_ws  # ✅ Incluir metadata sem flag processing
                }
            }
        )
        logger.info(f"📡 [INCOMING MEDIA] WebSocket attachment_updated enviado: {attachment.id}")
        
        logger.info(f"✅ [INCOMING MEDIA] Processamento completo: {attachment.id}")
        
    except httpx.TimeoutException as e:
        logger.error(f"❌ [INCOMING MEDIA] Timeout ao processar: {e}")
        # Marcar attachment como erro se existir
        try:
            from apps.chat.models import MessageAttachment
            existing = await sync_to_async(lambda: MessageAttachment.objects.filter(message__id=message_id).order_by('-created_at').first())()
            if existing:
                import json
                metadata = existing.metadata if existing.metadata else {}
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata) if metadata else {}
                    except:
                        metadata = {}
                elif not isinstance(metadata, dict):
                    metadata = {}
                metadata['error'] = 'timeout'
                metadata.pop('processing', None)
                existing.metadata = metadata
                await sync_to_async(existing.save)(update_fields=['metadata'])
        except Exception:
            pass  # Não quebrar se falhar ao atualizar metadata
    except Exception as e:
        logger.error(f"❌ [INCOMING MEDIA] Erro: {e}", exc_info=True)
        # Marcar attachment como erro se existir
        try:
            from apps.chat.models import MessageAttachment
            existing = await sync_to_async(lambda: MessageAttachment.objects.filter(message__id=message_id).order_by('-created_at').first())()
            if existing:
                import json
                metadata = existing.metadata if existing.metadata else {}
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata) if metadata else {}
                    except:
                        metadata = {}
                elif not isinstance(metadata, dict):
                    metadata = {}
                metadata['error'] = str(e)[:100]  # Limitar tamanho
                metadata.pop('processing', None)
                existing.metadata = metadata
                await sync_to_async(existing.save)(update_fields=['metadata'])
        except Exception:
            pass  # Não quebrar se falhar ao atualizar metadata


async def handle_process_uploaded_file(
    tenant_id: str,
    file_data: str,
    filename: str,
    content_type: str
):
    """
    Handler: Processa arquivo enviado pelo usuário.
    
    Fluxo:
        1. Decode base64
        2. Valida tamanho
        3. Se for imagem: processa
        4. Upload para S3
        5. Retorna URL (via callback ou WebSocket)
    
    Args:
        tenant_id: UUID do tenant
        file_data: Dados do arquivo em base64
        filename: Nome original do arquivo
        content_type: MIME type
    
    Returns:
        dict com file_url e thumb_url
    """
    logger.info(f"📤 [UPLOAD] Processando arquivo: {filename}")
    
    try:
        # 1. Decode base64
        binary_data = base64.b64decode(file_data)
        
        logger.info(f"✅ [UPLOAD] Decodificado: {len(binary_data)} bytes")
        
        # 2. Validar tamanho (usar settings: ATTACHMENTS_MAX_SIZE_MB)
        from django.conf import settings
        MAX_SIZE = int(getattr(settings, 'ATTACHMENTS_MAX_SIZE_MB', 50)) * 1024 * 1024
        if len(binary_data) > MAX_SIZE:
            logger.error(f"❌ [UPLOAD] Arquivo muito grande: {len(binary_data)} bytes")
            return {
                'success': False,
                'error': f"Arquivo muito grande (máx {MAX_SIZE // (1024*1024)}MB)"
            }
        
        # 3. Detectar tipo de mídia
        if content_type.startswith('image/'):
            media_type = 'image'
        elif content_type.startswith('audio/'):
            media_type = 'audio'
        elif content_type.startswith('video/'):
            media_type = 'video'
        else:
            media_type = 'document'
        
        # 4. Processar se for imagem
        processed_data = binary_data
        thumbnail_data = None
        
        if media_type == 'image' and is_valid_image(binary_data):
            result = process_image(binary_data, create_thumb=True, resize=True, optimize=True)
            if result['success']:
                processed_data = result['processed_data']
                thumbnail_data = result['thumbnail_data']
        
        # 5. Path no S3
        s3_path = generate_media_path(tenant_id, f'chat_{media_type}s', filename)
        
        # 6. Upload para S3
        s3_manager = get_s3_manager()
        success, msg = s3_manager.upload_to_s3(
            processed_data,
            s3_path,
            content_type=content_type
        )
        
        if not success:
            logger.error(f"❌ [UPLOAD] Erro no upload: {msg}")
            return {
                'success': False,
                'error': msg
            }
        
        # Upload thumbnail se houver
        thumb_s3_path = None
        if thumbnail_data:
            thumb_s3_path = generate_media_path(tenant_id, f'chat_{media_type}s', f"thumb_{filename}")
            s3_manager.upload_to_s3(thumbnail_data, thumb_s3_path, 'image/jpeg')
        
        # 7. URLs públicas
        file_url = get_public_url(s3_path)
        thumb_url = get_public_url(thumb_s3_path) if thumb_s3_path else None
        
        logger.info(f"✅ [UPLOAD] Upload completo: {filename}")
        
        return {
            'success': True,
            'file_url': file_url,
            'thumbnail_url': thumb_url,
            'file_size': len(processed_data),
            'file_type': media_type
        }
        
    except Exception as e:
        logger.error(f"❌ [UPLOAD] Erro: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }

