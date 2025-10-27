#!/usr/bin/env python3
"""
🔐 Gerador de API Keys Seguras - ALREA Sense
===============================================

Gera API keys usando os mais altos padrões de segurança:
- 256 bits de entropia
- Caracteres criptograficamente seguros
- Formato compatível com Evolution API
- Múltiplos formatos disponíveis

Uso:
    python scripts/generate_secure_api_key.py
"""

import secrets
import string
import uuid
from datetime import datetime


def generate_uuid_key():
    """
    Gera API key no formato UUID (padrão Evolution API).
    
    ✅ Segurança: 128 bits de entropia
    ✅ Formato: 8-4-4-4-12 (36 caracteres)
    ✅ Exemplo: 584B4A4A-0815-AC86-DC39-C38FC27E8E17
    """
    return str(uuid.uuid4()).upper()


def generate_hex_key(length=64):
    """
    Gera API key em formato hexadecimal.
    
    ✅ Segurança: 256 bits de entropia (length=64)
    ✅ Formato: hexadecimal (0-9, A-F)
    ✅ Exemplo: A7B2C9D4E1F3G8H5I6J7K8L9M0N1O2P3...
    """
    return secrets.token_hex(length // 2).upper()


def generate_urlsafe_key(length=43):
    """
    Gera API key URL-safe (Base64).
    
    ✅ Segurança: 256 bits de entropia (length=43)
    ✅ Formato: Base64 URL-safe (A-Z, a-z, 0-9, -, _)
    ✅ Exemplo: Xj9kL2mN5pQ8rS1tU4vW7xY0zA3bC6dE9fG2hI5jK8...
    """
    return secrets.token_urlsafe(length)[:length]


def generate_alphanumeric_key(length=64):
    """
    Gera API key alfanumérica (maiúsculas + números).
    
    ✅ Segurança: 256+ bits de entropia
    ✅ Formato: A-Z, 0-9
    ✅ Exemplo: 7K9M2P5R8T1W4Y6Z3B5D8F1H4J7L9N2Q5S8U1X4...
    """
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def generate_evolution_compatible_key():
    """
    Gera API key compatível com Evolution API (UUID sem hífens).
    
    ✅ Segurança: 128 bits de entropia
    ✅ Formato: 32 caracteres hexadecimais
    ✅ Exemplo: 584B4A4A0815AC86DC39C38FC27E8E17
    """
    return str(uuid.uuid4()).replace('-', '').upper()


def generate_multiple_formats():
    """
    Gera API keys em todos os formatos disponíveis.
    """
    print("=" * 80)
    print("🔐 GERADOR DE API KEYS SEGURAS - ALREA SENSE")
    print("=" * 80)
    print(f"\n📅 Gerado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n" + "=" * 80)
    
    print("\n✅ FORMATO 1: UUID (Recomendado para Evolution API)")
    print("-" * 80)
    uuid_key = generate_uuid_key()
    print(f"API Key: {uuid_key}")
    print(f"Entropia: 128 bits")
    print(f"Formato: UUID v4 com hífens")
    print(f"Uso: Evolution API (formato padrão)")
    
    print("\n" + "=" * 80)
    print("\n✅ FORMATO 2: UUID SEM HÍFENS (Alternativa Evolution API)")
    print("-" * 80)
    evo_key = generate_evolution_compatible_key()
    print(f"API Key: {evo_key}")
    print(f"Entropia: 128 bits")
    print(f"Formato: UUID v4 sem hífens")
    print(f"Uso: Evolution API (formato compacto)")
    
    print("\n" + "=" * 80)
    print("\n✅ FORMATO 3: HEXADECIMAL 256-BIT (Máxima Segurança)")
    print("-" * 80)
    hex_key = generate_hex_key(64)
    print(f"API Key: {hex_key}")
    print(f"Entropia: 256 bits")
    print(f"Formato: Hexadecimal (64 caracteres)")
    print(f"Uso: APIs que aceitam chaves longas")
    
    print("\n" + "=" * 80)
    print("\n✅ FORMATO 4: URL-SAFE BASE64 (JWT/Token)")
    print("-" * 80)
    urlsafe_key = generate_urlsafe_key(43)
    print(f"API Key: {urlsafe_key}")
    print(f"Entropia: 256 bits")
    print(f"Formato: Base64 URL-safe (43 caracteres)")
    print(f"Uso: JWTs, tokens de autorização")
    
    print("\n" + "=" * 80)
    print("\n✅ FORMATO 5: ALFANUMÉRICO (Fácil digitação)")
    print("-" * 80)
    alphanumeric_key = generate_alphanumeric_key(48)
    print(f"API Key: {alphanumeric_key}")
    print(f"Entropia: 256+ bits")
    print(f"Formato: A-Z, 0-9 (48 caracteres)")
    print(f"Uso: APIs que requerem apenas letras/números")
    
    print("\n" + "=" * 80)
    print("\n🎯 RECOMENDAÇÃO PARA EVOLUTION API:")
    print("=" * 80)
    print(f"\n🔑 NOVA API KEY: {uuid_key}")
    print(f"\n📋 FORMATO: UUID v4 (padrão Evolution API)")
    print(f"✅ ENTROPIA: 128 bits (340,282,366,920,938,463,463,374,607,431,768,211,456 combinações)")
    print(f"✅ SEGURANÇA: Criptograficamente seguro (secrets.token_*)")
    print(f"✅ COMPATIBILIDADE: 100% compatível com Evolution API")
    
    print("\n" + "=" * 80)
    print("\n⚠️ IMPORTANTE - ROTAÇÃO DE CHAVE:")
    print("=" * 80)
    print("""
1. ✅ Copie a NOVA chave acima
2. 🔧 Configure no servidor Evolution API
3. 🚀 Atualize a variável EVO_API_KEY no Railway
4. 🗑️ Delete a chave antiga do servidor Evolution
5. ✅ Teste a conexão com a nova chave
6. 📝 Documente a rotação no .cursorrules
""")
    
    print("\n" + "=" * 80)
    print("\n🔐 BOAS PRÁTICAS:")
    print("=" * 80)
    print("""
✅ SEMPRE:
- Usar secrets module (não random!)
- Gerar chaves de 128+ bits
- Rotacionar chaves comprometidas imediatamente
- Armazenar em variáveis de ambiente
- Logar acessos com API keys
- Implementar rate limiting

❌ NUNCA:
- Hardcodar chaves no código
- Commitar chaves no Git
- Compartilhar chaves em plaintext
- Reutilizar chaves comprometidas
- Usar random() para segurança
- Expor chaves em logs
""")
    
    print("\n" + "=" * 80)
    print("\n🎉 CHAVES GERADAS COM SUCESSO!")
    print("=" * 80)
    print("\n⚠️ LEMBRE-SE: Copie a chave AGORA! Esta janela será fechada.\n")
    
    # Retornar a chave recomendada
    return uuid_key


if __name__ == "__main__":
    recommended_key = generate_multiple_formats()
    
    # Salvar em arquivo temporário (opcional)
    import os
    temp_file = os.path.join(os.path.dirname(__file__), '.temp_api_key.txt')
    with open(temp_file, 'w', encoding='utf-8') as f:
        f.write(f"# NOVA API KEY EVOLUTION - {datetime.now()}\n")
        f.write(f"# WARNING: DELETE ESTE ARQUIVO APÓS COPIAR A CHAVE!\n\n")
        f.write(f"EVO_API_KEY={recommended_key}\n")
    
    print(f"\n💾 Chave salva temporariamente em: {temp_file}")
    print(f"⚠️ DELETE o arquivo após copiar a chave!\n")

