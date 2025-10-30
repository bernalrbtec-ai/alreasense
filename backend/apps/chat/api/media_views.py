"""
Views para servir mídia com cache inteligente.

Redis: 7 dias de cache
S3: 30 dias de retenção (lifecycle policy)
"""
import logging
from django.http import HttpResponse, Http404
from django.core.cache import cache
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from apps.chat.models import MessageAttachment
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# TTL do cache (Redis): definido por settings (padrão 30 dias)
from django.conf import settings
MEDIA_CACHE_TTL = int(getattr(settings, 'ATTACHMENTS_REDIS_TTL_DAYS', 30)) * 24 * 60 * 60


@api_view(['GET'])
@permission_classes([AllowAny])  # Público, mas hash é único e imprevisível
def serve_media(request, media_hash):
    """
    Serve mídia com cache Redis (TTL configurável; padrão 30 dias).
    
    Fluxo:
    1. Verifica cache Redis (7 dias)
    2. Se não tem, busca do S3
    3. Cacheia no Redis
    4. Retorna para Evolution API/Frontend
    
    Args:
        media_hash: Hash único de 12 caracteres
    
    Returns:
        HttpResponse com arquivo binário
        
    Raises:
        Http404: Se mídia não existe ou expirou (>30 dias no S3)
    """
    cache_key = f"media:{media_hash}"
    
    try:
        # 1. ✅ CACHE HIT: Verificar Redis primeiro
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.info(f"📦 [MEDIA CACHE] HIT - Servindo do Redis: {media_hash}")
            content_type = cached_data.get('content_type', 'application/octet-stream')
            binary_data = cached_data.get('data')
            
            return HttpResponse(
                binary_data,
                content_type=content_type,
                headers={
                    'X-Cache': 'HIT',
                    'Cache-Control': f'public, max-age={MEDIA_CACHE_TTL}',
                }
            )
        
        # 2. ❌ CACHE MISS: Buscar do banco de dados
        logger.info(f"💾 [MEDIA CACHE] MISS - Buscando do banco: {media_hash}")
        
        # Debug: listar alguns hashes recentes
        recent_hashes = MessageAttachment.objects.values_list('media_hash', flat=True).order_by('-created_at')[:10]
        logger.info(f"🔍 [DEBUG] Últimos 10 hashes no banco: {list(recent_hashes)}")
        
        try:
            attachment = MessageAttachment.objects.get(media_hash=media_hash)
            logger.info(f"✅ [MEDIA] Attachment encontrado: {attachment.id}")
        except MessageAttachment.DoesNotExist:
            logger.warning(f"⚠️ [MEDIA] Mídia não encontrada: {media_hash}")
            logger.warning(f"⚠️ [MEDIA] Total de attachments no banco: {MessageAttachment.objects.count()}")
            raise Http404("Mídia não encontrada")
        
        # 3. Baixar do S3
        logger.info(f"☁️ [MEDIA] Baixando do S3: {attachment.file_path}")
        
        try:
            binary_data = download_from_s3(attachment.file_path)
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            
            if error_code == 'NoSuchKey':
                logger.warning(f"⚠️ [MEDIA] Arquivo expirou do S3 (>30 dias): {media_hash}")
                raise Http404("Mídia expirada (removida após 30 dias)")
            else:
                logger.error(f"❌ [MEDIA] Erro S3: {e}")
                raise Http404("Erro ao baixar mídia")
        
        # 4. Cachear no Redis
        cache_data = {
            'data': binary_data,
            'content_type': attachment.mime_type,
        }
        cache.set(cache_key, cache_data, MEDIA_CACHE_TTL)
        logger.info(f"✅ [MEDIA CACHE] Cacheado por {MEDIA_CACHE_TTL} segundos: {media_hash}")
        
        # 5. Retornar
        return HttpResponse(
            binary_data,
            content_type=attachment.mime_type,
            headers={
                'X-Cache': 'MISS',
                'Cache-Control': f'public, max-age={MEDIA_CACHE_TTL}',
            }
        )
        
    except Http404:
        raise
    except Exception as e:
        logger.error(f"❌ [MEDIA] Erro inesperado: {e}", exc_info=True)
        raise Http404("Erro ao servir mídia")


def download_from_s3(s3_key):
    """
    Baixa arquivo do S3/MinIO.
    
    Args:
        s3_key: Chave do objeto no S3 (ex: alrea-media/chat/tenant/attachments/uuid.mp3)
    
    Returns:
        bytes: Conteúdo binário do arquivo
        
    Raises:
        ClientError: Se arquivo não existe ou erro S3
    """
    s3_client = boto3.client(
        's3',
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
        config=boto3.session.Config(signature_version='s3v4')
    )
    
    # Baixar objeto
    response = s3_client.get_object(
        Bucket=settings.S3_BUCKET,
        Key=s3_key
    )
    
    # Retornar conteúdo binário
    return response['Body'].read()



