# 📝 PROPOSTA FINAL - Respostas Rápidas com Cache

## ✅ ÚLTIMA REVISÃO - Melhorias Implementadas

### Mudanças Aplicadas:
1. ✅ **Cache Backend**: Redis com TTL de 5 minutos
2. ✅ **Cache Frontend**: localStorage + invalidação inteligente
3. ✅ **Contador Visual**: Removido do dropdown, mantido apenas na página de gerenciamento
4. ✅ **Performance**: Busca otimizada, cache em múltiplas camadas
5. ✅ **UX**: Dropdown mais limpo, foco na usabilidade

---

## 1. Backend - Modelo e API com Cache

### Modelo (`backend/apps/chat/models.py`):
```python
class QuickReply(models.Model):
    """
    Respostas rápidas para uso no chat.
    Multi-tenant, isolado por tenant.
    """
    tenant = models.ForeignKey('tenancy.Tenant', on_delete=models.CASCADE)
    title = models.CharField(max_length=100, help_text="Título curto (ex: 'Boa tarde')")
    content = models.TextField(help_text="Conteúdo da resposta")
    category = models.CharField(max_length=50, blank=True, help_text="Categoria opcional")
    use_count = models.IntegerField(default=0, db_index=True)  # Para ordenação
    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey('authn.User', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Resposta Rápida"
        verbose_name_plural = "Respostas Rápidas"
        ordering = ['-use_count', 'title']  # Padrão: mais usadas primeiro, depois alfabética
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['tenant', 'category', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.tenant.name})"
```

### ViewSet com Cache (`backend/apps/chat/api/views_quick_replies.py`):
```python
from django.core.cache import cache
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.authn.permissions import CanAccessChat
from apps.chat.models import QuickReply
from apps.chat.api.serializers import QuickReplySerializer
import logging

logger = logging.getLogger(__name__)

# ✅ Cache TTL: 5 minutos (respostas não mudam frequentemente)
CACHE_TTL_SECONDS = 300
CACHE_KEY_PREFIX = "quick_replies"


class QuickReplyViewSet(viewsets.ModelViewSet):
    """
    ViewSet para respostas rápidas com cache Redis.
    ✅ Segurança: IsAuthenticated + CanAccessChat + Multi-tenant automático
    ✅ Cache: Redis com TTL de 5 minutos
    ✅ Ordenação: Apenas por uso (use_count) e título (title)
    """
    permission_classes = [IsAuthenticated, CanAccessChat]
    serializer_class = QuickReplySerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'content']
    ordering_fields = ['use_count', 'title']
    ordering = ['-use_count', 'title']
    
    def _get_cache_key(self, tenant_id: str, search: str = '', ordering: str = '') -> str:
        """Gera chave de cache única baseada em tenant, busca e ordenação."""
        cache_key = f"{CACHE_KEY_PREFIX}:tenant:{tenant_id}"
        if search:
            cache_key += f":search:{search.lower()}"
        if ordering:
            cache_key += f":order:{ordering}"
        return cache_key
    
    def _invalidate_cache(self, tenant_id: str):
        """Invalida cache do tenant (chamado após criar/editar/deletar)."""
        # Invalidar todas as variações de cache deste tenant
        pattern = f"{CACHE_KEY_PREFIX}:tenant:{tenant_id}:*"
        try:
            from apps.common.cache_manager import CacheManager
            CacheManager.invalidate_pattern(pattern)
            logger.info(f"🗑️ [QUICK REPLIES] Cache invalidado para tenant {tenant_id}")
        except Exception as e:
            logger.warning(f"⚠️ [QUICK REPLIES] Erro ao invalidar cache: {e}")
    
    def get_queryset(self):
        """Filtra por tenant automaticamente."""
        return QuickReply.objects.filter(
            tenant=self.request.user.tenant,
            is_active=True
        )
    
    def list(self, request, *args, **kwargs):
        """
        Lista respostas rápidas com cache Redis.
        ✅ Cache: 5 minutos
        ✅ Invalidação: Automática após criar/editar/deletar
        """
        tenant_id = str(request.user.tenant.id)
        search = request.query_params.get('search', '').strip()
        ordering = request.query_params.get('ordering', '-use_count,title')
        
        # ✅ Gerar chave de cache
        cache_key = self._get_cache_key(tenant_id, search, ordering)
        
        # ✅ Tentar buscar do cache
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            logger.debug(f"✅ [QUICK REPLIES] Cache HIT: {cache_key}")
            return Response(cached_data)
        
        # ✅ Cache MISS: buscar do banco
        logger.debug(f"❌ [QUICK REPLIES] Cache MISS: {cache_key}")
        queryset = self.filter_queryset(self.get_queryset())
        
        # Serializar dados
        serializer = self.get_serializer(queryset, many=True)
        response_data = {
            'results': serializer.data,
            'count': len(serializer.data)
        }
        
        # ✅ Salvar no cache
        cache.set(cache_key, response_data, CACHE_TTL_SECONDS)
        logger.debug(f"💾 [QUICK REPLIES] Cache salvo: {cache_key} (TTL: {CACHE_TTL_SECONDS}s)")
        
        return Response(response_data)
    
    def perform_create(self, serializer):
        """Define tenant e criador, invalida cache."""
        instance = serializer.save(
            tenant=self.request.user.tenant,
            created_by=self.request.user
        )
        # ✅ Invalidar cache após criar
        self._invalidate_cache(str(self.request.user.tenant.id))
        logger.info(f"✅ [QUICK REPLIES] Criada: {instance.title} (cache invalidado)")
    
    def perform_update(self, serializer):
        """Invalida cache após atualizar."""
        instance = serializer.save()
        # ✅ Invalidar cache após editar
        self._invalidate_cache(str(self.request.user.tenant.id))
        logger.info(f"✅ [QUICK REPLIES] Atualizada: {instance.title} (cache invalidado)")
    
    def perform_destroy(self, instance):
        """Invalida cache após deletar."""
        tenant_id = str(instance.tenant.id)
        instance.delete()
        # ✅ Invalidar cache após deletar
        self._invalidate_cache(tenant_id)
        logger.info(f"✅ [QUICK REPLIES] Deletada (cache invalidado)")
    
    @action(detail=True, methods=['post'], url_path='use')
    def mark_as_used(self, request, pk=None):
        """
        Incrementa contador de uso (chamado ao usar no chat).
        ✅ Invalida cache para atualizar ordenação.
        """
        quick_reply = self.get_object()
        quick_reply.use_count += 1
        quick_reply.save(update_fields=['use_count'])
        
        # ✅ Invalidar cache para atualizar ordenação (mais usadas primeiro)
        self._invalidate_cache(str(quick_reply.tenant.id))
        
        logger.debug(f"📊 [QUICK REPLIES] Uso incrementado: {quick_reply.title} ({quick_reply.use_count}x)")
        
        return Response({
            'use_count': quick_reply.use_count,
            'message': 'Contador atualizado'
        })
```

### Serializer (`backend/apps/chat/api/serializers.py`):
```python
class QuickReplySerializer(serializers.ModelSerializer):
    """Serializer para respostas rápidas."""
    
    class Meta:
        model = QuickReply
        fields = ['id', 'title', 'content', 'category', 'use_count', 'created_at', 'updated_at']
        read_only_fields = ['use_count', 'created_at', 'updated_at']
    
    def validate_content(self, value):
        """Validação: conteúdo não pode estar vazio."""
        if not value or not value.strip():
            raise serializers.ValidationError("Conteúdo não pode estar vazio.")
        if len(value) > 4000:  # Limite do WhatsApp
            raise serializers.ValidationError("Conteúdo muito longo (máximo 4000 caracteres).")
        return value.strip()
    
    def validate_title(self, value):
        """Validação: título não pode estar vazio."""
        if not value or not value.strip():
            raise serializers.ValidationError("Título não pode estar vazio.")
        return value.strip()
```

---

## 2. Frontend - Componente com Cache Local

### Hook com Cache (`useQuickReplies.ts`):
```typescript
import { useState, useEffect, useCallback } from 'react';
import { api } from '../lib/api';

interface QuickReply {
  id: string;
  title: string;
  content: string;
  category?: string;
  use_count: number;
  created_at: string;
  updated_at: string;
}

const CACHE_KEY = 'quick_replies_cache';
const CACHE_TIMESTAMP_KEY = 'quick_replies_cache_timestamp';
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutos

export function useQuickReplies(search: string = '', ordering: string = '-use_count,title') {
  const [quickReplies, setQuickReplies] = useState<QuickReply[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const getCachedData = (): QuickReply[] | null => {
    try {
      const cached = localStorage.getItem(CACHE_KEY);
      const timestamp = localStorage.getItem(CACHE_TIMESTAMP_KEY);
      
      if (!cached || !timestamp) return null;
      
      const age = Date.now() - parseInt(timestamp, 10);
      if (age > CACHE_TTL_MS) {
        // Cache expirado
        localStorage.removeItem(CACHE_KEY);
        localStorage.removeItem(CACHE_TIMESTAMP_KEY);
        return null;
      }
      
      return JSON.parse(cached);
    } catch (e) {
      console.error('Erro ao ler cache:', e);
      return null;
    }
  };

  const setCachedData = (data: QuickReply[]) => {
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify(data));
      localStorage.setItem(CACHE_TIMESTAMP_KEY, Date.now().toString());
    } catch (e) {
      console.error('Erro ao salvar cache:', e);
    }
  };

  const invalidateCache = useCallback(() => {
    localStorage.removeItem(CACHE_KEY);
    localStorage.removeItem(CACHE_TIMESTAMP_KEY);
  }, []);

  const fetchQuickReplies = useCallback(async (forceRefresh = false) => {
    // ✅ Tentar cache primeiro (se não for refresh forçado)
    if (!forceRefresh) {
      const cached = getCachedData();
      if (cached) {
        console.log('✅ [QUICK REPLIES] Cache HIT (localStorage)');
        setQuickReplies(cached);
        return;
      }
    }

    setLoading(true);
    setError(null);

    try {
      const { data } = await api.get('/chat/quick-replies/', {
        params: { search, ordering }
      });
      
      const replies = data.results || data;
      setQuickReplies(replies);
      
      // ✅ Salvar no cache
      setCachedData(replies);
      console.log('💾 [QUICK REPLIES] Cache salvo (localStorage)');
    } catch (err: any) {
      const errorMsg = err.response?.data?.error || 'Erro ao buscar respostas rápidas';
      setError(errorMsg);
      console.error('❌ [QUICK REPLIES] Erro:', errorMsg);
    } finally {
      setLoading(false);
    }
  }, [search, ordering]);

  useEffect(() => {
    fetchQuickReplies();
  }, [fetchQuickReplies]);

  return {
    quickReplies,
    loading,
    error,
    refetch: () => fetchQuickReplies(true),
    invalidateCache
  };
}
```

### Componente (`QuickRepliesButton.tsx`):
```typescript
import { useState, useEffect, useMemo } from 'react';
import { Zap, Search, X } from 'lucide-react';
import { useQuickReplies } from './useQuickReplies';
import { api } from '../lib/api';

interface QuickRepliesButtonProps {
  onSelect: (content: string) => void;
  disabled?: boolean;
}

export function QuickRepliesButton({ onSelect, disabled }: QuickRepliesButtonProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');
  
  // ✅ Usar hook com cache
  const { quickReplies, loading, refetch, invalidateCache } = useQuickReplies(
    search,
    '-use_count,title'
  );

  // ✅ Buscar ao abrir (com cache)
  useEffect(() => {
    if (isOpen) {
      refetch();
    }
  }, [isOpen, refetch]);

  const handleSelect = async (reply: QuickReply) => {
    // Inserir conteúdo no input
    onSelect(reply.content);
    
    // Incrementar contador de uso (sem bloquear UI)
    api.post(`/chat/quick-replies/${reply.id}/use/`)
      .then(() => {
        // ✅ Invalidar cache local para atualizar ordenação
        invalidateCache();
        // ✅ Refetch silencioso em background
        setTimeout(() => refetch(true), 500);
      })
      .catch(console.error);
    
    // Fechar dropdown
    setIsOpen(false);
    setSearch('');
  };

  const filtered = useMemo(() => {
    if (!search) return quickReplies;
    const lower = search.toLowerCase();
    return quickReplies.filter(r => 
      r.title.toLowerCase().includes(lower) || 
      r.content.toLowerCase().includes(lower)
    );
  }, [quickReplies, search]);

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        disabled={disabled}
        className="p-2 hover:bg-gray-200 active:scale-95 rounded-full transition-all duration-150 flex-shrink-0 shadow-sm hover:shadow-md"
        title="Respostas rápidas (/)"
      >
        <Zap className="w-6 h-6 text-gray-600" />
      </button>
      
      {isOpen && (
        <div className="absolute bottom-full right-0 mb-2 w-80 bg-white rounded-lg shadow-xl border border-gray-200 z-50 max-h-96 flex flex-col">
          {/* Busca */}
          <div className="p-3 border-b">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Buscar respostas rápidas..."
                className="w-full pl-10 pr-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-[#00a884]"
                autoFocus
              />
              {search && (
                <button
                  onClick={() => setSearch('')}
                  className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>
          
          {/* Lista - ✅ SEM contador visual */}
          <div className="overflow-y-auto flex-1">
            {loading ? (
              <div className="p-4 text-center text-gray-500">Carregando...</div>
            ) : filtered.length === 0 ? (
              <div className="p-4 text-center text-gray-500">
                {search ? 'Nenhuma resposta encontrada' : 'Nenhuma resposta rápida cadastrada'}
              </div>
            ) : (
              filtered.map((reply) => (
                <button
                  key={reply.id}
                  onClick={() => handleSelect(reply)}
                  className="w-full px-4 py-3 text-left hover:bg-gray-50 border-b border-gray-100 last:border-0 transition-colors"
                >
                  {/* ✅ Layout simplificado - SEM contador */}
                  <div className="font-semibold text-gray-900">{reply.title}</div>
                  <div className="text-sm text-gray-600 mt-1 line-clamp-2">
                    {reply.content}
                  </div>
                  {reply.category && (
                    <div className="text-xs text-gray-400 mt-1">{reply.category}</div>
                  )}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
```

---

## 3. Página de Gerenciamento - Com Contador Visual

### Estrutura (`QuickRepliesPage.tsx`):
```typescript
// ✅ Contador visual APENAS na página de gerenciamento (para admin/gerentes)
export default function QuickRepliesPage() {
  const [search, setSearch] = useState('');
  const [ordering, setOrdering] = useState<'-use_count,title' | 'title'>('-use_count,title');
  const { quickReplies, loading, refetch } = useQuickReplies(search, ordering);

  return (
    <div className="space-y-4">
      {/* Filtros */}
      <div className="flex gap-4">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Buscar..."
          className="flex-1 px-4 py-2 border rounded-lg"
        />
        <select
          value={ordering}
          onChange={(e) => setOrdering(e.target.value as any)}
          className="px-4 py-2 border rounded-lg"
        >
          <option value="-use_count,title">Mais usadas</option>
          <option value="title">Título (A-Z)</option>
        </select>
      </div>

      {/* Lista com contador visual */}
      <div className="space-y-2">
        {quickReplies.map((reply) => (
          <div key={reply.id} className="p-4 border rounded-lg hover:bg-gray-50">
            <div className="flex items-center justify-between">
              <div className="font-semibold">{reply.title}</div>
              {/* ✅ Contador visual APENAS aqui (para admin/gerentes) */}
              <div className="text-sm text-gray-500">
                {reply.use_count > 0 ? (
                  <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded-full">
                    {reply.use_count}x usado{reply.use_count > 1 ? 's' : ''}
                  </span>
                ) : (
                  <span className="text-gray-400">Nunca usado</span>
                )}
              </div>
            </div>
            <div className="text-sm text-gray-600 mt-1">{reply.content}</div>
            {reply.category && (
              <div className="text-xs text-gray-400 mt-1">{reply.category}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
```

---

## 4. Integração no MessageInput

### Modificação Mínima (`MessageInput.tsx`):
```typescript
// ✅ ADICIONAR: Import
import { QuickRepliesButton } from './QuickRepliesButton';

// ✅ ADICIONAR: Handler para inserir conteúdo
const handleQuickReplySelect = useCallback((content: string) => {
  setMessage(prev => prev + (prev ? ' ' : '') + content);
  // Focar no input após inserir
  setTimeout(() => {
    const textarea = document.querySelector('textarea');
    textarea?.focus();
  }, 0);
}, []);

// ✅ ADICIONAR: Atalho de teclado "/"
useEffect(() => {
  const handleSlashKey = (e: KeyboardEvent) => {
    const target = e.target as HTMLElement;
    const isInInput = target.tagName === 'TEXTAREA' || target.closest('[data-mention-input]');
    if (e.key === '/' && isInInput && !message.trim() && !disabled) {
      e.preventDefault();
      // Abrir dropdown (via ref ou state do QuickRepliesButton)
      // Implementar conforme necessário
    }
  };
  
  document.addEventListener('keydown', handleSlashKey);
  return () => document.removeEventListener('keydown', handleSlashKey);
}, [message, disabled]);

// ✅ MODIFICAR: Adicionar botão antes do emoji picker
{/* Quick Replies button */}
<QuickRepliesButton 
  onSelect={handleQuickReplySelect}
  disabled={sending || !isConnected}
/>

{/* Emoji button - código existente */}
<div className="relative" ref={emojiPickerRef}>
  {/* ... código existente ... */}
</div>
```

---

## 5. Resumo das Melhorias

### ✅ Cache Implementado:
- **Backend**: Redis com TTL de 5 minutos
- **Frontend**: localStorage com TTL de 5 minutos
- **Invalidação**: Automática após criar/editar/deletar/usar

### ✅ UX Melhorada:
- **Dropdown**: Sem contador visual (mais limpo)
- **Página Admin**: Com contador visual (para gestão)
- **Performance**: Cache em múltiplas camadas
- **Busca**: Instantânea (filtro local)

### ✅ Ordenação:
- **Padrão**: Mais usadas primeiro (`-use_count,title`)
- **Alternativa**: Alfabética (`title`)
- **Atualização**: Cache invalida após uso

### ✅ Segurança:
- **Permissões**: `IsAuthenticated` + `CanAccessChat`
- **Multi-tenant**: Filtro automático
- **Validações**: Título e conteúdo obrigatórios

---

## 6. Checklist de Implementação

- [ ] Criar modelo `QuickReply`
- [ ] Criar migration
- [ ] Criar ViewSet com cache Redis
- [ ] Criar Serializer
- [ ] Adicionar rotas na API
- [ ] Testar cache backend (HIT/MISS)
- [ ] Criar hook `useQuickReplies` com cache localStorage
- [ ] Criar componente `QuickRepliesButton` (sem contador)
- [ ] Criar componente `QuickRepliesDropdown` (sem contador)
- [ ] Integrar no `MessageInput`
- [ ] Criar página de gerenciamento (com contador)
- [ ] Testar invalidação de cache
- [ ] Testar fluxo completo
- [ ] Validar performance (cache funcionando)

---

## ✅ Vantagens da Implementação Final:

1. **Performance**: Cache em 2 camadas (Redis + localStorage)
2. **UX Limpa**: Dropdown sem contador (foco no conteúdo)
3. **Gestão**: Contador apenas onde importa (página admin)
4. **Escalável**: Cache reduz carga no banco
5. **Inteligente**: Invalidação automática após mudanças


