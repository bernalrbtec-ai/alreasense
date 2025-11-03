"""
Utilitários para integração com MinIO/S3 (Railway).

Funções:
- upload_to_s3: Faz upload de arquivo para S3
- download_from_s3: Baixa arquivo do S3
- delete_from_s3: Remove arquivo do S3
- generate_presigned_url: Gera URL assinada para upload direto
- get_public_url: Retorna URL pública via proxy
"""
import logging
import hashlib
import mimetypes
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime, timedelta

import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
from django.conf import settings

logger = logging.getLogger(__name__)


class S3Manager:
    """Gerenciador de operações S3/MinIO"""
    
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
            config=Config(
                signature_version='s3v4',
                s3={'addressing_style': 'path'}  # Force path-style URLs for MinIO
            )
        )
        self.bucket = settings.S3_BUCKET
        self._bucket_checked = False  # Flag para evitar múltiplas verificações
    
    def ensure_bucket_exists(self) -> bool:
        """
        Garante que o bucket existe, criando se necessário.
        Só verifica uma vez por instância.
        
        Returns:
            True se bucket existe ou foi criado, False em caso de erro
        """
        if self._bucket_checked:
            return True
        
        try:
            # Verificar se bucket existe
            self.s3_client.head_bucket(Bucket=self.bucket)
            logger.info(f"✅ [S3] Bucket '{self.bucket}' já existe")
            self._bucket_checked = True
            return True
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            
            if error_code == '404':
                # Bucket não existe, tentar criar
                logger.warning(f"⚠️ [S3] Bucket '{self.bucket}' não existe, tentando criar...")
                
                try:
                    self.s3_client.create_bucket(Bucket=self.bucket)
                    logger.info(f"✅ [S3] Bucket '{self.bucket}' criado com sucesso")
                    
                    # Configurar CORS para permitir uploads do frontend
                    try:
                        cors_configuration = {
                            'CORSRules': [{
                                'AllowedHeaders': ['*'],
                                'AllowedMethods': ['GET', 'PUT', 'POST', 'DELETE'],
                                'AllowedOrigins': ['*'],
                                'ExposeHeaders': ['ETag'],
                                'MaxAgeSeconds': 3600
                            }]
                        }
                        self.s3_client.put_bucket_cors(
                            Bucket=self.bucket,
                            CORSConfiguration=cors_configuration
                        )
                        logger.info(f"✅ [S3] CORS configurado no bucket")
                    except Exception as cors_error:
                        logger.warning(f"⚠️ [S3] Erro ao configurar CORS (não crítico): {cors_error}")
                    
                    self._bucket_checked = True
                    return True
                    
                except ClientError as create_error:
                    logger.error(f"❌ [S3] Erro ao criar bucket: {create_error}")
                    return False
            else:
                logger.error(f"❌ [S3] Erro ao verificar bucket: {error_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ [S3] Erro inesperado ao verificar bucket: {e}")
            return False
    
    def upload_to_s3(
        self,
        file_data: bytes,
        file_path: str,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> Tuple[bool, str]:
        """
        Faz upload de arquivo para S3.
        
        Args:
            file_data: Dados binários do arquivo
            file_path: Caminho no S3 (ex: 'profile_pics/tenant_uuid/file.jpg')
            content_type: MIME type do arquivo
            metadata: Metadados adicionais
        
        Returns:
            (sucesso: bool, mensagem: str)
        """
        try:
            # Garantir que bucket existe
            if not self.ensure_bucket_exists():
                return False, "Bucket não existe e não pôde ser criado"
            
            # Auto-detectar content_type se não fornecido
            if not content_type:
                content_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
            
            # Preparar metadados
            extra_args = {
                'ContentType': content_type,
            }
            
            if metadata:
                extra_args['Metadata'] = metadata
            
            # Upload
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=file_path,
                Body=file_data,
                **extra_args
            )
            
            logger.info(f"✅ [S3] Upload realizado: {file_path} ({len(file_data)} bytes)")
            return True, f"s3://{self.bucket}/{file_path}"
            
        except ClientError as e:
            logger.error(f"❌ [S3] Erro no upload: {e}")
            return False, str(e)
        except Exception as e:
            logger.error(f"❌ [S3] Erro inesperado: {e}", exc_info=True)
            return False, str(e)
    
    def download_from_s3(self, file_path: str) -> Tuple[bool, Optional[bytes], str]:
        """
        Baixa arquivo do S3.
        
        Args:
            file_path: Caminho no S3
        
        Returns:
            (sucesso: bool, dados: bytes | None, mensagem: str)
        """
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket,
                Key=file_path
            )
            
            data = response['Body'].read()
            logger.info(f"✅ [S3] Download realizado: {file_path} ({len(data)} bytes)")
            return True, data, "OK"
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == 'NoSuchKey':
                logger.warning(f"⚠️ [S3] Arquivo não encontrado: {file_path}")
                return False, None, "Arquivo não encontrado"
            logger.error(f"❌ [S3] Erro no download: {e}")
            return False, None, str(e)
        except Exception as e:
            logger.error(f"❌ [S3] Erro inesperado: {e}", exc_info=True)
            return False, None, str(e)
    
    def delete_from_s3(self, file_path: str) -> Tuple[bool, str]:
        """
        Remove arquivo do S3.
        
        Args:
            file_path: Caminho no S3
        
        Returns:
            (sucesso: bool, mensagem: str)
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket,
                Key=file_path
            )
            logger.info(f"✅ [S3] Arquivo deletado: {file_path}")
            return True, "OK"
            
        except ClientError as e:
            logger.error(f"❌ [S3] Erro ao deletar: {e}")
            return False, str(e)
        except Exception as e:
            logger.error(f"❌ [S3] Erro inesperado: {e}", exc_info=True)
            return False, str(e)
    
    def generate_presigned_url(
        self,
        file_path: str,
        expiration: int = 3600,
        http_method: str = 'PUT'
    ) -> Optional[str]:
        """
        Gera URL pré-assinada para upload/download direto.
        
        Args:
            file_path: Caminho no S3
            expiration: Tempo de validade em segundos (padrão: 1h)
            http_method: Método HTTP ('PUT' para upload, 'GET' para download)
        
        Returns:
            URL assinada ou None em caso de erro
        """
        try:
            # Garantir que bucket existe
            if not self.ensure_bucket_exists():
                logger.error("❌ [S3] Não foi possível garantir que o bucket existe")
                return None
            
            url = self.s3_client.generate_presigned_url(
                'put_object' if http_method == 'PUT' else 'get_object',
                Params={
                    'Bucket': self.bucket,
                    'Key': file_path
                },
                ExpiresIn=expiration
            )
            logger.info(f"✅ [S3] URL presigned gerada: {file_path} (válida por {expiration}s)")
            return url
            
        except ClientError as e:
            logger.error(f"❌ [S3] Erro ao gerar URL presigned: {e}")
            return None
    
    def get_public_url(self, file_path: str) -> str:
        """
        Retorna URL pública via proxy Django.
        
        IMPORTANTE: Passa apenas o file_path, não presigned URL.
        O media-proxy acessa o S3 diretamente usando credenciais do Django.
        Isso evita problemas de presigned URL expirada.
        
        Args:
            file_path: Caminho no S3
        
        Returns:
            URL do proxy Django
        """
        # ✅ CORREÇÃO: Passar apenas o file_path, não presigned URL
        # O media-proxy vai acessar o S3 diretamente usando credenciais do Django
        # Isso evita problemas de presigned URL expirada ou AccessDenied
        from urllib.parse import urlencode
        params = urlencode({'s3_path': file_path})  # ✅ Mudado: usar 's3_path' ao invés de 'url'
        proxy_url = f"{settings.BASE_URL}/api/chat/media-proxy/?{params}"
        
        logger.info(f"📎 [S3] URL proxy gerada para: {file_path}")
        logger.info(f"   🌐 [S3] URL proxy: {proxy_url[:100]}...")
        
        return proxy_url
    
    def file_exists(self, file_path: str) -> bool:
        """
        Verifica se arquivo existe no S3.
        
        Args:
            file_path: Caminho no S3
        
        Returns:
            True se existe, False caso contrário
        """
        try:
            self.s3_client.head_object(
                Bucket=self.bucket,
                Key=file_path
            )
            return True
        except ClientError:
            return False


# Instância global (singleton)
_s3_manager = None


def get_s3_manager() -> S3Manager:
    """Retorna instância global do S3Manager"""
    global _s3_manager
    if _s3_manager is None:
        _s3_manager = S3Manager()
    return _s3_manager


# Funções de conveniência
def upload_to_s3(file_data: bytes, file_path: str, content_type: Optional[str] = None) -> Tuple[bool, str]:
    """Upload rápido para S3"""
    return get_s3_manager().upload_to_s3(file_data, file_path, content_type)


def download_from_s3(file_path: str) -> Tuple[bool, Optional[bytes], str]:
    """Download rápido do S3"""
    return get_s3_manager().download_from_s3(file_path)


def delete_from_s3(file_path: str) -> Tuple[bool, str]:
    """Delete rápido do S3"""
    return get_s3_manager().delete_from_s3(file_path)


def generate_presigned_url(file_path: str, expiration: int = 3600) -> Optional[str]:
    """Gera URL presigned para upload"""
    return get_s3_manager().generate_presigned_url(file_path, expiration)


def get_public_url(file_path: str) -> str:
    """Retorna URL pública via proxy"""
    return get_s3_manager().get_public_url(file_path)


def generate_media_path(tenant_id: str, media_type: str, filename: str) -> str:
    """
    Gera caminho único no S3.
    
    Args:
        tenant_id: UUID do tenant
        media_type: Tipo (profile_pics, chat_images, chat_audios, chat_docs)
        filename: Nome original do arquivo
    
    Returns:
        Caminho no formato: media_type/tenant_id/YYYYMMDD/hash_filename
    """
    # Data para organização
    date_prefix = datetime.now().strftime('%Y%m%d')
    
    # Hash do nome original para evitar conflitos
    file_hash = hashlib.md5(f"{filename}{datetime.now().isoformat()}".encode()).hexdigest()[:8]
    
    # Extensão original
    ext = Path(filename).suffix.lower()
    
    # Caminho final
    return f"{media_type}/{tenant_id}/{date_prefix}/{file_hash}{ext}"

