"""
Handlers RabbitMQ para processamento de mídia.

Handlers:
- handle_process_profile_pic: Processa foto de perfil
- handle_process_incoming_media: Processa mídia recebida do WhatsApp
- handle_process_uploaded_file: Processa arquivo enviado pelo usuário
"""
import logging
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
    
    try:
        # 1. Baixar do WhatsApp
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(media_url)
            response.raise_for_status()
            media_data = response.content
            content_type = response.headers.get('content-type', 'application/octet-stream')
        
        logger.info(f"✅ [INCOMING MEDIA] Baixado: {len(media_data)} bytes")
        
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
        
        # 4. Upload para S3
        s3_manager = get_s3_manager()
        success, msg = s3_manager.upload_to_s3(
            processed_data,
            s3_path,
            content_type=content_type
        )
        
        if not success:
            logger.error(f"❌ [INCOMING MEDIA] Erro no upload: {msg}")
            return
        
        # Upload thumbnail se houver
        thumb_s3_path = None
        if thumbnail_data:
            thumb_s3_path = generate_media_path(tenant_id, f'chat_{media_type}s', f"thumb_{filename}")
            s3_manager.upload_to_s3(thumbnail_data, thumb_s3_path, 'image/jpeg')
        
        # 5. URL pública
        public_url = get_public_url(s3_path)
        thumb_url = get_public_url(thumb_s3_path) if thumb_s3_path else None
        
        # 6. Criar/atualizar MessageAttachment
        message = await sync_to_async(Message.objects.get)(id=message_id)
        
        # Tentar encontrar attachment placeholder criado no webhook
        from asgiref.sync import sync_to_async
        existing = await sync_to_async(lambda: MessageAttachment.objects.filter(message=message).order_by('-created_at').first())()
        if existing and (not existing.file_url or existing.storage_type != 's3'):
            existing.file_url = public_url
            existing.thumbnail_url = thumb_url or existing.thumbnail_url
            existing.size_bytes = len(processed_data)
            existing.mime_type = content_type
            existing.original_filename = filename
            existing.file_path = s3_path
            existing.storage_type = 's3'
            await sync_to_async(existing.save)()
            attachment = existing
        else:
            attachment = await sync_to_async(MessageAttachment.objects.create)(
                message=message,
                tenant=message.conversation.tenant,
                original_filename=filename,
                mime_type=content_type,
                file_path=s3_path,
                file_url=public_url,
                storage_type='s3',
                size_bytes=len(processed_data)
            )
        
        # 7. Invalidar cache Redis
        import hashlib
        cache_key = f"media:{hashlib.md5(media_url.encode()).hexdigest()}"
        cache.delete(cache_key)
        
        # 8. Broadcast via WebSocket
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        
        await channel_layer.group_send(
            f'chat_tenant_{tenant_id}_conversation_{message.conversation_id}',
            {
                'type': 'attachment_updated',
                'data': {
                    'message_id': str(message_id),
                    'attachment_id': str(attachment.id),
                    'file_url': public_url,
                    'thumbnail_url': thumb_url,
                    'mime_type': content_type,
                    'file_type': media_type
                }
            }
        )
        
        logger.info(f"✅ [INCOMING MEDIA] Processamento completo: {attachment.id}")
        
    except Exception as e:
        logger.error(f"❌ [INCOMING MEDIA] Erro: {e}", exc_info=True)


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

