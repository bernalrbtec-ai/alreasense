#!/usr/bin/env python
"""
Script de teste para diagnosticar problema de conexão RabbitMQ
"""
import os
import sys
import asyncio
import aio_pika
from urllib.parse import urlparse, quote, urlunparse

async def test_connection(url, description):
    """Testa uma URL de conexão"""
    print(f"\n{'='*80}")
    print(f"🔍 TESTANDO: {description}")
    print(f"{'='*80}")
    
    # Parse URL
    parsed = urlparse(url)
    
    print(f"Scheme: {parsed.scheme}")
    print(f"Username: {parsed.username}")
    print(f"Password length: {len(parsed.password) if parsed.password else 0}")
    print(f"Password has ~: {'~' in parsed.password if parsed.password else False}")
    print(f"Password has @: {'@' in parsed.password if parsed.password else False}")
    print(f"Hostname: {parsed.hostname}")
    print(f"Port: {parsed.port}")
    
    # Mask URL
    safe_url = url
    if parsed.password:
        safe_url = url.replace(parsed.password, '******')
    print(f"URL: {safe_url}")
    
    # Tentar conectar
    try:
        print(f"⏳ Conectando...")
        connection = await aio_pika.connect_robust(
            url,
            heartbeat=0,
            blocked_connection_timeout=0,
            socket_timeout=10,
            retry_delay=1,
            connection_attempts=1
        )
        print(f"✅ SUCESSO! Conexão estabelecida!")
        await connection.close()
        return True
    except Exception as e:
        print(f"❌ FALHA: {type(e).__name__}")
        print(f"   Erro: {str(e)}")
        return False

async def main():
    print("="*80)
    print("🧪 TESTE DE CONEXÃO RABBITMQ - DEBUG COMPLETO")
    print("="*80)
    
    # Ler variáveis de ambiente
    print("\n📋 VARIÁVEIS DE AMBIENTE:")
    print("-"*80)
    
    env_vars = {
        'RABBITMQ_URL': os.environ.get('RABBITMQ_URL'),
        'RABBITMQ_PRIVATE_URL': os.environ.get('RABBITMQ_PRIVATE_URL'),
        'RABBITMQ_DEFAULT_USER': os.environ.get('RABBITMQ_DEFAULT_USER'),
        'RABBITMQ_DEFAULT_PASS': os.environ.get('RABBITMQ_DEFAULT_PASS'),
    }
    
    for name, value in env_vars.items():
        if value:
            if 'PASS' in name or 'URL' in name:
                # Mask sensitive data
                display = value[:20] + '...' if len(value) > 20 else value
            else:
                display = value
            print(f"{name}: {display}")
        else:
            print(f"{name}: ❌ NÃO CONFIGURADA")
    
    # URLs para testar
    urls_to_test = []
    
    # 1. URL do settings (PRIVATE)
    if env_vars['RABBITMQ_PRIVATE_URL']:
        urls_to_test.append((
            env_vars['RABBITMQ_PRIVATE_URL'],
            "RABBITMQ_PRIVATE_URL (original)"
        ))
        
        # 2. Com URL encoding na senha
        parsed = urlparse(env_vars['RABBITMQ_PRIVATE_URL'])
        if parsed.password and ('~' in parsed.password or '@' in parsed.password):
            encoded_password = quote(parsed.password, safe='')
            netloc = f"{parsed.username}:{encoded_password}@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
            
            encoded_url = urlunparse((
                parsed.scheme,
                netloc,
                parsed.path or '/',
                parsed.params,
                parsed.query,
                parsed.fragment
            ))
            urls_to_test.append((
                encoded_url,
                "RABBITMQ_PRIVATE_URL (URL encoded password)"
            ))
    
    # 3. URL pública
    if env_vars['RABBITMQ_URL']:
        urls_to_test.append((
            env_vars['RABBITMQ_URL'],
            "RABBITMQ_URL (proxy público)"
        ))
    
    # 4. Construir manualmente com DEFAULT_USER e DEFAULT_PASS
    if env_vars['RABBITMQ_DEFAULT_USER'] and env_vars['RABBITMQ_DEFAULT_PASS']:
        manual_url = f"amqp://{env_vars['RABBITMQ_DEFAULT_USER']}:{env_vars['RABBITMQ_DEFAULT_PASS']}@rabbitmq.railway.internal:5672"
        urls_to_test.append((
            manual_url,
            "Construída manualmente (DEFAULT_USER + DEFAULT_PASS)"
        ))
        
        # 5. Construída manualmente COM encoding
        encoded_pass = quote(env_vars['RABBITMQ_DEFAULT_PASS'], safe='')
        manual_encoded_url = f"amqp://{env_vars['RABBITMQ_DEFAULT_USER']}:{encoded_pass}@rabbitmq.railway.internal:5672"
        urls_to_test.append((
            manual_encoded_url,
            "Construída manualmente (DEFAULT_USER + DEFAULT_PASS encoded)"
        ))
    
    # Testar todas as URLs
    results = []
    for url, description in urls_to_test:
        result = await test_connection(url, description)
        results.append((description, result))
        await asyncio.sleep(1)  # Esperar 1s entre testes
    
    # Resumo
    print("\n" + "="*80)
    print("📊 RESUMO DOS TESTES")
    print("="*80)
    for description, success in results:
        status = "✅ SUCESSO" if success else "❌ FALHA"
        print(f"{status}: {description}")
    
    print("\n" + "="*80)
    print("🎯 RECOMENDAÇÃO")
    print("="*80)
    
    successful = [desc for desc, success in results if success]
    if successful:
        print(f"✅ Use a configuração: {successful[0]}")
    else:
        print("❌ NENHUMA URL funcionou!")
        print("📋 Possíveis causas:")
        print("   1. Credenciais incorretas")
        print("   2. RabbitMQ não está rodando")
        print("   3. Rede não permite conexão")
        print("   4. Usuário não tem permissões")

if __name__ == '__main__':
    asyncio.run(main())

