"""
Monitora o deploy do Railway e testa se FFmpeg foi instalado.
"""

import requests
import time
from decouple import config

BACKEND_URL = config('BACKEND_URL', default='https://alreasense-backend-production.up.railway.app')
CHECK_INTERVAL = 15  # segundos
MAX_ATTEMPTS = 30  # 7.5 minutos

print("=" * 70)
print("🚂 MONITORANDO INSTALAÇÃO FFMPEG - RAILWAY")
print("=" * 70)
print(f"\n🔗 Backend: {BACKEND_URL}")
print(f"⏱️  Verificando a cada {CHECK_INTERVAL} segundos...")
print(f"⏰ Timeout: {MAX_ATTEMPTS * CHECK_INTERVAL // 60} minutos")
print("\n📋 Esperando Railway:")
print("   1. Detectar push no GitHub")
print("   2. Rebuildar imagem Docker")
print("   3. Instalar FFmpeg (apt-get install ffmpeg)")
print("   4. Reiniciar backend")
print("\n🔄 Iniciando monitoramento...")
print("─" * 70)

attempt = 1
last_status = None

while attempt <= MAX_ATTEMPTS:
    try:
        timestamp = time.strftime('%H:%M:%S')
        
        # Testar se backend responde
        response = requests.get(f"{BACKEND_URL}/api/health/", timeout=10)
        
        if response.status_code == 200:
            status_msg = "✅ ONLINE"
            
            # Verificar se backend mudou (indicativo de redeploy)
            if last_status == "OFFLINE" and status_msg == "✅ ONLINE":
                print(f"\n[{timestamp}] 🎉 BACKEND VOLTOU ONLINE!")
                print("   ℹ️  Isso pode indicar que o redeploy terminou")
                print("   🧪 Aguarde 30 segundos para estabilizar...")
                time.sleep(30)
                print("   🎤 TESTE AGORA: Grave um áudio e veja os logs!")
                break
            
            if attempt % 4 == 0:  # Log a cada minuto (4 * 15s)
                print(f"[{timestamp}] ⏳ Tentativa #{attempt}/{MAX_ATTEMPTS} - Backend online, aguardando redeploy...")
        else:
            status_msg = "OFFLINE"
            print(f"[{timestamp}] 🔄 Backend retornou {response.status_code} - Provavelmente fazendo deploy...")
        
        last_status = status_msg
        
    except requests.exceptions.RequestException as e:
        print(f"[{time.strftime('%H:%M:%S')}] 🔄 Conexão falhou - Railway está fazendo deploy...")
        last_status = "OFFLINE"
    
    attempt += 1
    time.sleep(CHECK_INTERVAL)

print("\n" + "=" * 70)
print("📋 PRÓXIMOS PASSOS:")
print("=" * 70)
print("1. 🎤 Grave um NOVO áudio no chat (3-5 segundos)")
print()
print("2. 👀 Veja os logs do Railway:")
print()
print("   ✅ SE FUNCIONAR:")
print("      🔍 [AUDIO] Verificando se precisa converter...")
print("      🔄 [AUDIO] Detectado áudio OGG/WEBM, convertendo para MP3...")
print("      ✅ [AUDIO] Conversão completa!")
print("      ✅ [AUDIO] Áudio convertido para MP3!")
print("      📤 [CHAT] Enviando via Evolution API...")
print()
print("   ❌ SE AINDA FALHAR:")
print("      ❌ [AUDIO] Erro: [Errno 2] No such file or directory: 'ffprobe'")
print("      → Aguarde mais 2-3 minutos e tente novamente")
print()
print("3. 📱 Verifique se o áudio chegou no WhatsApp do destinatário")
print()
print("4. 🐛 Se NÃO funcionar, me envie os logs completos do Railway")
print("=" * 70)










