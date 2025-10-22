"""
Utilitário para converter áudios OGG → MP3.

PROBLEMA:
- Navegadores gravam em OGG (audio/ogg;codecs=opus)
- Navegadores NÃO reproduzem OGG bem
- Áudios recebidos do WhatsApp (OGG) não reproduzem no navegador

SOLUÇÃO:
- Converter OGG → MP3 automaticamente
- MP3 funciona em: Navegador + WhatsApp + TUDO

DEPENDÊNCIA:
- pydub (pip install pydub)
- ffmpeg (Railway tem por padrão)
"""
import logging
import io
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

def convert_ogg_to_mp3(ogg_data: bytes, source_format: str = "ogg") -> Tuple[bool, Optional[bytes], str]:
    """
    Converte áudio OGG/WEBM para MP3.
    
    Args:
        ogg_data: Bytes do arquivo OGG/WEBM
        source_format: Formato do áudio de origem ("ogg" ou "webm")
    
    Returns:
        (sucesso: bool, mp3_data: bytes | None, mensagem: str)
    """
    try:
        from pydub import AudioSegment
        
        logger.info(f"🔄 [AUDIO] Convertendo {source_format.upper()} → MP3...")
        
        # Carregar áudio (especificar formato ajuda FFmpeg)
        audio = AudioSegment.from_file(
            io.BytesIO(ogg_data),
            format=source_format
        )
        
        # Converter para MP3
        mp3_buffer = io.BytesIO()
        audio.export(
            mp3_buffer,
            format="mp3",
            bitrate="128k",  # Boa qualidade, tamanho razoável
            parameters=["-q:a", "2"]  # Qualidade VBR
        )
        
        mp3_data = mp3_buffer.getvalue()
        
        # Stats
        ogg_size = len(ogg_data)
        mp3_size = len(mp3_data)
        reduction = ((ogg_size - mp3_size) / ogg_size) * 100
        
        logger.info(f"✅ [AUDIO] Conversão completa!")
        logger.info(f"   OGG: {ogg_size:,} bytes")
        logger.info(f"   MP3: {mp3_size:,} bytes")
        logger.info(f"   Redução: {reduction:.1f}%")
        
        return True, mp3_data, "Conversão bem-sucedida"
        
    except ImportError:
        logger.error("❌ [AUDIO] pydub não instalado! Instale: pip install pydub")
        return False, None, "pydub não instalado"
    
    except Exception as e:
        logger.error(f"❌ [AUDIO] Erro na conversão: {e}", exc_info=True)
        return False, None, str(e)


def should_convert_audio(mime_type: str, filename: str) -> bool:
    """
    Verifica se áudio precisa ser convertido.
    
    Args:
        mime_type: MIME type do arquivo
        filename: Nome do arquivo
    
    Returns:
        True se precisa converter, False caso contrário
    """
    # Converter apenas OGG e WEBM
    if 'ogg' in mime_type.lower() or 'webm' in mime_type.lower():
        return True
    
    if filename.lower().endswith(('.ogg', '.webm')):
        return True
    
    return False


def get_converted_filename(original_filename: str) -> str:
    """
    Gera nome do arquivo convertido.
    
    Args:
        original_filename: Nome original (ex: voice-123.ogg)
    
    Returns:
        Nome convertido (ex: voice-123.mp3)
    """
    import os
    base = os.path.splitext(original_filename)[0]
    return f"{base}.mp3"

