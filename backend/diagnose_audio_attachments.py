"""
🔍 DIAGNÓSTICO DE ANEXOS DE ÁUDIO

Este script verifica:
1. Se anexos de áudio estão sendo criados
2. Se file_url está sendo atualizada após download
3. Se arquivos estão sendo salvos localmente
4. Se formato está correto para navegador
"""
import os
import django
import sys

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.chat.models import MessageAttachment, Message
from django.utils import timezone
from datetime import timedelta

print("=" * 80)
print("🔍 DIAGNÓSTICO DE ANEXOS DE ÁUDIO")
print("=" * 80)

# Buscar anexos de áudio recentes (últimas 24h)
recent_audios = MessageAttachment.objects.filter(
    mime_type__startswith='audio/',
    created_at__gte=timezone.now() - timedelta(hours=24)
).select_related('message', 'tenant').order_by('-created_at')[:10]

print(f"\n📊 Total de áudios nas últimas 24h: {recent_audios.count()}")
print()

if not recent_audios:
    print("❌ Nenhum anexo de áudio encontrado nas últimas 24 horas!")
    print("\n🔍 POSSÍVEIS CAUSAS:")
    print("   1. Nenhum áudio foi recebido")
    print("   2. Webhook não está criando MessageAttachment para áudios")
    sys.exit(1)

for i, audio in enumerate(recent_audios, 1):
    print(f"\n{'=' * 80}")
    print(f"🎵 ÁUDIO #{i}")
    print(f"{'=' * 80}")
    
    # Informações básicas
    print(f"📌 ID: {audio.id}")
    print(f"📅 Criado em: {audio.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"👤 Tenant: {audio.tenant.name}")
    print(f"📝 Nome do arquivo: {audio.original_filename}")
    print(f"🎭 MIME type: {audio.mime_type}")
    print(f"📦 Storage type: {audio.storage_type}")
    
    # Status do download
    print(f"\n🔗 URLs:")
    print(f"   Original (WhatsApp): {audio.file_url[:100]}...")
    
    # Verificar se URL foi atualizada
    is_whatsapp_url = 'mmg.whatsapp.net' in audio.file_url or 'media-' in audio.file_url
    is_local_url = audio.file_url.startswith('/api/chat/attachments/')
    is_s3_url = 's3.amazonaws.com' in audio.file_url or 'minio' in audio.file_url or 'bucket-production' in audio.file_url
    
    print(f"\n🔍 ANÁLISE DA URL:")
    if is_whatsapp_url:
        print(f"   ❌ URL ainda aponta para WhatsApp (download NÃO processado!)")
        print(f"   ⚠️ PROBLEMA: Task download_attachment não rodou ou falhou!")
    elif is_local_url:
        print(f"   ✅ URL atualizada para local: {audio.file_url}")
        print(f"   📂 Caminho local: {audio.file_path}")
        
        # Verificar se arquivo existe
        if audio.file_path:
            import os
            if os.path.exists(audio.file_path):
                file_size = os.path.getsize(audio.file_path)
                print(f"   ✅ Arquivo existe no disco ({file_size / 1024:.2f} KB)")
                
                # Verificar formato
                ext = audio.file_path.split('.')[-1].lower()
                print(f"   📄 Extensão: .{ext}")
                
                if ext == 'ogg':
                    print(f"   ⚠️ PROBLEMA: Formato .ogg pode não ser suportado em todos os navegadores!")
                    print(f"   💡 SOLUÇÃO: Converter para .mp3 ou .m4a")
                elif ext == 'opus':
                    print(f"   ⚠️ PROBLEMA: Codec OPUS pode não ser suportado!")
                    print(f"   💡 SOLUÇÃO: Converter para .mp3 ou usar .ogg com codec vorbis")
                elif ext in ['mp3', 'm4a', 'aac']:
                    print(f"   ✅ Formato compatível com navegadores!")
            else:
                print(f"   ❌ Arquivo NÃO existe no caminho: {audio.file_path}")
                print(f"   ⚠️ PROBLEMA: Download completou mas arquivo foi deletado!")
        else:
            print(f"   ⚠️ file_path vazio!")
    elif is_s3_url:
        print(f"   ✅ URL aponta para S3: {audio.file_url[:100]}...")
        print(f"   📦 Storage: S3/MinIO")
    else:
        print(f"   ❓ URL desconhecida: {audio.file_url[:100]}...")
    
    # Mensagem associada
    msg = audio.message
    print(f"\n📨 Mensagem:")
    print(f"   ID: {msg.id}")
    print(f"   Direção: {msg.direction}")
    print(f"   Conteúdo: {msg.content[:50] if msg.content else '[Áudio]'}")
    
    # Verificar se há erro
    if hasattr(audio, 'error_message') and audio.error_message:
        print(f"\n❌ ERRO REGISTRADO:")
        print(f"   {audio.error_message}")

print("\n" + "=" * 80)
print("🎯 RESUMO")
print("=" * 80)

# Contar status
total = recent_audios.count()
whatsapp_urls = sum(1 for a in recent_audios if 'mmg.whatsapp.net' in a.file_url or 'media-' in a.file_url)
local_urls = sum(1 for a in recent_audios if a.file_url.startswith('/api/chat/attachments/'))
s3_urls = sum(1 for a in recent_audios if 's3.amazonaws.com' in a.file_url or 'minio' in a.file_url or 'bucket-production' in a.file_url)

print(f"\n📊 ESTATÍSTICAS:")
print(f"   Total: {total}")
print(f"   ❌ Ainda no WhatsApp: {whatsapp_urls} ({whatsapp_urls/total*100:.1f}%)")
print(f"   ✅ Local (Railway): {local_urls} ({local_urls/total*100:.1f}%)")
print(f"   ✅ S3/MinIO: {s3_urls} ({s3_urls/total*100:.1f}%)")

if whatsapp_urls > 0:
    print(f"\n⚠️ PROBLEMA IDENTIFICADO!")
    print(f"   {whatsapp_urls} áudio(s) não foram processados pela task download_attachment")
    print()
    print("🔧 POSSÍVEIS CAUSAS:")
    print("   1. RabbitMQ Consumer (chat) não está rodando")
    print("   2. Task download_attachment está falhando")
    print("   3. Task está em fila mas não foi processada")
    print()
    print("🔍 PRÓXIMOS PASSOS:")
    print("   1. Verificar logs do backend: railway logs")
    print("   2. Procurar por '[DOWNLOAD]' nos logs")
    print("   3. Verificar se há mensagens de erro")
    print("   4. Verificar se consumer está rodando: grep 'Flow Chat Consumer'")
else:
    print(f"\n✅ Todos os áudios foram processados com sucesso!")
    print()
    print("🔍 Mas ainda há erro no frontend?")
    print("   Possíveis causas:")
    print("   1. Formato de áudio não suportado (.ogg com opus)")
    print("   2. CORS bloqueando acesso")
    print("   3. URL de download retornando erro 404/403")

print("\n" + "=" * 80)
print("✅ Diagnóstico concluído!")
print("=" * 80)

