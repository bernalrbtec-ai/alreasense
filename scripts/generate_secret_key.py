#!/usr/bin/env python
"""
Script para gerar uma SECRET_KEY segura para o Django.
Uso: python scripts/generate_secret_key.py
"""

from django.core.management.utils import get_random_secret_key

if __name__ == '__main__':
    secret_key = get_random_secret_key()
    print("\n" + "="*60)
    print("Django SECRET_KEY gerada:")
    print("="*60)
    print(f"\n{secret_key}\n")
    print("="*60)
    print("\nAdicione esta chave à variável DJANGO_SECRET_KEY")
    print("nas configurações de ambiente da Railway.")
    print("="*60 + "\n")

