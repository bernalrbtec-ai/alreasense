"""
Webhook handler para Evolution API.
Recebe eventos de mensagens e atualiza o banco.
"""
import logging
import httpx
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from apps.chat.models import Conversation, Message, MessageAttachment
# download_attachment removido - agora usa process_incoming_media diretamente (S3 + cache Redis)
from apps.tenancy.models import Tenant
from apps.connections.models import EvolutionConnection
from apps.notifications.models import WhatsAppInstance

logger = logging.getLogger(__name__)


def _mask_digits(value: str) -> str:
    """Masca números, preservando apenas os 4 últimos dígitos."""
    if not value or not isinstance(value, str):
        return value
    digits = ''.join(ch for ch in value if ch.isdigit())
    if not digits:
        return value
    suffix = digits[-4:] if len(digits) > 4 else digits
    return f"***{suffix}"


def _mask_remote_jid(remote_jid: str) -> str:
    """Masca remoteJid, preservando domínio."""
    if not remote_jid or not isinstance(remote_jid, str):
        return remote_jid
    if '@' not in remote_jid:
        return _mask_digits(remote_jid)
    user, domain = remote_jid.split('@', 1)
    return f"{_mask_digits(user)}@{domain}"


def _truncate_text(value: str, limit: int = 120) -> str:
    if not isinstance(value, str):
        return value
    return value if len(value) <= limit else f"{value[:limit]}…"


def mask_sensitive_data(data, parent_key: str = ""):
    """
    Retorna uma cópia do payload com dados sensíveis mascarados.
    """
    sensitive_keys_phone = {'number', 'phone', 'contact_phone'}
    sensitive_keys_remote = {'remoteJid', 'jid', 'participant'}
    sensitive_keys_ids = {'id', 'messageId', 'message_id', 'keyId', 'key_id'}
    sensitive_keys_text = {'text', 'content', 'body'}

    if isinstance(data, dict):
        masked = {}
        for key, value in data.items():
            key_lower = key.lower()
            if key in sensitive_keys_phone or key_lower in sensitive_keys_phone:
                masked[key] = _mask_digits(value) if isinstance(value, str) else value
            elif key in sensitive_keys_remote or key_lower in sensitive_keys_remote:
                masked[key] = _mask_remote_jid(value) if isinstance(value, str) else value
            elif key in sensitive_keys_ids or key_lower in sensitive_keys_ids:
                masked[key] = _mask_digits(value) if isinstance(value, str) else value
            elif key in sensitive_keys_text or key_lower in sensitive_keys_text:
                masked[key] = _truncate_text(value)
            else:
                masked[key] = mask_sensitive_data(value, key)
        return masked

    if isinstance(data, list):
        return [mask_sensitive_data(item, parent_key) for item in data]

    return data


def process_mentions_optimized(mentioned_jids: list, tenant, conversation=None) -> list:
    """
    Processa menções de forma otimizada (1 query ao invés de N).
    
    Prioridade de busca de nomes:
    1. Participantes do grupo (se conversation for grupo)
    2. Contatos do banco de dados
    3. Telefone formatado (fallback)
    
    Args:
        mentioned_jids: Lista de JIDs mencionados (ex: ["5511999999999@s.whatsapp.net"])
        tenant: Tenant para buscar contatos
        conversation: Conversation opcional (para buscar participantes do grupo)
    
    Returns:
        Lista de menções processadas: [{'phone': '...', 'name': '...'}, ...]
    """
    if not mentioned_jids:
        return []
    
    from apps.notifications.services import normalize_phone
    from apps.contacts.models import Contact
    
    # Função auxiliar para detectar se um número é LID (não é telefone válido)
    def is_lid_number(phone: str) -> bool:
        """
        Detecta se um número é LID (Local ID do WhatsApp) ao invés de telefone real.
        LIDs sempre terminam com @lid. Números com @g.us são grupos válidos, não LIDs.
        """
        if not phone:
            return False
        
        # ✅ CORREÇÃO CRÍTICA: Verificar sufixo primeiro
        # @g.us = grupo válido (NÃO é LID)
        # @lid = LID de usuário (É LID)
        # @s.whatsapp.net = JID de usuário (NÃO é LID)
        if phone.endswith('@lid'):
            return True
        if phone.endswith('@g.us') or phone.endswith('@s.whatsapp.net'):
            return False
        
        # Se não tem sufixo, verificar se número é muito longo (provavelmente LID)
        clean = phone.replace('+', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '').strip()
        
        # Se tem 16+ dígitos sem sufixo, provavelmente é LID
        if len(clean) >= 16:
            return True
        
        return False
    
    # Função auxiliar para formatar telefone para exibição
    def format_phone_for_display(phone: str) -> str:
        """Formata telefone para exibição: (11) 99999-9999"""
        if not phone:
            return phone
        
        import re
        # Remover tudo exceto números
        clean = re.sub(r'\D', '', phone)
        
        # Remover código do país (55) se presente
        digits = clean
        if clean.startswith('55') and len(clean) >= 12:
            digits = clean[2:]
        
        # Formatar baseado no tamanho
        if len(digits) == 11:
            return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
        elif len(digits) == 10:
            return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
        
        return phone  # Retornar original se não conseguir formatar
    
    # ✅ CORREÇÃO CRÍTICA: Mapear JID -> telefone real (não usar LID como telefone)
    jid_to_real_phone = {}  # JID -> telefone real do participante
    jid_to_name = {}  # JID completo -> nome
    
    # Primeiro, buscar telefones reais dos participantes do grupo (especialmente para @lid)
    if conversation and conversation.conversation_type == 'group':
        # ✅ IMPORTANTE: Recarregar conversa do banco para ter dados atualizados
        conversation.refresh_from_db()
        group_metadata = conversation.group_metadata or {}
        participants = group_metadata.get('participants', [])
        
        logger.info(f"🔍 [MENTIONS] Buscando em {len(participants)} participantes do grupo")
        logger.info(f"   Conversa ID: {conversation.id}")
        logger.info(f"   Group metadata keys: {list(group_metadata.keys())}")
        
        for i, p in enumerate(participants):
            participant_phone = p.get('phone', '')
            participant_jid = p.get('jid', '')
            participant_phone_number = p.get('phoneNumber', '') or p.get('phone_number', '')
            participant_name = p.get('name', '') or p.get('pushname', '')
            
            logger.debug(f"   Participante {i+1}: JID={participant_jid}, phone={participant_phone[:20] if participant_phone else 'N/A'}..., phoneNumber={participant_phone_number[:30] if participant_phone_number else 'N/A'}..., name={participant_name[:20] if participant_name else 'N/A'}...")
            
            if participant_jid:
                # ✅ CORREÇÃO CRÍTICA: Se JID é @lid, usar phoneNumber se disponível
                if participant_jid.endswith('@lid'):
                    logger.info(f"   🔍 [@LID] Processando JID @lid: {participant_jid}")
                    
                    # ✅ PRIORIDADE: Tentar usar phoneNumber primeiro (JID real)
                    if participant_phone_number:
                        phone_raw = participant_phone_number.split('@')[0]
                        normalized_real_phone = normalize_phone(phone_raw)
                        if normalized_real_phone:
                            jid_to_real_phone[participant_jid] = normalized_real_phone
                            logger.info(f"   ✅ [@LID] JID {participant_jid} -> telefone real via phoneNumber: {normalized_real_phone}")
                        else:
                            logger.warning(f"   ⚠️ [@LID] JID {participant_jid} não conseguiu normalizar phoneNumber: {participant_phone_number}")
                            jid_to_real_phone[participant_jid] = None
                    elif participant_phone:
                        # ✅ VALIDAÇÃO CRÍTICA: Verificar se o phone também é LID
                        if is_lid_number(participant_phone):
                            logger.warning(f"   ⚠️ [@LID] JID {participant_jid} tem phone que também é LID: {participant_phone[:30]}...")
                            logger.warning(f"   ⚠️ [@LID] Não será possível buscar contatos por telefone para este participante")
                            # Não usar como telefone real, mas salvar o LID para busca em contatos
                            jid_to_real_phone[participant_jid] = None  # Marcar como sem telefone válido
                        else:
                            # Normalizar telefone real do participante
                            clean_phone = participant_phone.replace('+', '').replace(' ', '').strip()
                            normalized_real_phone = normalize_phone(clean_phone)
                            if normalized_real_phone:
                                jid_to_real_phone[participant_jid] = normalized_real_phone
                                logger.info(f"   ✅ [@LID] JID {participant_jid} -> telefone real: {normalized_real_phone}")
                            else:
                                logger.warning(f"   ⚠️ [@LID] JID {participant_jid} não conseguiu normalizar phone: {participant_phone}")
                                jid_to_real_phone[participant_jid] = None
                    else:
                        logger.warning(f"   ⚠️ [@LID] JID {participant_jid} não tem phone nem phoneNumber, não será possível buscar contatos")
                else:
                    # JID não é @lid, usar phone normalmente
                    if participant_phone:
                        clean_phone = participant_phone.replace('+', '').replace(' ', '').strip()
                        normalized_phone = normalize_phone(clean_phone)
                        if normalized_phone:
                            jid_to_real_phone[participant_jid] = normalized_phone
                
                # Mapear JID -> nome
                if participant_name:
                    jid_to_name[participant_jid] = participant_name
                    logger.debug(f"   ✅ Mapeado JID -> nome: {participant_jid} -> {participant_name}")
    
    # Normalizar todos os telefones primeiro (usar telefone real quando disponível)
    normalized_phones = []
    jid_to_phone = {}  # Mapear JID original -> telefone normalizado
    
    for mentioned_jid in mentioned_jids:
        # ✅ CORREÇÃO: Se temos telefone real do participante (@lid), usar ele
        if mentioned_jid in jid_to_real_phone:
            normalized_phone = jid_to_real_phone[mentioned_jid]
            normalized_phones.append(normalized_phone)
            jid_to_phone[mentioned_jid] = normalized_phone
            logger.info(f"   ✅ [MENTIONS] Usando telefone real para @lid: {mentioned_jid} -> {normalized_phone}")
        else:
            # Formato normal: "5511999999999@s.whatsapp.net" ou apenas "5511999999999"
            phone_raw = mentioned_jid.split('@')[0] if '@' in mentioned_jid else mentioned_jid
            
            # ✅ VALIDAÇÃO: Se é @lid mas não temos telefone real, não tentar normalizar LID
            if mentioned_jid.endswith('@lid'):
                logger.warning(f"   ⚠️ [MENTIONS] JID @lid sem telefone real: {mentioned_jid}, pulando busca de contatos")
                jid_to_phone[mentioned_jid] = None  # Marcar como sem telefone válido
                continue
            
            # Normalizar telefone
            normalized_phone = normalize_phone(phone_raw)
            if normalized_phone:
                normalized_phones.append(normalized_phone)
                jid_to_phone[mentioned_jid] = normalized_phone
            else:
                logger.warning(f"⚠️ [WEBHOOK] Não foi possível normalizar telefone da menção: {phone_raw}")
    
    # ✅ MELHORIA 1: Buscar nomes dos participantes do grupo
    phone_to_name = {}  # Telefone normalizado -> nome
    
    if conversation and conversation.conversation_type == 'group':
        group_metadata = conversation.group_metadata or {}
        participants = group_metadata.get('participants', [])
        
        for p in participants:
            participant_phone = p.get('phone', '')
            participant_jid = p.get('jid', '')
            participant_name = p.get('name', '') or p.get('pushname', '')
            
            if not participant_name:
                continue
            
            # Normalizar telefone para comparação
            if participant_phone:
                clean_participant_phone = participant_phone.replace('+', '').replace(' ', '').strip()
                normalized_participant_phone = normalize_phone(clean_participant_phone)
                if normalized_participant_phone:
                    phone_to_name[normalized_participant_phone] = participant_name
    
    # ✅ MELHORIA 2: Buscar todos os contatos CADASTRADOS primeiro (prioridade máxima)
    phone_to_contact = {}
    jid_to_contact = {}  # JID/LID -> nome do contato (para buscar por LID também)
    
    if normalized_phones:
        contacts = Contact.objects.filter(
            tenant=tenant,
            phone__in=normalized_phones
        ).values('phone', 'name', 'metadata')
        
        # Criar mapa telefone -> nome dos contatos cadastrados
        for contact in contacts:
            normalized_contact_phone = normalize_phone(contact['phone'])
            if normalized_contact_phone:
                # ✅ IMPORTANTE: Contatos cadastrados têm prioridade sobre participantes do grupo
                contact_name = contact.get('name', '').strip()
                if contact_name:
                    phone_to_contact[normalized_contact_phone] = contact_name
            
            # ✅ NOVO: Buscar também por LID no metadata do contato
            contact_metadata = contact.get('metadata') or {}
            if isinstance(contact_metadata, dict):
                # Verificar se tem LID salvo no metadata
                contact_lid = contact_metadata.get('lid') or contact_metadata.get('jid')
                if contact_lid:
                    contact_name = contact.get('name', '').strip()
                    if contact_name:
                        jid_to_contact[contact_lid] = contact_name
                        logger.debug(f"   📝 [CONTATOS] Contato encontrado por LID: {contact_lid} -> {contact_name}")
    
    # ✅ NOVO: Buscar contatos também pelos JIDs originais (para LIDs sem telefone válido)
    lids_to_search = [jid for jid in mentioned_jids if jid.endswith('@lid')]
    if lids_to_search:
        # Buscar contatos que têm esses LIDs no metadata
        # Usar Q objects para buscar em JSONField
        from django.db.models import Q
        lid_queries = Q()
        for lid in lids_to_search:
            # Buscar LID no metadata (pode estar em 'lid' ou 'jid')
            lid_queries |= Q(metadata__lid=lid) | Q(metadata__jid=lid)
        
        if lid_queries:
            contacts_by_lid = Contact.objects.filter(
                tenant=tenant
            ).filter(lid_queries).values('name', 'metadata')
            
            for contact in contacts_by_lid:
                contact_name = contact.get('name', '').strip()
                if contact_name:
                    # Encontrar qual LID corresponde a este contato
                    contact_metadata = contact.get('metadata') or {}
                    contact_lid = contact_metadata.get('lid') or contact_metadata.get('jid')
                    if contact_lid and contact_lid in lids_to_search:
                        jid_to_contact[contact_lid] = contact_name
                        logger.info(f"   ✅ [CONTATOS] Contato encontrado por LID no metadata: {contact_lid} -> {contact_name}")
    
    # Processar menções usando os mapas (prioridade: CONTATOS CADASTRADOS > grupo > telefone formatado)
    mentions_list = []
    logger.info(f"🔄 [MENTIONS] Processando {len(mentioned_jids)} menções mencionadas")
    logger.info(f"   JIDs mencionados: {mentioned_jids}")
    logger.info(f"   JIDs com telefone real mapeado: {list(jid_to_real_phone.keys())}")
    logger.info(f"   JIDs com nome mapeado: {list(jid_to_name.keys())}")
    logger.info(f"   Contatos encontrados por telefone: {list(phone_to_contact.keys())}")
    logger.info(f"   Contatos encontrados por LID: {list(jid_to_contact.keys())}")
    
    for mentioned_jid in mentioned_jids:
        logger.info(f"   🔍 [MENTIONS] Processando menção: {mentioned_jid}")
        normalized_phone = jid_to_phone.get(mentioned_jid)
        logger.debug(f"      Telefone normalizado: {normalized_phone}")
        
        # ✅ CORREÇÃO: Se não temos telefone válido (ex: @lid sem phone), usar apenas nome do grupo
        if not normalized_phone:
            # Tentar buscar pelo JID completo no grupo
            mention_name = jid_to_name.get(mentioned_jid)
            if mention_name:
                # Temos nome do grupo, mas não telefone válido para buscar contatos
                mentions_list.append({
                    'jid': mentioned_jid,  # ✅ IMPORTANTE: Salvar JID original
                    'phone': '',  # Sem telefone válido
                    'name': mention_name
                })
                logger.info(f"   👤 Menção (sem telefone válido): {mention_name} | JID: {mentioned_jid}")
            continue
        
        # ✅ CORREÇÃO CRÍTICA: Prioridade de busca:
        # 1. CONTATOS CADASTRADOS por JID/LID (prioridade máxima - para LIDs)
        # 2. CONTATOS CADASTRADOS por telefone (prioridade máxima)
        # 3. Participantes do grupo (telefone normalizado)
        # 4. Participantes do grupo (JID completo - apenas se não encontrou por telefone)
        # 5. Telefone formatado (fallback - nunca mostrar LID)
        mention_name = (
            jid_to_contact.get(mentioned_jid) or  # 1. Contato cadastrado por LID/JID (PRIORIDADE MÁXIMA para LIDs)
            phone_to_contact.get(normalized_phone) or  # 2. Contato cadastrado por telefone (PRIORIDADE MÁXIMA)
            phone_to_name.get(normalized_phone) or  # 3. Telefone normalizado no grupo
            jid_to_name.get(mentioned_jid) or  # 4. JID completo no grupo (apenas se não encontrou)
            format_phone_for_display(normalized_phone) if normalized_phone and not is_lid_number(normalized_phone) else None  # 5. Telefone formatado (fallback - nunca LID)
        )
        
        # ✅ VALIDAÇÃO: Se não encontrou nome e o telefone é LID, usar apenas nome do grupo ou "Usuário"
        if not mention_name:
            if normalized_phone and is_lid_number(normalized_phone):
                # Telefone é LID, usar nome do grupo ou fallback
                mention_name = jid_to_name.get(mentioned_jid) or "Usuário"
                logger.warning(f"⚠️ [MENTIONS] Telefone é LID e não encontrou nome, usando: {mention_name}")
            else:
                # Telefone válido mas não encontrou nome, formatar telefone
                mention_name = format_phone_for_display(normalized_phone) if normalized_phone else "Usuário"
        
        # ✅ VALIDAÇÃO: Garantir que nunca retornamos LID ou JID como nome
        # Se o nome contém @lid ou é muito longo (provavelmente LID), usar telefone formatado
        if mention_name and ('@lid' in mention_name.lower() or '@s.whatsapp.net' in mention_name.lower() or len(mention_name) > 20):
            logger.warning(f"⚠️ [MENTIONS] Nome inválido detectado (possível LID): {mention_name}, usando telefone formatado")
            mention_name = format_phone_for_display(normalized_phone)
        
        # ✅ VALIDAÇÃO: Garantir que phone nunca contenha LID
        # Se normalized_phone é LID, não usar como phone
        clean_phone = normalized_phone
        if normalized_phone:
            if is_lid_number(normalized_phone):
                # Phone é LID, não usar como telefone válido
                logger.warning(f"⚠️ [MENTIONS] Phone é LID: {normalized_phone[:20]}..., não usando como telefone")
                clean_phone = ''  # Não usar LID como phone
            elif len(normalized_phone) > 15 or not normalized_phone.replace('+', '').isdigit():
                # Parece ser formato inválido, tentar extrair apenas números
                import re
                digits_only = re.sub(r'\D', '', normalized_phone)
                if len(digits_only) >= 10 and not is_lid_number(digits_only):  # Telefone válido tem pelo menos 10 dígitos e não é LID
                    clean_phone = digits_only
                else:
                    logger.warning(f"⚠️ [MENTIONS] Phone inválido ou LID detectado: {normalized_phone[:20]}..., não usando como telefone")
                    clean_phone = ''  # Não usar como telefone
        
        mentions_list.append({
            'jid': mentioned_jid,  # ✅ IMPORTANTE: Salvar JID original para reprocessamento
            'phone': clean_phone,  # ✅ Garantir que phone nunca seja LID
            'name': mention_name  # ✅ Garantir que name nunca seja LID
        })
        
        logger.info(f"   👤 Menção: {mention_name} ({clean_phone}) | JID original: {mentioned_jid}")
    
    return mentions_list


def clean_filename(filename: str, message_id: str = None, mime_type: str = None) -> str:
    """
    Limpa e normaliza nome de arquivo recebido do WhatsApp.
    
    Remove:
    - Extensões .enc (criptografadas)
    - Caracteres especiais inválidos
    - Nomes muito longos ou estranhos
    
    Args:
        filename: Nome original do arquivo
        message_id: ID da mensagem (para fallback)
        mime_type: MIME type do arquivo (para inferir extensão)
    
    Returns:
        Nome limpo e normalizado
    """
    import re
    import os
    
    if not filename:
        filename = f"arquivo_{message_id or 'unknown'}"
    
    # Remover extensão .enc se existir
    if filename.lower().endswith('.enc'):
        filename = filename[:-4]  # Remove .enc
        logger.info(f"🧹 [CLEAN FILENAME] Removida extensão .enc: {filename}")
    
    # Remover caracteres inválidos (manter apenas letras, números, pontos, hífens, underscores)
    filename = re.sub(r'[^a-zA-Z0-9.\-_ ]', '_', filename)
    
    # Se nome é muito longo (>100 chars) ou parece ser hash/ID estranho, gerar nome amigável
    if len(filename) > 100 or re.match(r'^[0-9_]+$', filename.split('.')[0]):
        # Gerar nome amigável baseado no tipo MIME
        if mime_type:
            ext_map = {
                'image/jpeg': 'jpg',
                'image/png': 'png',
                'image/gif': 'gif',
                'image/webp': 'webp',
                'video/mp4': 'mp4',
                'video/quicktime': 'mov',
                'audio/mpeg': 'mp3',
                'audio/ogg': 'ogg',
                'audio/webm': 'webm',
                'application/pdf': 'pdf',
                'application/msword': 'doc',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
                'application/vnd.ms-excel': 'xls',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
                'application/vnd.ms-powerpoint': 'ppt',
                'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'pptx',
            }
            ext = ext_map.get(mime_type, 'bin')
        else:
            # Tentar extrair extensão do nome original
            ext = filename.split('.')[-1] if '.' in filename else 'bin'
            if len(ext) > 5:  # Extensão muito longa, provavelmente inválida
                ext = 'bin'
        
        # Gerar nome amigável
        type_names = {
            'jpg': 'imagem', 'png': 'imagem', 'gif': 'imagem', 'webp': 'imagem',
            'mp4': 'video', 'mov': 'video',
            'mp3': 'audio', 'ogg': 'audio', 'webm': 'audio',
            'pdf': 'documento', 'doc': 'documento', 'docx': 'documento',
            'xls': 'planilha', 'xlsx': 'planilha',
            'ppt': 'apresentacao', 'pptx': 'apresentacao',
        }
        type_name = type_names.get(ext, 'arquivo')
        
        short_id = message_id[:8] if message_id else 'unknown'
        filename = f"{type_name}_{short_id}.{ext}"
        logger.info(f"🧹 [CLEAN FILENAME] Nome gerado automaticamente: {filename}")
    
    # Limitar tamanho total do nome (incluindo extensão)
    if len(filename) > 150:
        name, ext = os.path.splitext(filename)
        filename = name[:140] + ext
    
    return filename


@api_view(['POST'])
@permission_classes([AllowAny])
def evolution_webhook(request):
    """
    Webhook para receber eventos da Evolution API.
    
    Eventos suportados:
    - messages.upsert: Nova mensagem recebida
    - messages.update: Atualização de status (delivered/read)
    """
    try:
        data = request.data
        event_type = data.get('event')
        instance_name = data.get('instance')
        
        # ✅ DEBUG: Log completo do request
        logger.info(f"📥 [WEBHOOK] ====== NOVO EVENTO RECEBIDO ======")
        logger.info(f"📥 [WEBHOOK] Evento: {event_type}")
        logger.info(f"📥 [WEBHOOK] Instance: {instance_name}")
        logger.info(f"📥 [WEBHOOK] Data keys: {list(data.keys()) if isinstance(data, dict) else 'not dict'}")
        logger.info(f"📥 [WEBHOOK] Data completo: {data}")
        
        if not instance_name:
            logger.error(f"❌ [WEBHOOK] Instance não fornecido no webhook!")
            return Response(
                {'error': 'instance é obrigatório'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # ✅ CORREÇÃO: Buscar WhatsAppInstance pelo instance_name (UUID) primeiro
        # O webhook envia UUID (ex: "9afdad84-5411-4754-8f63-2599a6b9142c")
        # EvolutionConnection.name é nome amigável, não UUID
        wa_instance = None
        connection = None
        
        try:
            # Buscar WhatsAppInstance pelo instance_name (UUID do webhook)
            # ✅ FIX: Incluir select_related('default_department') para evitar query extra
            wa_instance = WhatsAppInstance.objects.select_related(
                'tenant', 
                'default_department'  # ✅ CRÍTICO: Carregar departamento padrão
            ).filter(
                instance_name=instance_name,
                is_active=True,
                status='active'
            ).first()
            
            if wa_instance:
                logger.info(f"✅ [WEBHOOK] WhatsAppInstance encontrada: {wa_instance.friendly_name} ({wa_instance.instance_name})")
                logger.info(f"   📌 Tenant: {wa_instance.tenant.name if wa_instance.tenant else 'Global'}")
                logger.info(f"   📋 Default Department: {wa_instance.default_department.name if wa_instance.default_department else 'Nenhum (Inbox)'}")
                
                # Buscar EvolutionConnection (servidor Evolution) para usar api_url/api_key
                # Se WhatsAppInstance tem api_url/api_key próprios, usar deles
                # Se não, usar do EvolutionConnection
                connection = EvolutionConnection.objects.filter(
                    is_active=True
                ).select_related('tenant').first()
                
                if not connection:
                    logger.warning(f"⚠️ [WEBHOOK] EvolutionConnection não encontrada, mas WhatsAppInstance encontrada")
                    # Continuar mesmo assim (WhatsAppInstance pode ter api_url/api_key próprios)
        except Exception as e:
            logger.warning(f"⚠️ [WEBHOOK] Erro ao buscar WhatsAppInstance: {e}")
        
        # ✅ FALLBACK: Se não encontrou WhatsAppInstance, tentar buscar EvolutionConnection pelo name
        # (pode ser que instance_name seja nome amigável em alguns casos)
        if not wa_instance:
            try:
                connection = EvolutionConnection.objects.select_related('tenant').get(
                    name=instance_name,
                    is_active=True
                )
                logger.info(f"✅ [WEBHOOK] EvolutionConnection encontrada pelo name: {connection.name} - Tenant: {connection.tenant.name}")
            except EvolutionConnection.DoesNotExist:
                logger.warning(f"⚠️ [WEBHOOK] Nenhuma conexão encontrada para instance: {instance_name}")
                logger.warning(f"   Tentando buscar qualquer conexão ativa...")
                
                # Fallback final: buscar qualquer conexão ativa
                connection = EvolutionConnection.objects.filter(
                    is_active=True
                ).select_related('tenant').first()
                
                if not connection:
                    logger.error(f"❌ [WEBHOOK] Nenhuma conexão ativa encontrada!")
                    return Response(
                        {'error': 'Conexão não encontrada'},
                        status=status.HTTP_404_NOT_FOUND
                    )
                
                logger.info(f"✅ [WEBHOOK] Usando conexão ativa encontrada: {connection.name} - Tenant: {connection.tenant.name}")
        
        # ✅ Determinar tenant: usar do wa_instance se tiver, senão usar do connection
        if wa_instance and wa_instance.tenant:
            tenant = wa_instance.tenant
        elif connection:
            tenant = connection.tenant
        else:
            logger.error(f"❌ [WEBHOOK] Nenhum tenant encontrado!")
            return Response(
                {'error': 'Tenant não encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Roteamento por tipo de evento
        # ✅ Passar wa_instance também para handler (pode ter api_url/api_key próprios)
        if event_type == 'messages.upsert':
            handle_message_upsert(data, tenant, connection=connection, wa_instance=wa_instance)
        elif event_type == 'messages.update':
            handle_message_update(data, tenant)
        elif event_type == 'messages.delete':
            handle_message_delete(data, tenant, connection=connection, wa_instance=wa_instance)
        else:
            logger.info(f"ℹ️ [WEBHOOK] Evento não tratado: {event_type}")
        
        return Response({'status': 'ok'}, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"❌ [WEBHOOK] Erro ao processar webhook: {e}", exc_info=True)
        return Response(
            {'error': 'Erro interno'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@transaction.atomic
def handle_message_upsert(data, tenant, connection=None, wa_instance=None):
    """
    Processa evento de nova mensagem (messages.upsert).
    
    Cria ou atualiza:
    - Conversation
    - Message
    - MessageAttachment (se houver)
    
    Args:
        data: Dados do webhook
        tenant: Tenant da mensagem
        connection: EvolutionConnection (opcional)
        wa_instance: WhatsAppInstance (opcional, tem instance_name UUID)
    """
    logger.info(f"📥 [WEBHOOK UPSERT] ====== INICIANDO PROCESSAMENTO ======")
    logger.info(f"📥 [WEBHOOK UPSERT] Tenant: {tenant.name} (ID: {tenant.id})")
    logger.info(f"📥 [WEBHOOK UPSERT] Dados recebidos: {data}")
    
    # Nome da instância (ex: "Comercial", "Suporte")
    instance_name = data.get('instance', '')
    logger.info(f"📱 [WEBHOOK UPSERT] Instância: {instance_name}")
    
    try:
        message_data = data.get('data', {})
        key = message_data.get('key', {})
        message_info = message_data.get('message', {})
        
        # Extrai dados
        remote_jid = key.get('remoteJid', '')  # Ex: 5517999999999@s.whatsapp.net ou 120363123456789012@g.us (grupo)
        remote_jid_alt = key.get('remoteJidAlt', '')  # ✅ Telefone real quando remoteJid é @lid
        from_me = key.get('fromMe', False)
        message_id = key.get('id')
        participant = key.get('participant', '')  # Quem enviou no grupo (apenas em grupos)
        
        # ✅ CORREÇÃO CRÍTICA: Detectar grupos quando remoteJidAlt é @lid
        # Quando grupo usa LID, remoteJid vem como telefone individual e remoteJidAlt como LID do grupo
        push_name = message_data.get('pushName', '')
        is_group_by_lid = remote_jid_alt and remote_jid_alt.endswith('@lid') and (
            'grupo' in push_name.lower() or 
            'group' in push_name.lower() or
            len(push_name) > 0  # Se tem pushName e remoteJidAlt é @lid, provavelmente é grupo
        )
        
        # ✅ CORREÇÃO CRÍTICA: Se remoteJid termina com @lid, usar remoteJidAlt (telefone real)
        # @lid é um ID longo que não é telefone, então precisamos do telefone real
        # MAS: Se remoteJidAlt é @lid (grupo com LID), manter remoteJid original e usar remoteJidAlt como group_id
        if remote_jid.endswith('@lid') and remote_jid_alt:
            if remote_jid_alt.endswith('@lid'):
                # Ambos são @lid - usar remoteJid original como group_id
                logger.info(
                    f"🔄 [@LID GRUPO] Ambos são @lid: remoteJid={remote_jid}, remoteJidAlt={remote_jid_alt}"
                )
                # Manter remote_jid como está (será usado como group_id)
            else:
                # remoteJid é @lid mas remoteJidAlt é telefone real
                logger.info(
                    f"🔄 [@LID] RemoteJID é @lid ({remote_jid}), usando remoteJidAlt: {remote_jid_alt}"
                )
                remote_jid = remote_jid_alt  # Usar telefone real ao invés do ID @lid
        
        # 🔍 Detectar tipo de conversa
        # ⚠️ IMPORTANTE: @lid é o novo formato de ID de PARTICIPANTE ou GRUPO!
        # Grupos podem ter remoteJid como telefone individual e remoteJidAlt como @lid
        is_group = remote_jid.endswith('@g.us') or is_group_by_lid  # @g.us = grupos OU grupo com LID
        is_broadcast = remote_jid.endswith('@broadcast')
        is_lid = remote_jid.endswith('@lid')  # ✅ Detectar se ainda é @lid (sem remoteJidAlt)
        
        if is_group:
            conversation_type = 'group'
        elif is_broadcast:
            conversation_type = 'broadcast'
        elif is_lid:
            # ✅ CORREÇÃO: @lid sem remoteJidAlt - tratar como grupo ou usar ID completo
            # Não podemos usar como telefone individual
            logger.warning(
                f"⚠️ [@LID] RemoteJID é @lid sem remoteJidAlt: {remote_jid}. "
                f"Usando ID completo como identificador."
            )
            conversation_type = 'group'  # Tratar como grupo para manter ID completo
        else:
            conversation_type = 'individual'
        
        logger.info(f"🔍 [TIPO] Conversa: {conversation_type} | RemoteJID: {remote_jid}")
        
        # ✅ CORREÇÃO CRÍTICA: Normalizar telefone/ID de forma consistente
        # Isso previne criação de conversas duplicadas para o mesmo contato
        def normalize_contact_phone(remote_jid: str, is_group: bool, remote_jid_alt: str = None) -> str:
            """
            Normaliza contact_phone para formato consistente usado no banco.
            
            Para grupos: mantém formato completo com @g.us (ou usa remoteJidAlt se for LID)
            Para individuais: remove @s.whatsapp.net e adiciona + se necessário
            
            Args:
                remote_jid: JID principal (pode ser telefone individual se grupo usa LID)
                is_group: Se é grupo
                remote_jid_alt: JID alternativo (pode conter LID do grupo)
            
            Returns:
                Telefone normalizado no formato usado no banco de dados
            """
            if is_group:
                # 👥 GRUPOS: Usar ID completo com @g.us
                # ✅ CORREÇÃO: Se remoteJidAlt existe e termina com @lid, grupo usa LID
                # Nesse caso, remoteJid pode ser telefone individual e remoteJidAlt é o LID do grupo
                if remote_jid_alt and remote_jid_alt.endswith('@lid'):
                    # Grupo usa LID: tentar usar remoteJid convertido para @g.us
                    # Se remoteJid já tem @g.us, usar ele
                    if remote_jid.endswith('@g.us'):
                        return remote_jid
                    # Se remoteJid é telefone individual, converter para @g.us
                    phone_part = remote_jid.split('@')[0]
                    return f"{phone_part}@g.us"
                
                # Grupo normal: usar remoteJid com @g.us
                if remote_jid.endswith('@g.us'):
                    return remote_jid
                elif remote_jid.endswith('@s.whatsapp.net'):
                    # Converter individual para grupo (caso raro)
                    return remote_jid.replace('@s.whatsapp.net', '@g.us')
                else:
                    # Adicionar @g.us se não tiver sufixo
                    return f"{remote_jid}@g.us"
            else:
                # 👤 INDIVIDUAIS: Remover @s.whatsapp.net e normalizar com +
                phone = remote_jid.split('@')[0]  # Remove @s.whatsapp.net ou @g.us
                # Remover espaços e caracteres especiais
                phone = phone.strip()
                # Adicionar + se não tiver
                if not phone.startswith('+'):
                    phone = '+' + phone.lstrip('+')
                return phone
        
        phone = normalize_contact_phone(remote_jid, is_group, remote_jid_alt)
        
        # Para grupos, extrair quem enviou
        sender_phone = ''
        sender_name = ''
        if is_group and participant:
            # 🆕 Usar participantAlt se disponível (formato @s.whatsapp.net = número real)
            # Caso contrário, usar participant (pode ser @lid = novo formato de ID)
            participant_to_use = key.get('participantAlt', participant)
            sender_phone = participant_to_use.split('@')[0]
            if not sender_phone.startswith('+'):
                sender_phone = '+' + sender_phone
            sender_name = message_data.get('pushName', '')  # Nome de quem enviou
            logger.info(f"👥 [GRUPO] Enviado por: {sender_name} ({sender_phone})")
        
        # Tipo de mensagem
        message_type = message_data.get('messageType', 'text')
        
        # ✅ DEBUG: Log do tipo de mensagem recebido
        logger.info(f"🔍 [WEBHOOK UPSERT] MessageType recebido: {message_type}")
        logger.info(f"   Message data keys: {list(message_data.keys())}")
        logger.info(f"   Message info keys: {list(message_info.keys()) if message_info else 'None'}")
        
        # ✅ CORREÇÃO CRÍTICA: Tratar reactionMessage como tipo especial
        # Reações NÃO são mensagens novas, são metadados de mensagens existentes
        # ✅ CORREÇÃO: Verificar também se message_info tem reactionMessage diretamente
        has_reaction_message = 'reactionMessage' in message_info if message_info else False
        
        if message_type == 'reactionMessage' or has_reaction_message:
            if has_reaction_message and message_type != 'reactionMessage':
                logger.info(f"⚠️ [WEBHOOK REACTION] reactionMessage encontrado em message_info mas messageType={message_type}, processando mesmo assim")
            logger.info(f"👍 [WEBHOOK REACTION] Reação recebida do WhatsApp")
            
            try:
                # ✅ CORREÇÃO: Estrutura do webhook pode variar, tentar múltiplas formas
                # Formato 1: reactionMessage.text e reactionMessage.key.id
                # Formato 2: reactionMessage.reactionText e key.id (ID da mensagem original)
                reaction_data = message_info.get('reactionMessage', {})
                
                # Tentar extrair emoji de múltiplas formas
                emoji = (
                    reaction_data.get('text') or 
                    reaction_data.get('reactionText') or 
                    reaction_data.get('reaction') or
                    ''
                )
                
                # Tentar extrair message_id da mensagem original
                # O key.id do webhook principal pode ser o ID da mensagem original
                # Ou pode estar em reactionMessage.key.id
                reaction_key = reaction_data.get('key', {})
                reaction_message_id = (
                    reaction_key.get('id') or  # ID da mensagem original em reactionMessage.key
                    key.get('id')  # ID da mensagem original no key principal
                )
                
                logger.info(f"   Message ID original: {reaction_message_id}")
                logger.info(f"   Emoji: {emoji}")
                logger.info(f"   RemoteJID: {remote_jid}")
                logger.info(f"   FromMe: {from_me}")
                logger.info(f"   Key principal: {mask_sensitive_data(key)}")
                logger.info(f"   Reaction data: {mask_sensitive_data(reaction_data)}")
                
                if not reaction_message_id:
                    logger.warning(f"⚠️ [WEBHOOK REACTION] Reação sem message_id, ignorando")
                    logger.warning(f"   Key principal: {key}")
                    logger.warning(f"   Reaction data: {reaction_data}")
                    return Response({'status': 'ok'}, status=status.HTTP_200_OK)
                
                # ✅ CORREÇÃO CRÍTICA: Processar mesmo se emoji vazio (remoção de reação)
                # Emoji vazio significa que o usuário removeu a reação no WhatsApp
                # Não ignorar, processar como remoção
                is_removal = not emoji or emoji.strip() == ''
                
                if is_removal:
                    logger.info(f"🗑️ [WEBHOOK REACTION] Remoção de reação detectada (emoji vazio)")
                else:
                    logger.info(f"👍 [WEBHOOK REACTION] Reação com emoji: {emoji}")
                
                # Buscar mensagem original pelo message_id externo
                # ✅ CORREÇÃO CRÍTICA: Tentar múltiplas formas de buscar mensagem (para suportar mensagens antigas)
                original_message = None
                
                try:
                    # Tentativa 1: Buscar pelo message_id exato
                    original_message = Message.objects.select_related(
                        'conversation', 'conversation__tenant'
                    ).get(
                        message_id=reaction_message_id,
                        conversation__tenant=tenant
                    )
                    logger.info(f"✅ [WEBHOOK REACTION] Mensagem encontrada pelo message_id: {original_message.id}")
                except Message.DoesNotExist:
                    logger.warning(f"⚠️ [WEBHOOK REACTION] Mensagem não encontrada pelo message_id={reaction_message_id}")
                    
                    # Tentativa 2: Buscar pela conversa + tentar encontrar mensagem mais recente sem message_id
                    # (para mensagens antigas que podem não ter message_id salvo)
                    try:
                        # Buscar conversa primeiro
                        conversation = Conversation.objects.filter(
                            tenant=tenant,
                            contact_phone=normalize_contact_phone(remote_jid, is_group, remote_jid_alt)
                        ).first()
                        
                        if conversation:
                            logger.info(f"🔍 [WEBHOOK REACTION] Tentando buscar mensagem na conversa {conversation.id} sem message_id...")
                            
                            # Buscar mensagens da conversa ordenadas por data (mais recentes primeiro)
                            # Limitar a últimas 50 mensagens para não sobrecarregar
                            messages = Message.objects.filter(
                                conversation=conversation,
                                direction='incoming' if not from_me else 'outgoing'
                            ).order_by('-created_at')[:50]
                            
                            # Tentar encontrar mensagem pelo timestamp aproximado (se disponível)
                            message_timestamp = message_data.get('messageTimestamp')
                            if message_timestamp:
                                # Converter timestamp Unix para datetime
                                from datetime import datetime
                                try:
                                    msg_date = datetime.fromtimestamp(message_timestamp)
                                    logger.info(f"🔍 [WEBHOOK REACTION] Buscando mensagem próxima ao timestamp: {msg_date}")
                                    
                                    # Buscar mensagem criada próximo ao timestamp (dentro de 1 hora)
                                    from django.utils import timezone
                                    from datetime import timedelta
                                    
                                    time_window_start = timezone.make_aware(msg_date - timedelta(hours=1))
                                    time_window_end = timezone.make_aware(msg_date + timedelta(hours=1))
                                    
                                    original_message = Message.objects.filter(
                                        conversation=conversation,
                                        created_at__gte=time_window_start,
                                        created_at__lte=time_window_end,
                                        direction='incoming' if not from_me else 'outgoing'
                                    ).order_by('-created_at').first()
                                    
                                    if original_message:
                                        logger.info(f"✅ [WEBHOOK REACTION] Mensagem encontrada pelo timestamp aproximado: {original_message.id}")
                                except Exception as e:
                                    logger.warning(f"⚠️ [WEBHOOK REACTION] Erro ao processar timestamp: {e}")
                            
                            # Se ainda não encontrou, tentar última mensagem da conversa (fallback)
                            if not original_message:
                                logger.warning(f"⚠️ [WEBHOOK REACTION] Tentando última mensagem da conversa como fallback...")
                                original_message = messages.first()
                                if original_message:
                                    logger.warning(f"⚠️ [WEBHOOK REACTION] Usando última mensagem como fallback: {original_message.id} (pode estar incorreto)")
                        else:
                            logger.warning(f"⚠️ [WEBHOOK REACTION] Conversa não encontrada para {remote_jid}")
                            
                    except Exception as e:
                        logger.error(f"❌ [WEBHOOK REACTION] Erro ao buscar mensagem por fallback: {e}", exc_info=True)
                
                if not original_message:
                    logger.error(f"❌ [WEBHOOK REACTION] Mensagem original não encontrada após todas as tentativas")
                    logger.error(f"   reaction_message_id: {reaction_message_id}")
                    logger.error(f"   message_id (webhook): {message_id}")
                    logger.error(f"   remote_jid: {remote_jid}")
                    logger.error(f"   tenant: {tenant.name}")
                    return Response({'status': 'ok'}, status=status.HTTP_200_OK)
                
                logger.info(f"✅ [WEBHOOK REACTION] Mensagem original encontrada: {original_message.id}")
                
                # Buscar ou criar reação
                # Para reações recebidas, não temos usuário interno, então precisamos identificar pelo número
                # Se from_me=False, é reação recebida de contato externo
                # Se from_me=True, é reação que enviamos (já deve estar no banco)
                
                # ✅ CORREÇÃO CRÍTICA: Criar ou atualizar reação no banco de dados
                from apps.chat.models import MessageReaction
                
                # ✅ CORREÇÃO CRÍTICA: Processar reações recebidas (from_me=False) e também reações que enviamos (from_me=True)
                # Isso garante sincronização bidirecional completa
                if from_me:
                    # ✅ CORREÇÃO CRÍTICA: Reação que enviamos - NÃO criar segunda reação
                    # Quando enviamos uma reação da aplicação, ela já foi salva no banco com user=request.user
                    # O webhook aqui é apenas confirmação do WhatsApp, não devemos criar duplicata
                    logger.info(f"ℹ️ [WEBHOOK REACTION] Reação enviada por nós (confirmação do WhatsApp)")
                    logger.info(f"   ✅ Reação já existe no banco (criada quando usuário reagiu na aplicação)")
                    logger.info(f"   ✅ Apenas fazendo broadcast para sincronizar todos os clientes")
                    
                    # ✅ CORREÇÃO CRÍTICA: Agora reações são criadas com external_sender = número da instância
                    # Verificar se reação já existe pelo número da instância (não mais por user)
                    if wa_instance and wa_instance.phone_number:
                        instance_phone = wa_instance.phone_number
                        logger.info(f"🔍 [WEBHOOK REACTION] Verificando reação existente - Número da instância: {instance_phone}")
                        
                        # Buscar reação pelo número da instância (formato atual)
                        existing_reaction = MessageReaction.objects.filter(
                            message=original_message,
                            external_sender=instance_phone,
                            user__isnull=True,
                            emoji=emoji if not is_removal else None
                        ).first()
                        
                        # Também tentar outros formatos possíveis
                        if not existing_reaction:
                            if instance_phone.startswith('+'):
                                existing_reaction = MessageReaction.objects.filter(
                                    message=original_message,
                                    external_sender=instance_phone.lstrip('+'),
                                    user__isnull=True,
                                    emoji=emoji if not is_removal else None
                                ).first()
                            else:
                                existing_reaction = MessageReaction.objects.filter(
                                    message=original_message,
                                    external_sender=f"+{instance_phone}",
                                    user__isnull=True,
                                    emoji=emoji if not is_removal else None
                                ).first()
                        
                        if existing_reaction:
                            logger.info(f"✅ [WEBHOOK REACTION] Reação encontrada pelo número da instância: {existing_reaction.id}")
                        else:
                            logger.warning(f"⚠️ [WEBHOOK REACTION] Reação não encontrada pelo número da instância (pode ser race condition ou remoção)")
                            # Não criar reação aqui - ela deve ter sido criada quando usuário reagiu na aplicação
                            # Se não existe, pode ser porque:
                            # 1. Race condition (ainda não foi salva)
                            # 2. Foi removida pelo usuário
                            # 3. Erro no envio da reação
                    else:
                        logger.warning(f"⚠️ [WEBHOOK REACTION] Instância WhatsApp não encontrada - não é possível verificar reação existente")
                else:
                    # ✅ CORREÇÃO CRÍTICA: Reação recebida de contato externo - SALVAR NO BANCO
                    # Extrair número do remetente (pode estar em participant ou remoteJid)
                    sender_phone = ''
                    if is_group and participant:
                        # Grupo: usar participant (quem reagiu no grupo)
                        sender_phone = participant.split('@')[0]
                        if not sender_phone.startswith('+'):
                            sender_phone = '+' + sender_phone.lstrip('+')
                    else:
                        # Individual: usar remoteJid (quem reagiu)
                        sender_phone = remote_jid.split('@')[0]
                        if not sender_phone.startswith('+'):
                            sender_phone = '+' + sender_phone.lstrip('+')
                    
                    # ✅ CORREÇÃO CRÍTICA: Verificar se o sender_phone é o número da instância conectada
                    # Se for, não criar reação com external_sender (já existe reação do usuário interno)
                    # Isso previne duplicação quando o webhook recebe confirmação com from_me=False mas sender_phone = número da instância
                    if wa_instance and wa_instance.phone_number:
                        instance_phone = wa_instance.phone_number
                        logger.info(f"🔍 [WEBHOOK REACTION] Comparando sender_phone ({sender_phone}) com instance_phone ({instance_phone})")
                        
                        # Comparar números (normalizar para comparação - remover tudo exceto dígitos)
                        import re
                        sender_digits = re.sub(r'\D', '', sender_phone)
                        instance_digits = re.sub(r'\D', '', instance_phone)
                        
                        logger.info(f"🔍 [WEBHOOK REACTION] Números normalizados - sender: {sender_digits}, instance: {instance_digits}")
                        
                        if sender_digits == instance_digits:
                            logger.warning(f"⚠️ [WEBHOOK REACTION] Reação recebida do número da instância conectada ({sender_phone} = {instance_phone})")
                            logger.warning(f"   ⚠️ IGNORANDO criação de reação com external_sender (já existe reação do usuário interno)")
                            
                            # Remover qualquer reação duplicada que possa ter sido criada antes desta verificação
                            # Tentar múltiplos formatos para garantir remoção completa
                            deleted_count = 0
                            deleted_count += MessageReaction.objects.filter(
                                message=original_message,
                                external_sender=sender_phone,
                                user__isnull=True
                            ).delete()[0]
                            
                            # Também remover com outros formatos possíveis
                            if sender_phone.startswith('+'):
                                deleted_count += MessageReaction.objects.filter(
                                    message=original_message,
                                    external_sender=sender_phone.lstrip('+'),
                                    user__isnull=True
                                ).delete()[0]
                            else:
                                deleted_count += MessageReaction.objects.filter(
                                    message=original_message,
                                    external_sender=f"+{sender_phone}",
                                    user__isnull=True
                                ).delete()[0]
                            
                            if deleted_count > 0:
                                logger.info(f"🗑️ [WEBHOOK REACTION] Removidas {deleted_count} reação(ões) duplicada(s) com external_sender")
                            
                            # Não criar reação com external_sender - já existe reação do usuário interno
                            # Apenas fazer broadcast para sincronizar
                            original_message = Message.objects.prefetch_related('reactions__user').get(id=original_message.id)
                            from apps.chat.utils.websocket import broadcast_message_reaction_update
                            broadcast_message_reaction_update(original_message)
                            logger.info(f"✅ [WEBHOOK REACTION] Broadcast enviado (sem criar reação duplicada)")
                            return Response({'status': 'ok'}, status=status.HTTP_200_OK)
                    
                    logger.info(f"📥 [WEBHOOK REACTION] Reação recebida de contato externo: {sender_phone}")
                    logger.info(f"   Emoji: '{emoji}' (vazio={is_removal})")
                    
                    # ✅ CORREÇÃO CRÍTICA FINAL: Verificar novamente ANTES de criar reação com external_sender
                    # Isso garante que mesmo se a verificação anterior falhou, não criamos duplicata
                    if wa_instance and wa_instance.phone_number:
                        instance_phone = wa_instance.phone_number
                        import re
                        sender_digits = re.sub(r'\D', '', sender_phone)
                        instance_digits = re.sub(r'\D', '', instance_phone)
                        
                        if sender_digits == instance_digits:
                            logger.error(f"❌ [WEBHOOK REACTION] ERRO: Tentativa de criar reação com external_sender do número da instância ({sender_phone})")
                            logger.error(f"   ⚠️ IGNORANDO - já existe reação do usuário interno")
                            # Remover qualquer reação duplicada que possa ter sido criada
                            MessageReaction.objects.filter(
                                message=original_message,
                                external_sender=sender_phone,
                                user__isnull=True
                            ).delete()
                            # Apenas fazer broadcast
                            original_message = Message.objects.prefetch_related('reactions__user').get(id=original_message.id)
                            from apps.chat.utils.websocket import broadcast_message_reaction_update
                            broadcast_message_reaction_update(original_message)
                            return Response({'status': 'ok'}, status=status.HTTP_200_OK)
                    
                    # ✅ CORREÇÃO CRÍTICA: Processar remoção ou adição de reação
                    if is_removal:
                        # Remover reação existente deste contato
                        deleted_count = MessageReaction.objects.filter(
                            message=original_message,
                            external_sender=sender_phone
                        ).delete()[0]
                        logger.info(f"✅ [WEBHOOK REACTION] Reação removida do contato externo (deletadas: {deleted_count})")
                    else:
                        # Criar ou atualizar reação do contato externo (apenas se NÃO for número da instância)
                        reaction, created = MessageReaction.objects.update_or_create(
                            message=original_message,
                            external_sender=sender_phone,
                            defaults={'emoji': emoji}
                        )
                        action = 'criada' if created else 'atualizada'
                        logger.info(f"✅ [WEBHOOK REACTION] Reação {action} no banco: {sender_phone} → {emoji}")
                
                # Recarregar mensagem com reações atualizadas (incluindo externas)
                original_message = Message.objects.prefetch_related('reactions__user').get(id=original_message.id)
                
                # Broadcast atualização de reação via WebSocket
                from apps.chat.utils.websocket import broadcast_message_reaction_update
                broadcast_message_reaction_update(original_message)
                
                logger.info(f"✅ [WEBHOOK REACTION] Broadcast de reação enviado")
                
                # ✅ IMPORTANTE: Retornar sem criar mensagem nova
                # Reações não são mensagens, são metadados
                return Response({'status': 'ok'}, status=status.HTTP_200_OK)
                
            except Exception as e:
                logger.error(f"❌ [WEBHOOK REACTION] Erro ao processar reação: {e}", exc_info=True)
                # Retornar OK para não bloquear webhook
                return Response({'status': 'ok'}, status=status.HTTP_200_OK)
        
        # Conteúdo (para outros tipos de mensagem)
        contact_message_data = None
        mentions_list = []  # ✅ NOVO: Lista de menções na mensagem recebida
        mentioned_jids_raw = []  # ✅ NOVO: JIDs mencionados originais (para reprocessar depois)
        quoted_message_id_evolution = None  # ✅ NOVO: ID da Evolution da mensagem sendo respondida
        
        # ✅ NOVO: Função helper para extrair quotedMessage de qualquer tipo de mensagem
        def extract_quoted_message(context_info):
            """Extrai quotedMessage do contextInfo."""
            # ✅ LOG CRÍTICO: Verificar se contextInfo existe e tem quotedMessage
            if not context_info:
                logger.debug(f"🔍 [WEBHOOK REPLY] contextInfo não existe")
                return None
            
            logger.critical(f"🔍 [WEBHOOK REPLY] Verificando contextInfo para quotedMessage:")
            logger.critical(f"   contextInfo keys: {list(context_info.keys()) if isinstance(context_info, dict) else 'not dict'}")
            
            quoted_message = context_info.get('quotedMessage', {})
            if quoted_message:
                logger.critical(f"✅ [WEBHOOK REPLY] quotedMessage encontrado!")
                logger.critical(f"   quotedMessage keys: {list(quoted_message.keys()) if isinstance(quoted_message, dict) else 'not dict'}")
                
                # ✅ PRIORIDADE 1: Buscar key.id diretamente no quotedMessage
                quoted_key = quoted_message.get('key', {})
                if quoted_key:
                    quoted_id = quoted_key.get('id')
                    logger.critical(f"✅ [WEBHOOK REPLY] quotedMessage.key.id encontrado: {_mask_digits(quoted_id) if quoted_id else 'N/A'}")
                    logger.critical(f"   quoted_key completo: {mask_sensitive_data(quoted_key)}")
                    if quoted_id:
                        return quoted_id
                
                # ✅ PRIORIDADE 2: Verificar se key está no messageContextInfo
                message_context_info = quoted_message.get('messageContextInfo', {})
                if message_context_info:
                    context_key = message_context_info.get('key', {})
                    if context_key:
                        quoted_id = context_key.get('id')
                        logger.critical(f"✅ [WEBHOOK REPLY] quotedMessage.messageContextInfo.key.id encontrado: {_mask_digits(quoted_id) if quoted_id else 'N/A'}")
                        if quoted_id:
                            return quoted_id
                
                # ✅ PRIORIDADE 3: Verificar se há stanzaId que pode ser usado
                stanza_id = context_info.get('stanzaId')
                if stanza_id:
                    logger.warning(f"⚠️ [WEBHOOK REPLY] quotedMessage não tem key.id, mas encontrou stanzaId: {_mask_digits(stanza_id)}")
                    logger.warning(f"   Tentando usar stanzaId como message_id...")
                    # stanzaId pode ser o message_id em alguns casos
                    return stanza_id
                
                logger.warning(f"⚠️ [WEBHOOK REPLY] quotedMessage existe mas não tem 'key' em nenhum lugar")
                logger.warning(f"   quotedMessage keys: {list(quoted_message.keys()) if isinstance(quoted_message, dict) else 'not dict'}")
                # ✅ FALLBACK: Tentar buscar pelo conteúdo se não tiver key.id
                # Algumas versões da Evolution API não enviam key.id, apenas o conteúdo
                quoted_conversation = quoted_message.get('conversation', '')
                if quoted_conversation:
                    logger.warning(f"⚠️ [WEBHOOK REPLY] Tentando fallback: buscar mensagem pelo conteúdo")
                    logger.warning(f"   Conteúdo do quotedMessage: {quoted_conversation[:100]}...")
                    # Retornar None por enquanto - vamos buscar depois pelo conteúdo
                    # Mas marcar que temos quotedMessage para processar depois
                    return None  # Vamos processar depois usando o conteúdo
            else:
                logger.debug(f"🔍 [WEBHOOK REPLY] quotedMessage não encontrado no contextInfo")
            return None
        
        if message_type == 'conversation':
            content = message_info.get('conversation', '')
            
            # ✅ NOVO: Verificar contextInfo mesmo em mensagens simples (pode ter reply)
            # ✅ FIX: Verificar contextInfo em message_info E em message_data (pode estar em qualquer lugar)
            conversation_context = message_info.get('contextInfo', {}) or message_data.get('contextInfo', {})
            logger.critical(f"🔍 [WEBHOOK REPLY] Verificando contextInfo para mensagem conversation:")
            logger.critical(f"   contextInfo em message_info: {bool(message_info.get('contextInfo'))}")
            logger.critical(f"   contextInfo em message_data: {bool(message_data.get('contextInfo'))}")
            logger.critical(f"   contextInfo final: {bool(conversation_context)}")
            if conversation_context:
                logger.critical(f"   contextInfo keys: {list(conversation_context.keys()) if isinstance(conversation_context, dict) else 'not dict'}")
            quoted_id = extract_quoted_message(conversation_context)
            if quoted_id:
                quoted_message_id_evolution = quoted_id
                logger.info(f"💬 [WEBHOOK] Mensagem conversation é resposta de: {quoted_id}")
            else:
                logger.critical(f"⚠️ [WEBHOOK REPLY] quoted_id é None após extract_quoted_message")
        elif message_type == 'extendedTextMessage':
            extended_text = message_info.get('extendedTextMessage', {})
            content = extended_text.get('text', '')
            
            # ✅ NOVO: Extrair menções do contextInfo (quando mensagem recebida tem menções)
            context_info = extended_text.get('contextInfo', {})
            mentioned_jids = context_info.get('mentionedJid', [])
            
            # ✅ NOVO: Extrair quotedMessage (mensagem sendo respondida)
            quoted_id = extract_quoted_message(context_info)
            if quoted_id:
                quoted_message_id_evolution = quoted_id
                logger.info(f"💬 [WEBHOOK] Mensagem extendedText é resposta de: {quoted_id}")
            
            if mentioned_jids:
                logger.info(f"🗣️ [WEBHOOK] Menções detectadas na mensagem recebida: {len(mentioned_jids)}")
                # ✅ MELHORIA: Armazenar JIDs para reprocessar depois com conversa disponível
                mentioned_jids_raw.extend(mentioned_jids)
                # Processar inicialmente (será reprocessado depois com conversa)
                text_mentions = process_mentions_optimized(mentioned_jids, tenant, conversation=None)
                mentions_list.extend(text_mentions)
                if text_mentions:
                    logger.info(f"✅ [WEBHOOK] {len(text_mentions)} menções de texto processadas")
        elif message_type == 'imageMessage':
            image_msg = message_info.get('imageMessage', {})
            content = image_msg.get('caption', '')
            
            # ✅ NOVO: Menções também podem vir em imagens com legenda
            context_info = image_msg.get('contextInfo', {})
            mentioned_jids = context_info.get('mentionedJid', [])
            
            # ✅ NOVO: Extrair quotedMessage (mensagem sendo respondida)
            quoted_id = extract_quoted_message(context_info)
            if quoted_id:
                quoted_message_id_evolution = quoted_id
                logger.info(f"💬 [WEBHOOK] Mensagem de imagem é resposta de: {quoted_id}")
            
            if mentioned_jids:
                logger.info(f"🗣️ [WEBHOOK] Menções detectadas na imagem recebida: {len(mentioned_jids)}")
                # ✅ MELHORIA: Armazenar JIDs para reprocessar depois com conversa disponível
                mentioned_jids_raw.extend(mentioned_jids)
                # Processar inicialmente (será reprocessado depois com conversa)
                image_mentions = process_mentions_optimized(mentioned_jids, tenant, conversation=None)
                mentions_list.extend(image_mentions)
        elif message_type == 'videoMessage':
            video_msg = message_info.get('videoMessage', {})
            content = video_msg.get('caption', '')
            
            # ✅ NOVO: Menções também podem vir em vídeos com legenda
            context_info = video_msg.get('contextInfo', {})
            mentioned_jids = context_info.get('mentionedJid', [])
            
            # ✅ NOVO: Extrair quotedMessage (mensagem sendo respondida)
            quoted_id = extract_quoted_message(context_info)
            if quoted_id:
                quoted_message_id_evolution = quoted_id
                logger.info(f"💬 [WEBHOOK] Mensagem de vídeo é resposta de: {quoted_id}")
            
            if mentioned_jids:
                logger.info(f"🗣️ [WEBHOOK] Menções detectadas no vídeo recebido: {len(mentioned_jids)}")
                # ✅ MELHORIA: Armazenar JIDs para reprocessar depois com conversa disponível
                mentioned_jids_raw.extend(mentioned_jids)
                # Processar inicialmente (será reprocessado depois com conversa)
                video_mentions = process_mentions_optimized(mentioned_jids, tenant, conversation=None)
                mentions_list.extend(video_mentions)
        elif message_type == 'documentMessage':
            document_msg = message_info.get('documentMessage', {})
            content = document_msg.get('caption', '')
            
            # ✅ NOVO: Extrair quotedMessage (mensagem sendo respondida)
            context_info = document_msg.get('contextInfo', {})
            quoted_id = extract_quoted_message(context_info)
            if quoted_id:
                quoted_message_id_evolution = quoted_id
                logger.info(f"💬 [WEBHOOK] Mensagem de documento é resposta de: {quoted_id}")
        elif message_type == 'audioMessage':
            audio_msg = message_info.get('audioMessage', {})
            content = ''  # Player de áudio já é auto-explicativo, não precisa de texto
            
            # ✅ NOVO: Extrair quotedMessage (mensagem sendo respondida)
            context_info = audio_msg.get('contextInfo', {})
            quoted_id = extract_quoted_message(context_info)
            if quoted_id:
                quoted_message_id_evolution = quoted_id
                logger.info(f"💬 [WEBHOOK] Mensagem de áudio é resposta de: {quoted_id}")
        elif message_type == 'contactMessage':
            # ✅ NOVO: Extrair dados do contato compartilhado
            contact_data = message_info.get('contactMessage', {})
            
            # ✅ FIX: Suportar dois formatos:
            # Formato 1: contactMessage.contactsArray[] (formato antigo)
            # Formato 2: contactMessage.displayName e contactMessage.vcard (formato novo)
            contacts_array = contact_data.get('contactsArray', [])
            
            # Se não tem contactsArray, tentar formato direto
            if not contacts_array or len(contacts_array) == 0:
                # Formato novo: dados diretos em contactMessage
                display_name = contact_data.get('displayName', '')
                vcard = contact_data.get('vcard', '')
                contact_id = contact_data.get('contactId', '')
                
                logger.info(f"📇 [CONTACT MESSAGE] Formato novo detectado - displayName: {display_name}, vcard: {vcard[:100] if vcard else 'N/A'}")
                
                if display_name or vcard:
                    # Processar como se fosse um contato único
                    contacts_array = [{
                        'displayName': display_name,
                        'vcard': vcard,
                        'contactId': contact_id
                    }]
                    logger.info(f"📇 [CONTACT MESSAGE] Array criado com {len(contacts_array)} contato(s)")
            
            if contacts_array and len(contacts_array) > 0:
                # Pegar primeiro contato (geralmente só vem um)
                first_contact = contacts_array[0]
                display_name = first_contact.get('displayName', '')
                vcard = first_contact.get('vcard', '')
                contact_id = first_contact.get('contactId', '')
                
                # Extrair telefone do vCard ou contactId
                phone_from_contact = None
                if contact_id and '@' in contact_id:
                    # Formato: 5511999999999@s.whatsapp.net
                    phone_from_contact = contact_id.split('@')[0]
                    if not phone_from_contact.startswith('+'):
                        phone_from_contact = f'+{phone_from_contact}'
                
                # Tentar extrair telefone do vCard se não tiver no contactId
                if not phone_from_contact and vcard:
                    import re
                    # ✅ FIX: Melhorar regex para pegar telefone do vCard
                    # Formato: item1.TEL;waid=5517996555683:+55 17 99655-5683
                    # Ou: TEL:+5517996555683
                    # Ou: item1.TEL:+55 17 99655-5683
                    # Tentar múltiplos padrões
                    tel_patterns = [
                        r'item\d+\.TEL[;:]?waid=\d+[:;]([+\d\s\-\(\)]+)',  # item1.TEL;waid=...:+55 17...
                        r'item\d+\.TEL[;:]?([+\d\s\-\(\)]+)',  # item1.TEL:+55 17...
                        r'TEL[;:]?waid=\d+[:;]([+\d\s\-\(\)]+)',  # TEL;waid=...:+55 17...
                        r'TEL[;:]?([+\d\s\-\(\)]+)',  # TEL:+55 17...
                    ]
                    
                    phone_from_contact = None
                    for pattern in tel_patterns:
                        tel_match = re.search(pattern, vcard, re.IGNORECASE)
                        if tel_match:
                            phone_from_contact = tel_match.group(1).strip()
                            break
                    
                    if phone_from_contact:
                        # Normalizar telefone - remover espaços, parênteses, hífens
                        phone_from_contact = ''.join(c for c in phone_from_contact if c.isdigit() or c == '+')
                        if phone_from_contact and not phone_from_contact.startswith('+'):
                            if phone_from_contact.startswith('55'):
                                phone_from_contact = '+' + phone_from_contact
                            else:
                                phone_from_contact = '+55' + phone_from_contact
                
                # Salvar dados do contato no metadata
                contact_message_data = {
                    'name': display_name or 'Contato',
                    'phone': phone_from_contact or '',
                    'display_name': display_name,
                    'vcard': vcard[:500] if vcard else None  # Limitar tamanho do vCard
                }
                
                # Conteúdo amigável para exibição
                if display_name and phone_from_contact:
                    content = f"📇 Compartilhou contato: {display_name}"
                elif display_name:
                    content = f"📇 Compartilhou contato: {display_name}"
                elif phone_from_contact:
                    content = f"📇 Compartilhou contato: {phone_from_contact}"
                else:
                    content = "📇 Contato compartilhado"
                
                logger.info(f"📇 [CONTACT MESSAGE] Nome: {display_name}, Telefone: {phone_from_contact}, vCard: {vcard[:100] if vcard else 'N/A'}")
            else:
                content = "📇 Contato compartilhado"
        else:
            content = f'[{message_type}]'
        
        # Nome do contato
        push_name = message_data.get('pushName', '')
        
        # Foto de perfil (se disponível)
        profile_pic_url = message_data.get('profilePicUrl', '')
        
        # Log da mensagem recebida
        direction_str = "📤 ENVIADA" if from_me else "📥 RECEBIDA"
        logger.info(f"{direction_str} [WEBHOOK] {phone}: {content[:50]}...")
        logger.info(f"   Tenant: {tenant.name} | Message ID: {message_id}")
        logger.info(f"   👤 Nome: {push_name} | 📸 Foto de Perfil: {profile_pic_url[:100] if profile_pic_url else 'NÃO ENVIADA'}")
        logger.info(f"🔍 [DEBUG] fromMe={from_me}, conversation_type={conversation_type}, remoteJid={remote_jid}")
        
        # Busca ou cria conversa
        # ✅ NOVO: Se instância tem default_department, nova conversa vai direto para ele
        # Senão, vai para INBOX (pending) sem departamento
        
        # Determinar departamento padrão
        default_department = None
        if wa_instance and wa_instance.default_department:
            default_department = wa_instance.default_department
            logger.info(f"📋 [ROUTING] Instância tem departamento padrão: {default_department.name}")
        else:
            logger.info(f"📋 [ROUTING] Instância sem departamento padrão - vai para Inbox")
        
        # ✅ NOVO: Padronizar nome do contato - usar dados da lista de contatos se existir
        # Se não existir, mostrar apenas o número formatado (não usar pushName)
        def _format_phone_for_display(phone: str) -> str:
            """Formata telefone para exibição (como WhatsApp faz)."""
            import re
            clean = re.sub(r'\D', '', phone)
            if clean.startswith('55') and len(clean) >= 12:
                clean = clean[2:]
            if len(clean) == 11:
                return f"({clean[0:2]}) {clean[2:7]}-{clean[7:11]}"
            elif len(clean) == 10:
                return f"({clean[0:2]}) {clean[2:6]}-{clean[6:10]}"
            elif len(clean) == 9:
                return f"{clean[0:5]}-{clean[5:9]}"
            elif len(clean) == 8:
                return f"{clean[0:4]}-{clean[4:8]}"
            return clean[:15] if clean else phone
        
        # Normalizar telefone para buscar contato
        from apps.contacts.signals import normalize_phone_for_search
        normalized_phone = normalize_phone_for_search(phone)
        
        # ✅ NOVO: Buscar contato na lista de contatos do tenant
        contact_name_to_save = None
        if not is_group:
            from apps.contacts.models import Contact
            from django.db.models import Q
            
            # Buscar contato por telefone normalizado ou original
            saved_contact = Contact.objects.filter(
                Q(tenant=tenant) &
                (Q(phone=normalized_phone) | Q(phone=phone))
            ).first()
            
            if saved_contact:
                # ✅ Contato existe na lista - usar nome salvo
                contact_name_to_save = saved_contact.name
                logger.info(f"✅ [CONTATO] Usando nome da lista de contatos: {contact_name_to_save} (telefone: {normalized_phone})")
            else:
                # ✅ Contato não existe - usar apenas número formatado (não pushName)
                clean_phone_for_name = phone.replace('+', '').replace('@s.whatsapp.net', '')
                contact_name_to_save = _format_phone_for_display(clean_phone_for_name)
                logger.info(f"📞 [CONTATO] Contato não encontrado na lista - usando número formatado: {contact_name_to_save}")
        
        # Para grupos, manter lógica atual
        if is_group:
            contact_name_to_save = 'Grupo WhatsApp'  # Placeholder até buscar da API
        
        # Para grupos, usar o ID do grupo como identificador único
        defaults = {
            'department': default_department,  # Departamento padrão da instância (ou None = Inbox)
            'contact_name': contact_name_to_save,
            'profile_pic_url': profile_pic_url if profile_pic_url else None,
            'instance_name': instance_name,  # Salvar instância de origem
            'status': 'pending' if not default_department else 'open',  # Pendente se Inbox, aberta se departamento
            'conversation_type': conversation_type,
        }
        
        # Para grupos, adicionar metadados
        # ⚠️ pushName é de quem ENVIOU, não do grupo! Nome real virá da API
        if is_group:
            # ✅ CORREÇÃO CRÍTICA: Quando grupo usa LID, tentar usar remoteJid como JID do grupo
            # Quando grupo usa LID: remoteJid = telefone individual, remoteJidAlt = LID do grupo
            # A Evolution API não aceita LID como groupJid, então tentamos usar remoteJid convertido para @g.us
            if is_group_by_lid:
                # Grupo com LID: tentar usar remoteJid (telefone) convertido para @g.us
                # Isso pode não funcionar, mas é a melhor tentativa
                phone_part = remote_jid.split('@')[0] if '@' in remote_jid else remote_jid
                group_id = f"{phone_part}@g.us"
                logger.warning(f"⚠️ [GRUPO LID] Tentando usar remoteJid como group_id: {group_id}")
                logger.warning(f"   remoteJid original: {remote_jid}")
                logger.warning(f"   remoteJidAlt (LID): {remote_jid_alt}")
                logger.warning(f"   ⚠️ A Evolution API pode não aceitar este formato!")
                
                # ✅ IMPORTANTE: Salvar também o LID no metadata para referência futura
                defaults['group_metadata'] = {
                    'group_id': group_id,  # Tentar usar telefone convertido para @g.us
                    'group_id_lid': remote_jid_alt,  # ✅ Salvar LID também para referência
                    'group_name': push_name or 'Grupo WhatsApp',
                    'is_group': True,
                    'uses_lid': True,  # ✅ Flag para indicar que grupo usa LID
                }
            elif remote_jid.endswith('@g.us'):
                group_id = remote_jid  # Usar remoteJid com @g.us
                defaults['group_metadata'] = {
                    'group_id': group_id,
                    'group_name': push_name or 'Grupo WhatsApp',
                    'is_group': True,
                }
            elif remote_jid.endswith('@lid'):
                group_id = remote_jid  # Usar remoteJid @lid como group_id
                defaults['group_metadata'] = {
                    'group_id': group_id,
                    'group_name': push_name or 'Grupo WhatsApp',
                    'is_group': True,
                }
            else:
                # Fallback: tentar construir @g.us a partir do telefone
                group_id = f"{remote_jid.split('@')[0]}@g.us"
                logger.warning(f"⚠️ [GRUPO] Construindo group_id a partir de telefone: {group_id}")
                defaults['group_metadata'] = {
                    'group_id': group_id,
                    'group_name': push_name or 'Grupo WhatsApp',
                    'is_group': True,
                }
            
            defaults['contact_name'] = push_name or 'Grupo WhatsApp'  # Usar pushName se disponível
            logger.info(f"✅ [GRUPO] group_id salvo: {group_id}")
        
        # ✅ CORREÇÃO CRÍTICA: Normalizar telefone para busca consistente
        # Isso previne criação de conversas duplicadas quando mensagens vêm do celular
        # em formatos diferentes (com/sem +, com/sem código do país)
        # Nota: normalized_phone já foi calculado acima ao buscar contato
        
        # Buscar conversa existente usando telefone normalizado
        # Usar Q() para buscar por telefone normalizado OU telefone original (para compatibilidade)
        # ✅ CORREÇÃO: Usar Q() para tudo para evitar erro de sintaxe (keyword + positional)
        from django.db.models import Q
        existing_conversation = Conversation.objects.filter(
            Q(tenant=tenant) &
            (Q(contact_phone=normalized_phone) | Q(contact_phone=phone))
        ).first()
        
        if existing_conversation:
            # Conversa existe - usar telefone normalizado para garantir consistência
            if existing_conversation.contact_phone != normalized_phone:
                logger.info(
                    f"🔄 [NORMALIZAÇÃO] Atualizando telefone da conversa {existing_conversation.id}: "
                    f"{existing_conversation.contact_phone} → {normalized_phone}"
                )
                existing_conversation.contact_phone = normalized_phone
                existing_conversation.save(update_fields=['contact_phone'])
            
            conversation = existing_conversation
            created = False
        else:
            # Criar nova conversa com telefone normalizado
            conversation = Conversation.objects.create(
                tenant=tenant,
                contact_phone=normalized_phone,
                **defaults
            )
            created = True
        
        logger.info(f"📋 [CONVERSA] {'NOVA' if created else 'EXISTENTE'}: {normalized_phone} (original: {phone}) | Tipo: {conversation_type}")
        logger.info(f"   📋 Departamento atual ANTES: {conversation.department.name if conversation.department else 'Nenhum (Inbox)'}")
        logger.info(f"   📊 Status atual ANTES: {conversation.status}")
        logger.info(f"   🆔 ID: {conversation.id}")
        logger.info(f"   🔍 Default Department disponível: {default_department.name if default_department else 'Nenhum'}")
        
        # ✅ FIX CRÍTICO: Se conversa já existia mas não tem departamento E instância tem default_department,
        # atualizar conversa para usar o departamento padrão
        # IMPORTANTE: get_or_create só usa defaults na criação, não atualiza existentes!
        needs_update = False
        update_fields_list = []
        
        if not created and default_department and not conversation.department:
            logger.info(f"📋 [ROUTING] Conversa existente sem departamento, aplicando default_department: {default_department.name}")
            conversation.department = default_department
            update_fields_list.append('department')
            needs_update = True
            
            # Mudar status de 'pending' para 'open' ao atribuir departamento
            if conversation.status == 'pending':
                conversation.status = 'open'
                update_fields_list.append('status')
        
        # ✅ FIX CRÍTICO: Se conversa foi criada COM departamento, garantir que status está correto
        if created and default_department:
            if conversation.status != 'open':
                logger.warning(f"⚠️ [ROUTING] Conversa criada com departamento mas status errado: {conversation.status} → corrigindo para 'open'")
                conversation.status = 'open'
                update_fields_list.append('status')
                needs_update = True
        
        # ✅ FIX CRÍTICO: Se conversa foi criada SEM departamento mas deveria ter (verificar se defaults foi aplicado)
        if created and default_department and not conversation.department:
            logger.error(f"❌ [ROUTING] ERRO: Conversa criada mas department não foi aplicado dos defaults!")
            logger.error(f"   Defaults tinha: department={default_department.id} ({default_department.name})")
            logger.error(f"   Conversa tem: department={conversation.department_id}")
            # Forçar atualização
            conversation.department = default_department
            conversation.status = 'open'
            update_fields_list.extend(['department', 'status'])
            needs_update = True
        
        if needs_update:
            conversation.save(update_fields=update_fields_list)
            logger.info(f"✅ [ROUTING] Conversa atualizada: {phone}")
            logger.info(f"   📋 Departamento DEPOIS: {conversation.department.name if conversation.department else 'Nenhum (Inbox)'}")
            logger.info(f"   📊 Status DEPOIS: {conversation.status}")
            logger.info(f"   🔧 Campos atualizados: {', '.join(update_fields_list)}")
        
        # ✅ DEBUG: Verificar estado final
        logger.info(f"📋 [CONVERSA] Estado final: {phone}")
        logger.info(f"   📋 Departamento FINAL: {conversation.department.name if conversation.department else 'Nenhum (Inbox)'} (ID: {conversation.department_id or 'None'})")
        logger.info(f"   📊 Status FINAL: {conversation.status}")
        
        # ✅ FIX CRÍTICO: Inicializar status_changed ANTES do bloco if created else
        # Isso evita UnboundLocalError quando conversa é nova ou existente
        status_changed = False
        
        if created:
            logger.info(f"✅ [WEBHOOK] Nova conversa criada: {phone}")
            logger.info(f"   📋 Departamento: {default_department.name if default_department else 'Nenhum (Inbox)'}")
            logger.info(f"   📊 Status: {conversation.status}")
            logger.info(f"   🆔 ID: {conversation.id}")
            
            # 📸 Buscar foto de perfil SÍNCRONAMENTE (é rápida)
            logger.info(f"📸 [FOTO] Iniciando busca... | Tipo: {conversation_type} | É grupo: {is_group}")
            try:
                # ✅ CORREÇÃO: Importar no escopo local para evitar problemas de escopo
                from apps.notifications.models import WhatsAppInstance as WAInstance
                from apps.connections.models import EvolutionConnection
                
                # Buscar instância WhatsApp ativa do tenant
                wa_instance = WAInstance.objects.filter(
                    tenant=tenant,
                    is_active=True,
                    status='active'
                ).first()
                
                # Buscar servidor Evolution
                evolution_server = EvolutionConnection.objects.filter(is_active=True).first()
                
                if wa_instance and evolution_server:
                    logger.info(f"📸 [WEBHOOK] Buscando foto de perfil...")
                    
                    base_url = (wa_instance.api_url or evolution_server.base_url).rstrip('/')
                    api_key = wa_instance.api_key or evolution_server.api_key
                    instance_name = wa_instance.instance_name
                    
                    # 👥 Para GRUPOS: enfileirar busca de informações (assíncrona, não bloqueia webhook)
                    if is_group:
                        group_jid = remote_jid
                        logger.info(f"👥 [GRUPO NOVO] Enfileirando busca de informações para Group JID: {group_jid}")
                        
                        # ✅ Enfileirar task assíncrona para buscar informações do grupo
                        from apps.chat.tasks import fetch_group_info
                        fetch_group_info.delay(
                            conversation_id=str(conversation.id),
                            group_jid=group_jid,
                            instance_name=instance_name,
                            api_key=api_key,
                            base_url=base_url
                        )
                        logger.info(f"✅ [GRUPO NOVO] Task enfileirada - informações serão buscadas em background")
                    
                    # 👤 Para INDIVIDUAIS: enfileirar busca de foto E nome (assíncrona, não bloqueia webhook)
                    else:
                        clean_phone = phone.replace('+', '').replace('@s.whatsapp.net', '')
                        logger.info(f"👤 [INDIVIDUAL] Enfileirando busca de informações do contato: {clean_phone}")
                        
                        # ✅ OTIMIZAÇÃO: fetch_profile_pic já busca nome E foto juntos (mais rápido que duas tasks separadas)
                        # Similar ao comportamento de grupos que usa uma única task
                        from apps.chat.tasks import fetch_profile_pic
                        
                        fetch_profile_pic.delay(
                            conversation_id=str(conversation.id),
                            phone=clean_phone
                        )
                        logger.info(f"✅ [INDIVIDUAL] Task de foto+nome enfileirada - informações serão buscadas em background")
                else:
                    logger.info(f"ℹ️ [WEBHOOK] Nenhuma instância Evolution ativa para buscar foto")
            except Exception as e:
                logger.error(f"❌ [WEBHOOK] Erro ao buscar foto de perfil: {e}", exc_info=True)
        
        # 📸 Para conversas EXISTENTES de GRUPO: sempre enfileirar busca (garante dados atualizados)
        elif is_group:
            logger.info("👥 [GRUPO EXISTENTE] Enfileirando busca de informações do grupo...")
            try:
                from apps.notifications.models import WhatsAppInstance as WAInstance
                from apps.connections.models import EvolutionConnection
                from apps.chat.tasks import fetch_group_info

                wa_instance = WAInstance.objects.filter(
                    tenant=tenant,
                    is_active=True,
                    status='active'
                ).first()

                evolution_server = EvolutionConnection.objects.filter(is_active=True).first()

                if wa_instance and evolution_server:
                    group_jid = remote_jid
                    logger.info("👥 [GRUPO EXISTENTE] Enfileirando busca para Group JID: %s", group_jid)

                    base_url = (wa_instance.api_url or evolution_server.base_url).rstrip('/')
                    api_key = wa_instance.api_key or evolution_server.api_key
                    instance_name = wa_instance.instance_name

                    # ✅ MELHORIA: Sempre enfileirar busca de info (garante nome e foto atualizados)
                    fetch_group_info.delay(
                        conversation_id=str(conversation.id),
                        group_jid=group_jid,
                        instance_name=instance_name,
                        api_key=api_key,
                        base_url=base_url
                    )
                    logger.info("✅ [GRUPO EXISTENTE] Task enfileirada - informações serão buscadas em background")
                else:
                    logger.warning("⚠️ [GRUPO EXISTENTE] Instância WhatsApp ou servidor Evolution não encontrado")
            except Exception as e:
                logger.error("❌ [GRUPO EXISTENTE] Erro ao enfileirar busca: %s", e, exc_info=True)
        
        # 👤 Para conversas EXISTENTES INDIVIDUAIS: sempre enfileirar busca (garante dados atualizados)
        elif not is_group:
            logger.info("👤 [INDIVIDUAL EXISTENTE] Enfileirando busca de informações do contato...")
            try:
                from apps.notifications.models import WhatsAppInstance as WAInstance
                from apps.connections.models import EvolutionConnection
                from apps.chat.tasks import fetch_contact_name, fetch_profile_pic

                wa_instance = WAInstance.objects.filter(
                    tenant=tenant,
                    is_active=True,
                    status='active'
                ).first()

                evolution_server = EvolutionConnection.objects.filter(is_active=True).first()

                if wa_instance and evolution_server:
                    clean_phone = phone.replace('+', '').replace('@s.whatsapp.net', '')
                    logger.info("👤 [INDIVIDUAL EXISTENTE] Enfileirando busca para telefone: %s", clean_phone)

                    base_url = (wa_instance.api_url or evolution_server.base_url).rstrip('/')
                    api_key = wa_instance.api_key or evolution_server.api_key
                    instance_name = wa_instance.instance_name

                    # ✅ OTIMIZAÇÃO: fetch_profile_pic já busca nome E foto juntos (mais rápido que duas tasks separadas)
                    # Similar ao comportamento de grupos que usa uma única task
                    from apps.chat.tasks import fetch_profile_pic
                    
                    fetch_profile_pic.delay(
                        conversation_id=str(conversation.id),
                        phone=clean_phone
                    )
                    logger.info("✅ [INDIVIDUAL EXISTENTE] Task de foto+nome enfileirada - informações serão buscadas em background")
                else:
                    logger.warning("⚠️ [INDIVIDUAL EXISTENTE] Instância WhatsApp ou servidor Evolution não encontrado")
            except Exception as e:
                logger.error("❌ [INDIVIDUAL EXISTENTE] Erro ao enfileirar busca: %s", e, exc_info=True)
        
        # ✅ CONVERSAS EXISTENTES: Se conversa estava fechada, reabrir automaticamente
        # ✅ FIX: status_changed já foi inicializado antes do bloco if created else
        if not created:
            if conversation.status == 'closed':
                old_status = conversation.status
                old_department = conversation.department.name if conversation.department else 'Nenhum'
                
                # ✅ CORREÇÃO CRÍTICA: Quando reabrir conversa fechada, remover departamento
                # para que ela volte para o Inbox (comportamento esperado)
                conversation.status = 'pending' if not from_me else 'open'
                conversation.department = None  # ✅ Remover departamento para voltar ao Inbox
                conversation.save(update_fields=['status', 'department'])
                
                status_str = "Inbox" if not from_me else "Aberta"
                status_changed = True
                logger.info(f"🔄 [WEBHOOK] Conversa {phone} reaberta automaticamente: {old_status} → {conversation.status} ({status_str})")
                logger.info(f"   📋 Departamento removido: {old_department} → Inbox (sem departamento)")
            
            # ✅ IMPORTANTE: Para conversas existentes, ainda precisamos atualizar last_message_at
            # Isso garante que a conversa aparece no topo da lista
            conversation.update_last_message()
            
        # ✅ NOVO: Atualizar nome da conversa com dados da lista de contatos se disponível
        # Prioridade: 1) Nome do contato salvo, 2) Número formatado (nunca pushName)
        update_fields = []
        name_or_pic_changed = False
        
        if not is_group:
            # Buscar contato na lista novamente (pode ter sido criado desde a última mensagem)
            from apps.contacts.models import Contact
            from django.db.models import Q
            
            # Reutilizar normalized_phone já calculado acima
            saved_contact = Contact.objects.filter(
                Q(tenant=tenant) &
                (Q(phone=normalized_phone) | Q(phone=phone))
            ).first()
            
            new_contact_name = None
            if saved_contact:
                # ✅ Contato existe - usar nome salvo
                new_contact_name = saved_contact.name
                logger.info(f"✅ [CONTATO] Atualizando nome da conversa com nome da lista: {new_contact_name}")
            else:
                # ✅ Contato não existe - usar número formatado
                clean_phone_for_name = phone.replace('+', '').replace('@s.whatsapp.net', '')
                new_contact_name = _format_phone_for_display(clean_phone_for_name)
                logger.info(f"📞 [CONTATO] Atualizando nome da conversa com número formatado: {new_contact_name}")
            
            # Atualizar se mudou
            if new_contact_name and conversation.contact_name != new_contact_name:
                conversation.contact_name = new_contact_name
                update_fields.append('contact_name')
                name_or_pic_changed = True
                logger.info(f"✅ [WEBHOOK] Nome da conversa atualizado: '{conversation.contact_name}'")
        
        if profile_pic_url and conversation.profile_pic_url != profile_pic_url:
            conversation.profile_pic_url = profile_pic_url
            update_fields.append('profile_pic_url')
            name_or_pic_changed = True
            logger.info(f"📸 [WEBHOOK] Foto de perfil atualizada: {profile_pic_url[:50]}...")
        
        if update_fields:
            conversation.save(update_fields=update_fields)
        
        # ✅ IMPORTANTE: Fazer broadcast UMA VEZ apenas se algo mudou (status OU nome/foto)
        # Isso evita duplicação de eventos e múltiplos toasts
        if status_changed or name_or_pic_changed:
            try:
                from apps.chat.utils.serialization import serialize_conversation_for_ws
                from django.db.models import Count, Q
                # ✅ Usar imports globais (linhas 12-13) ao invés de import local
                # from channels.layers import get_channel_layer  # ❌ REMOVIDO: causava UnboundLocalError
                # from asgiref.sync import async_to_sync  # ❌ REMOVIDO: causava UnboundLocalError
                
                # ✅ Recarregar do banco para garantir dados atualizados
                conversation.refresh_from_db()
                
                # ✅ FIX CRÍTICO: Recalcular unread_count para garantir que está atualizado
                if not hasattr(conversation, 'unread_count_annotated'):
                    from apps.chat.models import Conversation as ConvModel
                    conversation_with_annotate = ConvModel.objects.annotate(
                        unread_count_annotated=Count(
                            'messages',
                            filter=Q(
                                messages__direction='incoming',
                                messages__status__in=['sent', 'delivered']
                            ),
                            distinct=True
                        )
                    ).get(id=conversation.id)
                    conversation.unread_count_annotated = conversation_with_annotate.unread_count_annotated
                
                conv_data_serializable = serialize_conversation_for_ws(conversation)
                
                channel_layer = get_channel_layer()  # ✅ Usa import global (linha 12)
                tenant_group = f"chat_tenant_{tenant.id}"
                
                async_to_sync(channel_layer.group_send)(
                    tenant_group,
                    {
                        'type': 'conversation_updated',
                        'conversation': conv_data_serializable
                    }
                )
                
                change_type = "status mudou" if status_changed else "nome/foto atualizado"
                logger.info(f"📡 [WEBSOCKET] Broadcast de conversa atualizada ({change_type}) enviado (unread_count: {getattr(conversation, 'unread_count_annotated', 'N/A')})")
            except Exception as e:
                logger.error(f"❌ [WEBSOCKET] Erro ao fazer broadcast de conversa atualizada: {e}", exc_info=True)
        
        # Cria mensagem
        direction = 'outgoing' if from_me else 'incoming'
        
        message_defaults = {
            'conversation': conversation,
            'content': content,
            'direction': direction,
            'status': 'sent',
            'evolution_status': 'sent',
            'metadata': {}
        }
        
        # ✅ NOVO: Adicionar dados do contato compartilhado ao metadata
        if contact_message_data:
            message_defaults['metadata']['contact_message'] = contact_message_data
        
        # ✅ NOVO: Adicionar menções ao metadata (quando mensagem recebida tem menções)
        if mentions_list:
            message_defaults['metadata']['mentions'] = mentions_list
            logger.info(f"✅ [WEBHOOK] Menções adicionadas ao metadata: {len(mentions_list)}")
            
            # ✅ MELHORIA: Criar notificações para usuários mencionados
            try:
                from apps.authn.models import User
                from apps.notifications.services import normalize_phone
                
                # Buscar todos os telefones mencionados
                mentioned_phones = [m['phone'] for m in mentions_list]
                
                # Buscar usuários do tenant que têm esses telefones
                # Normalizar telefones para busca
                normalized_mentioned = []
                for phone in mentioned_phones:
                    normalized = normalize_phone(phone)
                    if normalized:
                        normalized_mentioned.append(normalized)
                        # Também tentar sem + e com +
                        normalized_mentioned.append(normalized.lstrip('+'))
                        if not normalized.startswith('+'):
                            normalized_mentioned.append(f"+{normalized}")
                
                if normalized_mentioned:
                    mentioned_users = User.objects.filter(
                        tenant=tenant,
                        phone__in=normalized_mentioned
                    ).select_related('tenant')
                    
                    for user in mentioned_users:
                        # ✅ MELHORIA: Enviar notificação via WebSocket (real-time)
                        try:
                            channel_layer = get_channel_layer()
                            if channel_layer:
                                async_to_sync(channel_layer.group_send)(
                                    f"user_{user.id}",
                                    {
                                        'type': 'mention_notification',
                                        'message': {
                                            'id': str(message_defaults.get('id', '')),
                                            'conversation_id': str(conversation.id),
                                            'content': message_defaults.get('content', '')[:100],
                                            'sender_name': sender_name or 'Usuário',
                                            'conversation_name': conversation.contact_name or 'Conversa'
                                        }
                                    }
                                )
                                logger.info(f"📬 [WEBHOOK] Notificação de menção enviada via WebSocket para usuário {user.email}")
                        except Exception as e:
                            logger.warning(f"⚠️ [WEBHOOK] Erro ao enviar notificação de menção via WebSocket: {e}")
            except Exception as e:
                logger.warning(f"⚠️ [WEBHOOK] Erro ao processar notificações de menção: {e}", exc_info=True)
        
        # ✅ NOVO: Processar quotedMessage (mensagem sendo respondida)
        # ✅ FALLBACK: Se quoted_message_id_evolution é None mas temos quotedMessage no contextInfo,
        # tentar buscar pelo conteúdo da mensagem original
        if not quoted_message_id_evolution:
            # Verificar se temos quotedMessage no contextInfo mas sem key.id
            conversation_context = message_info.get('contextInfo', {}) or message_data.get('contextInfo', {})
            quoted_message = conversation_context.get('quotedMessage', {}) if conversation_context else {}
            if quoted_message and not quoted_message.get('key', {}).get('id'):
                quoted_conversation = quoted_message.get('conversation', '')
                if quoted_conversation:
                    logger.warning(f"⚠️ [WEBHOOK REPLY] quotedMessage sem key.id, tentando buscar pelo conteúdo:")
                    logger.warning(f"   Conteúdo: {quoted_conversation[:100]}...")
                    logger.warning(f"   RemoteJid: {remote_jid}")
                    logger.warning(f"   Conversation ID: {conversation.id}")
                    
                    # Buscar mensagem recente com conteúdo similar na mesma conversa
                    # Limpar conteúdo para busca (remover formatação e assinatura)
                    import re
                    
                    # ✅ FIX CRÍTICO: Remover assinatura completamente
                    # Formato da assinatura: *Nome:*\n\nconteúdo ou *Nome:* conteúdo
                    # Primeiro, remover asteriscos e normalizar espaços
                    clean_quoted = quoted_conversation.replace('*', '').replace('_', '').replace('\n', ' ').replace('\r', ' ')
                    # Remover múltiplos espaços
                    clean_quoted = re.sub(r'\s+', ' ', clean_quoted).strip()
                    
                    # ✅ FIX: Remover padrão de assinatura: "Nome: " no início
                    # Pode ser "Paulo Bernal: " ou "Nome Sobrenome: " seguido do conteúdo
                    # Remover tudo até o primeiro ":" seguido de espaço
                    clean_quoted = re.sub(r'^[^:]+:\s+', '', clean_quoted, count=1)
                    clean_quoted = clean_quoted.strip()
                    
                    logger.warning(f"   Conteúdo limpo (sem assinatura): {clean_quoted[:100]}...")
                    
                    # ✅ FIX: Extrair palavras-chave mais específicas para busca
                    # Para mensagens longas, usar primeiras palavras únicas
                    words = clean_quoted.split()
                    
                    # Estratégia 1: Se tiver muitas palavras, usar primeiras palavras únicas
                    if len(words) > 10:
                        # Pegar primeiras 3-5 palavras que sejam únicas e significativas
                        unique_words = []
                        seen = set()
                        for w in words[:10]:  # Primeiras 10 palavras
                            w_clean = w.strip('.,;:!?@#$%&*()[]{}')
                            if len(w_clean) > 3 and w_clean.lower() not in seen:
                                unique_words.append(w_clean)
                                seen.add(w_clean.lower())
                                if len(unique_words) >= 5:
                                    break
                        search_text = ' '.join(unique_words) if unique_words else clean_quoted[:50]
                    else:
                        # Mensagem curta: usar texto completo
                        search_text = clean_quoted
                    
                    # Limitar tamanho da busca (máximo 100 caracteres)
                    if len(search_text) > 100:
                        search_text = search_text[:100]
                    
                    logger.warning(f"   Texto de busca: {search_text[:100]}...")
                    logger.warning(f"   Tamanho do texto de busca: {len(search_text)} caracteres")
                    
                    # ✅ FIX: Buscar em múltiplas tentativas com diferentes estratégias
                    recent_messages = None
                    
                    # Tentativa 1: Busca exata com texto completo (limitado)
                    if len(search_text) >= 10:
                        recent_messages = Message.objects.filter(
                            conversation=conversation,
                            content__icontains=search_text
                        ).order_by('-created_at')[:50]  # Aumentar para 50 mensagens
                        logger.warning(f"   Tentativa 1 (busca completa): {recent_messages.count()} mensagens")
                    
                    # Tentativa 2: Se não encontrou, buscar por primeiras palavras
                    if (not recent_messages or recent_messages.count() == 0) and len(words) > 0:
                        first_words = ' '.join(words[:3])  # Primeiras 3 palavras
                        if len(first_words) >= 5:
                            recent_messages = Message.objects.filter(
                                conversation=conversation,
                                content__icontains=first_words
                            ).order_by('-created_at')[:50]
                            logger.warning(f"   Tentativa 2 (primeiras palavras): {recent_messages.count()} mensagens")
                    
                    # Tentativa 3: Se ainda não encontrou, buscar por qualquer palavra significativa
                    if (not recent_messages or recent_messages.count() == 0) and len(words) > 0:
                        # Buscar por qualquer palavra com mais de 5 caracteres
                        significant_word = next((w for w in words if len(w.strip('.,;:!?@#$%&*()[]{}')) > 5), None)
                        if significant_word:
                            recent_messages = Message.objects.filter(
                                conversation=conversation,
                                content__icontains=significant_word.strip('.,;:!?@#$%&*()[]{}')
                            ).order_by('-created_at')[:50]
                            logger.warning(f"   Tentativa 3 (palavra significativa '{significant_word[:20]}...'): {recent_messages.count()} mensagens")
                    
                    if not recent_messages:
                        recent_messages = Message.objects.none()
                    
                    logger.warning(f"   Mensagens encontradas com conteúdo similar: {recent_messages.count()}")
                    for msg in recent_messages:
                        logger.warning(f"   - ID: {msg.id}, message_id: {msg.message_id}, content: {msg.content[:50] if msg.content else 'N/A'}...")
                    
                    # Se encontrou exatamente uma mensagem, usar ela
                    if recent_messages.count() == 1:
                        matched_message = recent_messages.first()
                        if matched_message.message_id:
                            quoted_message_id_evolution = matched_message.message_id
                            logger.warning(f"✅ [WEBHOOK REPLY] Mensagem encontrada pelo conteúdo! message_id: {_mask_digits(quoted_message_id_evolution)}")
                        else:
                            logger.warning(f"⚠️ [WEBHOOK REPLY] Mensagem encontrada mas sem message_id (Evolution)")
                    elif recent_messages.count() > 1:
                        logger.warning(f"⚠️ [WEBHOOK REPLY] Múltiplas mensagens encontradas ({recent_messages.count()}), usando a mais recente")
                        matched_message = recent_messages.first()
                        if matched_message.message_id:
                            quoted_message_id_evolution = matched_message.message_id
                            logger.warning(f"✅ [WEBHOOK REPLY] Usando mensagem mais recente: {_mask_digits(quoted_message_id_evolution)}")
        
        if quoted_message_id_evolution:
            logger.critical(f"💬 [WEBHOOK REPLY] ====== PROCESSANDO REPLY ======")
            logger.critical(f"   quoted_message_id_evolution: {_mask_digits(quoted_message_id_evolution)}")
            logger.critical(f"   Tenant: {tenant.name}")
            
            try:
                # Buscar mensagem original pelo message_id da Evolution
                logger.critical(f"🔍 [WEBHOOK REPLY] Buscando mensagem original com message_id: {_mask_digits(quoted_message_id_evolution)}")
                original_message = Message.objects.filter(
                    message_id=quoted_message_id_evolution,
                    conversation__tenant=tenant
                ).select_related('conversation').first()
                
                if original_message:
                    # Salvar UUID interno da mensagem original no metadata
                    reply_to_uuid = str(original_message.id)
                    message_defaults['metadata']['reply_to'] = reply_to_uuid
                    logger.critical(f"✅ [WEBHOOK REPLY] Mensagem original encontrada!")
                    logger.critical(f"   UUID interno: {reply_to_uuid}")
                    logger.critical(f"   Evolution ID: {_mask_digits(quoted_message_id_evolution)}")
                    logger.critical(f"   Conversa: {original_message.conversation.contact_phone}")
                    logger.critical(f"   Conteúdo original: {original_message.content[:50] if original_message.content else 'Sem conteúdo'}...")
                else:
                    logger.warning(f"⚠️ [WEBHOOK REPLY] Mensagem original NÃO encontrada para reply!")
                    logger.warning(f"   Evolution ID procurado: {_mask_digits(quoted_message_id_evolution)}")
                    logger.warning(f"   Tenant: {tenant.name}")
                    
                    # Tentar buscar em todas as conversas do tenant (pode estar em outra conversa?)
                    all_messages = Message.objects.filter(
                        message_id=quoted_message_id_evolution
                    ).select_related('conversation', 'conversation__tenant')
                    
                    logger.warning(f"   Total de mensagens com esse message_id em TODOS os tenants: {all_messages.count()}")
                    for msg in all_messages:
                        logger.warning(f"   - Encontrada em tenant: {msg.conversation.tenant.name} (conversa: {msg.conversation.contact_phone})")
                    
                    # Salvar o message_id da Evolution como fallback (pode ser útil para debug)
                    message_defaults['metadata']['reply_to_evolution_id'] = quoted_message_id_evolution
            except Exception as e:
                logger.error(f"❌ [WEBHOOK REPLY] Erro ao processar quotedMessage: {e}", exc_info=True)
        else:
            logger.debug(f"🔍 [WEBHOOK REPLY] Mensagem NÃO é reply (quoted_message_id_evolution é None)")
        
        # Para grupos, adicionar quem enviou
        if is_group and sender_phone:
            message_defaults['sender_name'] = sender_name
            message_defaults['sender_phone'] = sender_phone
        
        # ✅ CORREÇÃO: Reprocessar menções com a conversa disponível (para buscar nomes dos participantes)
        if mentioned_jids_raw and conversation:
            logger.info(f"🔄 [WEBHOOK] Reprocessando {len(mentioned_jids_raw)} menções com conversa disponível...")
            logger.info(f"   JIDs mencionados: {mentioned_jids_raw}")
            logger.info(f"   Conversa ID: {conversation.id}")
            logger.info(f"   Tipo de conversa: {conversation.conversation_type}")
            mentions_list = process_mentions_optimized(mentioned_jids_raw, tenant, conversation)
            logger.info(f"✅ [WEBHOOK] {len(mentions_list)} menções reprocessadas com nomes dos participantes")
            for i, mention in enumerate(mentions_list):
                logger.info(f"   Menção {i+1}: jid={mention.get('jid', 'N/A')}, name={mention.get('name', 'N/A')}, phone={mention.get('phone', 'N/A')}")
        
        # Atualizar metadata com menções (reprocessadas ou não)
        if mentions_list:
            message_defaults.setdefault('metadata', {})['mentions'] = mentions_list
        
        logger.critical(f"💾 [WEBHOOK] ====== SALVANDO MENSAGEM NO BANCO ======")
        logger.critical(f"   message_id={_mask_digits(message_id) if message_id else 'N/A'}")
        logger.critical(f"   direction={direction} (fromMe={from_me})")
        logger.critical(f"   conversation_id={conversation.id}")
        logger.critical(f"   content={content[:100] if content else '(vazio)'}...")
        logger.critical(f"   metadata ANTES de salvar: {message_defaults.get('metadata', {})}")
        logger.critical(f"   reply_to no metadata: {message_defaults.get('metadata', {}).get('reply_to', 'NÃO ENCONTRADO')}")
        
        # ✅ FIX: Verificar se mensagem já existe antes de criar
        # Isso evita duplicatas e garante que mensagens sejam encontradas
        existing_message = None
        if message_id:
            existing_message = Message.objects.filter(message_id=message_id).first()
        
        if existing_message:
            logger.critical(f"⚠️ [WEBHOOK] Mensagem já existe no banco (message_id={_mask_digits(message_id)}), preservando metadata existente")
            logger.critical(f"   ID interno: {existing_message.id}")
            logger.critical(f"   Conversa: {existing_message.conversation.id}")
            logger.critical(f"   Direction: {existing_message.direction}")
            logger.critical(f"   Content: {existing_message.content[:100] if existing_message.content else 'Sem conteúdo'}...")
            logger.critical(f"   Metadata existente: {existing_message.metadata}")
            logger.critical(f"   Metadata do webhook: {message_defaults.get('metadata', {})}")
            
            # ✅ FIX CRÍTICO: Preservar metadata existente (especialmente reply_to)
            # Se a mensagem foi criada pelo backend com reply_to, preservar
            existing_metadata = existing_message.metadata or {}
            new_metadata = message_defaults.get('metadata', {})
            
            # ✅ LOG CRÍTICO: Verificar reply_to antes de mesclar
            if 'reply_to' in existing_metadata:
                logger.critical(f"💬 [WEBHOOK REPLY] Mensagem existente TEM reply_to: {existing_metadata.get('reply_to')}")
            if 'reply_to' in new_metadata:
                logger.critical(f"💬 [WEBHOOK REPLY] Webhook trouxe reply_to: {new_metadata.get('reply_to')}")
            
            # Mesclar metadata: preservar existente, adicionar apenas campos novos do webhook
            merged_metadata = {**existing_metadata, **new_metadata}
            
            # ✅ IMPORTANTE: Se metadata existente tem reply_to, preservar (não sobrescrever)
            if 'reply_to' in existing_metadata and 'reply_to' not in new_metadata:
                # Manter reply_to existente
                logger.critical(f"💬 [WEBHOOK REPLY] ✅ PRESERVANDO reply_to existente: {existing_metadata.get('reply_to')}")
            elif 'reply_to' in new_metadata:
                # Se webhook trouxe reply_to (mensagem recebida é reply), usar do webhook
                logger.critical(f"💬 [WEBHOOK REPLY] ✅ USANDO reply_to do webhook: {new_metadata.get('reply_to')}")
            else:
                logger.critical(f"💬 [WEBHOOK REPLY] ⚠️ Nenhum reply_to encontrado (nem existente nem do webhook)")
            
            # Atualizar metadata preservando reply_to
            existing_message.metadata = merged_metadata
            existing_message.save(update_fields=['metadata'])
            
            logger.critical(f"💬 [WEBHOOK REPLY] Metadata final após merge: {existing_message.metadata}")
            
            message = existing_message
            msg_created = False
        else:
            # ✅ FIX: Se não tem message_id, gerar um baseado no key.id
            if not message_id:
                key_id = key.get('id')
                if key_id:
                    message_id = key_id
                    logger.info(f"⚠️ [WEBHOOK] message_id não fornecido, usando key.id: {message_id}")
                else:
                    # Fallback: gerar ID único baseado no timestamp e remoteJid
                    import hashlib
                    unique_str = f"{remote_jid}_{from_me}_{content[:50]}_{conversation.id}"
                    message_id = hashlib.md5(unique_str.encode()).hexdigest()[:16]
                    logger.warning(f"⚠️ [WEBHOOK] message_id não encontrado, gerando: {message_id}")
            
            message_defaults['message_id'] = message_id
            message, msg_created = Message.objects.get_or_create(
                message_id=message_id,
                defaults=message_defaults
            )
        
        if msg_created:
            logger.info(f"✅ [WEBHOOK] MENSAGEM NOVA CRIADA NO BANCO!")
            logger.info(f"   ID interno: {message.id}")
            logger.info(f"   Message ID: {message_id}")
            logger.info(f"   Direction: {direction}")
            logger.info(f"   Conversa: {conversation.id} | Phone: {conversation.contact_phone}")
            
            # ✅ NOVO: Verificar horário de atendimento e criar tarefa/mensagem automática
            if direction == 'incoming':
                logger.info(f"🔍 [BUSINESS HOURS] Verificando horário de atendimento para mensagem recebida...")
                logger.info(f"   Tenant: {tenant.name} (ID: {tenant.id})")
                logger.info(f"   Department: {conversation.department.name if conversation.department else 'None'}")
                logger.info(f"   Message created_at: {message.created_at}")
                try:
                    from apps.chat.services.business_hours_service import BusinessHoursService
                    
                    # Processa mensagem fora de horário (cria mensagem automática se configurado)
                    was_after_hours, auto_message = BusinessHoursService.handle_after_hours_message(
                        conversation=conversation,
                        message=message,
                        tenant=tenant,
                        department=conversation.department
                    )
                    
                    logger.info(f"🔍 [BUSINESS HOURS] Resultado da verificação: was_after_hours={was_after_hours}")
                    
                    if was_after_hours:
                        logger.info(f"⏰ [BUSINESS HOURS] Mensagem recebida fora de horário")
                        if auto_message:
                            logger.info(f"   📨 Mensagem automática criada: {auto_message.id}")
                        else:
                            logger.info(f"   ⚠️ Mensagem automática não foi criada (pode não estar configurada)")
                        
                        # Cria tarefa automática se configurado
                        logger.info(f"🔍 [BUSINESS HOURS] Tentando criar tarefa automática...")
                        task = BusinessHoursService.create_after_hours_task(
                            conversation=conversation,
                            message=message,
                            tenant=tenant,
                            department=conversation.department
                        )
                        
                        if task:
                            logger.info(f"   ✅ Tarefa automática criada: {task.id} - {task.title}")
                        else:
                            logger.warning(f"   ⚠️ Tarefa automática não foi criada - verifique os logs acima para detalhes")
                    else:
                        logger.info(f"✅ [BUSINESS HOURS] Mensagem recebida dentro do horário de atendimento")
                except Exception as e:
                    logger.error(f"❌ [BUSINESS HOURS] Erro ao processar horário de atendimento: {e}", exc_info=True)
            else:
                logger.info(f"ℹ️ [BUSINESS HOURS] Mensagem é {direction}, não verifica horário de atendimento")
            
            # Se tiver anexo, processa
            attachment_url = None
            mime_type = None
            filename = ''
            
            if message_type == 'imageMessage':
                attachment_url = message_info.get('imageMessage', {}).get('url')
                mime_type = message_info.get('imageMessage', {}).get('mimetype', 'image/jpeg')
                filename = f"{message.id}.jpg"
            elif message_type == 'videoMessage':
                attachment_url = message_info.get('videoMessage', {}).get('url')
                mime_type = message_info.get('videoMessage', {}).get('mimetype', 'video/mp4')
                filename = f"{message.id}.mp4"
            elif message_type == 'documentMessage':
                attachment_url = message_info.get('documentMessage', {}).get('url')
                mime_type = message_info.get('documentMessage', {}).get('mimetype', 'application/octet-stream')
                raw_filename = message_info.get('documentMessage', {}).get('fileName', f"{message.id}.bin")
                
                # ✅ CORREÇÃO: Limpar nome de arquivo inválido (ex: .enc, nomes muito longos)
                filename = clean_filename(raw_filename, message_id=message_id, mime_type=mime_type)
            elif message_type == 'audioMessage':
                attachment_url = message_info.get('audioMessage', {}).get('url')
                mime_type = message_info.get('audioMessage', {}).get('mimetype', 'audio/ogg')
                filename = f"{message.id}.ogg"
            
            if attachment_url:
                # Determinar media_type baseado no message_type
                if message_type == 'imageMessage':
                    incoming_media_type = 'image'
                elif message_type == 'videoMessage':
                    incoming_media_type = 'video'
                elif message_type == 'audioMessage':
                    incoming_media_type = 'audio'
                elif message_type == 'documentMessage':
                    incoming_media_type = 'document'
                else:
                    incoming_media_type = 'document'
                
                # Usar transaction para garantir que o anexo seja salvo antes de enfileirar
                from django.db import transaction
                with transaction.atomic():
                    # Criar placeholder (sem file_url ainda, será preenchido após processamento)
                    attachment = MessageAttachment.objects.create(
                        message=message,
                        tenant=tenant,
                        original_filename=filename,
                        mime_type=mime_type,
                        file_path='',  # Será preenchido após processamento S3
                        file_url='',  # Será preenchido com URL proxy após processamento
                        storage_type='s3',  # Direto para S3 (sem storage local)
                        size_bytes=0,  # Será preenchido após download
                        metadata={
                            'processing': True,
                            'media_type': incoming_media_type,
                            'mime_type': mime_type
                        }  # Flag para frontend mostrar loading + mime original
                    )
                    
                    attachment_id_str = str(attachment.id)
                    message_id_str = str(message.id)
                    tenant_id_str = str(tenant.id)
                    
                    logger.info(f"📎 [WEBHOOK] Criado anexo placeholder ID={attachment_id_str}, mime={mime_type}, type={incoming_media_type}")
                    logger.info(f"📎 [WEBHOOK] URL temporária: {attachment_url[:100]}...")
                    
                    # Força commit antes de enfileirar processamento direto (S3 direto - sem cache)
                    # ✅ MELHORIA: Usar conexão Evolution já encontrada no webhook para descriptografar arquivos
                    instance_name_for_media = None
                    api_key_for_media = None
                    evolution_api_url_for_media = None
                    
                    # ✅ CORREÇÃO: Usar WhatsAppInstance (tem instance_name UUID) ou EvolutionConnection
                    # Prioridade: wa_instance > connection > fallback
                    instance_name_for_media = None
                    api_key_for_media = None
                    evolution_api_url_for_media = None
                    
                    # ✅ OPÇÃO 1: Usar WhatsAppInstance (tem instance_name UUID do webhook)
                    if wa_instance:
                        instance_name_for_media = wa_instance.instance_name  # UUID da instância
                        api_key_for_media = wa_instance.api_key or (connection.api_key if connection else None)
                        evolution_api_url_for_media = wa_instance.api_url or (connection.base_url if connection else None)
                        
                        logger.info(f"✅ [WEBHOOK] Usando WhatsAppInstance para descriptografar mídia:")
                        logger.info(f"   📌 Instance (UUID): {instance_name_for_media}")
                        logger.info(f"   📌 Friendly Name: {wa_instance.friendly_name}")
                        logger.info(f"   📌 API URL: {evolution_api_url_for_media}")
                        logger.info(f"   📌 API Key: {'Configurada' if api_key_for_media else 'Não configurada'}")
                    
                    # ✅ OPÇÃO 2: Usar EvolutionConnection (fallback)
                    elif connection:
                        instance_name_for_media = instance_name  # Usar instance_name do webhook (pode ser UUID ou nome)
                        api_key_for_media = connection.api_key
                        evolution_api_url_for_media = connection.api_url or connection.base_url
                        
                        logger.info(f"✅ [WEBHOOK] Usando EvolutionConnection para descriptografar mídia:")
                        logger.info(f"   📌 Instance: {instance_name_for_media}")
                        logger.info(f"   📌 API URL: {evolution_api_url_for_media}")
                        logger.info(f"   📌 Connection: {connection.name}")
                    
                    # ✅ OPÇÃO 3: Fallback - buscar conexão diretamente
                    else:
                        logger.warning(f"⚠️ [WEBHOOK] Nenhuma conexão disponível, tentando buscar diretamente...")
                        
                        try:
                            # Tentar buscar WhatsAppInstance pelo instance_name (UUID)
                            from apps.notifications.models import WhatsAppInstance
                            from apps.connections.models import EvolutionConnection
                            
                            fallback_wa_instance = WhatsAppInstance.objects.filter(
                                instance_name=instance_name,
                                tenant=tenant,
                                is_active=True,
                                status='active'
                            ).first()
                            
                            if fallback_wa_instance:
                                instance_name_for_media = fallback_wa_instance.instance_name
                                api_key_for_media = fallback_wa_instance.api_key
                                evolution_api_url_for_media = fallback_wa_instance.api_url
                                
                                # Se não tem api_url/api_key próprios, buscar EvolutionConnection
                                if not evolution_api_url_for_media or not api_key_for_media:
                                    fallback_connection = EvolutionConnection.objects.filter(
                                        is_active=True
                                    ).first()
                                    if fallback_connection:
                                        evolution_api_url_for_media = evolution_api_url_for_media or fallback_connection.base_url
                                        api_key_for_media = api_key_for_media or fallback_connection.api_key
                                
                                logger.info(f"✅ [WEBHOOK] WhatsAppInstance encontrada via fallback:")
                                logger.info(f"   📌 Instance (UUID): {instance_name_for_media}")
                                logger.info(f"   📌 Friendly Name: {fallback_wa_instance.friendly_name}")
                                logger.info(f"   📌 API URL: {evolution_api_url_for_media}")
                            else:
                                # Último fallback: buscar EvolutionConnection
                                fallback_connection = EvolutionConnection.objects.filter(
                                    tenant=tenant,
                                    is_active=True
                                ).first()
                                
                                if fallback_connection:
                                    instance_name_for_media = instance_name
                                    api_key_for_media = fallback_connection.api_key
                                    evolution_api_url_for_media = fallback_connection.api_url or fallback_connection.base_url
                                    
                                    logger.info(f"✅ [WEBHOOK] EvolutionConnection encontrada via fallback:")
                                    logger.info(f"   📌 Instance: {instance_name_for_media}")
                                    logger.info(f"   📌 API URL: {evolution_api_url_for_media}")
                                    logger.info(f"   📌 Connection: {fallback_connection.name}")
                                else:
                                    logger.warning(f"⚠️ [WEBHOOK] Nenhuma conexão encontrada via fallback")
                                    logger.warning(f"   🔍 [WEBHOOK] Tentou buscar por: instance_name={instance_name}, tenant={tenant.name}")
                        except Exception as e:
                            logger.warning(f"⚠️ [WEBHOOK] Erro ao buscar conexão via fallback: {e}", exc_info=True)
                    
                    def enqueue_process():
                        logger.info(f"🔄 [WEBHOOK] Enfileirando processamento direto (S3) do anexo {attachment_id_str}...")
                        logger.info(f"   📌 tenant_id: {tenant_id_str}")
                        logger.info(f"   📌 message_id: {message_id_str}")
                        logger.info(f"   📌 media_url: {attachment_url[:100]}...")
                        logger.info(f"   📌 media_type: {incoming_media_type}")
                        
                        # ✅ MELHORIA: Passar message_key completo para getBase64FromMediaMessage
                        # O endpoint pode precisar do key completo (remoteJid, fromMe, id)
                        # ✅ IMPORTANTE: Usar 'key' já extraído acima (linha 162) para garantir consistência
                        message_key_data = None
                        try:
                            # ✅ CORREÇÃO: Usar 'key' já extraído acima (linha 162) ao invés de extrair novamente
                            # Isso garante que estamos usando o mesmo objeto que foi usado para message_id
                            if key and key.get('id'):
                                message_key_data = {
                                    'remoteJid': key.get('remoteJid'),
                                    'fromMe': key.get('fromMe', False),
                                    'id': key.get('id')
                                }
                                logger.info(f"✅ [WEBHOOK] message_key extraído com sucesso!")
                                logger.info(f"   📌 message_key.id: {message_key_data.get('id')}")
                                logger.info(f"   📌 message_key.remoteJid: {message_key_data.get('remoteJid')}")
                                logger.info(f"   📌 message_key.fromMe: {message_key_data.get('fromMe')}")
                            else:
                                logger.warning(f"⚠️ [WEBHOOK] key não disponível ou sem id!")
                                logger.warning(f"   📌 key disponível: {key is not None}")
                                if key:
                                    logger.warning(f"   📌 key.id: {key.get('id')}")
                        except Exception as e:
                            logger.error(f"❌ [WEBHOOK] Erro ao extrair message_key: {e}", exc_info=True)
                        
                        try:
                            from apps.chat.tasks import process_incoming_media
                            process_incoming_media.delay(
                                tenant_id=tenant_id_str,
                                message_id=message_id_str,
                                media_url=attachment_url,
                                media_type=incoming_media_type,
                                instance_name=instance_name_for_media,
                                api_key=api_key_for_media,
                                evolution_api_url=evolution_api_url_for_media,
                                message_key=message_key_data,
                                mime_type=mime_type
                            )
                            logger.info(f"✅ [WEBHOOK] Processamento enfileirado com sucesso na fila chat_process_incoming_media!")
                        except Exception as e:
                            logger.error(f"❌ [WEBHOOK] ERRO ao enfileirar processamento: {e}", exc_info=True)
                            raise  # ✅ Re-raise para não silenciar erro
                    
                    transaction.on_commit(enqueue_process)
                
                logger.info(f"📎 [WEBHOOK] Anexo {filename} preparado para processamento direto (S3+cache)")
            
            # ✅ FIX CRÍTICO: Broadcast via WebSocket (mensagem específica)
            # IMPORTANTE: Enviar para o grupo da conversa E para o grupo do tenant
            logger.info(f"📡 [WEBHOOK] Enviando mensagem para WebSocket...")
            broadcast_message_to_websocket(message, conversation)
            
            # ✅ FIX: Também enviar para o grupo do tenant para atualizar lista de conversas
            try:
                from apps.chat.utils.serialization import serialize_message_for_ws
                from apps.chat.utils.websocket import broadcast_conversation_updated
                from django.db import transaction
                
                # ✅ CORREÇÃO CRÍTICA: Garantir que broadcast acontece após commit da mensagem
                # Passar message.id para garantir que a mensagem seja incluída no last_message
                def do_broadcast():
                    try:
                        # ✅ FIX CRÍTICO: Usar broadcast_conversation_updated que já faz prefetch de last_message
                        # Passar message_id para garantir que a mensagem recém-criada seja incluída
                        broadcast_conversation_updated(conversation, message_id=str(message.id))
                    except Exception as e:
                        logger.error(f"❌ [WEBSOCKET] Erro no broadcast após commit: {e}", exc_info=True)
                
                # ✅ CORREÇÃO CRÍTICA: Executar broadcast após commit da transação
                # Isso garante que a mensagem está disponível no banco quando buscamos last_message
                # Se não estamos em uma transação ativa, executar imediatamente
                if transaction.get_connection().in_atomic_block:
                    transaction.on_commit(do_broadcast)
                else:
                    # Não estamos em transação, executar imediatamente
                    do_broadcast()
                
                # ✅ FIX: Também enviar message_received para adicionar mensagem na conversa ativa
                msg_data_serializable = serialize_message_for_ws(message)
                
                channel_layer = get_channel_layer()
                tenant_group = f"chat_tenant_{tenant.id}"
                
                # Broadcast message_received (para adicionar mensagem na conversa ativa)
                logger.info(f"📡 [WEBSOCKET] Enviando message_received para grupo do tenant: {tenant_group}")
                logger.info(f"   Message ID: {message.id}")
                logger.info(f"   Conversation ID: {conversation.id}")
                logger.info(f"   Message content (primeiros 50 chars): {message.content[:50] if message.content else 'N/A'}...")
                
                async_to_sync(channel_layer.group_send)(
                    tenant_group,
                    {
                        'type': 'message_received',
                        'message': msg_data_serializable,
                        'conversation_id': str(conversation.id)
                    }
                )
                
                logger.info(f"✅ [WEBSOCKET] message_received enviado para grupo do tenant: {tenant_group}")
            except Exception as e:
                logger.error(f"❌ [WEBSOCKET] Erro ao broadcast para tenant: {e}", exc_info=True)
            
            # 🔔 IMPORTANTE: Se for mensagem recebida (não enviada por nós)
            if not from_me:
                # ❌ REMOVIDO: Não marcar como lida automaticamente
                # O read receipt só deve ser enviado quando usuário REALMENTE abrir a conversa
                # Isso é feito via /mark_as_read/ quando frontend abre a conversa (após 2.5s)
                
                # 1. Notificar tenant sobre nova mensagem (toast)
                logger.info(f"📬 [WEBHOOK] Notificando tenant sobre nova mensagem...")
                try:
                    from apps.chat.api.serializers import ConversationSerializer
                    from django.db.models import Count, Q, Prefetch
                    from apps.chat.utils.serialization import convert_uuids_to_str
                    # ✅ Usar imports globais (linhas 12-13) ao invés de import local
                    # from asgiref.sync import async_to_sync  # ❌ REMOVIDO: causava UnboundLocalError
                    
                    # ✅ FIX CRÍTICO: Fazer prefetch de last_message antes de serializar
                    # Isso garante que last_message seja incluído na notificação
                    conversation_with_prefetch = Conversation.objects.annotate(
                        unread_count_annotated=Count(
                            'messages',
                            filter=Q(
                                messages__direction='incoming',
                                messages__status__in=['sent', 'delivered']
                            ),
                            distinct=True
                        )
                    ).prefetch_related(
                        Prefetch(
                            'messages',
                            queryset=Message.objects.select_related('sender', 'conversation')
                                .prefetch_related('attachments')
                                .order_by('-created_at')[:1],
                            to_attr='last_message_list'
                        )
                    ).get(id=conversation.id)
                    
                    # Transferir prefetch para o objeto original
                    conversation.last_message_list = conversation_with_prefetch.last_message_list
                    conversation.unread_count_annotated = conversation_with_prefetch.unread_count_annotated
                    
                    # Serializar com last_message incluído
                    conv_data = ConversationSerializer(conversation).data
                    conv_data_serializable = convert_uuids_to_str(conv_data)
                    
                    # Broadcast para todo o tenant (notificação de nova mensagem)
                    channel_layer = get_channel_layer()  # ✅ Usa import global (linha 12)
                    tenant_group = f"chat_tenant_{tenant.id}"
                    
                    # 📱 Para GRUPOS: Nome do grupo + quem enviou
                    if is_group:
                        group_name = conversation.group_metadata.get('group_name', 'Grupo WhatsApp') if conversation.group_metadata else 'Grupo WhatsApp'
                        # Pegar nome de quem enviou (sender_name já foi extraído no início)
                        sender_display = sender_name if sender_name else 'Alguém'
                        notification_text = f"📱 {group_name}\n{sender_display} enviou uma mensagem"
                    else:
                        notification_text = content[:100]  # Primeiros 100 caracteres para contatos individuais
                    
                    async_to_sync(channel_layer.group_send)(  # ✅ Usa import global (linha 13)
                        tenant_group,
                        {
                            'type': 'new_message_notification',
                            'conversation': conv_data_serializable,
                            'message': {
                                'content': notification_text,
                                'created_at': message.created_at.isoformat(),
                                'is_group': is_group
                            }
                        }
                    )
                    
                    logger.info(f"📡 [WEBSOCKET] Notificação de nova mensagem broadcast para tenant {tenant.name}")
                except Exception as e:
                    logger.error(f"❌ [WEBSOCKET] Error broadcasting notification: {e}", exc_info=True)
        
        else:
            logger.info(f"ℹ️ [WEBHOOK] Mensagem já existe no banco: {message_id}")
    
    except Exception as e:
        logger.error(f"❌ [WEBHOOK] Erro ao processar messages.upsert: {e}", exc_info=True)


def handle_message_update(data, tenant):
    """
    Processa evento de atualização de status (messages.update).
    Atualiza status: delivered, read
    """
    logger.info(f"🔄 [WEBHOOK UPDATE] Iniciando processamento...")
    
    try:
        # 🔧 Evolution API pode enviar 'data' como LISTA ou DICT
        raw_data = data.get('data', {})
        
        # Se for lista, pegar o primeiro item
        if isinstance(raw_data, list):
            if len(raw_data) == 0:
                logger.warning(f"⚠️ [WEBHOOK UPDATE] data está vazio")
                return
            message_data = raw_data[0]
            logger.info(f"📋 [WEBHOOK UPDATE] data é LISTA, usando primeiro item")
        else:
            message_data = raw_data
            logger.info(f"📋 [WEBHOOK UPDATE] data é DICT")
        
        # Estrutura pode variar: key.id ou messageId direto
        # IMPORTANTE: Usar keyId (ID real) ao invés de messageId (ID interno Evolution)
        key = message_data.get('key', {}) if isinstance(message_data, dict) else {}
        key_id = message_data.get('keyId') if isinstance(message_data, dict) else None
        message_id_evo = message_data.get('messageId') if isinstance(message_data, dict) else None
        message_id = key.get('id') if isinstance(key, dict) else None
        
        if not message_id:
            message_id = key_id or message_id_evo
        
        # Status: delivered, read
        update = message_data.get('update', {})
        status_value = update.get('status') or message_data.get('status', '').upper()
        
        logger.info(f"🔍 [WEBHOOK UPDATE] Buscando mensagem...")
        logger.info(f"   key.id: {key.get('id')}")
        logger.info(f"   keyId: {key_id}")
        logger.info(f"   messageId (evo): {message_id_evo}")
        logger.info(f"   Status recebido: {status_value}")
        
        if not message_id or not status_value:
            logger.warning(
                "⚠️ [WEBHOOK UPDATE] Payload sem message_id/status. Dados (mascados): %s",
                mask_sensitive_data(message_data)
            )
            return
        
        # Busca mensagem - tentar com keyId primeiro
        # ✅ FIX CRÍTICO: Adicionar retry para aguardar message_id ser salvo (race condition)
        message = None
        max_retries = 5
        retry_delay = 0.2  # 200ms entre tentativas
        
        for attempt in range(max_retries):
            # Tentar com keyId
            if key_id:
                try:
                    message = Message.objects.select_related('conversation').get(message_id=key_id)
                    logger.info("✅ [WEBHOOK UPDATE] Mensagem encontrada via keyId (tentativa %s)!", attempt + 1)
                    break
                except Message.DoesNotExist:
                    pass

            # Se não encontrou, tentar com key.id
            if not message and key.get('id'):
                try:
                    message = Message.objects.select_related('conversation').get(message_id=key.get('id'))
                    logger.info("✅ [WEBHOOK UPDATE] Mensagem encontrada via key.id (tentativa %s)!", attempt + 1)
                    break
                except Message.DoesNotExist:
                    pass

            # Se não encontrou, tentar com messageId do Evolution
            if not message and message_id_evo:
                try:
                    message = Message.objects.select_related('conversation').get(message_id=message_id_evo)
                    logger.info("✅ [WEBHOOK UPDATE] Mensagem encontrada via messageId (tentativa %s)!", attempt + 1)
                    break
                except Message.DoesNotExist:
                    pass

            # Se não encontrou e ainda tem tentativas, aguardar um pouco
            if not message and attempt < max_retries - 1:
                import time
                time.sleep(retry_delay)
                logger.debug("⏳ [WEBHOOK UPDATE] Aguardando message_id ser salvo (tentativa %s/%s)...", attempt + 1, max_retries)
        
        if not message:
            logger.warning(f"⚠️ [WEBHOOK UPDATE] Mensagem não encontrada no banco após {max_retries} tentativas!")
            logger.warning(
                "   Tentou: keyId=%s, key.id=%s, messageId=%s",
                _mask_digits(key_id) if isinstance(key_id, str) else key_id,
                _mask_digits(key.get('id')) if isinstance(key.get('id'), str) else key.get('id'),
                _mask_digits(message_id_evo) if isinstance(message_id_evo, str) else message_id_evo
            )
            logger.warning(f"   ⚠️ Possível race condition: webhook chegou antes do message_id ser salvo")
            return
        
        logger.info(f"✅ [WEBHOOK UPDATE] Mensagem encontrada!")
        logger.info(f"   ID no banco: {message.id}")
        logger.info(f"   Conversa: {message.conversation.contact_phone}")
        logger.info(f"   Status atual: {message.status}")
        
        # Mapeia status (aceita múltiplos formatos)
        status_map = {
            'PENDING': 'pending',
            'SERVER_ACK': 'sent',
            'DELIVERY_ACK': 'delivered',
            'READ': 'seen',
            # Formatos alternativos
            'delivered': 'delivered',
            'delivery_ack': 'delivered',
            'read': 'seen',
            'read_ack': 'seen',
            'sent': 'sent'
        }
        
        new_status = status_map.get(status_value.lower()) or status_map.get(status_value)
        
        if not new_status:
            logger.warning(f"⚠️ [WEBHOOK UPDATE] Status não mapeado: {status_value}")
            return
        
        if message.status != new_status:
            old_status = message.status
            
            # ✅ CORREÇÃO CRÍTICA: Ignorar status READ para mensagens INCOMING
            # Mensagens incoming são marcadas como lidas pelo USUÁRIO via mark_as_read(),
            # não pelo WhatsApp via webhook. WhatsApp envia READ apenas para mensagens
            # OUTGOING (quando o destinatário lê nossa mensagem).
            if new_status == 'seen' and message.direction == 'incoming':
                logger.info(f"⏸️ [WEBHOOK UPDATE] Ignorando status READ para mensagem INCOMING")
                logger.info(f"   Direction: {message.direction}")
                logger.info(f"   Mensagens incoming são marcadas como lidas pelo USUÁRIO")
                logger.info(f"   WhatsApp não controla status de leitura de mensagens que ELE enviou para NÓS")
                return
            
            message.status = new_status
            message.evolution_status = status_value
            message.save(update_fields=['status', 'evolution_status'])
            
            logger.info(f"✅ [WEBHOOK UPDATE] Status atualizado!")
            logger.info(f"   Direction: {message.direction}")
            logger.info(f"   {old_status} → {new_status}")
            logger.info(f"   Evolution status: {status_value}")
            
            # Broadcast via WebSocket
            logger.info(f"📡 [WEBHOOK UPDATE] Enviando atualização via WebSocket...")
            broadcast_status_update(message)
        else:
            logger.info(f"ℹ️ [WEBHOOK UPDATE] Status já está como '{new_status}', sem alteração")
    
    except Exception as e:
        logger.error(f"❌ [WEBHOOK] Erro ao processar messages.update: {e}", exc_info=True)


def broadcast_message_to_websocket(message, conversation):
    """Envia nova mensagem via WebSocket para o grupo da conversa."""
    try:
        channel_layer = get_channel_layer()
        room_group_name = f"chat_tenant_{conversation.tenant_id}_conversation_{conversation.id}"
        
        logger.info(f"📡 [WEBSOCKET] Preparando broadcast...")
        logger.info(f"   Room: {room_group_name}")
        logger.info(f"   Direction: {message.direction}")
        
        # ✅ Usar utilitário centralizado para serialização
        from apps.chat.utils.serialization import serialize_message_for_ws
        message_data_serializable = serialize_message_for_ws(message)
        
        logger.info(f"📡 [WEBSOCKET] Enviando message_received para room: {room_group_name}")
        logger.info(f"   Message ID: {message.id}")
        logger.info(f"   Conversation ID: {conversation.id}")
        logger.info(f"   Message content (primeiros 50 chars): {message.content[:50] if message.content else 'N/A'}...")
        
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'message_received',
                'message': message_data_serializable
            }
        )
        
        # ✅ NOVO: Também enviar para grupo do tenant (para garantir que chegue)
        tenant_group = f"chat_tenant_{conversation.tenant_id}"
        logger.info(f"📡 [WEBSOCKET] Enviando message_received para grupo do tenant: {tenant_group}")
        async_to_sync(channel_layer.group_send)(
            tenant_group,
            {
                'type': 'message_received',
                'message': message_data_serializable,
                'conversation_id': str(conversation.id)
            }
        )
        
        logger.info(f"✅ [WEBSOCKET] Mensagem broadcast com sucesso para room E tenant!")
        logger.info(f"   Message ID: {message.id} | Content: {message.content[:30]}...")
    
    except Exception as e:
        logger.error(f"❌ [WEBSOCKET] Error broadcasting message: {e}", exc_info=True)


def broadcast_status_update(message):
    """
    Envia atualização de status via WebSocket.
    
    ✅ REFATORADO: Usa função centralizada de utils/websocket.py
    """
    from apps.chat.utils.websocket import broadcast_message_status_update
    broadcast_message_status_update(message)


def send_delivery_receipt(conversation: Conversation, message: Message):
    """
    Envia ACK de ENTREGA (delivered) para Evolution API.
    Isso fará com que o remetente veja ✓✓ cinza no WhatsApp dele.
    """
    try:
        # Buscar instância WhatsApp ativa do tenant
        wa_instance = WhatsAppInstance.objects.filter(
            tenant=conversation.tenant,
            is_active=True,
            status='active'
        ).first()
        
        if not wa_instance:
            logger.warning(f"⚠️ [DELIVERY ACK] Nenhuma instância WhatsApp ativa para tenant {conversation.tenant.name}")
            return
        
        # Buscar servidor Evolution
        evolution_server = EvolutionConnection.objects.filter(is_active=True).first()
        if not evolution_server:
            logger.warning(f"⚠️ [DELIVERY ACK] Servidor Evolution não configurado")
            return
        
        # Endpoint da Evolution API para enviar ACK de entrega
        base_url = (wa_instance.api_url or evolution_server.base_url).rstrip('/')
        api_key = wa_instance.api_key or evolution_server.api_key
        instance_name = wa_instance.instance_name
        
        url = f"{base_url}/chat/markMessageAsRead/{instance_name}"
        
        # Payload para ACK de entrega (só marca como delivered, não como read)
        # Na Evolution API, geralmente o endpoint é o mesmo, mas há diferença no payload
        payload = {
            "readMessages": [
                {
                    "remoteJid": f"{conversation.contact_phone.replace('+', '')}@s.whatsapp.net",
                    "id": message.message_id,
                    "fromMe": False
                }
            ]
        }
        
        headers = {
            "Content-Type": "application/json",
            "apikey": api_key
        }
        
        logger.info(f"📬 [DELIVERY ACK] Enviando ACK de entrega...")
        logger.info(f"   URL: {url}")
        logger.info(f"   Message ID: {message.message_id}")
        logger.info(f"   Contact: {conversation.contact_phone}")
        
        # Enviar request de forma síncrona
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=payload, headers=headers)
            
            if response.status_code == 200 or response.status_code == 201:
                logger.info(f"✅ [DELIVERY ACK] ACK de entrega enviado!")
                logger.info(f"   Response: {response.text[:200]}")
                
                # Atualizar status local da mensagem
                message.status = 'delivered'
                message.save(update_fields=['status'])
            else:
                logger.warning(f"⚠️ [DELIVERY ACK] Resposta não esperada: {response.status_code}")
                logger.warning(f"   Response: {response.text[:300]}")
    
    except Exception as e:
        logger.error(f"❌ [DELIVERY ACK] Erro ao enviar ACK de entrega: {e}", exc_info=True)


def handle_message_delete(data, tenant, connection=None, wa_instance=None):
    """
    Processa mensagem apagada recebida do WhatsApp.
    
    Evolution API envia:
    {
        "event": "messages.delete",
        "instance": "instance_name",
        "data": {
            "key": {
                "remoteJid": "5517999999999@s.whatsapp.net",
                "fromMe": false,
                "id": "message_id_evolution"
            }
        }
    }
    """
    from django.utils import timezone
    
    try:
        # ✅ DEBUG: Log completo do webhook para verificar formato na 2.3.6
        logger.info(f"🗑️ [WEBHOOK DELETE] ====== INICIANDO PROCESSAMENTO ======")
        logger.info(f"🗑️ [WEBHOOK DELETE] Data completo recebido: {data}")
        logger.info(f"🗑️ [WEBHOOK DELETE] Data keys: {list(data.keys()) if isinstance(data, dict) else 'not dict'}")
        
        delete_data = data.get('data', {})
        logger.info(f"🗑️ [WEBHOOK DELETE] delete_data: {delete_data}")
        logger.info(f"🗑️ [WEBHOOK DELETE] delete_data keys: {list(delete_data.keys()) if isinstance(delete_data, dict) else 'not dict'}")
        
        # ✅ CORREÇÃO: Verificar se data é uma lista (pode ser formato diferente na 2.3.6)
        if isinstance(delete_data, list) and len(delete_data) > 0:
            logger.info(f"🗑️ [WEBHOOK DELETE] Data é lista, usando primeiro item")
            delete_data = delete_data[0]
        
        key = delete_data.get('key', {})
        logger.info(f"🗑️ [WEBHOOK DELETE] key: {key}")
        logger.info(f"🗑️ [WEBHOOK DELETE] key keys: {list(key.keys()) if isinstance(key, dict) else 'not dict'}")
        
        # ✅ CORREÇÃO: Tentar múltiplos formatos para message_id (pode estar em lugares diferentes)
        # Evolution API 2.3.6 pode usar keyId ou id dentro de key
        message_id_evolution = (
            key.get('id') or 
            key.get('messageId') or 
            key.get('message_id') or
            key.get('keyId') or
            delete_data.get('id') or 
            delete_data.get('messageId') or 
            delete_data.get('message_id') or
            delete_data.get('keyId') or
            data.get('keyId')  # Pode estar no root do webhook também
        )
        
        remote_jid = key.get('remoteJid') or delete_data.get('remoteJid')
        from_me = key.get('fromMe', False) if isinstance(key, dict) else delete_data.get('fromMe', False)
        key_id = key.get('keyId') or delete_data.get('keyId')  # keyId pode estar separado
        
        logger.info(f"🗑️ [WEBHOOK DELETE] Processando mensagem apagada:")
        logger.info(f"   Message ID Evolution: {_mask_digits(message_id_evolution) if message_id_evolution else 'N/A'}")
        logger.info(f"   Key ID: {_mask_digits(key_id) if key_id else 'N/A'}")
        logger.info(f"   Remote JID: {_mask_remote_jid(remote_jid) if remote_jid else 'N/A'}")
        logger.info(f"   From Me: {from_me}")
        
        if not message_id_evolution and not key_id:
            logger.warning("⚠️ [WEBHOOK DELETE] message_id nem keyId fornecido após todas as tentativas")
            logger.warning(f"   Estrutura completa do webhook: {mask_sensitive_data(data)}")
            return
        
        # Usar keyId como fallback se message_id não foi encontrado
        if not message_id_evolution and key_id:
            message_id_evolution = key_id
            logger.info(f"🗑️ [WEBHOOK DELETE] Usando keyId como message_id: {_mask_digits(key_id)}")
        
        # Buscar mensagem no banco por message_id
        message = None
        if message_id_evolution:
            message = Message.objects.filter(
                message_id=message_id_evolution,
                conversation__tenant=tenant
            ).select_related('conversation', 'conversation__tenant').first()
            
            if message:
                logger.info(f"✅ [WEBHOOK DELETE] Mensagem encontrada por message_id: {message.id}")
        
        # Se não encontrou por message_id, tentar por keyId (se diferente)
        if not message and key_id and key_id != message_id_evolution:
            message = Message.objects.filter(
                message_id=key_id,
                conversation__tenant=tenant
            ).select_related('conversation', 'conversation__tenant').first()
            
            if message:
                logger.info(f"✅ [WEBHOOK DELETE] Mensagem encontrada por keyId: {message.id}")
        
        # Se ainda não encontrou, tentar buscar por remoteJid e timestamp (mensagens recentes)
        if not message and remote_jid:
            logger.warning(f"⚠️ [WEBHOOK DELETE] Mensagem não encontrada por ID: {_mask_digits(message_id_evolution or key_id or 'N/A')}")
            logger.warning(f"   Tentando buscar por remoteJid e timestamp recente...")
            
            # Extrair telefone do remoteJid
            phone_raw = remote_jid.split('@')[0] if '@' in remote_jid else remote_jid
            from apps.notifications.services import normalize_phone
            normalized_phone = normalize_phone(phone_raw)
            
            if normalized_phone:
                # Buscar conversa
                conversation = Conversation.objects.filter(
                    tenant=tenant,
                    contact_phone__icontains=normalized_phone.replace('+', '').replace('-', '').replace(' ', '')
                ).first()
                
                if conversation:
                    logger.info(f"🗑️ [WEBHOOK DELETE] Conversa encontrada: {conversation.id}")
                    
                    # Tentar buscar mensagem na conversa (últimas 100 mensagens recentes, ordenadas por data)
                    from datetime import timedelta
                    
                    # Buscar nas últimas 24 horas (mensagens recentes)
                    recent_cutoff = timezone.now() - timedelta(hours=24)
                    messages = Message.objects.filter(
                        conversation=conversation,
                        created_at__gte=recent_cutoff,
                        is_deleted=False  # Apenas mensagens ainda não apagadas
                    ).order_by('-created_at')[:100]
                    
                    logger.info(f"🗑️ [WEBHOOK DELETE] Buscando em {messages.count()} mensagens recentes da conversa...")
                    
                    # Se temos keyId, tentar buscar mensagens que podem ter esse ID em metadata ou outros campos
                    if key_id:
                        # Tentar encontrar por similaridade de ID (pode estar em formato diferente)
                        for msg in messages:
                            # Verificar se message_id contém parte do keyId ou vice-versa
                            if msg.message_id:
                                if key_id in msg.message_id or msg.message_id in key_id:
                                    message = msg
                                    logger.info(f"✅ [WEBHOOK DELETE] Mensagem encontrada por similaridade de ID: {message.id}")
                                    break
                    
                    # Se ainda não encontrou e temos remoteJid, pode ser que message_id não foi salvo corretamente
                    # Neste caso, tentar buscar a mensagem mais recente que ainda não foi apagada
                    if not message and messages.exists():
                        logger.warning(f"⚠️ [WEBHOOK DELETE] Não encontrada por ID, mas temos conversa e mensagens recentes")
                        logger.warning(f"   Isso pode indicar que message_id não foi salvo corretamente na mensagem original")
        
        if not message:
            logger.error(f"❌ [WEBHOOK DELETE] Mensagem não encontrada após todas as tentativas")
            logger.error(f"   Message ID: {_mask_digits(message_id_evolution) if message_id_evolution else 'N/A'}")
            logger.error(f"   Key ID: {_mask_digits(key_id) if key_id else 'N/A'}")
            logger.error(f"   Remote JID: {_mask_remote_jid(remote_jid) if remote_jid else 'N/A'}")
            logger.error(f"   Webhook completo (mascado): {mask_sensitive_data(data)}")
            return
        
        # Marcar como apagada
        message.is_deleted = True
        message.deleted_at = timezone.now()
        message.save(update_fields=['is_deleted', 'deleted_at'])
        
        logger.info(f"✅ [WEBHOOK DELETE] Mensagem marcada como apagada: {message.id}")
        logger.info(f"   Conversa: {message.conversation.contact_phone}")
        logger.info(f"   Direction: {message.direction}")
        
        # Broadcast via WebSocket
        from apps.chat.utils.websocket import broadcast_message_deleted
        broadcast_message_deleted(message)
        
    except Exception as e:
        logger.error(f"❌ [WEBHOOK DELETE] Erro ao processar mensagem apagada: {e}", exc_info=True)


def send_read_receipt(conversation: Conversation, message: Message, max_retries: int = 3):
    """
    Envia confirmação de LEITURA (read) para Evolution API.
    Isso fará com que o remetente veja ✓✓ azul no WhatsApp dele.
    
    Args:
        conversation: Conversa da mensagem
        message: Mensagem a ser marcada como lida
        max_retries: Número máximo de tentativas (com backoff exponencial)
    
    Returns:
        bool: True se enviado com sucesso, False caso contrário
    """
    import time
    
    try:
        # Buscar instância WhatsApp ativa do tenant
        wa_instance = WhatsAppInstance.objects.filter(
            tenant=conversation.tenant,
            is_active=True,
            status='active'
        ).first()
        
        if not wa_instance:
            logger.warning(f"⚠️ [READ RECEIPT] Nenhuma instância WhatsApp ativa para tenant {conversation.tenant.name}")
            return False
        
        # ✅ CORREÇÃO CRÍTICA: Verificar connection_state antes de enviar
        # Se a instância está "connecting", a Evolution API retornará erro 500
        if wa_instance.connection_state not in ('open', 'connected'):
            logger.warning(
                f"⚠️ [READ RECEIPT] Instância não conectada (state: {wa_instance.connection_state}). "
                f"Pulando read receipt para mensagem {message.id}"
            )
            return False
        
        # Buscar servidor Evolution
        evolution_server = EvolutionConnection.objects.filter(is_active=True).first()
        if not evolution_server:
            logger.warning(f"⚠️ [READ RECEIPT] Servidor Evolution não configurado")
            return False
        
        # Endpoint da Evolution API para marcar como lida
        # Formato: POST /chat/markMessageAsRead/{instance}
        base_url = (wa_instance.api_url or evolution_server.base_url).rstrip('/')
        api_key = wa_instance.api_key or evolution_server.api_key
        instance_name = wa_instance.instance_name
        
        url = f"{base_url}/chat/markMessageAsRead/{instance_name}"
        
        # Payload para marcar mensagem como lida
        payload = {
            "readMessages": [
                {
                    "remoteJid": f"{conversation.contact_phone.replace('+', '')}@s.whatsapp.net",
                    "id": message.message_id,
                    "fromMe": False
                }
            ]
        }
        
        headers = {
            "Content-Type": "application/json",
            "apikey": api_key
        }
        
        logger.info(f"📖 [READ RECEIPT] Enviando confirmação de leitura...")
        logger.info(f"   URL: {url}")
        logger.info(f"   Message ID: {message.message_id}")
        logger.info(f"   Contact: {conversation.contact_phone}")
        logger.info(f"   Connection State: {wa_instance.connection_state}")
        
        # ✅ CORREÇÃO: Retry com backoff exponencial para erros temporários
        last_error = None
        for attempt in range(max_retries):
            try:
                with httpx.Client(timeout=5.0) as client:
                    response = client.post(url, json=payload, headers=headers)

                if response.status_code in (200, 201):
                    logger.info("✅ [READ RECEIPT] Confirmação enviada com sucesso!")
                    logger.info("   Response: %s", response.text[:200])
                    return True

                if response.status_code == 500:
                    response_text = response.text.lower()
                    if 'connection closed' in response_text or '1006' in response_text:
                        logger.warning(
                            "⚠️ [READ RECEIPT] Instância desconectada (Connection Closed/1006). "
                            "Pulando read receipt. Tentativa %s/%s",
                            attempt + 1,
                            max_retries
                        )
                        return False

                    last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt  # 1s, 2s, 4s
                        logger.warning(
                            "⚠️ [READ RECEIPT] Erro temporário (tentativa %s/%s). Retry em %ss...",
                            attempt + 1,
                            max_retries,
                            wait_time
                        )
                        time.sleep(wait_time)
                        continue
                else:
                    logger.warning("⚠️ [READ RECEIPT] Resposta não esperada: %s", response.status_code)
                    logger.warning("   Response: %s", response.text[:300])
                    return False

            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
                last_error = str(e)
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(
                        "⚠️ [READ RECEIPT] Erro de conexão (tentativa %s/%s): %s. Retry em %ss...",
                        attempt + 1,
                        max_retries,
                        e,
                        wait_time
                    )
                    time.sleep(wait_time)
                    continue

                logger.error("❌ [READ RECEIPT] Erro de conexão após %s tentativas: %s", max_retries, e)
                return False
        
        # Se chegou aqui, todas as tentativas falharam
        logger.error("❌ [READ RECEIPT] Falha após %s tentativas. Último erro: %s", max_retries, last_error)
        return False
    
    except Exception as e:
        logger.error(f"❌ [READ RECEIPT] Erro inesperado ao enviar confirmação de leitura: {e}", exc_info=True)
        return False

