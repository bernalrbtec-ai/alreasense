# Staging no Railway – Guia de configuração

Ambiente de staging para desenvolver e testar sem afetar a produção. Usado para a migração da API oficial Meta e para testes gerais antes do merge em `main`.

---

## Visão geral

| Ambiente   | Branch                      | Uso                    |
|-----------|-----------------------------|------------------------|
| Produção  | `main`                      | Clientes reais         |
| Staging   | `feature/meta-official-api` | Desenvolvimento e PR Meta |

**Manter staging atualizado com correções de produção:** de tempos em tempos fazer merge de `main` no branch do staging (ver seção 6).

---

## 1. Criar o branch de staging

```bash
git checkout main
git pull origin main
git checkout -b feature/meta-official-api
git push -u origin feature/meta-official-api
```

Se o branch já existir:

```bash
git checkout feature/meta-official-api
git pull origin feature/meta-official-api
```

---

## 2. Novo projeto no Railway (Staging)

1. Acesse [railway.app](https://railway.app) e faça login.
2. **New Project**.
3. **Deploy from GitHub repo** e selecione o repositório do Sense.
4. Na configuração do projeto:
   - **Branch:** `feature/meta-official-api` (não use `main`).
   - Mantenha esse projeto só para staging.

---

## 3. Serviços no projeto Staging

Crie (ou use os mesmos tipos da produção):

| Serviço    | Como adicionar |
|------------|----------------|
| PostgreSQL | Add Plugin → PostgreSQL |
| Redis      | Add Plugin → Redis |
| RabbitMQ   | Add Plugin → RabbitMQ (se usar na prod) |
| Backend    | New Service → GitHub repo, raiz do repo, usar `railway.backend.json` |
| Frontend   | New Service → GitHub repo, raiz do repo, usar `railway.frontend.json` |

Para backend e frontend, use os mesmos **Dockerfile** / config que a produção (`backend/Dockerfile`, `Dockerfile.frontend`), mas o **branch** do repositório deve ser `feature/meta-official-api`.

---

## 4. Variáveis de ambiente (Staging)

No projeto Staging, em cada serviço (backend/frontend), configure as variáveis.

### 4.1 Backend – variáveis gerais

Use as mesmas que na produção, mas com recursos do **próprio** projeto Staging:

- **DATABASE_URL** – do PostgreSQL do projeto Staging (Railway gera ao criar o plugin).
- **REDIS_URL** – do Redis do projeto Staging.
- **RABBITMQ_URL** – do RabbitMQ do projeto Staging (se usar).

### 4.2 Backend – URLs e hosts

Substitua pela URL real do **backend** de staging (ex.: `https://sense-backend-staging.up.railway.app`):

```env
ALLOWED_HOSTS=localhost,127.0.0.1,.railway.app
```

Ou use só a URL do serviço backend de staging, por exemplo:

```env
ALLOWED_HOSTS=localhost,127.0.0.1,sense-backend-staging.up.railway.app
```

(Depois do primeiro deploy, a Railway mostra a URL do serviço; use essa URL em `ALLOWED_HOSTS`.)

```env
BASE_URL=https://<URL-DO-BACKEND-STAGING>
CSRF_TRUSTED_ORIGINS=https://<URL-DO-BACKEND-STAGING>,https://<URL-DO-FRONTEND-STAGING>
```

### 4.3 Backend – Evolution

Pode ser o mesmo da produção ou um Evolution de teste:

```env
EVO_BASE_URL=https://evo.rbtec.com.br
EVO_API_KEY=sua_api_key
```

### 4.4 Backend – Meta (API oficial – webhook)

Necessário para receber webhooks da Meta no staging:

```env
WHATSAPP_CLOUD_VERIFY_TOKEN=<token_que_voce_escolhe>
WHATSAPP_CLOUD_APP_SECRET=<app_secret_do_app_meta>
```

- **WHATSAPP_CLOUD_VERIFY_TOKEN:** qualquer string secreta que você definir; a mesma deve ser usada no painel do Meta ao configurar o webhook.
- **WHATSAPP_CLOUD_APP_SECRET:** App Secret do app em developers.facebook.com (App Dashboard → Configurações → Básico).

### 4.5 Backend – outras

- **DJANGO_SECRET_KEY:** gere uma nova para staging (não use a da produção).
- **DEBUG:** pode ser `True` em staging se quiser; em produção deve ser `False`.

### 4.6 Frontend

Aponte para o backend de staging:

```env
VITE_API_BASE_URL=https://<URL-DO-BACKEND-STAGING>
```

Se usar WebSocket:

```env
VITE_WS_URL=wss://<URL-DO-BACKEND-STAGING>/ws/
```

(Substitua `<URL-DO-BACKEND-STAGING>` pela URL real do serviço backend no Railway.)

---

## 5. Webhook Meta apontando para o Staging

1. Acesse [developers.facebook.com](https://developers.facebook.com) → seu App → WhatsApp → Configuração.
2. Em **Webhook**, clique em **Editar**.
3. **URL de callback:**  
   `https://<URL-DO-BACKEND-STAGING>/webhooks/meta/`  
   (ex.: `https://sense-backend-staging.up.railway.app/webhooks/meta/`)
4. **Token de verificação:** o mesmo valor de `WHATSAPP_CLOUD_VERIFY_TOKEN` do backend staging.
5. Subscreva os campos necessários (ex.: `messages`).
6. Salve. A Meta fará um GET na URL; o backend precisa implementar a verificação (retornar `hub.challenge` quando `hub.verify_token` bater).

Assim, todo evento do número de teste da Meta virá para o staging, não para a produção.

---

## 6. Manter o staging alinhado com correções de produção

Quando houver hotfix ou mudanças em `main` que você queira no staging:

```bash
git checkout feature/meta-official-api
git pull origin main
# Resolver conflitos se houver
git push origin feature/meta-official-api
```

O deploy no Railway (staging) roda de novo e o ambiente fica com a correção + o que já existe no branch de staging.

---

## 7. Resumo rápido

| Passo | Ação |
|-------|------|
| 1 | Branch `feature/meta-official-api` |
| 2 | Novo projeto Railway, deploy desse branch |
| 3 | PostgreSQL, Redis, RabbitMQ (e backend/frontend) no projeto Staging |
| 4 | Variáveis no backend (incluindo ALLOWED_HOSTS, BASE_URL, Meta) |
| 5 | Webhook Meta com URL do backend staging |
| 6 | De tempos em tempos: `git pull origin main` no branch de staging |

---

## 8. Referências

- Plano da API oficial Meta: ver plano "API Oficial Meta WhatsApp" (seção Staging).
- Evolution: `EVO_BASE_URL` e `EVO_API_KEY` no `env.example`.
