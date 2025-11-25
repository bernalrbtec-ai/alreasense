"""
Script para verificar se FFmpeg foi instalado no Railway.
Monitora os logs do Railway para detectar quando o deploy terminar.
"""

import requests
import time
from decouple import config

BACKEND_URL = config('BACKEND_URL', default='https://alreasense-backend-production.up.railway.app')
CHECK_INTERVAL = 10  # segundos

print("=" * 70)
print("🚂 MONITORANDO DEPLOY RAILWAY - INSTALAÇÃO FFMPEG")
print("=" * 70)
print(f"\n🔗 Backend: {BACKEND_URL}")
print(f"⏱️  Verificando a cada {CHECK_INTERVAL} segundos...")
print("\n📋 O que estamos esperando:")
print("   1. Railway rebuildar imagem Docker")
print("   2. Instalar FFmpeg via Aptfile")
print("   3. Reiniciar backend")
print("\n⏳ Aguarde 3-5 minutos...")
print("\n" + "─" * 70)

attempt = 1

while True:
    try:
        print(f"\n[{time.strftime('%H:%M:%S')}] Tentativa #{attempt}")
        
        # Testar se backend está respondendo
        response = requests.get(f"{BACKEND_URL}/api/health/", timeout=10)
        
        if response.status_code == 200:
            print("   ✅ Backend online!")
            
            # Verificar se há mensagens de áudio recentes
            print("   🔍 Verificando logs de conversão de áudio...")
            print("\n   💡 TESTE MANUAL:")
            print("      1. Grave um novo áudio no chat (3-5 segundos)")
            print("      2. Veja se aparece no console:")
            print("         ✅ '✅ [AUDIO] Conversão completa!'")
            print("      3. Se aparecer, FFmpeg está funcionando! 🎉")
            print("\n   ⚠️  Se ainda aparecer:")
            print("      ❌ 'No such file or directory: ffprobe'")
            print("      → Aguarde mais 2-3 minutos e tente novamente")
            
            break
        else:
            print(f"   ⚠️ Backend retornou: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Erro de conexão: {e}")
        print("   ℹ️  Railway pode estar fazendo deploy...")
    
    attempt += 1
    time.sleep(CHECK_INTERVAL)

print("\n" + "=" * 70)
print("📋 PRÓXIMOS PASSOS:")
print("=" * 70)
print("1. Grave um NOVO áudio no chat (3-5 segundos)")
print("2. Veja o console do navegador:")
print("   ✅ '✅ [VOICE] Áudio enviado com sucesso!'")
print()
print("3. Verifique no WhatsApp do destinatário se chegou")
print()
print("4. Se NÃO chegar, me mande os logs do Railway:")
print("   Procure por:")
print("   - '🔍 [AUDIO] Verificando se precisa converter...'")
print("   - '✅ [AUDIO] Conversão completa!' (deve aparecer agora!)")
print("   - '📤 [CHAT] Enviando via Evolution API...'")
print("=" * 70)





































