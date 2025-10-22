"""
Script para reduzir logs do webhook e evitar rate limit do Railway.

Mudanças:
- Remove logs verbosos de INFO
- Mantém apenas WARNING e ERROR
- Loga apenas o essencial: erros e eventos importantes
"""
import re

# Ler arquivo atual
with open('backend/apps/chat/webhooks.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Logs que devem ser REMOVIDOS (muito verbosos)
logs_to_remove = [
    r'logger\.info\(f"📥 \[WEBHOOK UPSERT\] ====== INICIANDO PROCESSAMENTO ======"\)',
    r'logger\.info\(f"📥 \[WEBHOOK UPSERT\] Tenant: \{tenant\.name\} \(ID: \{tenant\.id\}\)"\)',
    r'logger\.info\(f"📥 \[WEBHOOK UPSERT\] Dados recebidos: \{data\}"\)',
    r'logger\.info\(f"📱 \[WEBHOOK UPSERT\] Instância: \{instance_name\}"\)',
    r'logger\.info\(f"🔍 \[TIPO\] Conversa: \{conversation_type\} \| RemoteJID: \{remote_jid\}"\)',
    r'logger\.info\(f"👥 \[GRUPO\] Enviado por: \{sender_name\} \(\{sender_phone\}\)"\)',
    r'logger\.info\(f"\{direction_str\} \[WEBHOOK\] \{phone\}: \{content\[:50\]\}\.\.\."\)',
    r'logger\.info\(f"   Tenant: \{tenant\.name\} \| Message ID: \{message_id\}"\)',
    r'logger\.info\(f"   👤 Nome: \{push_name\} \| 📸 Foto de Perfil: \{profile_pic_url\[:100\] if profile_pic_url else \'NÃO ENVIADA\'\}"\)',
    r'logger\.info\(f"📋 \[CONVERSA\] \{\'NOVA\' if created else \'EXISTENTE\'\}: \{phone\} \| Tipo: \{conversation_type\}"\)',
    r'logger\.info\(f"✅ \[WEBHOOK\] Nova conversa criada: \{phone\} \(Inbox\)"\)',
    r'logger\.info\(f"📸 \[FOTO\] Iniciando busca\.\.\. \| Tipo: \{conversation_type\} \| É grupo: \{is_group\}"\)',
    r'logger\.info\(f"📸 \[WEBHOOK\] Buscando foto de perfil\.\.\."\)',
    r'logger\.info\(f"👥 \[GRUPO NOVO\] Buscando informações com Group JID: \{group_jid\}"\)',
    r'logger\.info\(f"✅ \[GRUPO NOVO\] Informações recebidas!"\)',
    r'logger\.info\(f"✅ \[GRUPO NOVO\] Nome: \{group_name\}"\)',
    r'logger\.info\(f"✅ \[GRUPO NOVO\] Foto: \{group_pic_url\[:50\]\}\.\.\."\)',
    r'logger\.info\(f"👤 \[INDIVIDUAL\] Buscando informações do contato: \{clean_phone\}"\)',
    r'logger\.info\(f"✅ \[INDIVIDUAL\] Foto encontrada: \{profile_url\[:50\]\}\.\.\."\)',
    r'logger\.info\(f"ℹ️ \[INDIVIDUAL\] Foto não disponível"\)',
    r'logger\.info\(f"👤 \[INDIVIDUAL\] Nome vazio, buscando na API\.\.\."\)',
    r'logger\.info\(f"✅ \[INDIVIDUAL\] Nome encontrado via API: \{contact_name\}"\)',
    r'logger\.info\(f"ℹ️ \[INDIVIDUAL\] Nome não disponível, usando número"\)',
    r'logger\.info\(f"✅ \[INDIVIDUAL\] Conversa atualizada: \{

\', \'.join\(update_fields\)\}"\)',
    r'logger\.info\(f"ℹ️ \[WEBHOOK\] Nenhuma instância Evolution ativa para buscar foto"\)',
]

print("🔧 Reduzindo logs do webhook...")
print(f"📊 Tamanho original: {len(content)} bytes\n")

# Remover logs verbosos
for log_pattern in logs_to_remove:
    # Encontrar e comentar ao invés de deletar (para poder reverter se necessário)
    content = re.sub(
        r'(\s+)' + log_pattern,
        r'\1# ' + log_pattern.replace(r'\.', '.'),  # Comentar linha
        content
    )

print(f"📊 Tamanho depois: {len(content)} bytes\n")

# Salvar
with open('backend/apps/chat/webhooks.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Logs reduzidos com sucesso!")
print("\n📋 Logs que PERMANECEM (apenas importantes):")
print("   ✅ logger.error() - Erros")
print("   ✅ logger.warning() - Avisos")
print("   ⚠️  logger.info() removidos - Info verboso")
print("\n💡 Teste e reverta se necessário (os logs foram comentados, não deletados)")

