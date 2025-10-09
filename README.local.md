# 🐳 Alrea Sense - Ambiente de Desenvolvimento Local com Docker

## 📋 Pré-requisitos

- Docker Desktop instalado
- Docker Compose instalado
- 4GB RAM disponível (mínimo)
- 10GB espaço em disco

## 🚀 Como Usar

### 1️⃣ Subir o Ambiente Completo

```bash
# Subir todos os serviços
docker-compose -f docker-compose.local.yml up --build

# Ou em background (detached)
docker-compose -f docker-compose.local.yml up -d --build
```

### 2️⃣ Acessar os Serviços

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **Admin Django**: http://localhost:8000/admin
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

### 3️⃣ Credenciais Padrão

**Superusuário Django:**
- Username: `admin`
- Email: `admin@alrea.com`
- Password: `admin123` (definido em `create_superuser.py`)

**PostgreSQL:**
- User: `postgres`
- Password: `postgres`
- Database: `alrea_sense_local`

## 📦 Serviços Incluídos

| Serviço | Container | Porta | Descrição |
|---------|-----------|-------|-----------|
| PostgreSQL | `alrea_sense_db_local` | 5432 | Banco de dados com pgvector |
| Redis | `alrea_sense_redis_local` | 6379 | Cache e message broker |
| Backend | `alrea_sense_backend_local` | 8000 | Django + DRF + Channels |
| Celery Worker | `alrea_sense_celery_local` | - | Processamento assíncrono |
| Celery Beat | `alrea_sense_celery_beat_local` | - | Tarefas agendadas |
| Frontend | `alrea_sense_frontend_local` | 5173 | React + Vite |

## 🛠️ Comandos Úteis

### Ver logs de todos os serviços
```bash
docker-compose -f docker-compose.local.yml logs -f
```

### Ver logs de um serviço específico
```bash
docker-compose -f docker-compose.local.yml logs -f backend
docker-compose -f docker-compose.local.yml logs -f frontend
```

### Executar comandos Django
```bash
# Migrations
docker-compose -f docker-compose.local.yml exec backend python manage.py migrate

# Criar superusuário
docker-compose -f docker-compose.local.yml exec backend python manage.py createsuperuser

# Shell Django
docker-compose -f docker-compose.local.yml exec backend python manage.py shell

# Entrar no container
docker-compose -f docker-compose.local.yml exec backend bash
```

### Resetar banco de dados
```bash
# Parar e remover volumes
docker-compose -f docker-compose.local.yml down -v

# Subir novamente (cria banco limpo)
docker-compose -f docker-compose.local.yml up --build
```

### Parar todos os serviços
```bash
# Parar mas manter dados
docker-compose -f docker-compose.local.yml down

# Parar e remover volumes (CUIDADO: perde dados!)
docker-compose -f docker-compose.local.yml down -v
```

### Rebuild de um serviço específico
```bash
docker-compose -f docker-compose.local.yml up -d --build backend
docker-compose -f docker-compose.local.yml up -d --build frontend
```

## 🔧 Configurar Evolution API

1. Acesse: http://localhost:8000/admin
2. Login com `admin` / `admin123`
3. Vá em **Connections → Evolution connections**
4. Clique em **Add Evolution Connection**
5. Preencha:
   - **Name**: Evolution RBTec
   - **Base URL**: https://evo.rbtec.com.br
   - **API Key**: (sua chave master)
   - **Is Active**: ✅ Marque
6. Salve

## ✅ Testar Fluxo WhatsApp

1. Acesse: http://localhost:5173
2. Faça login
3. Vá em **Conexões → WhatsApp**
4. Clique em **Nova Instância**
5. Preencha os dados
6. Clique em **Gerar QR Code**
7. Escaneie com WhatsApp
8. Teste enviar mensagem
9. Delete a instância (deve remover da Evolution API)

## 🐛 Troubleshooting

### Porta já em uso
```bash
# Ver processos usando portas
netstat -ano | findstr :8000
netstat -ano | findstr :5173
netstat -ano | findstr :5432

# Matar processo (Windows)
taskkill /PID <numero_pid> /F
```

### Erro de migração
```bash
# Resetar banco
docker-compose -f docker-compose.local.yml down -v
docker-compose -f docker-compose.local.yml up --build
```

### Container não inicia
```bash
# Ver logs
docker-compose -f docker-compose.local.yml logs backend

# Rebuild forçado
docker-compose -f docker-compose.local.yml build --no-cache backend
```

### Frontend não conecta no backend
- Verifique se backend está rodando: http://localhost:8000/admin
- Verifique CORS no backend
- Limpe cache do navegador

## 📚 Estrutura de Dados

Os dados são persistidos em volumes Docker:
- `postgres_data_local` - Dados do PostgreSQL
- `redis_data_local` - Dados do Redis
- `backend_static` - Arquivos estáticos do Django

Para backup:
```bash
docker run --rm -v alrea_sense_postgres_data_local:/data -v $(pwd):/backup ubuntu tar czf /backup/postgres_backup.tar.gz /data
```

## 🎯 Próximos Passos

1. ✅ Ambiente Docker rodando
2. ✅ Configurar Evolution API
3. ✅ Testar criação de instância
4. ✅ Testar QR Code
5. ✅ Testar conexão WhatsApp
6. 🚀 Deploy para Railway quando tudo OK!

---

**Desenvolvido por Alrea Sense Team** 🚀

