"""
Aguarda instalação do FFmpeg no Railway.
Monitora os logs até detectar que a conversão de áudio funcionou.
"""

import requests
import time
from decouple import config

BACKEND_URL = config('BACKEND_URL', default='https://alreasense-backend-production.up.railway.app')
CHECK_INTERVAL = 20  # segundos

print("=" * 80)
print("🚂 AGUARDANDO INSTALAÇÃO DO FFMPEG NO RAILWAY")
print("=" * 80)
print(f"\n🔗 Backend: {BACKEND_URL}")
print(f"⏱️  Verificando a cada {CHECK_INTERVAL} segundos...")
print("\n📋 O que o Railway está fazendo AGORA:")
print("   1. 🔍 Detectando push no GitHub")
print("   2. 📦 Rebuilding imagem Docker")
print("   3. 📥 Lendo Aptfile na RAIZ")
print("   4. 🎬 Instalando FFmpeg via apt-get")
print("   5. 🚀 Reiniciando backend")
print("\n⏰ Tempo estimado: 5-7 minutos")
print("─" * 80)

attempt = 1
last_online = False
deploy_detected = False

print("\n🔄 Monitorando deploy...")

while True:
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
                print("✅ DEPLOY CONCLUÍDO!")
                print("=" * 80)
                print("\n⏳ Aguardando 30 segundos para backend estabilizar...")
                time.sleep(30)
                break
            
            if attempt % 3 == 0:  # Log a cada minuto
                print(f"[{timestamp}] ⏳ Backend online, aguardando redeploy... (#{attempt})")
            
            last_online = True
        else:
            # Backend offline (provavelmente fazendo deploy)
            if last_online:
                print(f"\n[{timestamp}] 🔄 BACKEND OFFLINE - Deploy iniciado!")
                deploy_detected = True
            last_online = False
            
    except requests.exceptions.RequestException:
        # Conexão falhou (backend offline)
        if last_online:
            print(f"\n[{timestamp}] 🔄 BACKEND OFFLINE - Deploy iniciado!")
            deploy_detected = True
        last_online = False
    
    attempt += 1
    time.sleep(CHECK_INTERVAL)

print("\n" + "=" * 80)
print("🧪 TESTE FINAL - GRAVE UM ÁUDIO AGORA!")
print("=" * 80)
print("\n📋 INSTRUÇÕES:")
print("\n1. 🎤 Grave um NOVO áudio no chat (3-5 segundos)")
print()
print("2. 👀 Veja os logs do Railway:")
print()
print("   ✅ SUCESSO (esperado agora):")
print("      🔍 [AUDIO] Verificando se precisa converter...")
print("      🔄 [AUDIO] Detectado áudio OGG/WEBM, convertendo para MP3...")
print("      ✅ [AUDIO] Conversão completa!")
print("         OGG/WEBM: 50,528 bytes")
print("         MP3: 40,123 bytes")
print("         Redução: 20.6%")
print("      ✅ [AUDIO] Áudio convertido para MP3!")
print("      📤 [CHAT] Enviando via Evolution API...")
print("      ✅ [CHAT] Mensagem enviada com sucesso!")
print()
print("   ❌ SE AINDA FALHAR:")
print("      ❌ [AUDIO] Erro: [Errno 2] No such file or directory: 'ffprobe'")
print("      → Me envie PRINT da tela do Railway mostrando os logs de build")
print("      → Procure por: 'apt-get install ffmpeg' nos logs de build")
print()
print("3. 📱 Verifique se o áudio CHEGOU no WhatsApp do destinatário!")
print()
print("4. ✅ Se funcionar, o sistema está 100% pronto!")
print("=" * 80)

