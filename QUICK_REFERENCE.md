# 🚀 QUICK REFERENCE - Melhorias Aplicadas

## 📖 Como Usar os Novos Utilitários

### 1. 🔐 Validação de Input (Backend)

```python
from apps.common.validators import SecureInputValidator

# Sanitizar HTML
clean_text = SecureInputValidator.sanitize_html(user_input)

# Validar telefone
phone = SecureInputValidator.validate_phone('+5511999999999')

# Validar email
email = SecureInputValidator.validate_email('user@example.com')

# Validar URL
url = SecureInputValidator.validate_url('https://example.com')

# Sanitizar nome de arquivo
filename = SecureInputValidator.sanitize_filename(user_filename)

# Sanitizar JSON
clean_json = SecureInputValidator.sanitize_json_value(user_data)
```

### 2. 🛡️ Error Handling (Backend)

```python
from apps.common.error_handlers import ErrorHandler, safe_execute

# Método 1: Try/except com handler
try:
    result = risky_operation()
except Exception as error:
    return ErrorHandler.handle_error(
        error,
        context={'operation': 'send_message'},
        user_message='Erro ao enviar mensagem'
    )

# Método 2: Safe execute (recomendado)
success, result = safe_execute(
    send_message,
    campaign_id=campaign.id,
    error_context={'campaign': campaign.name}
)

if success:
    return Response({'success': True, 'data': result})
else:
    return ErrorHandler.handle_error(result)

# Erros específicos
return ErrorHandler.handle_database_error(error, operation='create')
return ErrorHandler.handle_external_api_error(error, service='Evolution API')
```

### 3. 💾 Cache Management (Backend)

```python
from apps.common.cache_manager import CacheManager, cached, RateLimiter

# Usar cache manual
key = CacheManager.make_key('user', user_id, tenant_id=tenant.id)
user_data = CacheManager.get_or_set(
    key,
    load_user_from_db,
    ttl=CacheManager.TTL_HOUR,
    user_id=user_id
)

# Usar decorator (recomendado)
@cached(ttl=CacheManager.TTL_HOUR, prefix='campaign')
def get_campaign_stats(campaign_id):
    return expensive_query(campaign_id)

# Invalidar cache por pattern
deleted = CacheManager.invalidate_pattern('user:*')

# Rate limiting
allowed, remaining = RateLimiter.is_allowed(
    key=f"user:{user_id}:api_call",
    limit=100,
    window=3600  # 100 calls per hour
)

if not allowed:
    return Response(
        {'error': 'Rate limit exceeded'},
        status=status.HTTP_429_TOO_MANY_REQUESTS
    )
```

### 4. 🐰 RabbitMQ Configuration (Backend)

```python
from apps.campaigns.rabbitmq_config import (
    RabbitMQConfig, 
    RetryPolicy, 
    MessagePriority
)

# Obter configuração de fila com DLQ
queue_config = RabbitMQConfig.get_queue_config('campaign.process')

# Criar fila com config
channel.queue_declare(
    queue=queue_config.name,
    durable=queue_config.durable,
    arguments=queue_config.arguments
)

# Verificar se deve fazer retry
if RetryPolicy.should_retry(attempt, error):
    delay = RetryPolicy.get_delay(attempt)
    # Schedule retry com delay

# Publicar com prioridade
channel.basic_publish(
    exchange='campaigns',
    routing_key='campaign.process',
    body=json.dumps(message),
    properties=pika.BasicProperties(
        delivery_mode=2,  # persistent
        priority=MessagePriority.HIGH
    )
)
```

### 5. 🎨 API Error Handling (Frontend)

```typescript
import { ApiErrorHandler, withRetry } from '@/lib/apiErrorHandler';
import { toast } from 'sonner';

// Método 1: Extrair mensagem user-friendly
try {
  await api.post('/endpoint', data);
  toast.success('Operação realizada com sucesso!');
} catch (error) {
  const message = ApiErrorHandler.extractMessage(error);
  toast.error(message);
  
  // Log para debug (apenas em dev)
  ApiErrorHandler.log(error, 'create campaign');
}

// Método 2: Com retry automático
const result = await withRetry(
  () => api.post('/endpoint', data),
  { 
    maxRetries: 3,
    onRetry: (attempt, error) => {
      console.log(`Tentativa ${attempt} após erro:`, error);
      toast.info(`Tentando novamente... (${attempt}/3)`);
    }
  }
);

// Verificar se erro é retryable
if (ApiErrorHandler.isRetryable(error)) {
  const delay = ApiErrorHandler.getRetryDelay(error, attempt);
  // Retry com delay
}

// Parse completo do erro
const apiError = ApiErrorHandler.parse(error);
console.log({
  message: apiError.message,
  statusCode: apiError.statusCode,
  errors: apiError.errors  // Field-specific errors
});
```

---

## 📂 Estrutura de Arquivos Criados

```
backend/
├── apps/
│   ├── common/
│   │   ├── validators.py              (NEW) ✅
│   │   ├── error_handlers.py          (NEW) ✅
│   │   ├── cache_manager.py           (NEW) ✅
│   │   └── security_middleware.py     (EXISTS, activated)
│   │
│   ├── campaigns/
│   │   ├── rabbitmq_config.py         (NEW) ✅
│   │   └── migrations/
│   │       └── 0002_add_performance_indexes.py (NEW) ✅
│   │
│   ├── authn/
│   │   └── migrations/
│   │       └── 0004_add_performance_indexes.py (NEW) ✅
│   │
│   └── notifications/
│       └── migrations/
│           └── 0002_add_performance_indexes.py (NEW) ✅
│
└── alrea_sense/
    └── settings.py                    (UPDATED) ✅

frontend/
└── src/
    └── lib/
        └── apiErrorHandler.ts         (NEW) ✅

# Documentação
├── AUDITORIA_COMPLETA_2025.md         (NEW) ✅
├── RESUMO_EXECUTIVO_AUDITORIA.md      (NEW) ✅
├── QUICK_REFERENCE.md                 (NEW) ✅ (este arquivo)
└── .cursorrules                       (UPDATED) ✅
```

---

## 🚀 Deploy Checklist

### 1. Aplicar Migrations

```bash
# Backend
cd backend
python manage.py migrate campaigns 0002
python manage.py migrate authn 0004
python manage.py migrate notifications 0002
```

### 2. Verificar Dependências

```bash
# Verificar se bleach está instalado
pip freeze | grep bleach

# Se não estiver, instalar:
pip install bleach

# Atualizar requirements.txt se necessário
pip freeze > requirements.txt
```

### 3. Variáveis de Ambiente (Opcional)

```bash
# No Railway ou .env
DB_CONN_MAX_AGE=600  # Connection pooling
DEBUG=False          # Segurança
```

### 4. Restart Services

```bash
# Restart Daphne (ASGI)
# Restart RabbitMQ consumers
# Clear Redis cache (opcional)
```

---

## 📊 Monitoramento Pós-Deploy

### 1. Performance de Queries

```python
# Django shell
from django.db import connection
from django.db import reset_queries

# Fazer operação
reset_queries()
# ... operação ...
print(connection.queries)
```

### 2. Redis Stats

```python
# Django shell
from apps.common.cache_manager import CacheManager

stats = CacheManager.get_stats()
print(stats)
# Output: hits, misses, memory_used, etc
```

### 3. RabbitMQ Queues

```bash
# Management UI
http://localhost:15672

# CLI
rabbitmqctl list_queues name messages consumers
rabbitmqctl list_exchanges name type

# Verificar DLQ (deve estar vazia)
rabbitmqctl list_queue_bindings campaigns.dlq
```

### 4. Logs

```bash
# Backend logs
tail -f backend/logs/django.log

# Buscar por:
# - "Cache HIT" vs "Cache MISS" (cache performance)
# - "SENSITIVE ACCESS" (security audit)
# - "❌" (errors)
# - "⚠️" (warnings)
```

---

## 🎯 Métricas de Sucesso

### Performance

- [ ] Queries de campanha < 100ms (antes: 450ms)
- [ ] Login < 50ms (antes: 180ms)
- [ ] API response time < 200ms (média)
- [ ] Cache hit rate > 80%

### Confiabilidade

- [ ] RabbitMQ DLQ vazia ou < 10 mensagens
- [ ] Zero message loss
- [ ] Uptime > 99.9%
- [ ] Error rate < 0.1%

### Segurança

- [ ] Zero XSS vulnerabilities
- [ ] Zero SQL Injection attempts
- [ ] Rate limiting functional
- [ ] Security headers present

---

## 🆘 Troubleshooting

### Problema: Migration falha

```bash
# Ver status
python manage.py showmigrations

# Fazer fake se necessário (cuidado!)
python manage.py migrate campaigns 0002 --fake

# Rollback se necessário
python manage.py migrate campaigns 0001
```

### Problema: Redis connection error

```python
# Verificar configuração
from django.conf import settings
print(settings.REDIS_URL)

# Testar conexão
from apps.connections.webhook_cache import redis_client
redis_client.ping()
```

### Problema: RabbitMQ não conecta

```python
# Verificar URL
from django.conf import settings
print(settings.RABBITMQ_URL)

# Verificar se serviço está rodando
# Railway: verificar service logs
```

### Problema: Performance não melhorou

```python
# Verificar se indexes foram criados
from django.db import connection
cursor = connection.cursor()
cursor.execute("""
    SELECT indexname, tablename 
    FROM pg_indexes 
    WHERE tablename LIKE 'campaigns_%'
""")
print(cursor.fetchall())
```

---

## 📚 Documentação Adicional

### Leitura Recomendada

1. **AUDITORIA_COMPLETA_2025.md** - Análise técnica completa
2. **RESUMO_EXECUTIVO_AUDITORIA.md** - Resumo para gestão
3. **ANALISE_SEGURANCA_COMPLETA.md** - Análise de segurança detalhada
4. **rules.md** - Regras do projeto
5. **.cursorrules** - Regras atualizadas com segurança

### Exemplos de Uso

Todos os arquivos criados têm:
- ✅ Docstrings completas
- ✅ Type hints
- ✅ Exemplos de uso
- ✅ Comentários explicativos

---

## 💡 Dicas Importantes

### DO ✅

1. Use os validators para **TODO** input de usuário
2. Use error handlers para **TODAS** as exceptions
3. Use `@cached` para queries caras
4. Use rate limiting em endpoints críticos
5. Monitore cache hit rate regularmente

### DON'T ❌

1. Nunca hardcode credenciais
2. Nunca exponha API keys
3. Nunca desabilite CORS_ALLOW_ALL_ORIGINS
4. Nunca ignore errors silenciosamente
5. Nunca commite sem testar

---

## 🎓 Padrões a Seguir

### 1. Validação de Input

```python
# SEMPRE validar input do usuário
from apps.common.validators import SecureInputValidator

# ✅ CORRETO
phone = SecureInputValidator.validate_phone(request.data['phone'])

# ❌ ERRADO
phone = request.data['phone']  # Sem validação
```

### 2. Error Handling

```python
# SEMPRE usar error handler centralizado
from apps.common.error_handlers import safe_execute

# ✅ CORRETO
success, result = safe_execute(operation, param=value)

# ❌ ERRADO
try:
    result = operation(value)
except:
    pass  # Ignorando erro
```

### 3. Cache

```python
# SEMPRE usar decorator para queries caras
from apps.common.cache_manager import cached

# ✅ CORRETO
@cached(ttl=3600)
def expensive_query():
    return complex_operation()

# ❌ ERRADO
def expensive_query():
    return complex_operation()  # Sem cache
```

---

## 📞 Suporte

Para dúvidas:
1. Consultar este arquivo (Quick Reference)
2. Consultar AUDITORIA_COMPLETA_2025.md
3. Verificar docstrings nos arquivos criados
4. Revisar exemplos de uso inline

---

**Última atualização:** 26 de Outubro de 2025  
**Status:** ✅ Pronto para uso

