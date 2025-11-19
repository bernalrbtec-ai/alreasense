# 🧪 Guia de Teste - Histórico de Contatos

## ✅ O que está pronto:

1. ✅ Tabela `contacts_history` criada no banco
2. ✅ Modelo `ContactHistory` no Django
3. ✅ Signals automáticos registrados
4. ✅ API REST completa (`/api/contacts/history/`)
5. ✅ Componente frontend `ContactHistory`
6. ✅ Integração no chat (sidebar lateral)
7. ✅ Integração na lista de contatos (modal)

## 🧪 Como testar:

### 1. Testar API diretamente

```bash
# Listar histórico de um contato
curl -X GET "http://localhost:8000/api/contacts/history/?contact_id=<UUID_DO_CONTATO>" \
  -H "Authorization: Bearer <TOKEN>"

# Criar anotação manual
curl -X POST "http://localhost:8000/api/contacts/history/" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "contact_id": "<UUID_DO_CONTATO>",
    "title": "Cliente interessado em produto X",
    "description": "Demonstrou interesse durante conversa"
  }'
```

### 2. Testar no Frontend

#### No Chat:
1. Abra uma conversa com um contato que existe na lista
2. Clique no ícone de relógio (⏰) no header do chat
3. A sidebar deve abrir mostrando o histórico
4. Teste criar uma nova anotação

#### Na Lista de Contatos:
1. Vá para `/contacts`
2. Clique no ícone de relógio (⏰) em qualquer contato
3. O modal deve abrir com o histórico
4. Teste criar/editar/excluir anotação

### 3. Testar Signals Automáticos

#### Teste de Mensagem do Chat:
1. Envie uma mensagem no chat para um contato que existe na lista
2. Verifique se aparece no histórico como "Mensagem Enviada (Chat)"
3. Receba uma mensagem desse contato
4. Verifique se aparece como "Mensagem Recebida (Chat)"

#### Teste de Transferência:
1. Transfira uma conversa para outro departamento
2. Verifique se aparece no histórico como "Transferência de Departamento"

#### Teste de Atribuição:
1. Atribua uma conversa para um atendente
2. Verifique se aparece no histórico como "Atribuição de Atendente"

## 🔍 Verificar no Banco:

```sql
-- Ver todos os eventos de um contato
SELECT 
    id,
    event_type,
    title,
    created_at,
    is_editable
FROM contacts_history
WHERE contact_id = '<UUID_DO_CONTATO>'
ORDER BY created_at DESC;

-- Contar eventos por tipo
SELECT 
    event_type,
    COUNT(*) as total
FROM contacts_history
GROUP BY event_type
ORDER BY total DESC;

-- Ver eventos recentes
SELECT 
    ch.id,
    ch.event_type,
    ch.title,
    c.name as contact_name,
    ch.created_at
FROM contacts_history ch
JOIN contacts_contact c ON c.id = ch.contact_id
ORDER BY ch.created_at DESC
LIMIT 20;
```

## ⚠️ Troubleshooting:

### Se os signals não estiverem funcionando:
1. Verifique se o servidor Django foi reiniciado após criar a tabela
2. Verifique os logs do Django para erros nos signals
3. Confirme que `apps.contacts.signals` está sendo importado no `apps.py`

### Se a API não retornar dados:
1. Verifique se o `contact_id` está correto
2. Verifique se o contato pertence ao tenant do usuário logado
3. Verifique os logs do Django para erros

### Se o frontend não mostrar histórico:
1. Abra o console do navegador (F12) e verifique erros
2. Verifique se a API está retornando dados (Network tab)
3. Verifique se o `contactId` está sendo passado corretamente

## 📊 Próximos Passos (Opcional):

1. **Integrar eventos de campanha**: Adicionar signals no `rabbitmq_consumer.py` para criar eventos quando mensagens de campanha são enviadas
2. **Filtros no frontend**: Adicionar filtros por tipo de evento
3. **Exportação**: Exportar histórico em PDF/CSV
4. **Busca**: Busca textual no histórico
5. **Paginação**: Paginar histórico para contatos com muitos eventos

