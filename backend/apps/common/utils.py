"""
Common utilities for the application.
"""

import re
import hashlib
from typing import List, Dict, Any
from django.core.exceptions import ValidationError


def sanitize_pii(text: str) -> str:
    """
    Sanitize personally identifiable information from text.
    
    Args:
        text: Text to sanitize
    
    Returns:
        Sanitized text
    """
    
    # CPF pattern
    text = re.sub(r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b', '[CPF]', text)
    
    # CNPJ pattern
    text = re.sub(r'\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b', '[CNPJ]', text)
    
    # Email pattern
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', text)
    
    # Phone pattern (Brazilian)
    text = re.sub(r'\b\(?[0-9]{2}\)?\s?[0-9]{4,5}-?[0-9]{4}\b', '[PHONE]', text)
    
    # Credit card pattern
    text = re.sub(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', '[CARD]', text)
    
    return text


def hash_phone_number(phone: str) -> str:
    """
    Hash phone number for privacy.
    
    Args:
        phone: Phone number to hash
    
    Returns:
        Hashed phone number
    """
    
    # Clean phone number
    clean_phone = re.sub(r'[^\d]', '', phone)
    
    # Hash with salt
    salt = "evosense_salt_2024"
    return hashlib.sha256((clean_phone + salt).encode()).hexdigest()[:16]


def validate_plan_limits(tenant, resource_type: str, current_count: int) -> bool:
    """
    Validate if tenant can add more resources based on plan limits.
    
    Args:
        tenant: Tenant instance
        resource_type: Type of resource ('connections', 'users', etc.)
        current_count: Current number of resources
    
    Returns:
        True if within limits, False otherwise
    """
    
    limits = tenant.plan_limits
    
    if resource_type not in limits:
        return True
    
    limit = limits[resource_type]
    
    # -1 means unlimited
    if limit == -1:
        return True
    
    return current_count < limit


def format_currency(amount: float, currency: str = 'BRL') -> str:
    """
    Format currency amount.
    
    Args:
        amount: Amount to format
        currency: Currency code
    
    Returns:
        Formatted currency string
    """
    
    if currency == 'BRL':
        return f"R$ {amount:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    
    return f"{currency} {amount:,.2f}"


def calculate_sentiment_score(sentiment: float) -> str:
    """
    Calculate sentiment score category.
    
    Args:
        sentiment: Sentiment value (-1 to 1)
    
    Returns:
        Sentiment category
    """
    
    if sentiment >= 0.3:
        return 'positive'
    elif sentiment <= -0.3:
        return 'negative'
    else:
        return 'neutral'


def calculate_satisfaction_level(satisfaction: int) -> str:
    """
    Calculate satisfaction level category.
    
    Args:
        satisfaction: Satisfaction value (0 to 100)
    
    Returns:
        Satisfaction level
    """
    
    if satisfaction >= 80:
        return 'very_satisfied'
    elif satisfaction >= 60:
        return 'satisfied'
    elif satisfaction >= 40:
        return 'neutral'
    elif satisfaction >= 20:
        return 'dissatisfied'
    else:
        return 'very_dissatisfied'


def get_emotion_emoji(emotion: str) -> str:
    """
    Get emoji for emotion.
    
    Args:
        emotion: Emotion string
    
    Returns:
        Emoji string
    """
    
    emotion_emojis = {
        'positivo': '😊',
        'negativo': '😞',
        'neutro': '😐',
        'feliz': '😄',
        'triste': '😢',
        'irritado': '😠',
        'ansioso': '😰',
        'calmo': '😌',
        'confuso': '😕',
        'surpreso': '😲',
    }
    
    return emotion_emojis.get(emotion.lower(), '😐')


def truncate_text(text: str, max_length: int = 100) -> str:
    """
    Truncate text to maximum length.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
    
    Returns:
        Truncated text
    """
    
    if len(text) <= max_length:
        return text
    
    return text[:max_length-3] + '...'
