# Plano – Integração de Rotação de Proxies (Evolution) no Backend Sense

**Objetivo:** Incorporar a lógica do `proxy_manager.py` no backend Sense, com histórico, relatórios e estatísticas. Acesso exclusivo para superadmin. A interface fica na página **Serviços**, que centraliza a gestão de serviços da aplicação.

**Referência:** `d:\ProxyEvo\proxy_manager.py` – rotação de proxies Webshare.io nas instâncias Evolution API.

---

## 1. Visão geral

### 1.1 Página Serviços (hub)

Criar uma página `/admin/servicos` que concentra todos os serviços gerenciáveis pelo superadmin. Cada serviço aparece como aba ou card, com overview e botão de execução.

| Serviço | Descrição | Status |
|---------|-----------|--------|
| **Proxy** | Rotação de proxies Webshare nas instâncias Evolution | Primeiro serviço |
| (outros) | Sync, limpeza, etc. | Futuro |

### 1.2 Princípios

1. **Superadmin only** – Apenas usuários com `is_superuser` ou `is_staff` podem ver e executar.
2. **Reutilizar padrões existentes** – Mesma abordagem de `/admin/evolution`, `/admin/system`.
3. **Configuração via env** – Sem `config.json`; credenciais em variáveis de ambiente.
4. **Histórico em banco** – Cada execução registrada para relatórios e auditoria.
5. **n8n opcional** – Endpoint com API key para agendamento externo; superadmin também pode executar pela interface.
6. **Escalável** – Novos serviços entram como novas abas/cards na mesma página.

---

## 2. Permissões

| Ação | Superadmin | Admin/User |
|------|------------|------------|
| Ver página Serviços | ✅ | ❌ |
| Ver overview do Proxy | ✅ | ❌ |
| Executar rotação manual | ✅ | ❌ |
| Ver histórico de rotações | ✅ | ❌ |
| Ver estatísticas | ✅ | ❌ |

**Backend:** Overview, histórico e estatísticas: exigem `user.is_superuser` ou `user.is_staff`; caso contrário, 403. Rotação: aceita API key ou JWT + superadmin (ver seção 5.2).

**Frontend:** Rota e menu visíveis apenas para `isSuperAdmin`.

---

## 3. Modelos

### 3.1 Localização

- **Recomendado:** novo app `backend/apps/proxy/`, com responsabilidade clara e isolada, sem misturar com `notifications` ou `tenancy`.

### 3.2 `ProxyRotationLog`

Registro de cada execução de rotação.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| id | BigAutoField (PK) | PK |
| started_at | DateTimeField | Início da execução |
| finished_at | DateTimeField | Fim (null enquanto a execução estiver em andamento) |
| status | CharField | `running` / `success` / `partial` / `failed` |
| num_proxies | IntegerField | Proxies obtidos do Webshare |
| num_instances | IntegerField | Instâncias encontradas |
| num_updated | IntegerField | Instâncias atualizadas com sucesso |
| strategy | CharField | `rotate` / `prioritize` / `random` |
| error_message | TextField | Mensagem de erro global (null) |
| triggered_by | CharField | `manual` / `n8n` / `scheduled` |
| created_by | FK(User) | Usuário que disparou (null quando n8n/API key) |
| created_at | DateTimeField | auto_now_add |

### 3.3 `ProxyRotationInstanceLog`

Detalhe por instância em cada rotação.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| id | BigAutoField (PK) | PK |
| rotation_log | FK(ProxyRotationLog) | Referência à rotação |
| instance_name | CharField | Nome da instância Evolution |
| proxy_host | CharField | Host do proxy |
| proxy_port | IntegerField | Porta |
| success | BooleanField | Atualização bem-sucedida |
| error_message | TextField | Mensagem de erro (null) |
| created_at | DateTimeField | auto_now_add |

**Índice:** O índice em `rotation_log_id` (ver SQL na seção 12) é suficiente para listar os detalhes de uma rotação. Índice composto `(rotation_log_id, instance_name)` só seria necessário para buscas por instância específica.

---

## 4. Configuração (variáveis de ambiente)

| Variável | Obrigatória | Descrição |
|----------|-------------|-----------|
| WEBSHARE_API_KEY | Sim | API key do Webshare.io |
| WEBSHARE_PROXY_LIMIT | Não | Limite de proxies (default: 100) |
| EVO_BASE_URL | Sim* | URL base da Evolution (env; mapeado para EVOLUTION_API_URL no settings) |
| EVO_API_KEY | Sim* | API key da Evolution (env; mapeado para EVOLUTION_API_KEY no settings) |
| PROXY_ROTATION_STRATEGY | Não | `rotate` / `prioritize` / `random` (default: rotate) |
| PROXY_ROTATION_RESTART_INSTANCES | Não | `true` / `false` (default: true) |
| PROXY_ROTATION_WAIT_AFTER_UPDATE_SECONDS | Não | Segundos após update_proxy, antes do restart (default: 2) |
| PROXY_ROTATION_WAIT_SECONDS | Não | Segundos entre instâncias, após restart (default: 3) |
| PROXY_ROTATION_API_KEY | Não | API key para n8n (opcional) |
| PROXY_NOTIFICATION_ENABLED | Não | `true` / `false` (default: false) |
| PROXY_NOTIFICATION_INSTANCE | Não | Instância WhatsApp para notificação |
| PROXY_NOTIFICATION_PHONE | Não | Número WhatsApp destino |

\* O projeto já usa `EVO_BASE_URL` e `EVO_API_KEY` em `settings.py` (mapeados para `EVOLUTION_API_URL` e `EVOLUTION_API_KEY`). Reutilizar `EVOLUTION_API_URL` e `EVOLUTION_API_KEY` no serviço de rotação.

**Variáveis a adicionar em `settings.py` (backend/alrea_sense/settings.py):**

```python
# Proxy rotation (Webshare → Evolution)
WEBSHARE_API_KEY = config('WEBSHARE_API_KEY', default='')
WEBSHARE_PROXY_LIMIT = config('WEBSHARE_PROXY_LIMIT', default=100, cast=int)
PROXY_ROTATION_STRATEGY = config('PROXY_ROTATION_STRATEGY', default='rotate')
PROXY_ROTATION_RESTART_INSTANCES = config('PROXY_ROTATION_RESTART_INSTANCES', default=True, cast=bool)
PROXY_ROTATION_WAIT_AFTER_UPDATE_SECONDS = config('PROXY_ROTATION_WAIT_AFTER_UPDATE_SECONDS', default=2, cast=int)
PROXY_ROTATION_WAIT_SECONDS = config('PROXY_ROTATION_WAIT_SECONDS', default=3, cast=int)
PROXY_ROTATION_API_KEY = config('PROXY_ROTATION_API_KEY', default='')
PROXY_NOTIFICATION_ENABLED = config('PROXY_NOTIFICATION_ENABLED', default=False, cast=bool)
PROXY_NOTIFICATION_INSTANCE = config('PROXY_NOTIFICATION_INSTANCE', default='')
PROXY_NOTIFICATION_PHONE = config('PROXY_NOTIFICATION_PHONE', default='')
```

---

## 5. Backend – Estrutura

```
backend/apps/proxy/
├── __init__.py
├── models.py          # ProxyRotationLog, ProxyRotationInstanceLog
├── admin.py           # Django admin (opcional)
├── serializers.py
├── services.py        # Lógica de rotação (migração do proxy_manager)
├── views.py
├── urls.py
└── migrations/
```

### 5.1 `services.py` – Lógica de rotação

- Migrar `WebshareProxyManager`, `EvolutionAPIManager` e as funções `distribute_proxies`, `format_notification_message` do `proxy_manager.py` para o serviço Django.
- **Extração do nome da instância:** A Evolution API pode retornar formatos diferentes (`name`, `instance.instanceName`, `instanceName`, string). Reutilizar a lógica de `distribute_proxies` que tenta esses formatos. Instâncias sem nome extraído: ignorar ou marcar erro; nunca gravar `instance_name` vazio.
- Função `run_proxy_rotation(triggered_by: str, user=None) -> ProxyRotationLog`:
  - **Lock:** Verificar se há rotação em `status='running'` (usar `select_for_update()` ou transação para evitar race). Se houver, retornar erro 409.
  - Criar `ProxyRotationLog(status='running', created_by=user)`
  - Buscar proxies, listar instâncias, distribuir (por `distribute_proxies`), atualizar cada instância
  - **Fluxo por instância:** `update_proxy()` → `time.sleep(PROXY_ROTATION_WAIT_AFTER_UPDATE_SECONDS)` (default 2s) → se restart: `restart_instance()` → `time.sleep(PROXY_ROTATION_WAIT_SECONDS)`
  - Para cada instância da distribuição: criar `ProxyRotationInstanceLog`. (A função `distribute_proxies` já filtra instâncias sem nome; não gravar `instance_name` vazio.)
  - Atualizar `ProxyRotationLog` (status, num_updated, finished_at, error_message)
  - Enviar notificação WhatsApp se configurado
  - Retornar o log
- **Tratamento de exceção:** Em `try/except`, em qualquer falha não tratada: atualizar log com `status='failed'`, `error_message` e `finished_at`.
- **Status “travado”:** Considerar job periódico ou manage command para marcar como `failed` os logs em `running` há mais de 30 minutos.

### 5.2 Endpoints

| Método | Rota | Descrição | Auth |
|--------|------|-----------|------|
| POST | `/api/proxy/rotate/` | Executa rotação | JWT + superadmin **ou** API key |
| GET | `/api/proxy/overview/` | Overview (config, última execução, métricas) | Superadmin |
| GET | `/api/proxy/rotation-history/` | Histórico paginado | Superadmin |
| GET | `/api/proxy/statistics/` | Estatísticas agregadas | Superadmin |

**Endpoint de rotação – dois modos de autenticação (ordem de checagem):**

1. **API key (prioridade):** Header `X-API-Key` ou `Authorization: Bearer <key>`. Validar com `secrets.compare_digest()` contra `PROXY_ROTATION_API_KEY`. Se válida: aceitar; `triggered_by` do body ou default `"scheduled"`; `created_by` = null.
2. **JWT + superadmin:** Usuário autenticado com `is_superuser` ou `is_staff` – disparo considerado `manual`, `created_by` preenchido.

Usar `AllowAny` e validação manual da API key (mesmo padrão de `views_reports_sync.py`). Se não houver autenticação válida: 401 (credenciais ausentes) ou 403 (credenciais insuficientes).

**Body opcional em POST `/api/proxy/rotate/`:** `{"triggered_by": "n8n"}` – permite diferenciar chamadas do n8n de outros scripts.

### 5.3 Endpoint de overview

`GET /api/proxy/overview/` deve retornar um único objeto com:

- `config_ok`: boolean – credenciais presentes e válidas (WEBSHARE_API_KEY, EVOLUTION_API_URL, EVOLUTION_API_KEY preenchidos e sem placeholders como `"SEU_"`)
- `last_execution`: objeto ou null – { started_at, finished_at, status, num_proxies, num_instances, num_updated, num_errors }; null se nunca houve execução. `num_errors` é derivado: `num_instances - num_updated`.
- `last_errors`: lista dos últimos erros da **última execução** (até 5 de `ProxyRotationInstanceLog` com success=false); lista vazia se last_execution null ou sem erros
- `is_running`: boolean – existe rotação com status `running`
- `warnings`: lista de avisos (ex.: "Mais instâncias que proxies" se num_instances > num_proxies na última execução); lista vazia se last_execution null

**Quando nunca houve execução:** `last_execution` = null, `last_errors` = [], `warnings` = [], `is_running` = false. No frontend, para Instâncias × Proxies: exibir "—" ou omitir.

**Nota:** As instâncias e proxies exibidos vêm da última execução (Evolution API e Webshare), não do banco local de instâncias WhatsApp.

---

## 6. Frontend – Página Serviços

### 6.1 Rota e menu

- **Rota:** `/admin/servicos`
- **Menu (Layout):** Adicionar em `adminNavigation`:
  ```js
  { name: 'Serviços', href: '/admin/servicos', icon: Settings }  // ou Cog, Server
  ```
- **App.tsx:**
  ```jsx
  <Route path="admin/servicos" element={<ServicosPage />} />
  ```

### 6.2 Estrutura da página Serviços

- **Abas** (ou cards laterais) para cada serviço: Proxy, (futuros serviços).
- Aba **Proxy** selecionada por padrão.

### 6.3 Conteúdo da aba Proxy

1. **Overview (card principal)**
   - Instâncias × Proxies (ex.: "12 instâncias / 50 proxies" ou "15 instâncias / 8 proxies ⚠️"); quando `last_execution` null: exibir "—" ou omitir
   - Última execução: data/hora, status (sucesso/parcial/falha)
   - Sucessos, erros e avisos da última execução
   - Indicador se a rotação está em execução

2. **Botão “Executar rotação”**
   - Chama `POST /api/proxy/rotate/`
   - Loading durante execução (desabilitar botão)
   - Toast de sucesso/erro
   - Atualizar overview e histórico ao concluir

3. **Histórico (tabela compacta)**
   - Colunas: Data/Hora, Status, Proxies, Instâncias, Atualizadas, Estratégia, Acionado por
   - Paginação
   - Expandir linha para ver detalhes por instância (opcional)

4. **Estatísticas (card secundário)**
   - Taxa de sucesso (7/30 dias)
   - Total de rotações (30 dias)
   - Média de instâncias atualizadas por execução

---

## 7. n8n – Integração opcional

- **Workflow:** Schedule (ex.: 2× ao dia, 6h e 18h)
- **HTTP Request:**
  - URL: `POST {{BACKEND_URL}}/api/proxy/rotate/`
  - Headers: `X-API-Key: {{PROXY_ROTATION_API_KEY}}`
  - Body: `{"triggered_by": "n8n"}`
- O backend grava `triggered_by` no log; o JWT não é exigido quando a API key é válida.

---

## 8. Ordem de implementação

1. **Backend**
   - Rodar SQL da seção 12 no banco (ou criar migrations)
   - Criar app `proxy` (estrutura + modelos)
   - Adicionar `'apps.proxy'` ao `INSTALLED_APPS`
   - Adicionar variáveis em settings (bloco da seção 4; reutilizar EVOLUTION_API_URL, EVOLUTION_API_KEY)
   - `services.py` – migração do proxy_manager + lock de execução concorrente
   - Views + urls – endpoints com checagem superadmin e suporte a API key
   - Registrar rotas em `alrea_sense/urls.py`: `path('api/proxy/', include('apps.proxy.urls'))`

2. **Frontend**
   - Criar `ServicosPage.tsx` com abas
   - Aba Proxy: overview, botão executar, histórico, estatísticas
   - Rota `/admin/servicos` em App.tsx
   - Item "Serviços" em `adminNavigation` no Layout.tsx

3. **Testes**
   - Superadmin: visualizar, executar, ver histórico
   - API key: POST sem JWT
   - Execução concorrente: retorno 409 (Conflict)

4. **n8n**
   - Workflow agendado
   - Variável `PROXY_ROTATION_API_KEY` configurada

---

## 9. Possíveis problemas e mitigações

| Problema | Mitigação |
|----------|-----------|
| Execuções concorrentes | Lock: checar se há log `running`; usar `select_for_update()` ou transação; retornar 409 se houver |
| Logs travados em `running` | Job/manage command que marca como `failed` logs `running` há > 30 min |
| API key exposta | Nunca enviar API key no frontend; usar apenas em n8n/scripts |
| Credenciais em respostas | Nunca retornar valores de WEBSHARE_API_KEY ou EVO_API_KEY; apenas `config_ok: true/false` |
| Erro ao buscar proxies | Registrar em `error_message` do log; status `failed` ou `partial` conforme resultado |
| Evolution API indisponível | Tratar timeout/erro de rede; registrar falha; considerar retry em n8n |
| Instâncias sem nome extraído | Ignorar ou marcar erro; nunca gravar `instance_name` vazio no log |

---

## 10. Segurança

- Endpoints overview, histórico e estatísticas: exigem JWT + superadmin; retornam 403 para outros usuários.
- Endpoint de rotação: aceita API key (sem JWT) ou JWT + superadmin; retorna 401/403 quando nenhuma autenticação válida.
- API key não deve aparecer no frontend.
- Credenciais Webshare e Evolution permanecem em env; nunca em banco nem em respostas da API.
- O endpoint de overview não expõe detalhes de configuração além de `config_ok`.

---

## 11. Resumo

| Item | Descrição |
|------|-----------|
| Página | `/admin/servicos` – hub de serviços para superadmin |
| Primeiro serviço | Proxy – rotação Webshare → Evolution |
| Overview | Instâncias × proxies, última execução, sucessos, erros, avisos, botão executar |
| Backend | App `proxy`, modelos de log, serviço de rotação, endpoints |
| Auth | JWT + superadmin (UI) ou API key (n8n) |
| Histórico | ProxyRotationLog + ProxyRotationInstanceLog |
| Escalável | Novos serviços = novas abas na mesma página |

---

## 12. SQL para rodar direto no banco (PostgreSQL)

Use este SQL para criar as tabelas sem migrations Django:

```sql
-- Tabela principal: log de cada execução de rotação
CREATE TABLE IF NOT EXISTS proxy_proxyrotationlog (
    id BIGSERIAL PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    num_proxies INTEGER NOT NULL DEFAULT 0,
    num_instances INTEGER NOT NULL DEFAULT 0,
    num_updated INTEGER NOT NULL DEFAULT 0,
    strategy VARCHAR(20) NOT NULL DEFAULT 'rotate',
    error_message TEXT,
    triggered_by VARCHAR(20) NOT NULL DEFAULT 'manual',
    created_by_id BIGINT REFERENCES authn_user(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Índice para buscar última execução e logs em execução
CREATE INDEX IF NOT EXISTS idx_proxy_rotation_status ON proxy_proxyrotationlog(status);
CREATE INDEX IF NOT EXISTS idx_proxy_rotation_created ON proxy_proxyrotationlog(created_at DESC);

-- Tabela de detalhes por instância
CREATE TABLE IF NOT EXISTS proxy_proxyrotationinstancelog (
    id BIGSERIAL PRIMARY KEY,
    rotation_log_id BIGINT NOT NULL REFERENCES proxy_proxyrotationlog(id) ON DELETE CASCADE,
    instance_name VARCHAR(255) NOT NULL,
    proxy_host VARCHAR(255) NOT NULL,
    proxy_port INTEGER NOT NULL,
    success BOOLEAN NOT NULL DEFAULT FALSE,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Índice para buscas por rotação
CREATE INDEX IF NOT EXISTS idx_proxy_instance_rotation ON proxy_proxyrotationinstancelog(rotation_log_id);
```

**Após rodar o SQL:**
1. Adicionar `'apps.proxy'` ao `INSTALLED_APPS` em `settings.py`
2. Criar o app (estrutura de arquivos) e os modelos com campos alinhados ao SQL acima
3. Executar: `python manage.py migrate proxy --fake-initial` (ou `--fake` se a migration já existir)

Dessa forma, o Django reconhece as tabelas sem tentar recriá-las.

---

## 13. Checklist antes de implementar

- [ ] `WEBSHARE_API_KEY` disponível no ambiente (ou `.env`)
- [ ] `EVO_BASE_URL` e `EVO_API_KEY` já configurados (Evolution)
- [ ] PostgreSQL acessível para rodar o SQL
- [ ] Código-fonte do `proxy_manager.py` disponível para portar a lógica (ex.: `d:\ProxyEvo\`)
