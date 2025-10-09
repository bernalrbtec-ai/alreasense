# 🎉 AMBIENTE LOCAL DOCKER - PRONTO PARA USAR!

## ✅ STATUS: **TUDO RODANDO PERFEITAMENTE!**

---

## 📋 **SERVIÇOS ATIVOS**

| Serviço | Container | Status | URL/Porta |
|---------|-----------|--------|-----------|
| **PostgreSQL** | `alrea_sense_db_local` | ✅ Rodando | `localhost:5432` |
| **Redis** | `alrea_sense_redis_local` | ✅ Rodando | `localhost:6379` |
| **Backend Django** | `alrea_sense_backend_local` | ✅ Rodando | http://localhost:8000 |
| **Celery Worker** | `alrea_sense_celery_local` | ✅ Rodando | - |
| **Celery Beat** | `alrea_sense_celery_beat_local` | ✅ Rodando | - |
| **Frontend React** | `alrea_sense_frontend_local` | ✅ Rodando | http://localhost:5173 |

---

## 🔑 **CREDENCIAIS DE ACESSO**

### **Django Admin**
- URL: http://localhost:8000/admin
- Username: `admin@alreasense.com`
- Password: `admin123`

### **PostgreSQL**
- Host: `localhost`
- Port: `5432`
- Database: `alrea_sense_local`
- User: `postgres`
- Password: `postgres`

### **Redis**
- Host: `localhost`
- Port: `6379`

---

## 🚀 **COMO USAR**

### **Iniciar o Ambiente**
```bash
docker-compose -f docker-compose.local.yml up -d
```

### **Parar o Ambiente**
```bash
docker-compose -f docker-compose.local.yml down
```

### **Ver Logs**
```bash
# Todos os serviços
docker-compose -f docker-compose.local.yml logs -f

# Serviço específico
docker-compose -f docker-compose.local.yml logs -f backend
docker-compose -f docker-compose.local.yml logs -f frontend
```

### **Executar Comandos Django**
```bash
# Migrations
docker-compose -f docker-compose.local.yml exec backend python manage.py migrate

# Shell Django
docker-compose -f docker-compose.local.yml exec backend python manage.py shell

# Criar superusuário adicional
docker-compose -f docker-compose.local.yml exec backend python manage.py createsuperuser
```

### **Resetar Banco de Dados (CUIDADO!)**
```bash
# Para e remove volumes (perde dados)
docker-compose -f docker-compose.local.yml down -v

# Sobe novamente (banco limpo)
docker-compose -f docker-compose.local.yml up -d --build
```

---

## 📝 **PRÓXIMOS PASSOS**

### **1. Configurar Servidor Evolution API**

1. Acesse: http://localhost:8000/admin
2. Login: `admin@alreasense.com` / `admin123`
3. Navegue: **Connections → Evolution connections**
4. Clique: **Add Evolution Connection**
5. Preencha:
   - **Name**: `Evolution RBTec`
   - **Base URL**: `https://evo.rbtec.com.br`
   - **API Key**: `[SUA_CHAVE_MASTER_AQUI]`
   - **Is Active**: ✅ Marque
   - **Tenant**: Selecione `Default Tenant`
6. Clique: **Save**

### **2. Testar Fluxo WhatsApp Completo**

1. **Acessar Frontend**: http://localhost:5173
2. **Fazer Login** (criar conta ou usar admin)
3. **Ir para Conexões → WhatsApp**
4. **Criar Nova Instância**:
   - Nome Amigável: `Teste Local`
   - Nome da Instância: `teste_local_001`
5. **Gerar QR Code**
6. **Escanear com WhatsApp**
7. **Aguardar Conexão**
8. **Enviar Mensagem de Teste**
9. **Deletar Instância** (deve remover da Evolution API)

---

## 🛠️ **COMANDOS ÚTEIS**

### **Ver Status dos Containers**
```bash
docker-compose -f docker-compose.local.yml ps
```

### **Entrar no Container**
```bash
# Backend
docker-compose -f docker-compose.local.yml exec backend bash

# Frontend
docker-compose -f docker-compose.local.yml exec frontend sh
```

### **Rebuild de um Serviço**
```bash
docker-compose -f docker-compose.local.yml up -d --build backend
docker-compose -f docker-compose.local.yml up -d --build frontend
```

### **Limpar Tudo (Volumes, Networks, Images)**
```bash
docker-compose -f docker-compose.local.yml down -v --rmi all
```

---

## 📦 **VOLUMES CRIADOS**

- `sense_postgres_data_local` - Dados do PostgreSQL
- `sense_redis_data_local` - Dados do Redis  
- `sense_backend_static` - Arquivos estáticos do Django

---

## 🔍 **ENDPOINTS DISPONÍVEIS**

### **Backend API**
- **Admin**: http://localhost:8000/admin
- **API Health**: http://localhost:8000/api/health/
- **Auth**: http://localhost:8000/api/auth/
- **WhatsApp**: http://localhost:8000/api/notifications/whatsapp-instances/
- **Evolution Config**: http://localhost:8000/api/connections/evolution/config/
- **Webhook Evolution**: http://localhost:8000/api/webhooks/evolution/

### **Frontend**
- **App**: http://localhost:5173

---

## ⚠️ **IMPORTANTE**

1. **Dados são locais**: Tudo roda em Docker local, nada afeta Railway
2. **Banco separado**: Banco `alrea_sense_local` é independente do Railway
3. **Evolution API**: Servidor é EXTERNO (https://evo.rbtec.com.br)
4. **Porta 8000**: Se ocupada, edite `docker-compose.local.yml`
5. **Porta 5173**: Se ocupada, edite `docker-compose.local.yml`

---

## 🐛 **TROUBLESHOOTING**

### **Porta já em uso**
```powershell
# Ver processos
netstat -ano | findstr :8000
netstat -ano | findstr :5173

# Matar processo (Windows)
taskkill /PID <numero_pid> /F
```

### **Container não inicia**
```bash
# Ver logs
docker-compose -f docker-compose.local.yml logs backend

# Rebuild
docker-compose -f docker-compose.local.yml build --no-cache backend
```

### **Erro de conexão**
```bash
# Verificar network
docker network ls

# Recriar network
docker-compose -f docker-compose.local.yml down
docker-compose -f docker-compose.local.yml up -d
```

---

## 📚 **ARQUIVOS CRIADOS**

- ✅ `docker-compose.local.yml` - Orquestração Docker
- ✅ `backend/Dockerfile.local` - Dockerfile do backend
- ✅ `frontend/Dockerfile.local` - Dockerfile do frontend
- ✅ `.dockerignore` - Arquivos ignorados no build
- ✅ `README.local.md` - Documentação completa
- ✅ `AMBIENTE_LOCAL_PRONTO.md` - Este arquivo (resumo)

---

## ✅ **CHECKLIST DE VALIDAÇÃO**

- [x] PostgreSQL rodando
- [x] Redis rodando
- [x] Backend Django iniciado
- [x] Migrations aplicadas
- [x] Superusuário criado
- [x] Arquivos estáticos coletados
- [x] Celery Worker ativo
- [x] Celery Beat ativo
- [x] Frontend Vite rodando
- [ ] Evolution API configurada (VOCÊ FAZ AGORA)
- [ ] Instância WhatsApp criada (TESTE)
- [ ] QR Code gerado (TESTE)
- [ ] WhatsApp conectado (TESTE)

---

## 🎯 **AGORA É SUA VEZ!**

### **Teste Completo Recomendado:**

1. ✅ **Acesse Admin**: http://localhost:8000/admin
2. ✅ **Configure Evolution API** (passos acima)
3. ✅ **Teste Conexão** no admin
4. ✅ **Acesse Frontend**: http://localhost:5173
5. ✅ **Faça Login**
6. ✅ **Vá para Conexões → WhatsApp**
7. ✅ **Crie Instância**
8. ✅ **Gere QR Code**
9. ✅ **Escaneie com WhatsApp**
10. ✅ **Envie mensagem teste**
11. ✅ **Delete instância** (verifica se remove da Evo)

---

## 🚀 **QUANDO TUDO ESTIVER OK**

### **Deploy para Railway:**

```bash
# Commit mudanças
git add .
git commit -m "✅ Ambiente local testado e funcionando"
git push origin main

# Railway fará deploy automático
```

---

**Desenvolvido com 💙 por Alrea Sense Team**

**Data**: 09/10/2025  
**Ambiente**: Docker Compose Local  
**Status**: ✅ 100% Funcional

