# 🚀 Análise Completa de Performance - ALREA Sense

> **Data:** 2025-01-XX  
> **Objetivo:** Identificar e priorizar melhorias de performance para tornar a aplicação mais ágil

---

## 📊 RESUMO EXECUTIVO

### Status Atual
- ✅ **Bom:** WebSocket implementado para tempo real
- ✅ **Bom:** Alguns índices de banco já criados
- ✅ **Bom:** Cache manager centralizado existe
- ⚠️ **Atenção:** Muitos `print()` ainda no código (3634 ocorrências!)
- ⚠️ **Atenção:** Polling redundante no Dashboard (30s mesmo com WebSocket)
- ⚠️ **Atenção:** Queries sem paginação em alguns endpoints
- ⚠️ **Atenção:** Falta de `select_related/prefetch_related` em alguns ViewSets

### Impacto Esperado
- **Backend:** Redução de 50-80% no tempo de resposta
- **Frontend:** Redução de 40-60% no uso de recursos
- **Banco de Dados:** Redução de 60-90% em queries desnecessárias

---

## 🔴 CRÍTICO (Implementar Imediatamente)

### 1. **Remover print() Statements** ⚡
**Problema:** 3634 ocorrências de `print()` no código backend
- Logs não estruturados
- Difícil debugging em produção
- Performance degradada (I/O síncrono)

**Impacto:** 🔴 **ALTO** - Afeta todos os ambientes

**Solução:**
```python
# ❌ ERRADO
print(f"Debug: {data}")

# ✅ CORRETO
import logging
logger = logging.getLogger(__name__)
logger.debug("Debug info", extra={'data': data})
```

**Ação:** Criar script para substituir automaticamente + pre-commit hook

---

### 2. **Otimizar Dashboard - Remover Polling Redundante** ⚡
**Problema:** Dashboard faz polling a cada 30s mesmo com WebSocket ativo
- `DashboardPage.tsx` linha 168: `setInterval(fetchChatStats, 30000)`
- Busca 1000 conversas desnecessariamente
- WebSocket já fornece atualizações em tempo real

**Impacto:** 🔴 **ALTO** - Afeta todos os usuários no Dashboard

**Solução:**
```typescript
// ✅ CORRETO: Usar apenas WebSocket, polling apenas como fallback
useEffect(() => {
  fetchChatStats() // Apenas inicial
  
  // Polling apenas se WebSocket desconectado
  if (!isWebSocketConnected) {
    const interval = setInterval(fetchChatStats, 30000)
    return () => clearInterval(interval)
  }
}, [isWebSocketConnected])
```

**Ação:** Modificar `DashboardPage.tsx` para usar WebSocket como fonte primária

---

### 3. **Adicionar Paginação em Endpoints Sem Paginação** ⚡
**Problema:** Alguns endpoints retornam todos os registros
- `/api/contacts/tags/` - SEM paginação
- `/api/contacts/lists/` - SEM paginação
- `/api/notifications/whatsapp-instances/` - SEM paginação configurada

**Impacto:** 🔴 **ALTO** - Pode travar com muitos dados

**Solução:**
```python
# settings.py
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
}

# Para endpoints específicos que precisam de mais
class TagViewSet(viewsets.ModelViewSet):
    pagination_class = PageNumberPagination
    page_size = 100  # Se necessário
```

**Ação:** Adicionar paginação padrão + configurar endpoints específicos

---

### 4. **Otimizar Queries com select_related/prefetch_related** ⚡
**Problema:** Alguns ViewSets não otimizam queries relacionadas

**Locais identificados:**
- `WhatsAppInstanceViewSet` - Falta `select_related('tenant', 'created_by')`
- `TagViewSet` - Falta `prefetch_related('contacts')` se necessário
- `ContactListViewSet` - Verificar otimizações

**Impacto:** 🟡 **MÉDIO-ALTO** - N+1 queries em listagens

**Solução:**
```python
class WhatsAppInstanceViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        return WhatsAppInstance.objects.select_related(
            'tenant', 'created_by'
        ).filter(tenant=self.request.user.tenant)
```

**Ação:** Auditar todos os ViewSets e adicionar otimizações

---

## 🟡 IMPORTANTE (Implementar em 1-2 Semanas)

### 5. **Otimizar Busca de Estatísticas do Dashboard**
**Problema:** Dashboard busca TODAS as conversas para contar
- `page_size: 1000` - Busca desnecessária
- Poderia usar endpoint de estatísticas dedicado

**Solução:**
```python
# Criar endpoint dedicado
@action(detail=False, methods=['get'])
def stats(self, request):
    """Retorna estatísticas agregadas sem buscar todas as conversas"""
    tenant = request.user.tenant
    stats = Conversation.objects.filter(tenant=tenant).aggregate(
        open_count=Count('id', filter=Q(status='open')),
        unread_count=Count('messages', filter=Q(
            messages__direction='incoming',
            messages__status__in=['sent', 'delivered']
        ))
    )
    return Response(stats)
```

**Impacto:** 🟡 **MÉDIO** - Reduz carga no Dashboard

---

### 6. **Implementar Cache para Dados Estáticos**
**Problema:** Produtos e Planos consultados repetidamente
- `ProductViewSet` - Sem cache
- `PlanViewSet` - Sem cache
- Dados mudam raramente

**Solução:**
```python
from apps.common.cache_manager import CacheManager

class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    def list(self, request, *args, **kwargs):
        cache_key = CacheManager.make_key('products', 'active')
        cached_data = CacheManager.get_or_set(
            cache_key,
            lambda: super().list(request, *args, **kwargs).data,
            ttl=CacheManager.TTL_HOUR
        )
        return Response(cached_data)
```

**Impacto:** 🟡 **MÉDIO** - Reduz queries repetidas

---

### 7. **Adicionar Índices Faltantes**
**Problema:** Alguns campos frequentemente filtrados sem índices

**Verificar:**
- `Task.assigned_to` + `Task.department` (filtro composto)
- `Conversation.assigned_to` + `Conversation.status`
- `Campaign.status` + `Campaign.created_at`

**Solução:**
```python
# Migration
migrations.RunSQL(
    sql="""
        CREATE INDEX IF NOT EXISTS idx_task_dept_assigned_status 
        ON contacts_task(department_id, assigned_to_id, status);
    """,
    reverse_sql="DROP INDEX IF EXISTS idx_task_dept_assigned_status;"
)
```

**Impacto:** 🟡 **MÉDIO** - Melhora queries com filtros

---

### 8. **Otimizar Serializers - Usar only()/defer()**
**Problema:** Serializers carregam todos os campos sempre

**Solução:**
```python
# Em list views, carregar apenas campos necessários
def get_queryset(self):
    return Task.objects.only(
        'id', 'title', 'status', 'due_date', 'department_id', 'assigned_to_id'
    ).select_related('department', 'assigned_to')
```

**Impacto:** 🟢 **BAIXO-MÉDIO** - Reduz transferência de dados

---

## 🟢 MELHORIAS ADICIONAIS (Opcional)

### 9. **Lazy Loading de Imagens**
**Problema:** Todas as imagens carregam imediatamente

**Solução:** Usar `loading="lazy"` em imagens do frontend

---

### 10. **Code Splitting no Frontend**
**Problema:** Bundle único grande

**Solução:** Lazy loading de rotas com React.lazy()

---

### 11. **Compressão de Respostas API**
**Problema:** Respostas JSON não comprimidas

**Solução:** Habilitar gzip no nginx/servidor

---

## 📋 PLANO DE AÇÃO PRIORIZADO

### Semana 1 (Crítico)
1. ✅ Remover print() statements (script automatizado)
2. ✅ Otimizar Dashboard - remover polling redundante
3. ✅ Adicionar paginação padrão
4. ✅ Otimizar queries críticas (select_related/prefetch_related)

### Semana 2 (Importante)
5. ✅ Criar endpoint de estatísticas do Dashboard
6. ✅ Implementar cache para produtos/planos
7. ✅ Adicionar índices faltantes

### Semana 3+ (Opcional)
8. ✅ Otimizar serializers
9. ✅ Lazy loading de imagens
10. ✅ Code splitting

---

## 🛠️ FERRAMENTAS DE MONITORAMENTO

### Backend
- ✅ `PerformanceMiddleware` - Já existe, adiciona `X-Response-Time`
- ✅ `DatabaseQueryCountMiddleware` - Para DEBUG (desabilitado em produção)
- ⚠️ Adicionar: Logging estruturado de queries lentas

### Frontend
- ⚠️ Adicionar: React DevTools Profiler
- ⚠️ Adicionar: Web Vitals monitoring

---

## 📊 MÉTRICAS DE SUCESSO

### Antes vs Depois (Estimativas)

| Métrica | Antes | Depois | Melhoria |
|---------|-------|--------|----------|
| Tempo de resposta Dashboard | 800ms | <200ms | 75% |
| Queries por requisição | 50-100 | 5-15 | 80% |
| Tamanho resposta API | 500KB | 50KB | 90% |
| Uso de CPU (pico) | 80% | 40% | 50% |
| Uso de memória | 2GB | 1GB | 50% |

---

## ✅ CHECKLIST DE IMPLEMENTAÇÃO

### Backend
- [ ] Remover todos os print() statements
- [ ] Adicionar paginação padrão
- [ ] Otimizar queries com select_related/prefetch_related
- [ ] Criar endpoint de estatísticas do Dashboard
- [ ] Implementar cache para dados estáticos
- [ ] Adicionar índices faltantes
- [ ] Configurar logging estruturado

### Frontend
- [ ] Remover polling redundante do Dashboard
- [ ] Usar WebSocket como fonte primária
- [ ] Implementar lazy loading de imagens
- [ ] Code splitting de rotas
- [ ] Adicionar React DevTools Profiler

### Infraestrutura
- [ ] Habilitar compressão gzip
- [ ] Configurar cache headers
- [ ] Monitorar métricas de performance

---

## 📚 REFERÊNCIAS

- `PROJECT_REVIEW_AND_IMPROVEMENTS.md` - Análise anterior
- `.cursorrules` - Regras de performance
- `backend/apps/common/cache_manager.py` - Cache manager existente
- `backend/apps/common/performance_middleware.py` - Middleware de performance

---

**Próximo Passo:** Começar pela Semana 1 (itens críticos)

