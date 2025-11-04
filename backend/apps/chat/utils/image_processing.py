"""
Processamento de imagens para chat.

Funções:
- create_thumbnail: Cria thumbnail de imagem
- resize_image: Redimensiona imagem mantendo proporção
- optimize_image: Otimiza qualidade/tamanho
- process_image: Pipeline completo de processamento
"""
import logging
import io
from typing import Tuple, Optional
from PIL import Image, ImageOps
import hashlib

logger = logging.getLogger(__name__)

# Configurações
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
THUMBNAIL_SIZE = (150, 150)  # Thumbnail para lista de conversas
PREVIEW_SIZE = (800, 800)  # Preview no chat
QUALITY_HIGH = 90
QUALITY_MEDIUM = 75
QUALITY_LOW = 60


def create_thumbnail(
    image_data: bytes,
    size: Tuple[int, int] = THUMBNAIL_SIZE,
    quality: int = QUALITY_MEDIUM
) -> Tuple[bool, Optional[bytes], str]:
    """
    Cria thumbnail de uma imagem.
    
    Args:
        image_data: Dados binários da imagem original
        size: Tamanho do thumbnail (width, height)
        quality: Qualidade JPEG (1-100)
    
    Returns:
        (sucesso: bool, thumbnail_data: bytes | None, mensagem: str)
    """
    try:
        # Abrir imagem
        img = Image.open(io.BytesIO(image_data))
        
        # Converter RGBA para RGB se necessário
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        
        # Corrigir orientação EXIF
        img = ImageOps.exif_transpose(img)
        
        # Criar thumbnail (mantém proporção, preenche com crop)
        img.thumbnail(size, Image.Resampling.LANCZOS)
        
        # Salvar em buffer
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=quality, optimize=True)
        thumbnail_data = buffer.getvalue()
        
        logger.info(f"✅ [IMG] Thumbnail criado: {len(image_data)} → {len(thumbnail_data)} bytes")
        return True, thumbnail_data, "OK"
        
    except Exception as e:
        logger.error(f"❌ [IMG] Erro ao criar thumbnail: {e}", exc_info=True)
        return False, None, str(e)


def resize_image(
    image_data: bytes,
    max_size: Tuple[int, int] = PREVIEW_SIZE,
    quality: int = QUALITY_HIGH
) -> Tuple[bool, Optional[bytes], str]:
    """
    Redimensiona imagem mantendo proporção.
    
    Args:
        image_data: Dados binários da imagem original
        max_size: Tamanho máximo (width, height)
        quality: Qualidade JPEG (1-100)
    
    Returns:
        (sucesso: bool, resized_data: bytes | None, mensagem: str)
    """
    try:
        # Abrir imagem
        img = Image.open(io.BytesIO(image_data))
        
        # Verificar se precisa redimensionar
        if img.size[0] <= max_size[0] and img.size[1] <= max_size[1]:
            logger.info(f"ℹ️ [IMG] Imagem já está dentro do tamanho: {img.size}")
            return True, image_data, "OK"
        
        # Converter RGBA para RGB se necessário
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        
        # Corrigir orientação EXIF
        img = ImageOps.exif_transpose(img)
        
        # Redimensionar mantendo proporção
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Salvar em buffer
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=quality, optimize=True)
        resized_data = buffer.getvalue()
        
        logger.info(f"✅ [IMG] Imagem redimensionada: {len(image_data)} → {len(resized_data)} bytes")
        return True, resized_data, "OK"
        
    except Exception as e:
        logger.error(f"❌ [IMG] Erro ao redimensionar: {e}", exc_info=True)
        return False, None, str(e)


def optimize_image(
    image_data: bytes,
    target_size_kb: Optional[int] = None,
    min_quality: int = QUALITY_LOW
) -> Tuple[bool, Optional[bytes], str]:
    """
    Otimiza imagem para reduzir tamanho mantendo qualidade aceitável.
    
    Args:
        image_data: Dados binários da imagem original
        target_size_kb: Tamanho alvo em KB (None = usa qualidade fixa)
        min_quality: Qualidade mínima aceitável (1-100)
    
    Returns:
        (sucesso: bool, optimized_data: bytes | None, mensagem: str)
    """
    try:
        # Abrir imagem
        img = Image.open(io.BytesIO(image_data))
        
        # Converter RGBA para RGB se necessário
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        
        # Corrigir orientação EXIF
        img = ImageOps.exif_transpose(img)
        
        # Se não tem target_size, usar qualidade média
        if target_size_kb is None:
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=QUALITY_MEDIUM, optimize=True)
            optimized_data = buffer.getvalue()
            logger.info(f"✅ [IMG] Imagem otimizada: {len(image_data)} → {len(optimized_data)} bytes")
            return True, optimized_data, "OK"
        
        # Tentar atingir target_size ajustando qualidade
        target_size_bytes = target_size_kb * 1024
        quality = QUALITY_HIGH
        
        while quality >= min_quality:
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=quality, optimize=True)
            optimized_data = buffer.getvalue()
            
            if len(optimized_data) <= target_size_bytes:
                logger.info(
                    f"✅ [IMG] Imagem otimizada: "
                    f"{len(image_data)} → {len(optimized_data)} bytes (quality={quality})"
                )
                return True, optimized_data, "OK"
            
            quality -= 5
        
        # Se não conseguiu atingir target, retornar com qualidade mínima
        logger.warning(
            f"⚠️ [IMG] Não foi possível atingir {target_size_kb}KB, "
            f"usando qualidade mínima: {len(optimized_data)} bytes"
        )
        return True, optimized_data, "OK"
        
    except Exception as e:
        logger.error(f"❌ [IMG] Erro ao otimizar: {e}", exc_info=True)
        return False, None, str(e)


def process_image(
    image_data: bytes,
    create_thumb: bool = True,
    resize: bool = True,
    optimize: bool = True
) -> dict:
    """
    Pipeline completo de processamento de imagem.
    
    Args:
        image_data: Dados binários da imagem original
        create_thumb: Se deve criar thumbnail
        resize: Se deve redimensionar
        optimize: Se deve otimizar
    
    Returns:
        dict com resultados:
        {
            'success': bool,
            'original_size': int,
            'processed_data': bytes | None,
            'processed_size': int,
            'thumbnail_data': bytes | None,
            'thumbnail_size': int,
            'errors': list[str]
        }
    """
    result = {
        'success': False,
        'original_size': len(image_data),
        'processed_data': None,
        'processed_size': 0,
        'thumbnail_data': None,
        'thumbnail_size': 0,
        'errors': []
    }
    
    try:
        # Validar que é uma imagem
        try:
            img = Image.open(io.BytesIO(image_data))
            img.verify()
        except Exception as e:
            result['errors'].append(f"Arquivo não é uma imagem válida: {e}")
            return result
        
        # Dados processados começam como original
        processed_data = image_data
        
        # 1. Redimensionar se necessário
        if resize:
            success, resized, msg = resize_image(processed_data)
            if success and resized:
                processed_data = resized
            else:
                result['errors'].append(f"Erro ao redimensionar: {msg}")
        
        # 2. Otimizar
        if optimize:
            success, optimized, msg = optimize_image(processed_data)
            if success and optimized:
                processed_data = optimized
            else:
                result['errors'].append(f"Erro ao otimizar: {msg}")
        
        # 3. Criar thumbnail
        if create_thumb:
            success, thumb, msg = create_thumbnail(image_data)
            if success and thumb:
                result['thumbnail_data'] = thumb
                result['thumbnail_size'] = len(thumb)
            else:
                result['errors'].append(f"Erro ao criar thumbnail: {msg}")
        
        # Resultado final
        result['processed_data'] = processed_data
        result['processed_size'] = len(processed_data)
        result['success'] = True
        
        logger.info(
            f"✅ [IMG] Processamento completo: "
            f"{result['original_size']} → {result['processed_size']} bytes "
            f"(thumbnail: {result['thumbnail_size']} bytes)"
        )
        
    except Exception as e:
        logger.error(f"❌ [IMG] Erro no processamento: {e}", exc_info=True)
        result['errors'].append(str(e))
    
    return result


def get_image_info(image_data: bytes) -> Optional[dict]:
    """
    Extrai informações de uma imagem.
    
    Args:
        image_data: Dados binários da imagem
    
    Returns:
        dict com informações ou None em caso de erro
    """
    try:
        img = Image.open(io.BytesIO(image_data))
        
        return {
            'format': img.format,
            'mode': img.mode,
            'size': img.size,  # (width, height)
            'width': img.size[0],
            'height': img.size[1],
            'file_size': len(image_data),
            'has_transparency': img.mode in ('RGBA', 'LA', 'P')
        }
    except Exception as e:
        logger.error(f"❌ [IMG] Erro ao extrair info: {e}")
        return None


def is_valid_image(image_data: bytes) -> bool:
    """
    Valida se os dados são de uma imagem válida.
    
    Args:
        image_data: Dados binários
    
    Returns:
        True se é imagem válida, False caso contrário
    """
    try:
        img = Image.open(io.BytesIO(image_data))
        img.verify()
        return True
    except Exception:
        return False


def validate_magic_numbers(data: bytes) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Valida magic numbers (primeiros bytes) para detectar formato real do arquivo.
    
    Args:
        data: Dados binários do arquivo
    
    Returns:
        (is_valid: bool, detected_format: str | None, detected_mime: str | None)
    """
    if len(data) < 4:
        return False, None, None
    
    # JPEG: FF D8 FF
    if data[:3] == b'\xff\xd8\xff':
        return True, 'jpeg', 'image/jpeg'
    
    # PNG: 89 50 4E 47 0D 0A 1A 0A
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return True, 'png', 'image/png'
    
    # GIF: GIF87a ou GIF89a
    if data[:6] in [b'GIF87a', b'GIF89a']:
        return True, 'gif', 'image/gif'
    
    # WebP: RIFF ... WEBP
    if data[:4] == b'RIFF' and len(data) > 12 and data[8:12] == b'WEBP':
        return True, 'webp', 'image/webp'
    
    # MP4: ftyp box
    if len(data) >= 12 and data[4:8] == b'ftyp':
        return True, 'mp4', 'video/mp4'
    
    # MP3: FF FB, FF F3, FF F2 ou ID3
    if len(data) >= 3 and (data[:2] in [b'\xff\xfb', b'\xff\xf3', b'\xff\xf2'] or data[:3] == b'ID3'):
        return True, 'mp3', 'audio/mpeg'
    
    # PDF: %PDF
    if data[:4] == b'%PDF':
        return True, 'pdf', 'application/pdf'
    
    # OGG: OggS
    if data[:4] == b'OggS':
        return True, 'ogg', 'audio/ogg'
    
    # WEBM: webm (pode estar em diferentes posições)
    if b'webm' in data[:32].lower():
        return True, 'webm', 'video/webm'
    
    return False, None, None


def validate_image_data(data: bytes, media_type: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Valida dados de imagem: magic numbers + PIL verification.
    
    Args:
        data: Dados binários
        media_type: Tipo de mídia esperado (image, video, audio, document)
    
    Returns:
        (is_valid: bool, error_message: str | None, detected_format: str | None)
    """
    # 1. Validar tamanho mínimo
    if len(data) < 4:
        return False, 'Arquivo muito pequeno para ser válido', None
    
    # 2. Validar magic numbers
    is_valid_magic, detected_format, detected_mime = validate_magic_numbers(data)
    
    # 3. Para imagens, validar com PIL também
    if media_type == 'image':
        if not is_valid_magic:
            # Log primeiros bytes para debug
            hex_preview = data[:16].hex() if len(data) >= 16 else data.hex()
            return False, f'Magic numbers inválidos para imagem (primeiros bytes: {hex_preview})', None
        
        # Validar com PIL
        try:
            img = Image.open(io.BytesIO(data))
            img.verify()
            # Reabrir para usar (verify() fecha o arquivo)
            img = Image.open(io.BytesIO(data))
            img.load()  # Carregar dados completos
            return True, None, detected_format
        except Exception as e:
            logger.warning(f'⚠️ [VALIDATION] Magic numbers OK mas PIL falhou: {e}')
            return False, f'Imagem não passa na validação PIL: {str(e)}', detected_format
    
    # 4. Para outros tipos, só validar magic numbers
    if media_type in ['video', 'audio', 'document']:
        if not is_valid_magic:
            hex_preview = data[:16].hex() if len(data) >= 16 else data.hex()
            return False, f'Magic numbers inválidos para {media_type} (primeiros bytes: {hex_preview})', None
        return True, None, detected_format
    
    return True, None, detected_format
