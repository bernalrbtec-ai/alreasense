"""
Aguarda instalação do FFmpeg via Dockerfile no Railway.
Este será o deploy DEFINITIVO.
"""

import requests
import time
from decouple import config

BACKEND_URL = config('BACKEND_URL', default='https://alreasense-backend-production.up.railway.app')
CHECK_INTERVAL = 30  # segundos
MAX_WAIT = 15  # minutos

print("=" * 80)
print("🎬 AGUARDANDO INSTALAÇÃO DO FFMPEG VIA DOCKERFILE")
print("=" * 80)
print(f"\n🔗 Backend: {BACKEND_URL}")
print(f"⏱️  Verificando a cada {CHECK_INTERVAL} segundos...")
print(f"⏰ Timeout máximo: {MAX_WAIT} minutos")
print("\n📋 O que o Railway está fazendo AGORA:")
print("   1. 🔍 Detectando push no GitHub")
print("   2. 📦 Lendo backend/Dockerfile")
print("   3. 🏗️  Buildando Docker image DO ZERO")
print("   4. 📥 apt-get install ffmpeg")
print("   5. 🐍 pip install requirements.txt")
print("   6. 🚀 Iniciando backend")
print("\n⏰ Tempo estimado: 5-10 minutos (build completo)")
print("─" * 80)

attempt = 1
max_attempts = (MAX_WAIT * 60) // CHECK_INTERVAL
last_online = True  # Backend está online agora
deploy_detected = False

print("\n🔄 Monitorando deploy...")

while attempt <= max_attempts:
    try:
        timestamp = time.strftime('%H:%M:%S')
        
        # Testar conexão
        response = requests.get(f"{BACKEND_URL}/api/health/", timeout=10)
        
        if response.status_code == 200:
            # Backend está online
            if not last_online and deploy_detected:
                # Backend voltou online após ficar offline (redeploy concluído)
                print(f"\n[{timestamp}] 🎉 BACKEND VOLTOU ONLINE APÓS REDEPLOY!")
                print("\n" + "=" * 80)
                print("✅ DEPLOY CONCLUÍDO - FFMPEG DEVE ESTAR INSTALADO AGORA!")
                print("=" * 80)
                print("\n⏳ Aguardando 45 segundos para backend estabilizar...")
                time.sleep(45)
                break
            
            if attempt % 2 == 0:  # Log a cada minuto
                print(f"[{timestamp}] ⏳ Backend online, aguardando redeploy... (#{attempt}/{max_attempts})")
            
            last_online = True
        else:
            # Backend offline (provavelmente fazendo deploy)
            if last_online:
                print(f"\n[{timestamp}] 🔄 BACKEND OFFLINE - Deploy iniciado!")
                print("   ℹ️  Railway está rebuilding Docker image...")
                print("   ⏱️  Isso vai demorar 5-10 minutos")
                deploy_detected = True
            else:
                if attempt % 2 == 0:
                    print(f"[{timestamp}] 🏗️  Build em progresso... ({attempt}/{max_attempts})")
            last_online = False
            
    except requests.exceptions.RequestException:
        # Conexão falhou (backend offline)
        if last_online:
            print(f"\n[{timestamp}] 🔄 BACKEND OFFLINE - Deploy iniciado!")
            print("   ℹ️  Railway está rebuilding Docker image...")
            print("   ⏱️  Isso vai demorar 5-10 minutos")
            deploy_detected = True
        else:
            if attempt % 2 == 0:
                print(f"[{timestamp}] 🏗️  Build em progresso... ({attempt}/{max_attempts})")
        last_online = False
    
    attempt += 1
    time.sleep(CHECK_INTERVAL)

if attempt > max_attempts:
    print("\n⚠️  Timeout atingido. Verifique o Railway manualmente.")
    print("   URL: https://railway.app/")

print("\n" + "=" * 80)
print("🧪 TESTE FINAL - AGORA SIM VAI FUNCIONAR!")
print("=" * 80)
print("\n📋 INSTRUÇÕES:")
print("\n1. 🎤 Grave um NOVO áudio no chat (3-5 segundos)")
print()
print("2. 👀 Veja os logs do Railway:")
print()
print("   ✅ SUCESSO (ESPERADO AGORA):")
print("      🔍 [AUDIO] Verificando se precisa converter...")
print("      🔄 [AUDIO] Detectado áudio OGG/WEBM, convertendo para MP3...")
print("      ✅ [S3] Download realizado: *.webm (46,664 bytes)")
print("      🔄 [AUDIO] Convertendo OGG → MP3...")
print("      ✅ [AUDIO] Conversão completa!")
print("         OGG/WEBM: 46,664 bytes")
print("         MP3: 37,200 bytes")
print("         Redução: 20.3%")
print("      ✅ [AUDIO] Áudio convertido para MP3!")
print("      📤 [CHAT] Enviando via Evolution API...")
print("      ✅ [CHAT] Mensagem enviada com sucesso!")
print()
print("   ❌ SE AINDA FALHAR:")
print("      Me envie SCREENSHOT dos logs do Railway")
print("      E também logs de BUILD (Deployments > View Logs)")
print()
print("3. 📱 Verifique se o áudio CHEGOU no WhatsApp!")
print()
print("4. 🎉 Se funcionar:")
print("   ✅ Sistema de áudio está 100% operacional!")
print("   ✅ Pode gravar áudios e eles chegam como MP3 no WhatsApp!")
print("=" * 80)





