#!/usr/bin/env python
"""
🔍 DEBUG AVANÇADO: Por que Chat Consumer falha e Campaigns funciona?

Este script vai:
1. Ler todas as variáveis de ambiente RabbitMQ
2. Simular EXATAMENTE o que settings.py faz
3. Tentar conectar com aio-pika (como ambos consumers fazem)
4. Mostrar CADA byte das credenciais
"""
import os
import sys
import asyncio
from pathlib import Path
from urllib.parse import urlparse, quote

# Adicionar backend ao path
backend_path = Path(__file__).parent / 'backend'
sys.path.insert(0, str(backend_path))

# Importar settings depois de adicionar ao path
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
import django
django.setup()

from django.conf import settings
import aio_pika


def analyze_url(url_name, url):
    """Analisa uma URL RabbitMQ em detalhes"""
    print(f"\n{'='*80}")
    print(f"📋 ANALISANDO: {url_name}")
    print(f"{'='*80}")
    
    if not url or url == 'NOT_SET':
        print("❌ URL não configurada ou vazia")
        return None
    
    # Parse da URL
    parsed = urlparse(url)
    
    print(f"🔹 Scheme: {parsed.scheme}")
    print(f"🔹 Hostname: {parsed.hostname}")
    print(f"🔹 Port: {parsed.port}")
    print(f"🔹 Path: {parsed.path}")
    
    if parsed.username:
        print(f"\n🔐 CREDENCIAIS:")
        print(f"Username: {parsed.username}")
        print(f"Username Length: {len(parsed.username)}")
        print(f"Username Bytes: {parsed.username.encode()}")
        print(f"Username HEX: {parsed.username.encode().hex()}")
        
        # Verificar se tem caracteres especiais
        special_chars = []
        for char in parsed.username:
            if not char.isalnum():
                special_chars.append(f"'{char}' (ord={ord(char)})")
        if special_chars:
            print(f"⚠️ Username tem caracteres especiais: {', '.join(special_chars)}")
    
    if parsed.password:
        print(f"\nPassword: {'*' * len(parsed.password)}")
        print(f"Password Length: {len(parsed.password)}")
        print(f"Password Bytes: {len(parsed.password.encode())} bytes")
        
        # Mostrar APENAS os caracteres especiais da senha
        special_chars = []
        for i, char in enumerate(parsed.password):
            if not char.isalnum():
                special_chars.append(f"pos[{i}]='{char}' (ord={ord(char)})")
        if special_chars:
            print(f"⚠️ Password tem caracteres especiais: {', '.join(special_chars)}")
        
        # Verificar se já está URL encoded
        if '%' in parsed.password:
            print(f"⚠️ Password PARECE conter URL encoding (tem %)")
    
    # URL completa mascarada
    safe_url = url.replace(parsed.password, '***') if parsed.password else url
    safe_url = safe_url.replace(parsed.username, parsed.username[:4] + '***') if parsed.username else safe_url
    print(f"\n🔗 URL Mascarada: {safe_url}")
    print(f"📏 URL Length: {len(url)}")
    
    return parsed


async def test_connection(url_name, url):
    """Tenta conectar com uma URL específica"""
    print(f"\n{'='*80}")
    print(f"🧪 TESTANDO CONEXÃO: {url_name}")
    print(f"{'='*80}")
    
    if not url or url == 'NOT_SET':
        print("⏭️ Pulando - URL não configurada")
        return False
    
    try:
        print(f"⏳ Tentando conectar com aio_pika.connect_robust...")
        print(f"   Parâmetros: heartbeat=0, blocked_connection_timeout=0")
        print(f"   socket_timeout=10, retry_delay=1, connection_attempts=1")
        
        connection = await aio_pika.connect_robust(
            url,
            heartbeat=0,
            blocked_connection_timeout=0,
            socket_timeout=10,
            retry_delay=1,
            connection_attempts=1
        )
        
        print(f"✅ CONEXÃO ESTABELECIDA!")
        
        # Testar criar channel
        channel = await connection.channel()
        print(f"✅ CHANNEL CRIADO!")
        
        # Fechar
        await channel.close()
        await connection.close()
        print(f"✅ FECHADO COM SUCESSO")
        
        return True
        
    except Exception as e:
        error_str = str(e)
        print(f"❌ FALHOU: {error_str}")
        
        if 'ACCESS_REFUSED' in error_str or 'authentication' in error_str.lower():
            print(f"\n🚨 ERRO DE AUTENTICAÇÃO DETECTADO!")
            print(f"   Isso significa que:")
            print(f"   1. Usuário ou senha estão INCORRETOS")
            print(f"   2. OU as credenciais estão com encoding errado")
            print(f"   3. OU o usuário não tem permissões")
        
        return False


async def main():
    print("=" * 80)
    print("🔍 DIAGNÓSTICO AVANÇADO - RabbitMQ Chat Consumer vs Campaigns")
    print("=" * 80)
    
    # 1. Ler TODAS as variáveis de ambiente
    print("\n📋 PASSO 1: Variáveis de Ambiente Diretas")
    print("=" * 80)
    
    env_vars = {
        'RABBITMQ_PRIVATE_URL': os.environ.get('RABBITMQ_PRIVATE_URL', 'NOT_SET'),
        'RABBITMQ_URL': os.environ.get('RABBITMQ_URL', 'NOT_SET'),
        'CLOUDAMQP_URL': os.environ.get('CLOUDAMQP_URL', 'NOT_SET'),
        'RABBITMQ_DEFAULT_USER': os.environ.get('RABBITMQ_DEFAULT_USER', 'NOT_SET'),
        'RABBITMQ_DEFAULT_PASS': os.environ.get('RABBITMQ_DEFAULT_PASS', 'NOT_SET'),
    }
    
    for var_name, var_value in env_vars.items():
        is_set = var_value != 'NOT_SET'
        status = "✅ Configurada" if is_set else "❌ Não configurada"
        
        if 'PASS' in var_name and is_set:
            print(f"{var_name}: {status} (len={len(var_value)})")
        elif is_set and '@' in var_value:
            # É uma URL, mascarar
            safe = var_value.split('@')[0].split(':')[0] + ':***@' + var_value.split('@')[1]
            print(f"{var_name}: {status}")
            print(f"  → {safe}")
        else:
            print(f"{var_name}: {var_value}")
    
    # 2. O que settings.py vai usar?
    print("\n📋 PASSO 2: O que settings.py vai escolher?")
    print("=" * 80)
    
    print(f"settings.RABBITMQ_URL = {settings.RABBITMQ_URL.split('@')[0].split(':')[0]}:***@{settings.RABBITMQ_URL.split('@')[1] if '@' in settings.RABBITMQ_URL else 'NO_HOST'}")
    
    # 3. Analisar cada URL em detalhes
    print("\n📋 PASSO 3: Análise Detalhada de Cada URL")
    
    urls_to_analyze = {}
    
    if env_vars['RABBITMQ_PRIVATE_URL'] != 'NOT_SET':
        urls_to_analyze['RABBITMQ_PRIVATE_URL (env)'] = env_vars['RABBITMQ_PRIVATE_URL']
    
    if env_vars['RABBITMQ_URL'] != 'NOT_SET':
        urls_to_analyze['RABBITMQ_URL (env)'] = env_vars['RABBITMQ_URL']
    
    urls_to_analyze['settings.RABBITMQ_URL'] = settings.RABBITMQ_URL
    
    parsed_urls = {}
    for name, url in urls_to_analyze.items():
        parsed = analyze_url(name, url)
        if parsed:
            parsed_urls[name] = (url, parsed)
    
    # 4. Comparar credenciais
    print("\n📋 PASSO 4: Comparação de Credenciais")
    print("=" * 80)
    
    if len(parsed_urls) > 1:
        usernames = {name: parsed.username for name, (url, parsed) in parsed_urls.items()}
        passwords = {name: parsed.password for name, (url, parsed) in parsed_urls.items()}
        
        print("\n🔹 Comparação de Usernames:")
        unique_usernames = set(usernames.values())
        if len(unique_usernames) == 1:
            print(f"✅ TODOS IGUAIS")
        else:
            print(f"⚠️ DIFERENTES!")
            for name, user in usernames.items():
                print(f"   {name}: {user}")
        
        print("\n🔹 Comparação de Passwords (length):")
        password_lens = {name: len(pwd) for name, pwd in passwords.items()}
        unique_lens = set(password_lens.values())
        if len(unique_lens) == 1:
            print(f"✅ TODOS com mesmo tamanho ({list(unique_lens)[0]} chars)")
        else:
            print(f"⚠️ TAMANHOS DIFERENTES!")
            for name, pwd_len in password_lens.items():
                print(f"   {name}: {pwd_len} chars")
    
    # 5. Testar conexões
    print("\n📋 PASSO 5: Testes de Conexão")
    print("=" * 80)
    
    results = {}
    for name, url in urls_to_analyze.items():
        success = await test_connection(name, url)
        results[name] = success
    
    # 6. Resumo Final
    print("\n" + "=" * 80)
    print("🎯 RESUMO FINAL")
    print("=" * 80)
    
    print("\n📊 Resultados de Conexão:")
    for name, success in results.items():
        status = "✅ SUCESSO" if success else "❌ FALHOU"
        print(f"   {name}: {status}")
    
    # Identificar qual URL funcionou
    working_urls = [name for name, success in results.items() if success]
    failing_urls = [name for name, success in results.items() if not success]
    
    if working_urls and failing_urls:
        print(f"\n🔍 ANÁLISE:")
        print(f"   ✅ Funcionaram: {', '.join(working_urls)}")
        print(f"   ❌ Falharam: {', '.join(failing_urls)}")
        print(f"\n💡 RECOMENDAÇÃO:")
        print(f"   O Chat Consumer deveria usar: {working_urls[0]}")
    elif working_urls:
        print(f"\n✅ TODAS as URLs funcionaram!")
        print(f"   O problema NÃO é nas credenciais.")
    else:
        print(f"\n❌ NENHUMA URL funcionou!")
        print(f"   Problema nas credenciais do RabbitMQ.")
        print(f"\n📋 AÇÕES:")
        print(f"   1. Verificar se serviço RabbitMQ está rodando")
        print(f"   2. Regenerar credenciais no Railway")
        print(f"   3. Verificar logs do RabbitMQ no Railway")
    
    print("\n" + "=" * 80)


if __name__ == '__main__':
    asyncio.run(main())

