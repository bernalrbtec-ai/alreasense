# n8n: Webhook genérico (utility)

Um único webhook para ações utilitárias. O Sense envia um body com `action` e o n8n roteia para o fluxo correspondente. Assim não é preciso abrir uma URL nova para cada tipo de chamada.

**URL:** `N8N_UTILITY_WEBHOOK` (env).

**Método:** POST  
**Content-Type:** application/json

## Contrato genérico

### Entrada (body)

```json
{
  "action": "suggest_keywords",
  "department_name": "Suporte Técnico",
  "count": 10
}
```

- **`action`** (string, obrigatório): identifica o que executar. Ex.: `suggest_keywords`. Outras ações podem ser adicionadas depois.
- Demais campos dependem da ação.

No n8n: o payload do POST chega no item do Webhook (em geral `$json` já é o body). Use um nó **Switch** ou **IF** em `$json.action` para rotear (ex.: `suggest_keywords` → subfluxo Qwen; outras ações → outros nós).

---

## Ação: `suggest_keywords`

Usada ao sugerir palavras-chave de roteamento para um departamento (cadastro/edição). O n8n chama o Qwen e devolve a lista.

### Entrada (junto com `action`)

| Campo             | Tipo   | Obrigatório | Descrição                                      |
|------------------|--------|-------------|------------------------------------------------|
| `department_name`| string | sim         | Nome do departamento                           |
| `count`          | number | não         | Quantidade de palavras-chave (default 10, máx 30) |

### Saída esperada (response JSON)

```json
{
  "keywords": ["computador", "não liga", "sistema", "software", "erro", "técnico", "notebook", "internet", "tela", "teclado"]
}
```

- `keywords`: array de strings. O Sense aplica trim e lower em cada item; o n8n pode enviar em qualquer formato. Itens não-string são convertidos para string; lista inválida ou ausente resulta em `[]`.

### Prompt sugerido para o Qwen

```
Liste exatamente {{ $json.count }} palavras ou expressões curtas em português do Brasil que um cliente pode usar ao pedir ajuda para o departamento "{{ $json.department_name }}". 
São termos que a secretária virtual usa para encaminhar a conversa ao departamento certo.
Retorne APENAS um JSON válido com uma única chave "keywords" cujo valor é um array de strings. Sem explicação, sem markdown.
Exemplo: {"keywords": ["palavra1", "palavra2", ...]}
```

### Fluxo n8n (resumo)

1. Webhook (POST) recebe body com `action`, `department_name`, `count`.
2. Roteamento: se `action === 'suggest_keywords'` → segue para o subfluxo.
3. Nó Code ou LLM: monta o prompt e chama o Qwen.
4. Parse da resposta do Qwen (extrair `keywords`).
5. Responder ao webhook com `{ "keywords": [...] }`.

---

## Futuras ações

Novas ações podem usar o mesmo `N8N_UTILITY_WEBHOOK`: o Sense envia `action: "outra_acao"` e os campos necessários; o n8n adiciona um ramo no roteador e implementa o fluxo.
