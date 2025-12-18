# 📝 PROPOSTA REVISADA - Respostas Rápidas

## ✅ AJUSTES: Ordenação Simplificada

**Removido:** Ordenação por data  
**Mantido:** Apenas título e mais usadas

---

## 1. Backend - Modelo e API

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
        ordering = ['-use_count', 'title']  # ✅ Padrão: mais usadas primeiro, depois alfabética
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['tenant', 'category', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.tenant.name})"
```

### ViewSet (`backend/apps/chat/api/views_quick_replies.py`):
```python
class QuickReplyViewSet(viewsets.ModelViewSet):
    """
    ViewSet para respostas rápidas.
    ✅ Segurança: IsAuthenticated + CanAccessChat + Multi-tenant automático
    ✅ Ordenação: Apenas por uso (use_count) e título (title)
    """
    permission_classes = [IsAuthenticated, CanAccessChat]
    serializer_class = QuickReplySerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'content']  # Busca simples
    ordering_fields = ['use_count', 'title']  # ✅ Apenas uso e título (sem data)
    ordering = ['-use_count', 'title']  # ✅ Padrão: mais usadas primeiro, depois alfabética
    
    def get_queryset(self):
        """Filtra por tenant automaticamente."""
        return QuickReply.objects.filter(
            tenant=self.request.user.tenant,
            is_active=True
        )
    
    def perform_create(self, serializer):
        """Define tenant e criador automaticamente."""
        serializer.save(
            tenant=self.request.user.tenant,
            created_by=self.request.user
        )
    
    @action(detail=True, methods=['post'], url_path='use')
    def mark_as_used(self, request, pk=None):
        """Incrementa contador de uso (chamado ao usar no chat)."""
        quick_reply = self.get_object()
        quick_reply.use_count += 1
        quick_reply.save(update_fields=['use_count'])
        return Response({'use_count': quick_reply.use_count})
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

## 2. Frontend - Componente de Uso no Chat

### Componente (`QuickRepliesButton.tsx`):
```typescript
// Componente isolado, não modifica MessageInput diretamente
export function QuickRepliesButton({ 
  onSelect, 
  disabled 
}: { 
  onSelect: (content: string) => void;
  disabled?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [quickReplies, setQuickReplies] = useState<QuickReply[]>([]);
  const [loading, setLoading] = useState(false);
  
  // Buscar respostas ao abrir
  useEffect(() => {
    if (isOpen) {
      fetchQuickReplies();
    }
  }, [isOpen]);
  
  const fetchQuickReplies = async () => {
    setLoading(true);
    try {
      // ✅ Ordenação: mais usadas primeiro, depois alfabética
      const { data } = await api.get('/chat/quick-replies/', {
        params: { 
          search, 
          ordering: '-use_count,title'  // ✅ Apenas uso e título
        }
      });
      setQuickReplies(data.results || data);
    } catch (error) {
      console.error('Erro ao buscar respostas rápidas:', error);
    } finally {
      setLoading(false);
    }
  };
  
  const handleSelect = async (reply: QuickReply) => {
    // Inserir conteúdo no input
    onSelect(reply.content);
    
    // Incrementar contador de uso (sem bloquear UI)
    api.post(`/chat/quick-replies/${reply.id}/use/`).catch(console.error);
    
    // Fechar dropdown
    setIsOpen(false);
    setSearch('');
  };
  
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
        <QuickRepliesDropdown
          search={search}
          onSearchChange={setSearch}
          quickReplies={quickReplies}
          loading={loading}
          onSelect={handleSelect}
          onClose={() => {
            setIsOpen(false);
            setSearch('');
          }}
        />
      )}
    </div>
  );
}
```

### Dropdown (`QuickRepliesDropdown.tsx`):
```typescript
export function QuickRepliesDropdown({
  search,
  onSearchChange,
  quickReplies,
  loading,
  onSelect,
  onClose
}: QuickRepliesDropdownProps) {
  const filtered = useMemo(() => {
    if (!search) return quickReplies;
    const lower = search.toLowerCase();
    return quickReplies.filter(r => 
      r.title.toLowerCase().includes(lower) || 
      r.content.toLowerCase().includes(lower)
    );
  }, [quickReplies, search]);
  
  return (
    <div className="absolute bottom-full right-0 mb-2 w-80 bg-white rounded-lg shadow-xl border border-gray-200 z-50 max-h-96 flex flex-col">
      {/* Busca */}
      <div className="p-3 border-b">
        <input
          type="text"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Buscar respostas rápidas..."
          className="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-[#00a884]"
          autoFocus
        />
      </div>
      
      {/* Lista */}
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
              onClick={() => onSelect(reply)}
              className="w-full px-4 py-3 text-left hover:bg-gray-50 border-b border-gray-100 last:border-0 transition-colors"
            >
              <div className="flex items-center justify-between">
                <div className="font-semibold text-gray-900">{reply.title}</div>
                {reply.use_count > 0 && (
                  <div className="text-xs text-gray-400">
                    {reply.use_count}x
                  </div>
                )}
              </div>
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
  );
}
```

---

## 3. Página de Gerenciamento - Ordenação Simplificada

### Estrutura (`QuickRepliesPage.tsx`):
```typescript
// ✅ Ordenação: Apenas "Mais usadas" e "Título (A-Z)"
const [ordering, setOrdering] = useState<'-use_count,title' | 'title'>('-use_count,title');

// Opções de ordenação no UI
<select 
  value={ordering} 
  onChange={(e) => setOrdering(e.target.value as any)}
  className="px-3 py-2 border rounded-lg"
>
  <option value="-use_count,title">Mais usadas</option>
  <option value="title">Título (A-Z)</option>
</select>

// Buscar com ordenação
const { data } = await api.get('/chat/quick-replies/', {
  params: { 
    search,
    ordering  // ✅ Apenas uso e título
  }
});
```

---

## 4. Resumo das Mudanças

### ✅ Ordenação Simplificada:
- **Removido:** `created_at` dos `ordering_fields`
- **Mantido:** `use_count` (mais usadas) e `title` (alfabética)
- **Padrão:** `-use_count,title` (mais usadas primeiro, depois alfabética)

### ✅ Frontend:
- Dropdown mostra contador de uso (`5x`) ao lado do título
- Página de gerenciamento tem apenas 2 opções de ordenação
- API sempre retorna ordenado por uso + título

### ✅ UX Melhorada:
- Respostas mais usadas aparecem primeiro (mais prático)
- Ordenação alfabética como fallback (fácil de encontrar)
- Contador visual mostra popularidade (`5x`)

---

## 5. Checklist de Implementação

- [ ] Criar modelo `QuickReply` com ordenação `['-use_count', 'title']`
- [ ] Criar migration
- [ ] Criar ViewSet com `ordering_fields = ['use_count', 'title']`
- [ ] Criar Serializer
- [ ] Adicionar rotas na API
- [ ] Testar ordenação (mais usadas primeiro)
- [ ] Criar componente `QuickRepliesButton` com ordenação `-use_count,title`
- [ ] Criar componente `QuickRepliesDropdown` com contador de uso
- [ ] Integrar no `MessageInput`
- [ ] Criar página de gerenciamento com 2 opções de ordenação
- [ ] Testar fluxo completo
- [ ] Validar que respostas mais usadas aparecem primeiro

---

## ✅ Vantagens da Ordenação Simplificada:

1. **Mais Prático:** Respostas mais usadas aparecem primeiro
2. **Mais Simples:** Apenas 2 opções de ordenação (não confunde)
3. **Melhor UX:** Contador visual mostra popularidade
4. **Performance:** Menos campos para ordenar = mais rápido


