"""
Script para verificar se o backend está processando áudio corretamente.
Verifica:
1. Se FFmpeg está instalado
2. Se a conversão OGG → MP3 está funcionando
3. Se o envio para Evolution API está acontecendo
"""

import os
from decouple import config

print("=" * 60)
print("🔍 DIAGNÓSTICO: BACKEND AUDIO PROCESSING")
print("=" * 60)

# 1. Verificar se FFmpeg está disponível
print("\n1️⃣ Verificando FFmpeg...")
import subprocess

try:
    result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
    if result.returncode == 0:
        print("   ✅ FFmpeg instalado!")
        # Pegar primeira linha (versão)
        version_line = result.stdout.split('\n')[0]
        print(f"   📦 {version_line}")
    else:
        print("   ❌ FFmpeg não encontrado!")
except FileNotFoundError:
    print("   ❌ FFmpeg não encontrado no PATH!")

# 2. Testar conversão OGG → MP3
print("\n2️⃣ Testando conversão de áudio...")
try:
    from pydub import AudioSegment
    print("   ✅ pydub importado com sucesso!")
    
    # Testar se pydub consegue acessar FFmpeg
    try:
        AudioSegment.converter = 'ffmpeg'
        print("   ✅ pydub configurado para usar FFmpeg")
    except Exception as e:
        print(f"   ⚠️ Erro ao configurar pydub: {e}")
        
except ImportError as e:
    print(f"   ❌ pydub não instalado: {e}")

# 3. Verificar últimas mensagens de áudio no banco
print("\n3️⃣ Verificando mensagens de áudio no banco...")
print("   Conectando ao Railway PostgreSQL...")

import psycopg2

try:
    # Conectar ao Railway
    conn = psycopg2.connect(
        host=config('RAILWAY_DB_HOST', default=''),
        port=config('RAILWAY_DB_PORT', default='5432'),
        database=config('RAILWAY_DB_NAME', default=''),
        user=config('RAILWAY_DB_USER', default=''),
        password=config('RAILWAY_DB_PASSWORD', default='')
    )
    
    cursor = conn.cursor()
    
    # Buscar últimas 5 mensagens de áudio
    cursor.execute("""
        SELECT 
            m.id,
            m.created_at,
            m.status,
            a.original_filename,
            a.mime_type,
            a.size_bytes,
            LEFT(a.file_url, 100) as file_url_preview
        FROM chat_message m
        LEFT JOIN chat_attachment a ON m.id = a.message_id
        WHERE a.is_audio = true
        ORDER BY m.created_at DESC
        LIMIT 5
    """)
    
    rows = cursor.fetchall()
    
    if rows:
        print(f"\n   ✅ Encontradas {len(rows)} mensagens de áudio recentes:\n")
        for row in rows:
            msg_id, created_at, status, filename, mime, size, url = row
            print(f"   📨 Mensagem: {msg_id}")
            print(f"      Data: {created_at}")
            print(f"      Status: {status}")
            print(f"      Arquivo: {filename}")
            print(f"      Tipo: {mime}")
            print(f"      Tamanho: {size:,} bytes")
            print(f"      URL: {url}...")
            print()
    else:
        print("   ⚠️ Nenhuma mensagem de áudio encontrada")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"   ❌ Erro ao conectar no banco: {e}")

print("\n" + "=" * 60)
print("📋 PRÓXIMOS PASSOS:")
print("=" * 60)
print("1. Se FFmpeg NÃO estiver instalado:")
print("   → Aguarde 2-3 minutos para Railway terminar deploy")
print("   → Rode este script novamente")
print()
print("2. Se FFmpeg estiver instalado MAS áudio não chega:")
print("   → Verifique os logs do Railway:")
print("   → railway logs --service backend")
print()
print("3. Procure por estas mensagens nos logs:")
print("   → '🔍 [AUDIO] Verificando se precisa converter...'")
print("   → '🔄 [AUDIO] Convertendo OGG → MP3...'")
print("   → '✅ [AUDIO] Conversão completa!'")
print("   → '📤 [CHAT] Enviando via Evolution API...'")
print("=" * 60)












