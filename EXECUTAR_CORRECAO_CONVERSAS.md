# 🚀 Como Executar Correção de Conversas na Railway

## Via Railway Dashboard (Recomendado)

1. **Acesse Railway Dashboard:** https://railway.app
2. **Abra seu projeto** AlreaSense
3. **Vá em Deployments** → Último deploy
4. **Clique em "Shell"** (ou vá em **Services** → **backend** → **Shell**)
5. **Execute:**

```bash
cd backend
python fix_conversation_names_railway.py
```

**OU** via comando Django:

```bash
cd backend
python manage.py fix_conversation_names
```

## O que o Script Faz

1. ✅ Busca todas as conversas individuais
2. ✅ Para cada conversa, busca contato correspondente por telefone
3. ✅ Atualiza `contact_name` se contato existir
4. ✅ Mostra estatísticas de atualizações

## Resultado Esperado

```
📊 Estatísticas:
   ✅ Conversas atualizadas: X
   ✅ Conversas já corretas: Y
   ⚠️  Conversas sem contato: Z
   📋 Total processadas: N
```

## Após Executar

- Conversas que tinham contatos cadastrados serão atualizadas automaticamente
- Conversas sem contatos continuarão mostrando número (normal)
- Novos contatos criados depois serão atualizados automaticamente pelo signal

---

**Nota:** Este comando precisa ser executado apenas **uma vez** para corrigir conversas existentes. Novos contatos serão atualizados automaticamente pelo signal.

