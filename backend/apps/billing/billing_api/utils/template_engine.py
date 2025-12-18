"""
BillingTemplateEngine - Engine para renderizar templates com variáveis e condicionais
"""
import re
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class BillingTemplateEngine:
    """
    Engine para renderizar templates de billing com:
    - Substituição de variáveis: {{variavel}}
    - Condicionais: {{#if variavel}}...{{/if}}
    - Condicionais negativas: {{#unless variavel}}...{{/unless}}
    
    Uso:
        engine = BillingTemplateEngine()
        rendered = engine.render(
            template_text="Olá {{nome_cliente}}, sua cobrança de R$ {{valor}} vence em {{dias_vencimento}} dias.",
            variables={
                'nome_cliente': 'João Silva',
                'valor': '100.00',
                'dias_vencimento': '5'
            }
        )
    """
    
    # Padrões regex
    VARIABLE_PATTERN = re.compile(r'\{\{([a-z_]+)\}\}')
    CONDITIONAL_IF_START = re.compile(r'\{\{#if\s+([a-z_]+)\}\}(.*?)\{\{/if\}\}', re.DOTALL)
    CONDITIONAL_UNLESS_START = re.compile(r'\{\{#unless\s+([a-z_]+)\}\}(.*?)\{\{/unless\}\}', re.DOTALL)
    
    def render(
        self,
        template_text: str,
        variables: Dict[str, Any],
        strict: bool = False
    ) -> str:
        """
        Renderiza template substituindo variáveis e processando condicionais
        
        Args:
            template_text: Texto do template com variáveis e condicionais
            variables: Dicionário com valores das variáveis
            strict: Se True, lança exceção se variável não encontrada
        
        Returns:
            Template renderizado
        
        Raises:
            KeyError: Se strict=True e variável não encontrada
        """
        if not template_text:
            return ''
        
        result = template_text
        
        # 1. Processar condicionais {{#unless}} primeiro (mais específico)
        result = self._process_unless_conditionals(result, variables, strict)
        
        # 2. Processar condicionais {{#if}}
        result = self._process_if_conditionals(result, variables, strict)
        
        # 3. Substituir variáveis simples
        result = self._replace_variables(result, variables, strict)
        
        logger.debug(f"Template renderizado: {len(result)} caracteres")
        return result
    
    def _process_if_conditionals(
        self,
        text: str,
        variables: Dict[str, Any],
        strict: bool
    ) -> str:
        """Processa condicionais {{#if variavel}}...{{/if}}"""
        def replace_if(match):
            var_name = match.group(1)
            content = match.group(2)
            
            # Verificar se variável existe e tem valor verdadeiro
            var_value = variables.get(var_name)
            is_truthy = self._is_truthy(var_value)
            
            if is_truthy:
                # Renderizar conteúdo dentro do bloco
                return self._replace_variables(content, variables, strict)
            else:
                # Remover conteúdo
                return ''
        
        result = self.CONDITIONAL_IF_START.sub(replace_if, text)
        return result
    
    def _process_unless_conditionals(
        self,
        text: str,
        variables: Dict[str, Any],
        strict: bool
    ) -> str:
        """Processa condicionais {{#unless variavel}}...{{/unless}}"""
        def replace_unless(match):
            var_name = match.group(1)
            content = match.group(2)
            
            # Verificar se variável existe e tem valor verdadeiro
            var_value = variables.get(var_name)
            is_truthy = self._is_truthy(var_value)
            
            if not is_truthy:
                # Renderizar conteúdo dentro do bloco (variável é falsy)
                return self._replace_variables(content, variables, strict)
            else:
                # Remover conteúdo
                return ''
        
        result = self.CONDITIONAL_UNLESS_START.sub(replace_unless, text)
        return result
    
    def _replace_variables(
        self,
        text: str,
        variables: Dict[str, Any],
        strict: bool
    ) -> str:
        """Substitui variáveis {{variavel}} pelos valores"""
        def replace_var(match):
            var_name = match.group(1)
            
            if var_name in variables:
                value = variables[var_name]
                # Converter para string
                return str(value) if value is not None else ''
            else:
                if strict:
                    raise KeyError(f"Variável '{var_name}' não encontrada")
                # Em modo não-strict, deixa a variável no texto
                logger.warning(f"Variável '{var_name}' não encontrada no contexto")
                return match.group(0)  # Retorna original {{variavel}}
        
        result = self.VARIABLE_PATTERN.sub(replace_var, text)
        return result
    
    @staticmethod
    def _is_truthy(value: Any) -> bool:
        """
        Verifica se valor é "truthy" (existe e não é vazio)
        
        Valores falsy:
        - None
        - False
        - 0
        - '' (string vazia)
        - [] (lista vazia)
        - {} (dict vazio)
        """
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return value.strip() != ''
        if isinstance(value, (list, dict)):
            return len(value) > 0
        # Outros tipos são considerados truthy
        return True
    
    def extract_variables(self, template_text: str) -> list[str]:
        """
        Extrai lista de variáveis usadas no template
        
        Args:
            template_text: Texto do template
        
        Returns:
            Lista de nomes de variáveis únicas
        """
        if not template_text:
            return []
        
        # Extrair variáveis simples
        variables = set(self.VARIABLE_PATTERN.findall(template_text))
        
        # Extrair variáveis de condicionais {{#if var}}
        if_vars = self.CONDITIONAL_IF_START.findall(template_text)
        for var_name, _ in if_vars:
            variables.add(var_name)
        
        # Extrair variáveis de condicionais {{#unless var}}
        unless_vars = self.CONDITIONAL_UNLESS_START.findall(template_text)
        for var_name, _ in unless_vars:
            variables.add(var_name)
        
        return sorted(list(variables))



