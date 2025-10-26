# 🔐 ANÁLISE COMPLETA DE SEGURANÇA - ALREA SENSE

**Data:** 26 de Outubro de 2025  
**Severidade:** 🔴 **CRÍTICA**  
**Status:** API KEY DA EVOLUTION VAZOU

---

## ⚠️ RESUMO EXECUTIVO

A API key da Evolution API (`584B4A4A-0815-AC86-DC39-C38FC27E8E17`) está **EXPOSTA** em múltiplos vetores do projeto. Este documento detalha **COMO** ela vazou, **ONDE** está exposta, e **COMO CORRIGIR**.

---

## 🚨 VETORES DE VAZAMENTO IDENTIFICADOS

### 1. ⚠️ **HARDCODED CREDENTIALS NO CÓDIGO-FONTE** (CRÍTICO)

#### Arquivos com Credenciais Hardcoded:

```bash
# Evolution API Key: 584B4A4A-0815-AC86-DC39-C38FC27E8E17
test_groups_correct.py:8
test_evolution_direct.py:9
backend/apps/connections/webhook_views.py:524
backend/test_evolution_api.py:7
backend/simulate_evolution_config.py:37
backend/create_evolution_connection.py:30
```

**IMPACTO:**
- ✅ Credenciais commitadas no Git
- ✅ Visíveis no histórico do Git (mesmo se removidas)
- ✅ Expostas em repositório público/privado
- ✅ Acessíveis a qualquer desenvolvedor com acesso ao repo

**POR QUE É GRAVE:**
- Uma vez no Git, a credencial fica permanentemente no histórico
- Ferramentas de scanning de segurança detectam isso automaticamente
- Bots vasculham GitHub buscando credenciais expostas
- Se o repositório for público, a chave está 100% vazada

---

### 2. ⚠️ **CREDENCIAIS EM DEFAULTS DO SETTINGS.PY** (CRÍTICO)

#### Arquivo: `backend/alrea_sense/settings.py`

```python
# Linha 327-328 (Evolution API)
EVOLUTION_API_URL = config('EVOLUTION_API_URL', default='https://evo.rbtec.com.br')
EVOLUTION_API_KEY = config('EVOLUTION_API_KEY', default='')

# Linha 422-423 (S3/MinIO)
S3_ACCESS_KEY = config('S3_ACCESS_KEY', default='u2gh8aomMEdqPFW1JIlTn7VcCUhRCobL')
S3_SECRET_KEY = config('S3_SECRET_KEY', default='zSMwLiOH1fURqSNX8zMtMYKBjrScDQYynCW2TbI2UuXM7Bti')

# Linha 306 (RabbitMQ)
RABBITMQ_URL = config('RABBITMQ_PRIVATE_URL', default='amqp://75jkOmkcjQmQLFs3:~CiJnJU1I-1k~GS.vRf4qj8-EqeurdvJ@rabbitmq.railway.internal:5672')
```

**IMPACTO:**
- ✅ Credenciais de S3 hardcoded como default
- ✅ Credenciais de RabbitMQ hardcoded como default
- ✅ Se a env var não existir, usa credenciais hardcoded
- ✅ Expostas no Git

**POR QUE É GRAVE:**
- Defaults NUNCA devem conter credenciais reais
- Se alguém rodar o projeto sem configurar .env, usa credenciais de produção
- Credenciais permanentemente no histórico do Git

---

### 3. ⚠️ **API ENDPOINT RETORNA CREDENCIAIS EM PLAINTEXT** (CRÍTICO)

#### Arquivo: `backend/apps/connections/views.py`

```python
# Linha 116-129 - GET /api/connections/evolution/config/
return Response({
    'id': str(connection.id),
    'name': connection.name,
    'base_url': connection.base_url,
    'api_key': api_key_value,  # ⚠️ RETORNA API KEY EM PLAINTEXT
    'webhook_url': webhook_url,
    'is_active': connection.is_active,
    # ...
})

# Linha 246-261 - POST /api/connections/evolution/test/
return Response({
    'success': True,
    'message': f'Conexão estabelecida com sucesso!',
    'instances': instances,
    'config': {
        'api_key': api_key,  # ⚠️ RETORNA API KEY EM PLAINTEXT
        # ...
    }
})
```

**IMPACTO:**
- ✅ API key enviada para o frontend em plaintext
- ✅ Visível no Network tab das DevTools do navegador
- ✅ Armazenada em estado do React (memória do navegador)
- ✅ Pode ser interceptada por XSS
- ✅ Pode ser logada por ferramentas de monitoring
- ✅ Acessível via `localStorage` ou `sessionStorage` se for cached

**POR QUE É GRAVE:**
- Qualquer usuário superuser pode ver a chave completa no frontend
- Ferramentas de análise de tráfego (Burp Suite, etc) capturam isso
- Se houver uma vulnerabilidade XSS, a chave vaza
- Logs de proxy reverso podem capturar essa resposta

**PROTEÇÃO ATUAL:**
- ✅ Apenas superusers podem acessar (`if not user.is_superuser`)
- ❌ MAS AINDA ASSIM A CHAVE É ENVIADA EM PLAINTEXT

**O QUE DEVERIA FAZER:**
- Mascarar a chave no GET (mostrar apenas `****...últimos4dígitos`)
- Permitir edição mas nunca retornar a chave completa
- Usar campo `password` no frontend (type="password")

---

### 4. ⚠️ **DOCUMENTAÇÃO COM CREDENCIAIS** (MODERADO)

#### Arquivos de Documentação:

```bash
# Credenciais expostas em documentação commitada:
DEPLOY_CHECKLIST.md:39-40 (S3 keys)
IMPLEMENTACAO_SISTEMA_MIDIA.md:706-707, 1798-1799 (S3 keys)
WHATSAPP_CONFIG.md (Evolution API URL e estrutura)
```

**IMPACTO:**
- ✅ Credenciais documentadas no repositório
- ✅ Acessíveis a qualquer pessoa com acesso ao repo
- ✅ Indexadas pelo Git history

**POR QUE É GRAVE:**
- Documentação frequentemente contém "exemplos reais"
- Desenvolvedores copiam e colam dessas docs
- Difícil de rastrear onde mais as credenciais foram copiadas

---

### 5. ⚠️ **LOGS IMPRIMEM INFORMAÇÕES SENSÍVEIS** (MODERADO)

#### Prints de Debug com Dados Sensíveis:

```python
# backend/alrea_sense/settings.py
print(f"🔧 [SETTINGS] REDIS_PASSWORD: {'Set' if REDIS_PASSWORD else 'Not set'}")
print(f"🔧 [SETTINGS] RABBITMQ_URL: {RABBITMQ_URL[:50]}...")  # Mostra 50 chars

# Múltiplos arquivos de teste/debug:
backend/apps/notifications/models.py:382 - print(f"✅ API key: {api_key[:20]}...")
backend/apps/notifications/models.py:484 - print(f"   🔑 API Key: {api_key[:20]}...")
```

**IMPACTO:**
- ✅ Credenciais parciais em logs do Railway
- ✅ Logs podem ser acessados por desenvolvedores
- ✅ Logs podem ser exportados/compartilhados
- ✅ Logs podem ser indexados por ferramentas de monitoring

**POR QUE É PERIGOSO:**
- Mesmo parciais, facilitam ataques de força bruta
- Logs geralmente têm retenção longa
- Logs podem ser acessíveis a mais pessoas que o código

---

### 6. ⚠️ **CORS ALLOW ALL ORIGINS** (ALTO)

#### Arquivo: `backend/alrea_sense/settings.py`

```python
# Linha 196
CORS_ALLOW_ALL_ORIGINS = True  # ⚠️ Temporarily True to fix Railway CORS issue
```

**IMPACTO:**
- ✅ Qualquer domínio pode fazer requisições à API
- ✅ Facilita ataques de phishing
- ✅ Permite que sites maliciosos façam chamadas autenticadas
- ✅ Bypass de proteções de origem

**POR QUE É GRAVE:**
- Se um usuário autenticado visitar um site malicioso
- O site pode fazer requisições à API usando o token do usuário
- CSRF tokens não protegem contra isso se CORS está aberto
- Credential harvesting fica muito mais fácil

---

### 7. ⚠️ **SECRET_KEY COM DEFAULT VALUE** (CRÍTICO)

#### Arquivo: `backend/alrea_sense/settings.py`

```python
# Linha 14
SECRET_KEY = config('SECRET_KEY', default='N;.!iB5@sw?D2wJPr{Ysmt5][R%5.aHyAuvNpM_@DOb:OX*<.f')
```

**IMPACTO:**
- ✅ Secret key hardcoded no código
- ✅ Usada para assinar tokens JWT
- ✅ Se vazar, todos os tokens podem ser forjados
- ✅ Atacante pode criar tokens de qualquer usuário

**POR QUE É GRAVÍSSIMO:**
- A SECRET_KEY é a chave mestra do Django
- Assina: sessões, tokens CSRF, JWT tokens, cookies
- Com ela, um atacante pode:
  - Criar tokens de qualquer usuário (incluindo admin)
  - Descriptografar dados sensíveis
  - Forjar sessões de qualquer tenant
  - Bypass completo de autenticação

---

## 🔍 COMO A API KEY DA EVOLUTION VAZOU

### Cenário Mais Provável:

1. **Desenvolvedor commitou código com chave hardcoded**
   - Arquivos: `webhook_views.py`, scripts de teste, etc
   - Data: Presente no Git history

2. **Repositório é privado MAS:**
   - ✅ Acessível a múltiplos desenvolvedores
   - ✅ Pode ter sido clonado em máquinas comprometidas
   - ✅ Pode ter sido compartilhado inadvertidamente
   - ✅ Backups/exports podem conter o histórico
   - ✅ CI/CD pode ter logado as credenciais

3. **API endpoint expõe a chave para superusers**
   - Qualquer superuser pode ver a chave completa
   - Se conta de superuser foi comprometida → chave vazou
   - Se DevTools estavam abertas durante desenvolvimento → chave em screenshots

4. **Logs do Railway**
   - Prints de debug podem ter exposto a chave
   - Logs são visíveis no painel do Railway
   - Múltiplos desenvolvedores têm acesso

5. **Documentação**
   - Docs compartilhados podem conter a chave
   - PDFs/screenshots gerados da documentação

---

## 🛡️ VETORES DE ATAQUE POSSÍVEIS

Se um atacante obtiver a API key da Evolution:

### 1. **Acesso Total às Instâncias WhatsApp**
```bash
# Listar todas as instâncias
curl -H "apikey: 584B4A4A-0815-AC86-DC39-C38FC27E8E17" \
  https://evo.rbtec.com.br/instance/fetchInstances

# Enviar mensagens de qualquer instância
curl -X POST -H "apikey: 584B4A4A-0815-AC86-DC39-C38FC27E8E17" \
  https://evo.rbtec.com.br/message/sendText/{instance} \
  -d '{"number": "...", "text": "..."}'

# Desconectar instâncias
# Deletar instâncias
# Interceptar mensagens via webhook manipulation
```

### 2. **Phishing e Fraude**
- Enviar mensagens em nome da empresa
- Criar campanhas maliciosas
- Phishing de clientes/contatos
- Roubo de informações via engenharia social

### 3. **Exfiltração de Dados**
- Histórico de mensagens de todas as instâncias
- Lista de contatos de todos os tenants
- Mídias enviadas/recebidas
- Metadados de campanhas

### 4. **Negação de Serviço (DoS)**
- Deletar todas as instâncias
- Desconectar todos os WhatsApps
- Sobrecarregar a API com requisições
- Corromper configurações

### 5. **Lateral Movement**
- Se S3 keys também vazaram → acesso ao storage
- Se RabbitMQ credentials vazaram → acesso à fila
- Se SECRET_KEY vazou → acesso total ao sistema

---

## 🔥 IMPACTO ESTIMADO

| Vetor | Severidade | Probabilidade | Impacto |
|-------|-----------|---------------|---------|
| **Hardcoded credentials** | 🔴 Crítica | 100% (já aconteceu) | Total |
| **API endpoint expõe keys** | 🔴 Crítica | Alta (se superuser comprometido) | Total |
| **CORS Allow All** | 🟠 Alta | Média | Alto |
| **SECRET_KEY hardcoded** | 🔴 Crítica | 100% (já aconteceu) | Total |
| **S3 credentials hardcoded** | 🔴 Crítica | 100% (já aconteceu) | Total |
| **RabbitMQ credentials hardcoded** | 🟠 Alta | 100% (já aconteceu) | Alto |
| **Logs com credenciais** | 🟡 Média | Média | Moderado |

**RESUMO:** O projeto tem múltiplas vulnerabilidades **CRÍTICAS** de exposição de credenciais.

---

## 🚨 AÇÕES IMEDIATAS (AGORA!)

### 1. **ROTACIONAR TODAS AS CREDENCIAIS** (PRIORIDADE MÁXIMA)

#### Evolution API:
```bash
# 1. Gerar nova API key no servidor Evolution
# 2. Atualizar no Railway:
railway variables set EVOLUTION_API_KEY="NOVA_CHAVE_AQUI"

# 3. Remover todas as hardcoded keys do código
# 4. Force push para limpar Git history (CUIDADO!)
```

#### S3/MinIO:
```bash
# 1. Rotacionar access keys no MinIO
railway variables set S3_ACCESS_KEY="NOVA_CHAVE"
railway variables set S3_SECRET_KEY="NOVA_SECRET"
```

#### Django SECRET_KEY:
```bash
# 1. Gerar nova secret key
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'

# 2. Atualizar no Railway
railway variables set SECRET_KEY="NOVA_SECRET_KEY_AQUI"
```

#### RabbitMQ:
```bash
# Rotacionar senha do RabbitMQ no Railway
```

---

### 2. **INVALIDAR TOKENS JWT EXISTENTES**

```python
# Forçar logout de todos os usuários
# Invalidar todos os tokens JWT em circulação
# Requer que usuários façam login novamente
```

---

### 3. **AUDITAR ACESSOS RECENTES**

```bash
# Verificar logs do Evolution API:
# - Quais instâncias foram acessadas recentemente?
# - Quais mensagens foram enviadas?
# - Houve criação/deleção de instâncias suspeitas?

# Verificar logs do Railway:
# - Acessos não autorizados?
# - Mudanças de configuração suspeitas?
# - Deploys não esperados?

# Verificar S3:
# - Arquivos deletados recentemente?
# - Acessos anômalos?
```

---

## 🛠️ CORREÇÕES PERMANENTES

### 1. **REMOVER TODAS AS CREDENCIAIS HARDCODED**

```python
# ❌ NUNCA FAZER ISSO:
API_KEY = config('API_KEY', default='chave-real-aqui')

# ✅ SEMPRE FAZER ISSO:
API_KEY = config('API_KEY')  # Sem default! Se não existir, vai quebrar (comportamento desejado)
```

### 2. **SANITIZAR ENDPOINTS DE CONFIGURAÇÃO**

```python
# backend/apps/connections/views.py

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def evolution_config(request):
    if request.method == 'GET':
        # ✅ NUNCA retornar a chave completa
        api_key_masked = '****' + (connection.api_key[-4:] if connection.api_key else '')
        
        return Response({
            'id': str(connection.id),
            'name': connection.name,
            'base_url': connection.base_url,
            'api_key': api_key_masked,  # ✅ APENAS MASCARADA
            'api_key_set': bool(connection.api_key),  # ✅ Flag se está configurada
            # ...
        })
    
    elif request.method == 'POST':
        # ✅ Aceitar nova chave mas nunca retornar
        new_api_key = data.get('api_key')
        if new_api_key and not new_api_key.startswith('****'):
            # Só atualizar se não for mascarada
            connection.api_key = new_api_key
        
        # Retornar mascarada
        api_key_masked = '****' + (connection.api_key[-4:] if connection.api_key else '')
        return Response({
            'api_key': api_key_masked,
            # ...
        })
```

### 3. **IMPLEMENTAR RATE LIMITING**

```python
# settings.py
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/day',
        'evolution_config': '10/hour',  # Limitar acesso a configurações
    }
}
```

### 4. **CORRIGIR CORS**

```python
# settings.py
# ❌ REMOVER ISSO:
CORS_ALLOW_ALL_ORIGINS = True

# ✅ USAR ISSO:
CORS_ALLOWED_ORIGINS = [
    'https://alreasense-production.up.railway.app',
    'http://localhost:5173',  # Apenas em dev
]
CORS_ALLOW_ALL_ORIGINS = False  # SEMPRE False
```

### 5. **IMPLEMENTAR AUDITORIA DE SEGURANÇA**

```python
# apps/common/models.py
class SecurityAuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=255)  # 'view_api_key', 'update_api_key', etc
    resource = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'security_audit_log'
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
        ]
```

### 6. **LIMPAR GIT HISTORY** (CUIDADO!)

```bash
# ⚠️ ATENÇÃO: Isso reescreve o histórico do Git!
# Fazer backup antes!

# 1. Usar BFG Repo-Cleaner para remover credenciais
git clone --mirror git://github.com/your-repo.git
bfg --replace-text passwords.txt your-repo.git
cd your-repo.git
git reflog expire --expire=now --all && git gc --prune=now --aggressive
git push --force

# 2. Ou usar git-filter-repo (mais moderno)
git filter-repo --path backend/alrea_sense/settings.py --invert-paths
git filter-repo --replace-text <(echo "584B4A4A-0815-AC86-DC39-C38FC27E8E17==>REDACTED")
```

**⚠️ IMPORTANTE:** Limpar Git history é uma operação destrutiva. Todos os desenvolvedores precisarão re-clonar o repositório.

### 7. **IMPLEMENTAR PRE-COMMIT HOOKS**

```bash
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
        exclude: package-lock.json

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: check-added-large-files
      - id: check-merge-conflict
      - id: check-yaml
      - id: detect-private-key

# Instalar:
pip install pre-commit
pre-commit install
```

### 8. **CONFIGURAR SECRETS SCANNING NO GITHUB**

```yaml
# .github/workflows/security-scan.yml
name: Security Scan
on: [push, pull_request]
jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run Gitleaks
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

---

## 📋 CHECKLIST DE SEGURANÇA COMPLETO

### Imediato (Hoje):
- [ ] Rotacionar Evolution API key
- [ ] Rotacionar S3 credentials
- [ ] Rotacionar SECRET_KEY
- [ ] Rotacionar RabbitMQ credentials
- [ ] Invalidar todos os JWT tokens
- [ ] Auditar logs de acesso (Evolution, Railway, S3)
- [ ] Verificar se houve atividade suspeita

### Curto Prazo (Esta Semana):
- [ ] Remover todas as credenciais hardcoded do código
- [ ] Mascarar API keys nos endpoints GET
- [ ] Implementar rate limiting
- [ ] Corrigir CORS (remover ALLOW_ALL)
- [ ] Adicionar auditoria de segurança
- [ ] Implementar pre-commit hooks
- [ ] Configurar secrets scanning no GitHub

### Médio Prazo (Este Mês):
- [ ] Limpar Git history (com backup!)
- [ ] Implementar vault para secrets (AWS Secrets Manager, HashiCorp Vault)
- [ ] Adicionar 2FA para superusers
- [ ] Implementar IP whitelisting para rotas administrativas
- [ ] Pen test profissional
- [ ] Treinamento de segurança para desenvolvedores

### Longo Prazo (Este Trimestre):
- [ ] Certificação ISO 27001 / SOC 2
- [ ] Bug bounty program
- [ ] SIEM/SOC para monitoramento contínuo
- [ ] Disaster recovery plan
- [ ] Incident response plan

---

## 🎯 MELHORES PRÁTICAS DE SEGURANÇA

### 1. **The Twelve-Factor App - Config**
- ✅ Credenciais SEMPRE em variáveis de ambiente
- ❌ NUNCA hardcoded no código
- ❌ NUNCA em defaults
- ❌ NUNCA commitadas no Git

### 2. **Principle of Least Privilege**
- ✅ API keys devem ter escopo mínimo necessário
- ✅ Usuários devem ter apenas as permissões que precisam
- ✅ Tokens JWT com tempo de expiração curto

### 3. **Defense in Depth**
- ✅ Múltiplas camadas de segurança
- ✅ Mesmo se uma falhar, outras protegem
- ✅ Não confiar apenas em autenticação

### 4. **Fail Securely**
- ✅ Se credencial não existir → erro (não usar default)
- ✅ Se autenticação falhar → negar acesso (não permitir)
- ✅ Em dúvida → negar

### 5. **Security by Design**
- ✅ Pensar em segurança desde o início
- ✅ Code review focado em segurança
- ✅ Threat modeling antes de implementar features

---

## 📞 CONTATOS DE EMERGÊNCIA

Em caso de incidente de segurança:

1. **Isolar o sistema** (tirar do ar se necessário)
2. **Preservar evidências** (logs, backups)
3. **Notificar stakeholders**
4. **Seguir incident response plan**
5. **Investigar root cause**
6. **Implementar correções**
7. **Post-mortem sem culpa**

---

## 📚 REFERÊNCIAS

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [OWASP API Security Top 10](https://owasp.org/www-project-api-security/)
- [Django Security Best Practices](https://docs.djangoproject.com/en/5.0/topics/security/)
- [The Twelve-Factor App](https://12factor.net/)
- [CWE-798: Use of Hard-coded Credentials](https://cwe.mitre.org/data/definitions/798.html)
- [CWE-200: Exposure of Sensitive Information](https://cwe.mitre.org/data/definitions/200.html)

---

**Análise realizada por:** AI Assistant (Claude Sonnet 4.5)  
**Data:** 26 de Outubro de 2025, 22:30 BRT  
**Versão do Documento:** 1.0

