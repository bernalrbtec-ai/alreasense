"""
✅ IMPROVEMENT: Common validators and sanitizers for secure input handling
"""
import re
import bleach
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator, URLValidator
from typing import Any, Optional


class SecureInputValidator:
    """
    Validator para garantir entrada segura de usuários
    Previne: XSS, SQL Injection, Command Injection
    """
    
    # Padrões perigosos para detectar
    DANGEROUS_PATTERNS = [
        r'<script[^>]*>.*?</script>',  # Script tags
        r'javascript:',  # JavaScript protocol
        r'on\w+\s*=',  # Event handlers (onclick, onload, etc)
        r'eval\s*\(',  # eval() calls
        r'expression\s*\(',  # CSS expressions
        r'import\s*\(',  # Dynamic imports
        r'<iframe',  # iframes
        r'<object',  # objects
        r'<embed',  # embeds
        r'<applet',  # applets
    ]
    
    @classmethod
    def sanitize_html(cls, text: str, allowed_tags: Optional[list] = None) -> str:
        """
        Sanitiza HTML removendo tags perigosas
        
        Args:
            text: Texto para sanitizar
            allowed_tags: Tags permitidas (default: nenhuma)
        
        Returns:
            Texto sanitizado
        """
        if not text:
            return ''
        
        if allowed_tags is None:
            allowed_tags = []  # No HTML by default
        
        # Usar bleach para limpar HTML
        clean_text = bleach.clean(
            text,
            tags=allowed_tags,
            attributes={},
            strip=True
        )
        
        return clean_text
    
    @classmethod
    def validate_no_xss(cls, value: str) -> str:
        """
        Valida que o valor não contém vetores de XSS
        
        Args:
            value: Valor para validar
        
        Returns:
            Valor original se válido
        
        Raises:
            ValidationError: Se detectar XSS
        """
        if not value:
            return value
        
        value_lower = value.lower()
        
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, value_lower, re.IGNORECASE):
                raise ValidationError(
                    f'Entrada contém código potencialmente perigoso e foi bloqueada',
                    code='xss_detected'
                )
        
        return value
    
    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """
        Sanitiza nome de arquivo removendo caracteres perigosos
        
        Args:
            filename: Nome do arquivo
        
        Returns:
            Nome sanitizado
        """
        if not filename:
            return ''
        
        # Remover path traversal
        filename = filename.replace('../', '').replace('..\\', '')
        
        # Permitir apenas caracteres alfanuméricos, underscores, hífens e pontos
        filename = re.sub(r'[^\w\s.-]', '', filename)
        
        # Remover espaços extras
        filename = '_'.join(filename.split())
        
        # Limitar tamanho
        if len(filename) > 255:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            filename = name[:250] + ('.' + ext if ext else '')
        
        return filename
    
    @classmethod
    def validate_phone(cls, phone: str) -> str:
        """
        Valida e sanitiza número de telefone
        
        Args:
            phone: Número de telefone
        
        Returns:
            Telefone sanitizado
        
        Raises:
            ValidationError: Se inválido
        """
        if not phone:
            raise ValidationError('Telefone é obrigatório')
        
        # Remover tudo exceto números e +
        sanitized = re.sub(r'[^\d+]', '', phone)
        
        # Validar formato E.164
        if not re.match(r'^\+?[1-9]\d{1,14}$', sanitized):
            raise ValidationError(
                'Telefone deve estar no formato internacional (ex: +5511999999999)',
                code='invalid_phone'
            )
        
        # Adicionar + se não tiver
        if not sanitized.startswith('+'):
            sanitized = '+' + sanitized
        
        return sanitized
    
    @classmethod
    def validate_email(cls, email: str) -> str:
        """
        Valida email
        
        Args:
            email: Email para validar
        
        Returns:
            Email válido
        
        Raises:
            ValidationError: Se inválido
        """
        if not email:
            raise ValidationError('Email é obrigatório')
        
        validator = EmailValidator()
        validator(email)
        
        return email.lower().strip()
    
    @classmethod
    def validate_url(cls, url: str, allowed_protocols: Optional[list] = None) -> str:
        """
        Valida URL
        
        Args:
            url: URL para validar
            allowed_protocols: Protocolos permitidos (default: http, https)
        
        Returns:
            URL válida
        
        Raises:
            ValidationError: Se inválida
        """
        if not url:
            raise ValidationError('URL é obrigatória')
        
        if allowed_protocols is None:
            allowed_protocols = ['http', 'https']
        
        # Validar formato
        validator = URLValidator(schemes=allowed_protocols)
        validator(url)
        
        # Verificar que não tem javascript:
        if 'javascript:' in url.lower():
            raise ValidationError('URL com javascript: não é permitida', code='invalid_url')
        
        return url
    
    @classmethod
    def sanitize_json_value(cls, value: Any, max_depth: int = 10, current_depth: int = 0) -> Any:
        """
        Sanitiza valores JSON recursivamente
        
        Args:
            value: Valor para sanitizar
            max_depth: Profundidade máxima
            current_depth: Profundidade atual
        
        Returns:
            Valor sanitizado
        """
        if current_depth >= max_depth:
            return None
        
        if isinstance(value, str):
            # Sanitizar strings
            return cls.sanitize_html(value, allowed_tags=[])
        elif isinstance(value, dict):
            # Sanitizar dicionários
            return {
                k: cls.sanitize_json_value(v, max_depth, current_depth + 1)
                for k, v in value.items()
                if isinstance(k, str)  # Chaves devem ser strings
            }
        elif isinstance(value, list):
            # Sanitizar listas
            return [
                cls.sanitize_json_value(item, max_depth, current_depth + 1)
                for item in value
            ]
        elif isinstance(value, (int, float, bool, type(None))):
            # Valores primitivos são seguros
            return value
        else:
            # Tipos desconhecidos: retornar None
            return None


class RateLimitValidator:
    """
    Validador para rate limiting baseado em Redis
    """
    
    @staticmethod
    def check_rate_limit(key: str, limit: int, window: int) -> tuple[bool, int]:
        """
        Verifica rate limit
        
        Args:
            key: Chave única (ex: ip:endpoint)
            limit: Número máximo de requests
            window: Janela de tempo em segundos
        
        Returns:
            (permitido: bool, remaining: int)
        """
        from django.core.cache import cache
        import time
        
        current = int(time.time())
        window_start = current - window
        
        # Obter contadores atuais
        cache_key = f"ratelimit:{key}"
        timestamps = cache.get(cache_key, [])
        
        # Filtrar timestamps dentro da janela
        timestamps = [ts for ts in timestamps if ts > window_start]
        
        # Verificar limite
        if len(timestamps) >= limit:
            return False, 0
        
        # Adicionar timestamp atual
        timestamps.append(current)
        cache.set(cache_key, timestamps, window)
        
        return True, limit - len(timestamps)

