# 📋 CHANGELOG - Ambiente Local e Melhorias WhatsApp

## 🗓️ Data: 09/10/2025

---

## ✨ NOVAS FUNCIONALIDADES

### 🐳 **Ambiente Docker Local Completo**
- ✅ PostgreSQL 16 + pgvector (porta 5432)
- ✅ Redis 7 (porta 6379)
- ✅ Backend Django (porta 8000)
- ✅ Frontend React + Vite (porta 5173)
- ✅ Celery Worker
- ✅ Celery Beat
- ✅ Volumes persistentes para dados
- ✅ Health checks automáticos
- ✅ Documentação completa

### 📱 **WhatsApp Instance - UX Melhorada**

#### **1. API Key Visível com Toggle**
- Mostra API Key mascarada: `••••••••••••••••`
- Botão olhinho (👁️) para mostrar/ocultar
- Substitui UUID inútil que aparecia antes
- Font monospace para melhor visualização

#### **2. Auto-Update de Status**
- Polling automático a cada 3 segundos após gerar QR
- Detecta quando WhatsApp conecta
- Modal fecha automaticamente quando conectar
- Toast de sucesso: "🎉 WhatsApp conectado!"
- Busca número de telefone automaticamente
- Atualiza lista de instâncias

#### **3. Botão Enviar Teste**
- Novo botão 📱 (MessageSquare) nos cards
- Abre modal para enviar mensagem de teste
- Pede número de telefone (DDI completo)
- Pré-preenche com número da instância se disponível
- Mostra mensagem que será enviada
- **Habilitado APENAS se instância conectada** (`connection_state === 'open'`)

#### **4. Controle Inteligente de Botões**
- **Teste** e **Desconectar**: Só habilitados se conectado
- Feedback visual: botões ficam cinzas quando desabilitados
- Tooltips explicativos quando hover
- Cursor `not-allowed` quando desabilitado

---

## 🐛 CORREÇÕES DE BUGS

### **Backend**

#### **Migration 0011: api_key Nullable**
- **Problema**: `IntegrityError: null value in column "api_key" violates not-null constraint`
- **Solução**: Campo `api_key` agora aceita `null`
- **Motivo**: API key só é obtida APÓS criar instância na Evolution API

#### **Delete Evolution API**
- **Problema**: Deletar instância do sistema não deletava da Evolution API
- **Solução**: Override `perform_destroy` para chamar `/instance/delete/{name}` antes
- **Padrão**: whatsapp-orchestrator - sempre deletar da API externa primeiro

### **Frontend**

#### **QR Code - Prefixo Duplicado**
- **Problema**: `data:image/png;base64,data:image/png;base64,iVBORw...`
- **Solução**: Detectar se backend já retorna com prefixo antes de adicionar
- **Código**: 
  ```typescript
  qr_code.startsWith('data:') ? qr_code : `data:image/png;base64,${qr_code}`
  ```

#### **Modal QR - Erro null.id**
- **Problema**: `Cannot read properties of null (reading 'id')` ao clicar "Atualizar QR"
- **Solução**: Salvar `qrInstance` no estado ao gerar QR
- **Motivo**: `editingInstance` estava null no contexto do modal

---

## 📁 ARQUIVOS CRIADOS

### **Docker**
- ✅ `docker-compose.local.yml` - Orquestração completa
- ✅ `backend/Dockerfile.local` - Backend otimizado
- ✅ `frontend/Dockerfile.local` - Frontend otimizado
- ✅ `.dockerignore` - Otimização de build

### **Documentação**
- ✅ `README.local.md` - Guia completo Docker
- ✅ `AMBIENTE_LOCAL_PRONTO.md` - Resumo rápido
- ✅ `GUIA_TESTE_LOCAL.md` - Passo a passo de testes
- ✅ `CHANGELOG_LOCAL.md` - Este arquivo

### **Migrations**
- ✅ `0011_fix_api_key_nullable.py` - Torna api_key nullable

---

## 🔧 ARQUIVOS MODIFICADOS

### **Backend**
- `apps/notifications/models.py` - API key nullable
- `apps/notifications/views.py` - Delete Evolution API

### **Frontend**
- `src/pages/ConnectionsPage.tsx` - Todas as melhorias de UX

---

## 📊 RESUMO TÉCNICO

### **Padrão whatsapp-orchestrator Implementado**
1. **API Master Global**: Servidor Evolution configurado no admin
2. **API Key Específica**: Cada instância tem sua própria key
3. **Operações Admin**: Usar API Master (create, delete, status)
4. **Operações Cliente**: Usar API Key da instância (send message)
5. **Delete Cascade**: Deletar da Evolution API antes do banco

### **Fluxo Correto**
```
1. Configurar Servidor Evolution (Admin) → API Master
2. Criar Instância (Django) → Salva no banco local
3. Gerar QR Code → Cria na Evolution API + captura API Key
4. Escanear QR → Conecta WhatsApp
5. Auto-update → Sistema detecta conexão + busca número
6. Enviar Teste → Usa API Key da instância
7. Deletar → Remove da Evolution API + remove do banco
```

---

## 🚀 PRÓXIMOS PASSOS

### **Teste Local**
- [ ] Criar instância
- [ ] Gerar QR Code
- [ ] Conectar WhatsApp
- [ ] Ver API Key (olhinho)
- [ ] Enviar teste
- [ ] Desconectar
- [ ] Deletar

### **Deploy para Railway**
- [ ] Garantir que tudo funciona 100% local
- [ ] Fazer commit final
- [ ] Push para GitHub
- [ ] Aguardar Railway processar
- [ ] Testar em produção

---

## 💡 COMANDOS ÚTEIS

### Reiniciar Frontend (mudanças React)
```bash
docker-compose -f docker-compose.local.yml restart frontend
```

### Rebuild Frontend (mudanças grandes)
```bash
docker-compose -f docker-compose.local.yml up -d --build frontend
```

### Ver logs em tempo real
```bash
docker-compose -f docker-compose.local.yml logs -f backend
```

### Parar tudo
```bash
docker-compose -f docker-compose.local.yml down
```

### Resetar banco (CUIDADO!)
```bash
docker-compose -f docker-compose.local.yml down -v
docker-compose -f docker-compose.local.yml up -d --build
```

---

## 🎯 STATUS ATUAL

| Funcionalidade | Status | Testado |
|----------------|--------|---------|
| Ambiente Docker Local | ✅ Funcionando | ✅ Sim |
| PostgreSQL + pgvector | ✅ Funcionando | ✅ Sim |
| Redis | ✅ Funcionando | ✅ Sim |
| Backend Django | ✅ Funcionando | ✅ Sim |
| Frontend React | ✅ Funcionando | ✅ Sim |
| Criar Instância | ✅ Funcionando | ✅ Sim |
| Gerar QR Code | ✅ Funcionando | ✅ Sim |
| Auto-update Status | ✅ Implementado | ⏳ Aguardando teste |
| API Key Display | ✅ Implementado | ⏳ Aguardando teste |
| Botão Teste | ✅ Implementado | ⏳ Aguardando teste |
| Deletar da Evo | ✅ Implementado | ⏳ Aguardando teste |

---

**Desenvolvido com 💙 por Alrea Sense Team**

