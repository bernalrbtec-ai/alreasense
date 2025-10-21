"""
Gerenciamento de storage híbrido para anexos do chat.

- Cache local: Railway Volume (/mnt/storage/whatsapp/)
- Storage definitivo: MinIO (S3-compatible)
"""
import os
import logging
import httpx
from pathlib import Path
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config

logger = logging.getLogger(__name__)

# Configurações de storage
LOCAL_STORAGE_PATH = getattr(settings, 'CHAT_LOCAL_STORAGE_PATH', '/mnt/storage/whatsapp/')
S3_BUCKET = getattr(settings, 'S3_BUCKET', 'flow-attachments')
S3_ENDPOINT = getattr(settings, 'S3_ENDPOINT_URL', 'https://bucket-production-8fb1.up.railway.app')
S3_ACCESS_KEY = getattr(settings, 'S3_ACCESS_KEY', 'u2gh8aomMEdqPFW1JIlTn7VcCUhRCobL')
S3_SECRET_KEY = getattr(settings, 'S3_SECRET_KEY', 'zSMwLiOH1fURqSNX8zMtMYKBjrScDQYynCW2TbI2UuXM7Bti')
S3_REGION = getattr(settings, 'S3_REGION', 'us-east-1')

# Cliente S3
s3_client = boto3.client(
    's3',
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
    region_name=S3_REGION,
    config=Config(
        signature_version='s3v4',
        s3={'addressing_style': 'path'}  # Force path-style URLs for MinIO
    )
)


def get_local_path(tenant_slug: str, filename: str) -> Path:
    """
    Retorna caminho local para salvar arquivo.
    Estrutura: /mnt/storage/whatsapp/{tenant_slug}/{YYYY-MM-DD}/filename
    """
    today = datetime.now().strftime('%Y-%m-%d')
    path = Path(LOCAL_STORAGE_PATH) / tenant_slug / today
    path.mkdir(parents=True, exist_ok=True)
    return path / filename


def get_s3_key(tenant_slug: str, filename: str) -> str:
    """
    Retorna S3 key para arquivo.
    Estrutura: {tenant_slug}/{YYYY-MM-DD}/filename
    """
    today = datetime.now().strftime('%Y-%m-%d')
    return f"{tenant_slug}/{today}/{filename}"


async def download_and_save_attachment(attachment, evolution_url: str) -> bool:
    """
    Baixa anexo da Evolution API e salva localmente.
    
    Args:
        attachment: Instância de MessageAttachment
        evolution_url: URL completa do arquivo na Evolution
    
    Returns:
        True se sucesso, False se falhou
    """
    try:
        # Usar tenant.id ao invés de slug
        tenant_id = str(attachment.tenant.id)
        filename = f"{attachment.id}_{attachment.original_filename}"
        local_path = get_local_path(tenant_id, filename)
        
        # Download do arquivo
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(evolution_url)
            response.raise_for_status()
            
            # Salva localmente
            with open(local_path, 'wb') as f:
                f.write(response.content)
        
        # Atualiza attachment
        from asgiref.sync import sync_to_async
        attachment.file_path = str(local_path)
        attachment.file_url = f"/api/chat/attachments/{attachment.id}/download/"
        attachment.storage_type = 'local'
        attachment.size_bytes = local_path.stat().st_size
        attachment.expires_at = timezone.now() + timedelta(days=7)
        await sync_to_async(attachment.save)()
        
        logger.info(f"✅ [STORAGE] Arquivo salvo localmente: {local_path}")
        return True
    
    except Exception as e:
        logger.error(f"❌ [STORAGE] Erro ao baixar anexo: {e}", exc_info=True)
        return False


async def migrate_to_minio(attachment) -> bool:
    """
    Migra anexo do storage local para MinIO.
    
    Args:
        attachment: Instância de MessageAttachment
    
    Returns:
        True se sucesso, False se falhou
    """
    try:
        if attachment.storage_type == 's3':
            logger.info(f"ℹ️ [STORAGE] Anexo {attachment.id} já está no S3")
            return True
        
        local_path = Path(attachment.file_path)
        
        if not local_path.exists():
            logger.error(f"❌ [STORAGE] Arquivo local não encontrado: {local_path}")
            return False
        
        # Upload para MinIO - acessar tenant de forma assíncrona
        from asgiref.sync import sync_to_async
        tenant = await sync_to_async(lambda: attachment.tenant)()
        tenant_id = str(tenant.id)
        s3_key = get_s3_key(tenant_id, local_path.name)
        
        with open(local_path, 'rb') as f:
            s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=s3_key,
                Body=f,
                ContentType=attachment.mime_type
            )
        
        # Gera presigned URL (válida por 7 dias)
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': S3_BUCKET, 'Key': s3_key},
            ExpiresIn=604800  # 7 dias
        )
        
        # Atualiza attachment
        attachment.file_path = s3_key
        attachment.file_url = presigned_url
        attachment.storage_type = 's3'
        await sync_to_async(attachment.save)()
        
        # Remove arquivo local
        local_path.unlink()
        
        logger.info(f"✅ [STORAGE] Anexo migrado para S3: {s3_key}")
        return True
    
    except ClientError as e:
        logger.error(f"❌ [STORAGE] Erro ao fazer upload para S3: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"❌ [STORAGE] Erro ao migrar anexo: {e}", exc_info=True)
        return False


def generate_presigned_url(s3_key: str, expires_in: int = 604800) -> str:
    """
    Gera presigned URL para arquivo no S3.
    
    Args:
        s3_key: Chave do arquivo no S3
        expires_in: Tempo de expiração em segundos (padrão: 7 dias)
    
    Returns:
        URL presigned
    """
    try:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': S3_BUCKET, 'Key': s3_key},
            ExpiresIn=expires_in
        )
        return url
    except ClientError as e:
        logger.error(f"❌ [STORAGE] Erro ao gerar presigned URL: {e}", exc_info=True)
        return ""


def save_upload_temporarily(file, tenant):
    """
    Salva arquivo de upload temporariamente e retorna URL.
    
    Args:
        file: Arquivo do request.FILES
        tenant: Instância do Tenant
    
    Returns:
        URL relativa do arquivo
    """
    import uuid
    from django.core.files.storage import default_storage
    
    try:
        # Gerar nome único
        ext = file.name.split('.')[-1] if '.' in file.name else 'bin'
        unique_name = f"{uuid.uuid4()}.{ext}"
        
        # Caminho local
        tenant_id = str(tenant.id)
        local_path = get_local_path(tenant_id, unique_name)
        
        # Salvar arquivo
        with open(local_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)
        
        # Retornar URL relativa
        file_url = f"/api/chat/attachments/download/{tenant_id}/{unique_name}"
        
        logger.info(f"✅ [STORAGE] Upload salvo: {local_path}")
        return file_url
    
    except Exception as e:
        logger.error(f"❌ [STORAGE] Erro ao salvar upload: {e}", exc_info=True)
        raise


def cleanup_expired_local_files():
    """
    Remove arquivos locais expirados (>7 dias).
    Executar via cron ou management command.
    """
    from apps.chat.models import MessageAttachment
    
    try:
        # Busca anexos locais expirados
        expired = MessageAttachment.objects.filter(
            storage_type='local',
            expires_at__lt=timezone.now()
        )
        
        deleted_count = 0
        
        for attachment in expired:
            local_path = Path(attachment.file_path)
            
            if local_path.exists():
                local_path.unlink()
                deleted_count += 1
                logger.info(f"🗑️ [STORAGE] Arquivo local expirado removido: {local_path}")
            
            # Se não está no S3, marca para migração ou deleta o registro
            if attachment.storage_type != 's3':
                attachment.delete()
        
        logger.info(f"✅ [STORAGE] Limpeza concluída: {deleted_count} arquivos removidos")
        return deleted_count
    
    except Exception as e:
        logger.error(f"❌ [STORAGE] Erro na limpeza de arquivos: {e}", exc_info=True)
        return 0

