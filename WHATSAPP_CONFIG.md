# 📱 Configuração do WhatsApp - Evolution API

## 🔑 Variáveis de Ambiente Necessárias

Configure estas variáveis no **Railway** (Backend):

```bash
# URL do servidor Evolution API
EVOLUTION_API_URL=https://evo.rbtec.com.br

# API Key GLOBAL do servidor (para criar novas instâncias)
EVOLUTION_API_KEY=<sua_chave_global_aqui>

# URL base do backend (para webhooks)
BASE_URL=https://alreasense-backend-production.up.railway.app
```

## 🔄 Fluxo Completo de Conexão

### 1️⃣ **Criação da Instância** (Cliente cria)
```
Cliente preenche:
- Nome Amigável: "Atendimento 01"
- Telefone: (opcional)
- Instância Padrão: ☐

Sistema gera automaticamente:
- UUID da instância: 6c663f61-e344-4296-ab7a-f4fd6844749e
- API URL: https://evo.rbtec.com.br (do settings)
```

### 2️⃣ **Geração do QR Code** (Cliente clica no botão QR)
```python
# Backend executa:
1. Usa EVOLUTION_API_KEY (global) para criar instância no servidor
   POST https://evo.rbtec.com.br/instance/create
   Headers: { 'apikey': EVOLUTION_API_KEY }
   
2. Servidor Evolution retorna API key específica da instância
   Response: { "apikey": "B6D711FCDE4D4FD5936544120E713976" }
   
3. Sistema salva essa API key no banco de dados
   instance.api_key = "B6D711FCDE4D4FD5936544120E713976"
   
4. Usa a API key DA INSTÂNCIA para gerar QR code
   GET https://evo.rbtec.com.br/instance/connect/{uuid}
   Headers: { 'apikey': instance.api_key }
   
5. Retorna QR code em base64 para o cliente
```

### 3️⃣ **Cliente Escaneia QR Code**
```
Cliente escaneia com WhatsApp
└─ Connection state muda para "connecting"
   └─ Ao conectar com sucesso, muda para "open"
```

### 4️⃣ **Verificação de Status** (Cliente clica em "Verificar Status")
```python
# Backend executa:
1. Usa API key DA INSTÂNCIA (não a global)
   GET https://evo.rbtec.com.br/instance/connectionState/{uuid}
   Headers: { 'apikey': instance.api_key }
   
2. Se conectado, busca informações do telefone
   GET https://evo.rbtec.com.br/instance/fetchInstances
   Headers: { 'apikey': instance.api_key }
   
3. Salva o número de telefone retornado
   instance.phone_number = "+5517991253112"
```

### 5️⃣ **Uso da Instância** (Enviar mensagens)
```python
# Backend executa:
Sempre usa API key DA INSTÂNCIA (nunca a global)
POST https://evo.rbtec.com.br/message/sendText/{uuid}
Headers: { 'apikey': instance.api_key }
Body: {
  "number": "5517991253112",
  "text": "Mensagem de teste"
}
```

## 🔐 Segurança

### API Key Global (EVOLUTION_API_KEY)
- ✅ Usada APENAS para criar novas instâncias
- ✅ Armazenada em variável de ambiente (segura)
- ✅ Nunca exposta ao frontend
- ✅ Tem permissões administrativas no servidor

### API Key da Instância
- ✅ Retornada pelo servidor ao criar a instância
- ✅ Criptografada no banco de dados (django-cryptography)
- ✅ Usada para todas as operações da instância
- ✅ Mostrada mascarada no frontend (••••••••••••••••••••)
- ✅ Pode ser revelada clicando no ícone do olho 👁️

## 📊 Logs de Auditoria

Todas as ações são registradas:
- ✅ `created` - Instância criada no Evolution API
- ✅ `qr_generated` - QR code gerado para conexão
- ✅ `connected` - Instância conectada com número X
- ✅ `disconnected` - Instância desconectada

## 🧪 Teste Local

Para testar localmente:

```bash
cd backend
python test_whatsapp_instance.py
```

Resultado esperado:
```
============================================================
🔍 TESTANDO generate_qr_code()
============================================================
📋 Configurações:
   - EVOLUTION_API_URL: https://evo.rbtec.com.br ✅
   - EVOLUTION_API_KEY: CONFIGURADO ✅

🔄 Chamando generate_qr_code()...
✅ QR Code gerado com sucesso!
   - Tamanho: 2847 caracteres
   - API Key salva: SIM ✅
   - Connection state: connecting
============================================================
```

## ❌ Erros Comuns

### "API key do sistema não configurada"
**Causa:** Variável `EVOLUTION_API_KEY` não está no Railway  
**Solução:** Adicionar a variável no Railway → Variables

### "URL da Evolution API não configurada"
**Causa:** Variável `EVOLUTION_API_URL` não está no Railway  
**Solução:** Adicionar a variável no Railway → Variables

### "Falha ao gerar QR code" (sem detalhes)
**Causa:** Erro de comunicação com o servidor Evolution  
**Solução:** Verificar se a URL está acessível e a API key é válida

## 🎯 Checklist de Configuração

- [ ] EVOLUTION_API_URL configurada no Railway
- [ ] EVOLUTION_API_KEY configurada no Railway
- [ ] BASE_URL configurada no Railway
- [ ] Servidor Evolution API acessível
- [ ] API key global do servidor válida
- [ ] Teste local executado com sucesso
- [ ] Deploy realizado
- [ ] Teste de criação de instância
- [ ] Teste de geração de QR code
- [ ] Teste de verificação de status
- [ ] Teste de envio de mensagem

