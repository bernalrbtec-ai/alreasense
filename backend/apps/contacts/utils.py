"""
Utilitários para o módulo de contatos
"""

import re


# Mapeamento completo DDD → Estado (Brasil)
DDD_TO_STATE_MAP = {
    # São Paulo
    '11': 'SP', '12': 'SP', '13': 'SP', '14': 'SP', '15': 'SP',
    '16': 'SP', '17': 'SP', '18': 'SP', '19': 'SP',
    
    # Rio de Janeiro
    '21': 'RJ', '22': 'RJ', '24': 'RJ',
    
    # Espírito Santo
    '27': 'ES', '28': 'ES',
    
    # Minas Gerais
    '31': 'MG', '32': 'MG', '33': 'MG', '34': 'MG',
    '35': 'MG', '37': 'MG', '38': 'MG',
    
    # Paraná
    '41': 'PR', '42': 'PR', '43': 'PR', '44': 'PR',
    '45': 'PR', '46': 'PR',
    
    # Santa Catarina
    '47': 'SC', '48': 'SC', '49': 'SC',
    
    # Rio Grande do Sul
    '51': 'RS', '53': 'RS', '54': 'RS', '55': 'RS',
    
    # Distrito Federal
    '61': 'DF',
    
    # Goiás
    '62': 'GO', '64': 'GO',
    
    # Tocantins
    '63': 'TO',
    
    # Mato Grosso
    '65': 'MT', '66': 'MT',
    
    # Mato Grosso do Sul
    '67': 'MS',
    
    # Acre
    '68': 'AC',
    
    # Rondônia
    '69': 'RO',
    
    # Bahia
    '71': 'BA', '73': 'BA', '74': 'BA', '75': 'BA', '77': 'BA',
    
    # Sergipe
    '79': 'SE',
    
    # Pernambuco
    '81': 'PE', '87': 'PE',
    
    # Alagoas
    '82': 'AL',
    
    # Paraíba
    '83': 'PB',
    
    # Rio Grande do Norte
    '84': 'RN',
    
    # Ceará
    '85': 'CE', '88': 'CE',
    
    # Piauí
    '86': 'PI', '89': 'PI',
    
    # Pará
    '91': 'PA', '93': 'PA', '94': 'PA',
    
    # Amazonas
    '92': 'AM', '97': 'AM',
    
    # Roraima
    '95': 'RR',
    
    # Amapá
    '96': 'AP',
    
    # Maranhão
    '98': 'MA', '99': 'MA',
}


def normalize_phone(phone):
    """
    Normaliza telefone para formato E.164
    
    Exemplos:
    - (11) 99999-9999  → +5511999999999
    - 11999999999      → +5511999999999
    - +5511999999999   → +5511999999999 (já correto)
    
    Args:
        phone (str): Telefone em qualquer formato
        
    Returns:
        str: Telefone no formato E.164
    """
    if not phone:
        return phone
    
    # Remover formatação (parênteses, hífens, espaços)
    clean = re.sub(r'[^\d+]', '', phone)
    
    # Adicionar +55 se não tiver código de país
    if not clean.startswith('+'):
        if clean.startswith('55'):
            clean = f'+{clean}'
        else:
            clean = f'+55{clean}'
    
    return clean


def get_state_from_ddd(ddd):
    """
    Retorna a UF (estado) baseado no DDD
    
    Args:
        ddd (str|int): DDD de 2 dígitos
        
    Returns:
        str|None: Sigla do estado (ex: 'SP') ou None se não encontrado
        
    Examples:
        >>> get_state_from_ddd('11')
        'SP'
        >>> get_state_from_ddd(21)
        'RJ'
        >>> get_state_from_ddd('99')
        'MA'
        >>> get_state_from_ddd('00')
        None
    """
    if not ddd:
        return None
    
    ddd_str = str(ddd).strip()
    
    # Remover caracteres não numéricos
    ddd_clean = ''.join(filter(str.isdigit, ddd_str))
    
    # Se DDD tiver mais de 2 dígitos, pegar apenas os 2 primeiros
    if len(ddd_clean) > 2:
        ddd_clean = ddd_clean[:2]
    
    return DDD_TO_STATE_MAP.get(ddd_clean)


def extract_ddd_from_phone(phone):
    """
    Extrai o DDD de um telefone no formato E.164 ou brasileiro
    
    Args:
        phone (str): Telefone em qualquer formato
        
    Returns:
        str|None: DDD de 2 dígitos ou None
        
    Examples:
        >>> extract_ddd_from_phone('+5511999998888')
        '11'
        >>> extract_ddd_from_phone('11999998888')
        '11'
        >>> extract_ddd_from_phone('(11) 99999-8888')
        '11'
        >>> extract_ddd_from_phone('999998888')
        None
    """
    if not phone:
        return None
    
    # Remover formatação
    clean = re.sub(r'[^\d]', '', phone)
    
    # Se começar com 55 (código do Brasil), remover
    if clean.startswith('55') and len(clean) >= 12:
        clean = clean[2:]  # Remove '55'
    
    # DDD são os primeiros 2 dígitos
    if len(clean) >= 10:  # Mínimo: DDD (2) + número (8)
        return clean[:2]
    
    return None


def get_state_from_phone(phone):
    """
    Conveniência: extrai DDD do telefone e retorna o estado
    
    Args:
        phone (str): Telefone em qualquer formato
        
    Returns:
        str|None: Sigla do estado ou None
        
    Examples:
        >>> get_state_from_phone('+5511999998888')
        'SP'
        >>> get_state_from_phone('21988887777')
        'RJ'
    """
    ddd = extract_ddd_from_phone(phone)
    return get_state_from_ddd(ddd) if ddd else None


