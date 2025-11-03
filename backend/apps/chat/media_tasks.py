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
from apps.chat.utils.s3 import (
    get_s3_manager,
    generate_media_path,
    get_public_url
)
# ✅ Import image_processing apenas para profile_pic (foto de perfil ainda precisa processar)
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
    
    Fluxo (padronizado com ENVIO - sem cache):
        1. Baixa mídia da URL temporária do WhatsApp (com retry)
        2. Valida tamanho antes/depois de baixar
        3. Converte áudio OGG/WEBM → MP3 (se necessário)
        4. Faz upload direto para S3 (sem processar imagem)
        5. Atualiza MessageAttachment placeholder com file_url e file_path
        6. Broadcast via WebSocket
    
    Args:
        tenant_id: UUID do tenant
        message_id: UUID da mensagem
        media_url: URL temporária do WhatsApp
        media_type: Tipo de mídia (image, audio, document, video)
    """
    from apps.chat.models import Message, MessageAttachment
    
    logger.info(f"📦 [INCOMING MEDIA] Processando: {media_type}")
    logger.info(f"   🔗 [INCOMING MEDIA] URL WhatsApp (original): {media_url}")
    logger.info(f"   📌 [INCOMING MEDIA] message_id: {message_id}")
    logger.info(f"   📌 [INCOMING MEDIA] tenant_id: {tenant_id}")
    
    # ✅ VALIDAÇÃO: Verificar tamanho ANTES de baixar (economia de recursos)
    from django.conf import settings
    MAX_SIZE = int(getattr(settings, 'ATTACHMENTS_MAX_SIZE_MB', 50)) * 1024 * 1024  # 50MB padrão
    
    try:
        # HEAD request para verificar tamanho antes de baixar
        async with httpx.AsyncClient(timeout=10.0) as client:
            head_response = await client.head(media_url)
            content_length = int(head_response.headers.get('content-length', 0))
            
            if content_length > MAX_SIZE:
                logger.error(f"❌ [INCOMING MEDIA] Arquivo muito grande! {content_length / 1024 / 1024:.2f}MB > {MAX_SIZE / 1024 / 1024}MB")
                # Marcar attachment como erro se existir
                try:
                    from apps.chat.models import MessageAttachment
                    from apps.chat.utils.serialization import normalize_metadata
                    
                    existing = await sync_to_async(lambda: MessageAttachment.objects.filter(
                        message__id=message_id,
                        file_url='',
                        file_path=''
                    ).first())()
                    if existing:
                        metadata = normalize_metadata(existing.metadata)
                        metadata['error'] = f'Arquivo muito grande ({content_length / 1024 / 1024:.2f}MB). Máximo: {MAX_SIZE / 1024 / 1024}MB'
                        metadata.pop('processing', None)
                        existing.metadata = metadata
                        await sync_to_async(existing.save)(update_fields=['metadata'])
                except Exception:
                    pass
                return  # Não processar arquivo muito grande
    except Exception as size_check_error:
        # Se HEAD falhar, continuar e validar após download (fallback)
        logger.warning(f"⚠️ [INCOMING MEDIA] Não foi possível verificar tamanho antes de baixar: {size_check_error}. Validando após download...")
    
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
            
            # ✅ VALIDAÇÃO: Verificar tamanho após download (se não foi possível antes)
            if len(media_data) > MAX_SIZE:
                logger.error(f"❌ [INCOMING MEDIA] Arquivo muito grande após download! {len(media_data) / 1024 / 1024:.2f}MB > {MAX_SIZE / 1024 / 1024}MB")
                # Marcar attachment como erro se existir
                try:
                    from apps.chat.models import MessageAttachment
                    from apps.chat.utils.serialization import normalize_metadata
                    
                    existing = await sync_to_async(lambda: MessageAttachment.objects.filter(
                        message__id=message_id,
                        file_url='',
                        file_path=''
                    ).first())()
                    if existing:
                        metadata = normalize_metadata(existing.metadata)
                        metadata['error'] = f'Arquivo muito grande ({len(media_data) / 1024 / 1024:.2f}MB). Máximo: {MAX_SIZE / 1024 / 1024}MB'
                        metadata.pop('processing', None)
                        existing.metadata = metadata
                        await sync_to_async(existing.save)(update_fields=['metadata'])
                except Exception:
                    pass
                return  # Não processar arquivo muito grande
            
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
        logger.error(f"❌ [INCOMING MEDIA] Failed to download media after {max_retries} attempts")
        # Mark attachment as error if exists
        try:
            from apps.chat.models import MessageAttachment
            from apps.chat.utils.serialization import normalize_metadata
            
            existing = await sync_to_async(lambda: MessageAttachment.objects.filter(
                message__id=message_id,
                file_url='',
                file_path=''
            ).first())()
            if existing:
                metadata = normalize_metadata(existing.metadata)
                metadata['error'] = f'Falha ao baixar mídia após {max_retries} tentativas'
                metadata.pop('processing', None)
                existing.metadata = metadata
                await sync_to_async(existing.save)(update_fields=['metadata'])
        except Exception:
            pass
        return
    
    try:
        import uuid
        from urllib.parse import urlparse
        
        # 2. Converter áudio OGG/WEBM → MP3 (padronizado com ENVIO)
        processed_data = media_data
        filename = urlparse(media_url).path.split('/')[-1] or f"media_{message_id}"
        
        # ✅ Forçar content-type seguro se vier genérico (apenas para imagens)
        if media_type == 'image' and (not content_type or content_type.startswith('application/octet-stream')):
            content_type = 'image/jpeg'
        
        # ✅ Áudio: converter OGG/WEBM → MP3 para compatibilidade universal (mesmo do ENVIO)
        if media_type == 'audio':
            from apps.chat.utils.audio_converter import should_convert_audio, convert_ogg_to_mp3, get_converted_filename
            
            inferred_filename = urlparse(media_url).path.split('/')[-1] or f"audio_{message_id}"
            if should_convert_audio(content_type or '', inferred_filename):
                source_format = "webm" if ('webm' in (content_type or '').lower() or inferred_filename.lower().endswith('.webm')) else "ogg"
                success_conv, mp3_data, conv_msg = convert_ogg_to_mp3(processed_data, source_format=source_format)
                if success_conv and mp3_data:
                    processed_data = mp3_data
                    content_type = 'audio/mpeg'
                    filename = get_converted_filename(inferred_filename)
                    logger.info(f"✅ [AUDIO] Incoming convertido para MP3")
                else:
                    logger.warning(f"⚠️ [AUDIO] Conversão falhou: {conv_msg}. Seguindo com formato original")
        
        # 3. ✅ Path S3 padronizado (mesmo do ENVIO): chat/{tenant_id}/attachments/{uuid}.{ext}
        attachment_id = uuid.uuid4()
        file_ext = filename.split('.')[-1] if '.' in filename else ''
        # Se não tem extensão, inferir do content_type
        if not file_ext and content_type:
            if 'image' in content_type:
                file_ext = 'jpg'
            elif 'audio' in content_type:
                file_ext = 'mp3' if 'mpeg' in content_type else 'ogg'
            elif 'video' in content_type:
                file_ext = 'mp4'
            elif 'pdf' in content_type:
                file_ext = 'pdf'
            else:
                file_ext = 'bin'
        
        s3_path = f"chat/{tenant_id}/attachments/{attachment_id}.{file_ext}"
        
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
                logger.info(f"✅ [INCOMING MEDIA] Upload para S3 concluído: {s3_path} ({len(processed_data)} bytes)")
                break  # ✅ IMPORTANTE: Sair do loop ao conseguir upload com sucesso
            else:
                upload_retries += 1
                if upload_retries <= max_upload_retries:
                    wait_time = upload_retries * 1  # Backoff: 1s, 2s
                    logger.warning(f"⚠️ [INCOMING MEDIA] Erro no upload (tentativa {upload_retries}/{max_upload_retries}): {msg}. Aguardando {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"❌ [INCOMING MEDIA] Falha no upload após {max_upload_retries + 1} tentativas: {msg}")
                    # ✅ IMPORTANTE: Marcar attachment como erro se upload falhar completamente
                    try:
                        from apps.chat.models import MessageAttachment
                        from apps.chat.utils.serialization import normalize_metadata
                        
                        existing = await sync_to_async(lambda: MessageAttachment.objects.filter(
                            message__id=message_id,
                            file_url='',
                            file_path=''
                        ).first())()
                        if existing:
                            metadata = normalize_metadata(existing.metadata)
                            metadata['error'] = f'Falha no upload para S3 após {max_upload_retries + 1} tentativas: {msg[:100]}'
                            metadata.pop('processing', None)
                            existing.metadata = metadata
                            await sync_to_async(existing.save)(update_fields=['metadata'])
                            logger.error(f"❌ [INCOMING MEDIA] Attachment marcado como erro: {existing.id}")
                    except Exception as update_error:
                        logger.error(f"❌ [INCOMING MEDIA] Erro ao marcar attachment como erro: {update_error}", exc_info=True)
                    return
        
        # 5. URL pública (padronizado com ENVIO)
        public_url = get_public_url(s3_path)
        
        # ✅ DEBUG: Log detalhado das URLs
        logger.info(f"📎 [INCOMING MEDIA] URLs geradas:")
        logger.info(f"   🔗 [INCOMING MEDIA] URL WhatsApp (original): {media_url}")
        logger.info(f"   📦 [INCOMING MEDIA] S3 Path: {s3_path}")
        logger.info(f"   🌐 [INCOMING MEDIA] URL Proxy (final): {public_url}")
        logger.info(f"   📏 [INCOMING MEDIA] Tamanho: {len(processed_data)} bytes ({len(processed_data) / 1024:.2f} KB)")
        logger.info(f"   📄 [INCOMING MEDIA] Content-Type: {content_type}")
        logger.info(f"   📝 [INCOMING MEDIA] Filename: {filename}")
        
        # 6. Atualizar MessageAttachment placeholder (padronizado com ENVIO)
        # ✅ BUSCAR placeholder criado no webhook (file_url vazio E file_path vazio)
        logger.info(f"🔍 [INCOMING MEDIA] Buscando placeholder para message_id={message_id}")
        message = await sync_to_async(Message.objects.select_related('conversation', 'conversation__tenant').get)(id=message_id)
        
        # ✅ Buscar placeholder - buscar por file_url vazio (placeholder criado no webhook)
        # Simplificado: buscar apenas por file_url vazio, que é o que o placeholder tem
        # ✅ MELHORIA: Buscar TODOS os attachments da mensagem para debug
        all_attachments = await sync_to_async(list)(
            MessageAttachment.objects.filter(message__id=message_id).values('id', 'file_url', 'file_path', 'metadata', 'created_at')
        )
        logger.info(f"🔍 [INCOMING MEDIA] Total de attachments na mensagem: {len(all_attachments)}")
        for att in all_attachments:
            logger.info(f"   📎 Attachment: {att['id']}, file_url={att['file_url'][:50] if att['file_url'] else 'VAZIO'}..., file_path={att['file_path'][:50] if att['file_path'] else 'VAZIO'}..., metadata={att['metadata']}")
        
        existing = await sync_to_async(lambda: MessageAttachment.objects.filter(
            message__id=message_id,
            file_url=''  # ✅ Placeholder criado no webhook tem file_url vazio
        ).order_by('-created_at').first())()
        
        if existing:
            logger.info(f"✅ [INCOMING MEDIA] Placeholder encontrado: {existing.id}")
        else:
            logger.warning(f"⚠️ [INCOMING MEDIA] Placeholder NÃO encontrado! Total attachments: {len(all_attachments)}")
        
        if existing:
            # ✅ ATUALIZAR placeholder existente (padronizado com ENVIO)
            from apps.chat.utils.serialization import normalize_metadata
            from django.utils import timezone
            from datetime import timedelta
            
            # Normalizar metadata e remover flag processing
            metadata = normalize_metadata(existing.metadata)
            metadata.pop('processing', None)
            if 'media_type' not in metadata:
                metadata['media_type'] = media_type
            
            existing.file_url = public_url
            existing.file_path = s3_path
            existing.storage_type = 's3'
            existing.size_bytes = len(processed_data)
            existing.mime_type = content_type
            existing.original_filename = filename
            existing.expires_at = timezone.now() + timedelta(days=365)  # ✅ Mesmo do ENVIO
            existing.metadata = metadata
            
            # ✅ IMPORTANTE: Usar save() para gerar media_hash e short_url (mesmo do ENVIO)
            await sync_to_async(existing.save)()
            attachment = existing
            logger.info(f"✅ [INCOMING MEDIA] Attachment atualizado: {attachment.id}")
            logger.info(f"   📌 file_url: {public_url[:60]}...")
            logger.info(f"   📌 file_path: {s3_path}")
            logger.info(f"   📌 media_hash: {attachment.media_hash}")
            logger.info(f"   📌 metadata.processing: {metadata.get('processing', 'N/A')}")
        else:
            # ✅ Se não encontrou placeholder, criar novo (não deveria acontecer)
            from apps.chat.utils.serialization import normalize_metadata
            from django.utils import timezone
            from datetime import timedelta
            
            logger.warning(f"⚠️ [INCOMING MEDIA] Placeholder não encontrado! Criando novo attachment para message_id={message_id}")
            attachment = await sync_to_async(MessageAttachment.objects.create)(
                message=message,
                tenant=message.conversation.tenant,
                original_filename=filename,
                mime_type=content_type,
                file_path=s3_path,
                file_url=public_url,
                storage_type='s3',
                size_bytes=len(processed_data),
                expires_at=timezone.now() + timedelta(days=365),
                metadata={'media_type': media_type}  # ✅ Sem flag processing
            )
            logger.info(f"✅ [INCOMING MEDIA] Novo attachment criado: {attachment.id}")
        
        # 7. ✅ REMOVIDO: Cache Redis (padronizado com ENVIO - sem cache)
        # O envio não usa cache, então o recebimento também não usa
        
        # 8. Broadcast via WebSocket (padronizado com ENVIO)
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        
        # ✅ Garantir que metadata está serializado corretamente para WebSocket
        # NORMALIZAR: sempre retornar dict, nunca string
        from apps.chat.utils.serialization import normalize_metadata
        
        metadata_for_ws = normalize_metadata(attachment.metadata)
        # Garantir que não tem flag processing (já foi removido acima)
        metadata_for_ws.pop('processing', None)
        
        # ✅ IMPORTANTE: Sempre incluir message_id no broadcast para facilitar busca no frontend
        # ✅ ENVIAR PARA DOIS GRUPOS:
        # 1. Grupo da conversa específica (usuários com conversa aberta)
        # 2. Grupo do tenant inteiro (para que seja recebido mesmo se conversa não estiver aberta)
        attachment_update_event = {
            'type': 'attachment_updated',
            'data': {
                'message_id': str(message_id),  # ✅ Incluir message_id para busca precisa
                'attachment_id': str(attachment.id),
                'file_url': public_url,  # ✅ URL do proxy (via get_public_url)
                'thumbnail_url': None,  # ✅ Removido: não geramos thumbnail mais (padronizado com ENVIO)
                'mime_type': content_type,
                'file_type': media_type,
                'metadata': metadata_for_ws  # ✅ Incluir metadata sem flag processing
            }
        }
        
        logger.info(f"📡 [INCOMING MEDIA] Preparando WebSocket broadcast:")
        logger.info(f"   📌 message_id: {message_id}")
        logger.info(f"   📌 attachment_id: {attachment.id}")
        logger.info(f"   📌 file_url: {public_url[:80]}...")
        logger.info(f"   📌 conversation_id: {message.conversation_id}")
        logger.info(f"   📌 tenant_id: {tenant_id}")
        
        # ✅ CORREÇÃO: Enviar APENAS para grupo do tenant (evita duplicação)
        # O useTenantSocket já cobre todas as conversas, então não precisa enviar para grupo específico
        # Isso evita que o evento chegue duas vezes (useChatSocket + useTenantSocket)
        tenant_group = f'chat_tenant_{tenant_id}'
        await channel_layer.group_send(tenant_group, attachment_update_event)
        logger.info(f"📡 [INCOMING MEDIA] WebSocket enviado para grupo tenant: {tenant_group}")
        logger.info(f"   ℹ️ [INCOMING MEDIA] NOTA: Não enviando para grupo conversa para evitar duplicação")
        
        logger.info(f"✅ [INCOMING MEDIA] Processamento completo: {attachment.id}")
        
    except httpx.TimeoutException as e:
        logger.error(f"❌ [INCOMING MEDIA] Timeout ao processar: {e}")
        # Mark attachment as error if exists
        try:
            from apps.chat.models import MessageAttachment
            from apps.chat.utils.serialization import normalize_metadata
            
            # ✅ Use specific filter for placeholder (consistent with other error handlers)
            existing = await sync_to_async(lambda: MessageAttachment.objects.filter(
                message__id=message_id,
                file_url='',
                file_path=''
            ).first())()
            if existing:
                metadata = normalize_metadata(existing.metadata)
                metadata['error'] = 'Timeout ao processar mídia. Tente novamente mais tarde.'
                metadata.pop('processing', None)
                existing.metadata = metadata
                await sync_to_async(existing.save)(update_fields=['metadata'])
        except Exception:
            pass  # Don't break if metadata update fails
    except Exception as e:
        logger.error(f"❌ [INCOMING MEDIA] Erro: {e}", exc_info=True)
        # Marcar attachment como erro se existir
        try:
            from apps.chat.models import MessageAttachment
            from apps.chat.utils.serialization import normalize_metadata
            
            # ✅ LÓGICA CORRIGIDA: Buscar placeholder especificamente
            existing = await sync_to_async(lambda: MessageAttachment.objects.filter(
                message__id=message_id,
                file_url='',
                file_path=''
            ).first())()
            if existing:
                metadata = normalize_metadata(existing.metadata)
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

