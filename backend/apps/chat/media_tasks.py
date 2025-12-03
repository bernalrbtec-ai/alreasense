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
from typing import Optional
from asgiref.sync import sync_to_async
from apps.chat.utils.s3 import (
    get_s3_manager,
    generate_media_path,
    get_public_url
)
from apps.chat.utils.instance_state import should_defer_instance, InstanceTemporarilyUnavailable, compute_backoff
# ✅ Import image_processing apenas para profile_pic (foto de perfil ainda precisa processar)
from apps.chat.utils.image_processing import process_image, is_valid_image

logger = logging.getLogger(__name__)
media_logger = logging.getLogger("flow.chat.media")


async def handle_fetch_group_info(conversation_id: str, group_jid: str, instance_name: str, api_key: str, base_url: str):
    """
    Handler: Busca informações de grupo (nome, foto, participantes) de forma assíncrona.
    
    Fluxo:
        1. Busca informações do grupo via Evolution API
        2. Atualiza conversation com nome e metadados
        3. Broadcast via WebSocket para atualizar frontend
    
    Args:
        conversation_id: UUID da conversa
        group_jid: JID completo do grupo (ex: 5517991106338-1396034900@g.us)
        instance_name: Nome da instância WhatsApp
        api_key: API key da instância
        base_url: URL base da Evolution API
    """
    from apps.chat.models import Conversation
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    from asgiref.sync import sync_to_async
    
    logger.critical(f"👥 [GROUP INFO] Buscando informações do grupo: {group_jid}")
    
    # ✅ VALIDAÇÃO CRÍTICA: Garantir que group_jid termina com @g.us
    if not group_jid.endswith('@g.us'):
        logger.critical(f"❌ [GROUP INFO] ERRO CRÍTICO: group_jid não termina com @g.us!")
        logger.critical(f"   group_jid recebido: {group_jid}")
        logger.critical(f"   conversation_id: {conversation_id}")
        logger.critical(f"   ⚠️ ISSO CAUSA ERRO 400 NA EVOLUTION API!")
        logger.critical(f"   ⚠️ NÃO BUSCANDO INFORMAÇÕES DO GRUPO!")
        
        # ✅ Tentar buscar conversation para verificar conversation_type
        try:
            conversation = await sync_to_async(
                Conversation.objects.select_related('tenant').get
            )(id=conversation_id)
            logger.critical(f"   Conversation Type: {conversation.conversation_type}")
            logger.critical(f"   Contact Phone: {conversation.contact_phone}")
            logger.critical(f"   ⚠️ Se conversation_type é 'individual', isso explica o erro!")
        except Exception as e:
            logger.critical(f"   Erro ao buscar conversation: {e}")
        
        return  # ✅ Retornar sem processar
    
    try:
        # Buscar informações do grupo
        endpoint = f"{base_url.rstrip('/')}/group/findGroupInfos/{instance_name}"
        headers = {
            'apikey': api_key,
            'Content-Type': 'application/json'
        }
        
        logger.critical(f"📡 [GROUP INFO] Chamando Evolution API: {endpoint}")
        logger.critical(f"   groupJid: {group_jid}")
        
        # ✅ MELHORIA: Retry com backoff exponencial para erros de rede
        max_retries = 3
        retry_count = 0
        last_error = None
        
        while retry_count < max_retries:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(
                        endpoint,
                        params={'groupJid': group_jid},
                        headers=headers
                    )
                    
                    # ✅ Verificar status HTTP antes de processar
                    if response.status_code == 200:
                        group_info = response.json()
                        logger.info(f"✅ [GROUP INFO] Informações recebidas para {group_jid}")
                        
                        # Extrair dados
                        group_name = group_info.get('subject', '')
                        group_pic_url = group_info.get('pictureUrl')
                        participants_count = group_info.get('size', 0)
                        group_desc = group_info.get('desc', '')
                        
                        # ✅ CORREÇÃO: Tratar caso de conversa não existir (pode ter sido deletada)
                        try:
                            conversation = await sync_to_async(
                                Conversation.objects.select_related('tenant').get
                            )(id=conversation_id)
                        except Conversation.DoesNotExist:
                            logger.warning(f"⚠️ [GROUP INFO] Conversa não encontrada (pode ter sido deletada): {conversation_id}")
                            logger.warning(f"   Group JID: {group_jid}")
                            break  # ✅ Sair do loop de retry - conversa não existe mais
                        
                        # ✅ VALIDAÇÃO CRÍTICA: Verificar se conversation_type é realmente 'group'
                        # Se não for, NÃO atualizar para evitar sobrescrever dados de contato individual
                        if conversation.conversation_type != 'group':
                            logger.critical(f"❌ [GROUP INFO] ERRO CRÍTICO: Tentativa de atualizar conversa individual com dados de grupo!")
                            logger.critical(f"   Conversation ID: {conversation_id}")
                            logger.critical(f"   Conversation Type: {conversation.conversation_type}")
                            logger.critical(f"   Contact Phone: {conversation.contact_phone}")
                            logger.critical(f"   Group JID recebido: {group_jid}")
                            logger.critical(f"   ⚠️ NÃO ATUALIZANDO para evitar sobrescrever dados de contato individual!")
                            break  # ✅ Sair do loop - não atualizar conversa individual
                        
                        update_fields = []
                        
                        # ✅ MELHORIA: Sempre atualizar nome, mesmo se já existir (garante nome correto)
                        if group_name:
                            conversation.contact_name = group_name
                            update_fields.append('contact_name')
                            logger.info(f"✅ [GROUP INFO] Nome atualizado: {group_name}")
                        elif not conversation.contact_name or conversation.contact_name == 'Grupo WhatsApp':
                            # Se não tem nome ou é placeholder, usar JID como fallback
                            conversation.contact_name = group_jid.split('@')[0]
                            update_fields.append('contact_name')
                            logger.info(f"⚠️ [GROUP INFO] Nome não disponível, usando JID como fallback")
                        
                        if group_pic_url:
                            conversation.profile_pic_url = group_pic_url
                            update_fields.append('profile_pic_url')
                            logger.info(f"✅ [GROUP INFO] Foto atualizada")
                        
                        # Atualizar metadados
                        conversation.group_metadata = {
                            'group_id': group_jid,
                            'group_name': group_name,
                            'group_pic_url': group_pic_url,
                            'participants_count': participants_count,
                            'description': group_desc,
                            'is_group': True,
                        }
                        update_fields.append('group_metadata')
                        
                        if update_fields:
                            await sync_to_async(conversation.save)(update_fields=update_fields)
                            logger.info(f"✅ [GROUP INFO] Conversa atualizada: {conversation_id}")
                            
                            # Broadcast via WebSocket para atualizar frontend
                            try:
                                from apps.chat.utils.serialization import serialize_conversation_for_ws_async
                                
                                channel_layer = get_channel_layer()
                                if channel_layer:
                                    # ✅ CORREÇÃO: Usar serialize_conversation_for_ws_async em contexto async
                                    conv_data_serializable = await serialize_conversation_for_ws_async(conversation)
                                    
                                    # Broadcast para room específico da conversa
                                    room_group_name = f"chat_tenant_{conversation.tenant_id}_conversation_{conversation.id}"
                                    await channel_layer.group_send(
                                        room_group_name,
                                        {
                                            'type': 'conversation_updated',
                                            'conversation': conv_data_serializable
                                        }
                                    )
                                    
                                    # Broadcast global para tenant
                                    tenant_group_name = f"chat_tenant_{conversation.tenant_id}"
                                    await channel_layer.group_send(
                                        tenant_group_name,
                                        {
                                            'type': 'conversation_updated',
                                            'conversation': conv_data_serializable
                                        }
                                    )
                                    logger.info(f"📡 [GROUP INFO] Broadcast WebSocket enviado")
                            except Exception as ws_error:
                                logger.warning(f"⚠️ [GROUP INFO] Erro ao enviar WebSocket: {ws_error}", exc_info=True)
                        
                        # ✅ Sucesso, sair do loop de retry
                        return
                    
                    elif response.status_code == 404:
                        # Grupo não encontrado - não é erro de rede, não retry
                        logger.warning(f"⚠️ [GROUP INFO] Grupo não encontrado: {group_jid} (HTTP 404)")
                        return
                    
                    elif response.status_code >= 500:
                        # Erro do servidor - pode tentar novamente
                        last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                        logger.warning(f"⚠️ [GROUP INFO] Erro do servidor (tentativa {retry_count + 1}/{max_retries}): {last_error}")
                        retry_count += 1
                        if retry_count < max_retries:
                            wait_time = 2 ** retry_count  # Backoff exponencial: 2s, 4s, 8s
                            logger.info(f"⏳ [GROUP INFO] Aguardando {wait_time}s antes de retry...")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            logger.error(f"❌ [GROUP INFO] Falhou após {max_retries} tentativas")
                            return
                    
                    else:
                        # Outros erros HTTP (400, 401, 403) - não retry
                        logger.warning(f"⚠️ [GROUP INFO] Erro HTTP {response.status_code}: {response.text[:200]}")
                        return
                        
            except (httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError) as e:
                # ✅ Erros de rede/conexão - fazer retry
                last_error = str(e)
                retry_count += 1
                logger.warning(f"⚠️ [GROUP INFO] Erro de rede (tentativa {retry_count}/{max_retries}): {last_error}")
                
                if retry_count < max_retries:
                    wait_time = 2 ** retry_count  # Backoff exponencial: 2s, 4s, 8s
                    logger.info(f"⏳ [GROUP INFO] Aguardando {wait_time}s antes de retry...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"❌ [GROUP INFO] Falhou após {max_retries} tentativas: {last_error}")
                    return
            
            except httpx.HTTPStatusError as e:
                # ✅ Erros HTTP específicos
                last_error = f"HTTP {e.response.status_code}: {e.response.text[:200] if e.response else 'No response'}"
                logger.warning(f"⚠️ [GROUP INFO] Erro HTTP (tentativa {retry_count + 1}/{max_retries}): {last_error}")
                
                # Só retry para erros 5xx
                if e.response.status_code >= 500:
                    retry_count += 1
                    if retry_count < max_retries:
                        wait_time = 2 ** retry_count
                        logger.info(f"⏳ [GROUP INFO] Aguardando {wait_time}s antes de retry...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"❌ [GROUP INFO] Falhou após {max_retries} tentativas")
                        return
                else:
                    # Erros 4xx - não retry
                    logger.error(f"❌ [GROUP INFO] Erro do cliente (não retry): {last_error}")
                    return
                
    except Exception as e:
        logger.error(f"❌ [GROUP INFO] Erro inesperado ao buscar informações do grupo: {e}", exc_info=True)


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
        from django.core.cache import cache
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
    media_type: str,
    instance_name: str = None,
    api_key: str = None,
    evolution_api_url: str = None,
    decrypted_bytes: bytes = None,
    message_key: dict = None,
    retry_count: int = 0,
    mime_type: Optional[str] = None,
):
    """
    Handler: Processa mídia recebida do WhatsApp.
    
    Fluxo (padronizado com ENVIO - sem cache):
        1. ✅ Tenta obter URL descriptografada do Evolution API (se disponível)
        2. Baixa mídia da URL (descriptografada ou direta do WhatsApp)
        3. Valida tamanho antes/depois de baixar
        4. Converte áudio OGG/WEBM → MP3 (se necessário)
        5. Faz upload direto para S3 (sem processar imagem)
        6. Atualiza MessageAttachment placeholder com file_url e file_path
        7. Broadcast via WebSocket
    
    Args:
        tenant_id: UUID do tenant
        message_id: UUID da mensagem
        media_url: URL temporária do WhatsApp (pode estar criptografada)
        media_type: Tipo de mídia (image, audio, document, video)
        instance_name: Nome da instância Evolution (opcional, para descriptografar)
        api_key: API key do Evolution (opcional, para descriptografar)
        evolution_api_url: URL base do Evolution API (opcional, para descriptografar)
        decrypted_bytes: Bytes já descriptografados (opcional, se obtido via base64)
        message_key: Key completo da mensagem (opcional, para getBase64FromMediaMessage)
        mime_type: MIME type original informado pelo WhatsApp (ex: application/vnd.ms-excel)
    """
    from apps.chat.models import Message, MessageAttachment
    
    log = media_logger

    def _extract_base64_field(payload: dict) -> Optional[str]:
        """
        Evolution API pode retornar o base64 em chaves diferentes dependendo da versão.
        Essa função tenta localizar o campo correto de forma resiliente.
        """
        if not isinstance(payload, dict):
            return None
        
        candidate_keys = [
            'base64', 'data', 'result', 'file', 'fileData',
            'fileEncoded', 'media', 'content', 'payload'
        ]
        
        # 1️⃣ Procurar na raiz
        for key in candidate_keys:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
        
        # 2️⃣ Procurar dentro de payload['data'] se for dict
        nested_data = payload.get('data')
        if isinstance(nested_data, dict):
            for key in candidate_keys:
                value = nested_data.get(key)
                if isinstance(value, str) and value.strip():
                    return value
        
        return None

    log.info("📦 [INCOMING MEDIA] Processando %s | message_id=%s tenant=%s retry=%s", media_type, message_id, tenant_id, retry_count)
    log.debug("   🔗 URL original: %s", (media_url or '')[:200])
    log.debug("   📌 instance_name=%s api_key=%s evolution_api_url=%s", instance_name, bool(api_key), evolution_api_url)
    log.debug("   📌 message_key=%s decrypted_bytes=%s", message_key, bool(decrypted_bytes))

    if instance_name:
        defer, state_info = should_defer_instance(instance_name)
        if defer:
            wait_seconds = compute_backoff(retry_count)
            log.warning(
                "⏳ [INCOMING MEDIA] Instância %s em estado %s (age=%.2fs). Reagendando em %ss.",
                instance_name,
                (state_info.state if state_info else 'unknown'),
                (state_info.age if state_info else -1),
                wait_seconds,
            )
            raise InstanceTemporarilyUnavailable(instance_name, (state_info.raw if state_info else {}), wait_seconds)
    
    # ✅ REFATORAÇÃO: Priorizar base64 quando message_key disponível (mais confiável)
    # Base64 é sempre descriptografado e não depende do MongoDB estar atualizado
    final_media_url = media_url
    decrypted_data = decrypted_bytes  # Bytes já descriptografados (se vier do webhook)
    
    if instance_name and api_key and evolution_api_url and not decrypted_data:
        logger.info(f"🔐 [INCOMING MEDIA] Tentando obter mídia descriptografada do Evolution API...")
        logger.info(f"   📌 [INCOMING MEDIA] Instance: {instance_name}")
        logger.info(f"   📌 [INCOMING MEDIA] Message ID: {message_id}")
        logger.info(f"   📌 [INCOMING MEDIA] message_key disponível: {message_key is not None}")
        if message_key:
            logger.info(f"   📌 [INCOMING MEDIA] message_key.id: {message_key.get('id')}")
            logger.info(f"   📌 [INCOMING MEDIA] message_key completo: {message_key}")
        else:
            logger.warning(f"   ⚠️ [INCOMING MEDIA] message_key NÃO disponível! Base64 não será tentado como prioridade.")
        
        try:
            base_url = evolution_api_url.rstrip('/')
            async with httpx.AsyncClient(timeout=10.0) as client:
                
                # ✅ PRIORIDADE 1: Base64 quando message_key disponível (mais confiável)
                if message_key and message_key.get('id'):
                    logger.info(f"🔐 [INCOMING MEDIA] PRIORIDADE 1: Tentando /chat/getBase64FromMediaMessage (base64)...")
                    logger.info(f"   📌 [INCOMING MEDIA] message_key.id: {message_key.get('id')}")
                    logger.info(f"   📌 [INCOMING MEDIA] message_key.remoteJid: {message_key.get('remoteJid')}")
                    logger.info(f"   📌 [INCOMING MEDIA] message_key.fromMe: {message_key.get('fromMe')}")
                    logger.info(f"   📌 [INCOMING MEDIA] message_key.participant: {message_key.get('participant')}")
                    
                    endpoint_base64 = f"{base_url}/chat/getBase64FromMediaMessage/{instance_name}"
                    payload = {
                        'message': {
                            'key': {
                                'id': message_key.get('id')
                            }
                        },
                        'convertToMp4': False  # Para áudio, usar MP3 ao invés de MP4
                    }
                    # ✅ Incluir remoteJid/fromMe/participant quando disponíveis
                    if message_key.get('remoteJid'):
                        payload['message']['key']['remoteJid'] = message_key.get('remoteJid')
                    if 'fromMe' in message_key:
                        payload['message']['key']['fromMe'] = message_key.get('fromMe', False)
                    if message_key.get('participant'):
                        payload['message']['key']['participant'] = message_key.get('participant')
                    
                    logger.info(f"📤 [INCOMING MEDIA] Payload enviado: {payload}")
                    
                    try:
                        response_base64 = await client.post(
                                endpoint_base64,
                                json=payload,
                                headers={'apikey': api_key, 'Content-Type': 'application/json'}
                            )
                        
                        logger.info(f"📥 [INCOMING MEDIA] Response recebida: status={response_base64.status_code}")
                        
                        # ✅ CORREÇÃO: Aceitar 200 (OK) e 201 (Created) - ambos são válidos!
                        if response_base64.status_code in [200, 201]:
                            try:
                                data_base64 = response_base64.json()
                                logger.info(f"🔍 [INCOMING MEDIA] Response JSON keys: {list(data_base64.keys()) if isinstance(data_base64, dict) else 'N/A'}")
                                logger.info(f"🔍 [INCOMING MEDIA] Response JSON (primeiros 500 chars): {str(data_base64)[:500]}")
                                base64_data = _extract_base64_field(data_base64)
                                logger.info(f"🔍 [INCOMING MEDIA] Base64 extraído: {'SIM' if base64_data else 'NÃO'} (tamanho: {len(base64_data) if base64_data else 0})")
                            except Exception as json_error:
                                logger.error(f"❌ [INCOMING MEDIA] Erro ao parsear JSON da resposta: {json_error}", exc_info=True)
                                logger.error(f"   📄 [INCOMING MEDIA] Response text (primeiros 500 chars): {response_base64.text[:500]}")
                                raise
                            
                            if base64_data:
                                # ✅ CRUCIAL: Decodificar base64 para bytes (já descriptografado)
                                import base64
                                try:
                                    # Se vier como data URI, remover prefixo (ex: data:application/pdf;base64,...)
                                    if base64_data.strip().startswith('data:'):
                                        comma_index = base64_data.find(',')
                                        if comma_index != -1:
                                            base64_data = base64_data[comma_index + 1:]
                                    base64_data = base64_data.strip()
                                    # ✅ IMPORTANTE: O base64 pode vir truncado no log, mas está completo no JSON
                                    decoded_bytes = base64.b64decode(base64_data)
                                    
                                    logger.info(f"✅ [INCOMING MEDIA] Base64 obtido via /chat/getBase64FromMediaMessage!")
                                    logger.info(f"   📏 [INCOMING MEDIA] Status: {response_base64.status_code} ({'OK' if response_base64.status_code == 200 else 'Created'})")
                                    logger.info(f"   📏 [INCOMING MEDIA] Tamanho base64 (string): {len(base64_data)} caracteres")
                                    logger.info(f"   📏 [INCOMING MEDIA] Tamanho decodificado: {len(decoded_bytes)} bytes")
                                    logger.info(f"   🔍 [INCOMING MEDIA] Primeiros bytes (hex): {decoded_bytes[:16].hex()}")
                                    
                                    # ✅ CRUCIAL: Usar bytes descriptografados diretamente
                                    decrypted_data = decoded_bytes
                                    logger.info(f"✅ [INCOMING MEDIA] Bytes descriptografados prontos para uso!")
                                except Exception as decode_error:
                                    logger.error(f"❌ [INCOMING MEDIA] Erro ao decodificar base64: {decode_error}", exc_info=True)
                                    logger.error(f"   📄 [INCOMING MEDIA] Base64 (primeiros 100 chars): {base64_data[:100] if base64_data else 'None'}...")
                            else:
                                logger.warning(f"⚠️ [INCOMING MEDIA] /chat/getBase64FromMediaMessage retornou sem base64")
                                logger.warning(f"   📄 [INCOMING MEDIA] Response keys: {list(data_base64.keys()) if isinstance(data_base64, dict) else 'N/A'}")
                        else:
                            logger.warning(f"⚠️ [INCOMING MEDIA] /chat/getBase64FromMediaMessage retornou {response_base64.status_code}")
                            if response_base64.status_code != 404:
                                logger.warning(f"   📄 [INCOMING MEDIA] Response: {response_base64.text[:200]}")
                    except Exception as e_base64:
                        logger.warning(f"⚠️ [INCOMING MEDIA] Erro ao tentar /chat/getBase64FromMediaMessage: {e_base64}", exc_info=True)
                
                # ✅ PRIORIDADE 2: URL descriptografada se base64 não funcionou ou não tiver message_key
                if not decrypted_data:
                    logger.info(f"🔐 [INCOMING MEDIA] PRIORIDADE 2: Tentando /s3/getMediaUrl (URL descriptografada)...")
                    logger.info(f"   📌 [INCOMING MEDIA] Motivo: base64 não funcionou ou message_key não disponível")
                    endpoint_url = f"{base_url}/s3/getMediaUrl/{instance_name}"
                    
                    response_url = await client.get(
                        endpoint_url,
                        params={'mediaId': message_id},
                        headers={'apikey': api_key}
                    )
                    
                    if response_url.status_code == 200:
                        data_url = response_url.json()
                        decrypted_url = data_url.get('url') or data_url.get('mediaUrl')
                        
                        if decrypted_url:
                            logger.info(f"✅ [INCOMING MEDIA] URL descriptografada obtida via /s3/getMediaUrl!")
                            logger.info(f"   🔗 [INCOMING MEDIA] URL descriptografada: {decrypted_url[:100]}...")
                            final_media_url = decrypted_url
                        else:
                            logger.warning(f"⚠️ [INCOMING MEDIA] /s3/getMediaUrl retornou sucesso mas sem URL")
                    else:
                        logger.warning(f"⚠️ [INCOMING MEDIA] /s3/getMediaUrl retornou {response_url.status_code}")
                    
                    # ✅ FALLBACK: Tentar base64 com message_id se não tiver message_key
                    if not decrypted_data and final_media_url == media_url and not message_key:
                        logger.info(f"🔐 [INCOMING MEDIA] FALLBACK: Tentando /chat/getBase64FromMediaMessage com message_id...")
                        endpoint_fallback = f"{base_url}/chat/getBase64FromMediaMessage/{instance_name}"
                        payload_fallback = {
                            'message': {
                                'key': {
                                    'id': message_id
                                }
                            },
                            'convertToMp4': False
                        }
                        if message_key and message_key.get('remoteJid'):
                            payload_fallback['message']['key']['remoteJid'] = message_key.get('remoteJid')
                        if message_key and 'fromMe' in message_key:
                            payload_fallback['message']['key']['fromMe'] = message_key.get('fromMe', False)
                        
                        try:
                            response_fallback = await client.post(
                                endpoint_fallback,
                                json=payload_fallback,
                                headers={'apikey': api_key, 'Content-Type': 'application/json'}
                            )
                            
                            # ✅ CORREÇÃO: Aceitar 200 (OK) e 201 (Created) - ambos são válidos!
                            if response_fallback.status_code in [200, 201]:
                                data_fallback = response_fallback.json()
                                base64_fallback = _extract_base64_field(data_fallback)
                                
                                if base64_fallback:
                                    import base64
                                    try:
                                        if base64_fallback.strip().startswith('data:'):
                                            comma_index = base64_fallback.find(',')
                                            if comma_index != -1:
                                                base64_fallback = base64_fallback[comma_index + 1:]
                                        base64_fallback = base64_fallback.strip()
                                        decoded_fallback = base64.b64decode(base64_fallback)
                                        logger.info(f"✅ [INCOMING MEDIA] Base64 obtido via fallback!")
                                        logger.info(f"   📏 [INCOMING MEDIA] Status: {response_fallback.status_code}")
                                        logger.info(f"   📏 [INCOMING MEDIA] Tamanho: {len(decoded_fallback)} bytes")
                                        decrypted_data = decoded_fallback
                                    except Exception as e_fallback:
                                        logger.error(f"❌ [INCOMING MEDIA] Erro ao decodificar base64 do fallback: {e_fallback}", exc_info=True)
                        except Exception as e_fallback:
                            logger.warning(f"⚠️ [INCOMING MEDIA] Erro no fallback base64: {e_fallback}", exc_info=True)
                
                # Se todos os métodos falharam, usar URL original (pode estar criptografada)
                if final_media_url == media_url and not decrypted_data:
                    logger.warning(f"⚠️ [INCOMING MEDIA] Todos os métodos falharam, usando URL original (pode estar criptografada)")
        except Exception as e:
            logger.warning(f"⚠️ [INCOMING MEDIA] Erro ao obter mídia descriptografada: {e}. Usando URL original.", exc_info=True)
    
    # ✅ Se URL original tem .enc, avisar
    if '.enc' in media_url.lower() and final_media_url == media_url and not decrypted_data:
        logger.warning(f"⚠️ [INCOMING MEDIA] URL original tem .enc e não foi possível descriptografar!")
        logger.warning(f"   🔐 [INCOMING MEDIA] URL pode estar criptografada: {media_url[:100]}...")
    
    # ✅ RETRY: Tentar até 3 vezes em caso de falha de rede
    max_retries = 3
    retry_count = 0
    media_data = None
    original_mime_type = (mime_type or '').strip()
    content_type = original_mime_type or 'application/octet-stream'
    
    # ✅ OPÇÃO 1: Se já temos bytes descriptografados, usar diretamente
    if decrypted_data:
        logger.info(f"✅ [INCOMING MEDIA] Usando bytes já descriptografados (não precisa baixar)")
        logger.info(f"   📏 [INCOMING MEDIA] Tamanho: {len(decrypted_data)} bytes")
        media_data = decrypted_data
        # ✅ Detectar Content-Type dos bytes
        from apps.chat.utils.image_processing import validate_magic_numbers
        is_valid_magic, detected_format, detected_mime = validate_magic_numbers(decrypted_data)
        if detected_mime:
            content_type = detected_mime
            logger.info(f"   📄 [INCOMING MEDIA] Content-Type detectado: {content_type}")
        else:
            # Inferir do media_type
            if media_type == 'image':
                content_type = original_mime_type or 'image/jpeg'
            elif media_type == 'video':
                content_type = original_mime_type or 'video/mp4'
            elif media_type == 'audio':
                content_type = original_mime_type or 'audio/mpeg'
            elif media_type == 'document':
                content_type = original_mime_type or 'application/octet-stream'
    
    # ✅ OPÇÃO 2: Se não temos bytes descriptografados, baixar da URL
    if not media_data:
        # ✅ VALIDAÇÃO: Verificar tamanho ANTES de baixar (economia de recursos)
        from django.conf import settings
        MAX_SIZE = int(getattr(settings, 'ATTACHMENTS_MAX_SIZE_MB', 50)) * 1024 * 1024  # 50MB padrão
        
        try:
            # HEAD request para verificar tamanho antes de baixar
            async with httpx.AsyncClient(timeout=10.0) as client:
                head_response = await client.head(final_media_url)
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
        
        while retry_count < max_retries:
            try:
                # 1. Baixar do WhatsApp (ou URL descriptografada do Evolution API)
                async with httpx.AsyncClient(timeout=30.0) as client:
                    logger.info(f"📥 [INCOMING MEDIA] Baixando de: {final_media_url}")
                    response = await client.get(final_media_url)
                    response.raise_for_status()
                
                # ✅ CRUCIAL: Verificar se response.content é bytes
                media_data = response.content
                if not isinstance(media_data, bytes):
                    logger.error(f"❌ [INCOMING MEDIA] response.content não é bytes! Tipo: {type(media_data)}")
                    # Tentar converter se for string
                    if isinstance(media_data, str):
                        logger.warning(f"⚠️ [INCOMING MEDIA] Tentando converter string para bytes...")
                        media_data = media_data.encode('utf-8')
                    else:
                        raise ValueError(f"response.content é {type(media_data)}, esperado bytes")
                
                content_type = response.headers.get('content-type', 'application/octet-stream')
                
                # ✅ DEBUG: Log detalhado do que foi baixado
                logger.info(f"📥 [INCOMING MEDIA] Download concluído:")
                logger.info(f"   📏 [INCOMING MEDIA] Tamanho: {len(media_data)} bytes")
                logger.info(f"   📄 [INCOMING MEDIA] Content-Type: {content_type}")
                logger.info(f"   🔍 [INCOMING MEDIA] Primeiros bytes (hex): {media_data[:16].hex()}")
                logger.info(f"   🔍 [INCOMING MEDIA] Primeiros bytes (repr): {repr(media_data[:16])}")
                logger.info(f"   🔍 [INCOMING MEDIA] Últimos bytes (hex): {media_data[-16:].hex() if len(media_data) >= 16 else media_data.hex()}")
                
                # ✅ VERIFICAR: Se arquivo tem extensão .enc (criptografado)
                if '.enc' in media_url.lower():
                    logger.warning(f"⚠️ [INCOMING MEDIA] Arquivo com extensão .enc detectada! Pode estar criptografado.")
                    logger.warning(f"   🔐 [INCOMING MEDIA] URL contém .enc: {media_url}")
                
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
                
                # ✅ VALIDAÇÃO: Verificar tamanho real vs Content-Length
                expected_length = int(response.headers.get('content-length', 0))
                if expected_length > 0 and abs(len(media_data) - expected_length) > 1024:  # Diferença > 1KB
                    logger.warning(f"⚠️ [INCOMING MEDIA] Tamanho real ({len(media_data)}) difere do Content-Length ({expected_length})")
                
                # ✅ VALIDAÇÃO: Magic numbers (primeiros bytes)
                from apps.chat.utils.image_processing import validate_magic_numbers, validate_image_data
                is_valid_magic, detected_format, detected_mime = validate_magic_numbers(media_data)
                
                if is_valid_magic:
                    logger.info(f"✅ [INCOMING MEDIA] Magic numbers válidos: {detected_format} ({detected_mime})")
                    logger.info(f"   🔍 [INCOMING MEDIA] Primeiros bytes (hex): {media_data[:16].hex()}")
                else:
                    logger.warning(f"⚠️ [INCOMING MEDIA] Magic numbers não reconhecidos (primeiros bytes: {media_data[:16].hex()})")
                    # Continuar mesmo assim (pode ser formato não suportado)
                
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
        
        # ✅ VALIDAÇÃO: Validar dados baixados (magic numbers + PIL para imagens)
        # ✅ EXCEÇÃO: Se arquivo tem extensão .enc, pode estar criptografado - não validar magic numbers
        is_encrypted = '.enc' in media_url.lower()
        
        if is_encrypted:
            logger.warning(f"⚠️ [INCOMING MEDIA] Arquivo .enc detectado - pode estar criptografado. Pulando validação de magic numbers.")
            # Continuar mesmo sem validar magic numbers (arquivo pode estar criptografado)
            is_valid = True
            validation_error = None
            detected_format = None
        else:
            from apps.chat.utils.image_processing import validate_image_data
            is_valid, validation_error, detected_format = validate_image_data(media_data, media_type)
            
            if not is_valid:
                logger.error(f"❌ [INCOMING MEDIA] Validação falhou: {validation_error}")
                # Marcar attachment como erro
                try:
                    existing = await sync_to_async(lambda: MessageAttachment.objects.filter(
                        message__id=message_id,
                        file_url='',
                        file_path=''
                    ).first())()
                    if existing:
                        from apps.chat.utils.serialization import normalize_metadata
                        metadata = normalize_metadata(existing.metadata)
                        metadata['error'] = f'Validação falhou: {validation_error}'
                        metadata.pop('processing', None)
                        existing.metadata = metadata
                        await sync_to_async(existing.save)(update_fields=['metadata'])
                except Exception:
                    pass
                return  # Não processar arquivo inválido
        
        # ✅ DETECÇÃO: Usar formato detectado pelos magic numbers
        from apps.chat.utils.image_processing import validate_magic_numbers
        is_valid_magic, detected_format_final, detected_mime = validate_magic_numbers(media_data)
        
        if is_valid_magic and detected_mime:
            # Usar MIME type detectado se for mais confiável que o Content-Type do WhatsApp
            if not content_type or content_type.startswith('application/octet-stream'):
                content_type = detected_mime
                logger.info(f"✅ [INCOMING MEDIA] Content-Type detectado pelos magic numbers: {detected_mime}")
            elif detected_mime != content_type:
                logger.warning(f"⚠️ [INCOMING MEDIA] Content-Type do WhatsApp ({content_type}) difere do detectado ({detected_mime}). Usando detectado.")
                content_type = detected_mime
        
        # 2. Converter áudio OGG/WEBM → MP3 (padronizado com ENVIO)
        processed_data = media_data
        
        # ✅ CORREÇÃO: Buscar original_filename do attachment se disponível (já foi limpo no webhook)
        # Se não tiver, extrair da URL e limpar
        from apps.chat.models import MessageAttachment
        attachment_placeholder = await sync_to_async(lambda: MessageAttachment.objects.filter(
            message__id=message_id,
            file_url=''
        ).order_by('-created_at').first())()
        
        if attachment_placeholder and attachment_placeholder.original_filename:
            filename = attachment_placeholder.original_filename
            logger.info(f"✅ [INCOMING MEDIA] Usando original_filename do attachment: {filename}")
        else:
            # Fallback: extrair da URL e limpar
            raw_filename = urlparse(media_url).path.split('/')[-1] or f"media_{message_id}"
            from apps.chat.webhooks import clean_filename
            filename = clean_filename(raw_filename, message_id=message_id, mime_type=content_type)
            logger.info(f"🧹 [INCOMING MEDIA] Nome limpo da URL: {filename}")
        
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
        
        # ✅ MELHORIA: Usar formato detectado pelos magic numbers se disponível
        if is_valid_magic and detected_format_final:
            # Mapear formato detectado para extensão
            format_to_ext = {
                'jpeg': 'jpg',
                'png': 'png',
                'gif': 'gif',
                'webp': 'webp',
                'mp4': 'mp4',
                'mp3': 'mp3',
                'pdf': 'pdf',
                'ogg': 'ogg',
                'webm': 'webm'
            }
            detected_ext = format_to_ext.get(detected_format_final)
            if detected_ext:
                file_ext = detected_ext
                logger.info(f"✅ [INCOMING MEDIA] Extensão detectada pelos magic numbers: {detected_ext}")
        
        # Se ainda não tem extensão, inferir do content_type
        if not file_ext and content_type:
            if 'image' in content_type:
                file_ext = 'jpg'  # Default para JPEG
            elif 'audio' in content_type:
                file_ext = 'mp3' if 'mpeg' in content_type else 'ogg'
            elif 'video' in content_type:
                file_ext = 'mp4'
            elif 'pdf' in content_type:
                file_ext = 'pdf'
            else:
                file_ext = 'bin'
        
        s3_path = f"chat/{tenant_id}/attachments/{attachment_id}.{file_ext}"
        
        # ✅ DEBUG: Log detalhado antes do upload
        logger.info(f"📤 [INCOMING MEDIA] Preparando upload para S3:")
        logger.info(f"   📦 [INCOMING MEDIA] S3 Path: {s3_path}")
        logger.info(f"   📄 [INCOMING MEDIA] Content-Type: {content_type}")
        logger.info(f"   📏 [INCOMING MEDIA] Tamanho: {len(processed_data)} bytes ({len(processed_data) / 1024:.2f} KB)")
        logger.info(f"   🔍 [INCOMING MEDIA] Primeiros bytes (hex): {processed_data[:16].hex()}")
        logger.info(f"   📝 [INCOMING MEDIA] Extensão: {file_ext}")
        if is_valid_magic:
            logger.info(f"   ✅ [INCOMING MEDIA] Formato detectado: {detected_format_final} ({detected_mime})")
        
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
                
                # ✅ VALIDAÇÃO: Verificar se arquivo foi salvo corretamente no S3
                try:
                    file_exists = s3_manager.file_exists(s3_path)
                    if file_exists:
                        logger.info(f"✅ [INCOMING MEDIA] Arquivo verificado no S3: {s3_path}")
                    else:
                        logger.error(f"❌ [INCOMING MEDIA] Arquivo não encontrado no S3 após upload: {s3_path}")
                        # Continuar mesmo assim (pode ser delay no S3)
                except Exception as verify_error:
                    logger.warning(f"⚠️ [INCOMING MEDIA] Erro ao verificar arquivo no S3: {verify_error}")
                
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
                'size_bytes': len(processed_data),  # ✅ NOVO: Incluir tamanho do arquivo
                'original_filename': filename,  # ✅ NOVO: Incluir nome original do arquivo
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

