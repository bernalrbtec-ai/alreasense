"""
TemplateSanitizer - Sanitiza templates para prevenir XSS e validar sintaxe
"""
import re
import logging

logger = logging.getLogger(__name__)


class TemplateSanitizer:
    """
    Sanitiza e valida templates de mensagem
    
    Uso:
        sanitizer = TemplateSanitizer()
        safe_text = sanitizer.sanitize(template_text)
        is_valid = sanitizer.validate_conditional_syntax(template_text)
    """
    
    # Padrões de variáveis permitidas
    ALLOWED_VARIABLES = [
        'nome_cliente',
        'primeiro_nome',
        'valor',
        'data_vencimento',
        'dias_atraso',
        'dias_vencimento',
        'link_pagamento',
        'codigo_pix',
        'observacoes',
    ]
    
    # Padrão regex para variáveis válidas
    VARIABLE_PATTERN = re.compile(r'\{\{([a-z_]+)\}\}')
    
    # Padrão para condicionais
    CONDITIONAL_START = re.compile(r'\{\{#if\s+([a-z_]+)\}\}')
    CONDITIONAL_END = re.compile(r'\{\{/if\}\}')
    CONDITIONAL_UNLESS_START = re.compile(r'\{\{#unless\s+([a-z_]+)\}\}')
    CONDITIONAL_UNLESS_END = re.compile(r'\{\{/unless\}\}')
    
    @classmethod
    def sanitize(cls, template_text: str) -> str:
        """
        Remove conteúdo perigoso do template (scripts, iframes, etc.)
        
        Args:
            template_text: Texto do template
        
        Returns:
            Template sanitizado
        """
        if not template_text:
            return ''
        
        # Remover scripts
        template_text = re.sub(r'<script[^>]*>.*?</script>', '', template_text, flags=re.DOTALL | re.IGNORECASE)
        
        # Remover iframes
        template_text = re.sub(r'<iframe[^>]*>.*?</iframe>', '', template_text, flags=re.DOTALL | re.IGNORECASE)
        
        # Remover event handlers (onclick, onerror, etc.)
        template_text = re.sub(r'\s+on\w+\s*=\s*["\'][^"\']*["\']', '', template_text, flags=re.IGNORECASE)
        
        # Remover javascript: URLs
        template_text = re.sub(r'javascript:', '', template_text, flags=re.IGNORECASE)
        
        logger.debug(f"Template sanitizado: removidos scripts, iframes e event handlers")
        return template_text.strip()
    
    @classmethod
    def validate_conditional_syntax(cls, template_text: str) -> tuple[bool, str]:
        """
        Valida sintaxe de condicionais ({{#if}} e {{#unless}})
        
        Args:
            template_text: Texto do template
        
        Returns:
            (is_valid: bool, error_message: str)
        """
        if not template_text:
            return True, ""
        
        # Verificar balanceamento de {{#if}}
        if_matches = cls.CONDITIONAL_START.findall(template_text)
        if_end_matches = cls.CONDITIONAL_END.findall(template_text)
        
        if len(if_matches) != len(if_end_matches):
            return False, f"Condicionais {{#if}} não balanceadas: {len(if_matches)} aberturas, {len(if_end_matches)} fechamentos"
        
        # Verificar balanceamento de {{#unless}}
        unless_matches = cls.CONDITIONAL_UNLESS_START.findall(template_text)
        unless_end_matches = cls.CONDITIONAL_UNLESS_END.findall(template_text)
        
        if len(unless_matches) != len(unless_end_matches):
            return False, f"Condicionais {{#unless}} não balanceadas: {len(unless_matches)} aberturas, {len(unless_end_matches)} fechamentos"
        
        # Verificar se há condicionais aninhadas (não suportado por enquanto)
        # Pattern simplificado: procurar por {{#if dentro de {{#if
        if_regex = r'\{\{#if[^}]+\}\}'
        nested_pattern = rf'{if_regex}.*?{if_regex}'
        if re.search(nested_pattern, template_text, re.DOTALL):
            return False, "Condicionais aninhadas não são suportadas (ex: {{#if}} dentro de {{#if}})"
        
        return True, ""
    
    @classmethod
    def validate_variables(cls, template_text: str) -> tuple[bool, list[str]]:
        """
        Valida variáveis usadas no template
        
        Args:
            template_text: Texto do template
        
        Returns:
            (is_valid: bool, invalid_variables: list[str])
        """
        if not template_text:
            return True, []
        
        # Extrair todas as variáveis do template
        variables = cls.VARIABLE_PATTERN.findall(template_text)
        
        # Filtrar variáveis inválidas
        invalid = [v for v in variables if v not in cls.ALLOWED_VARIABLES]
        
        if invalid:
            logger.warning(f"Variáveis inválidas encontradas no template: {invalid}")
            return False, invalid
        
        return True, []



