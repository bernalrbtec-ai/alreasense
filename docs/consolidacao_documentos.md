# 📋 Consolidação de Documentos - Plano de Ação

## 🎯 Objetivo
Consolidar e organizar os 214+ documentos markdown do projeto, removendo depreciados e criando estrutura clara.

---

## 📊 Análise Atual

### Estatísticas
- **Total de documentos:** 214+
- **Documentos ativos:** ~50
- **Documentos depreciados:** ~164
- **Documentos duplicados:** ~30

### Categorias Identificadas

1. **Especificações Oficiais** (ALREA_*)
2. **Análises Técnicas** (ANALISE_*)
3. **Guias Operacionais** (GUIA_*)
4. **Relatórios Temporários** (RELATORIO_*, RESUMO_*)
5. **Troubleshooting** (TROUBLESHOOTING_*, DIAGNOSTICO_*)
6. **Correções Aplicadas** (CORRECAO_*, CORRECOES_*)
7. **Implementações** (IMPLEMENTACAO_*)
8. **Prompts e Templates** (PROMPT_*)

---

## 🗂️ Estrutura Proposta

```
docs/
├── README.md                    # Índice principal
├── arquitetura/
│   ├── README.md
│   ├── sistema_completo.md     # Consolidado de ANALISE_COMPLETA_PROJETO_2025.md
│   ├── midia_anexos.md         # Consolidado de IMPLEMENTACAO_SISTEMA_MIDIA.md
│   └── notificacoes.md         # ARQUITETURA_NOTIFICACOES.md
├── modulos/
│   ├── README.md
│   ├── contatos/
│   │   ├── especificacao.md    # ALREA_CONTACTS_SPEC.md
│   │   ├── importacao.md       # PLANO_IMPORTACAO_CAMPANHAS_CSV.md
│   │   └── fluxo.md            # ANALISE_FLUXO_CONTATOS.md
│   ├── campanhas/
│   │   ├── especificacao.md    # ALREA_CAMPAIGNS_TECHNICAL_SPEC.md
│   │   ├── status.md           # ALREA_CAMPAIGNS_STATUS.md
│   │   └── websocket.md        # WEBSOCKET_CAMPAIGNS.md
│   └── chat/
│       ├── especificacao.md    # ANALISE_SISTEMA_CHAT_COMPLETA.md
│       ├── anexos.md           # IMPLEMENTACAO_ANEXOS_FLOW_CHAT.md
│       └── melhorias_ux.md     # MELHORIAS_UX_CHAT.md
├── guias/
│   ├── README.md
│   ├── deploy.md               # DEPLOY_CHECKLIST.md
│   ├── migrations.md           # GUIA_MIGRATIONS_FINAL.md
│   ├── workers.md              # CONFIGURAR_WORKER_RAILWAY.md
│   └── troubleshooting/
│       ├── rabbitmq.md        # TROUBLESHOOTING_RABBITMQ_CHAT.md
│       ├── webhooks.md         # TROUBLESHOOTING_WEBHOOK_EVENTOS.md
│       └── webhook_railway.md  # DIAGNOSTICO_WEBHOOK_RAILWAY.md
├── manutencao/
│   ├── README.md
│   ├── limpar_chat.md          # COMO_LIMPAR_CHAT.md
│   ├── limpar_rabbitmq.md      # LIMPAR_FILA_RABBITMQ.md
│   └── reduzir_logs.md         # REDUZIR_LOGS_RAILWAY.md
├── seguranca/
│   ├── README.md
│   ├── analise.md              # ANALISE_SEGURANCA_COMPLETA.md
│   ├── guia_rapido.md          # README_SEGURANCA_URGENTE.md
│   └── refatoracao.md          # REFATORACAO_COMPLETA.md
└── deprecated/
    ├── README.md               # Lista de documentos depreciados
    ├── relatorios/             # Relatórios antigos
    ├── correcoes_aplicadas/    # Correções já aplicadas
    └── prompts/                # Prompts e templates antigos
```

---

## ✅ Ações de Consolidação

### Fase 1: Identificação ✅
- [x] Listar todos os documentos
- [x] Identificar categorias
- [x] Marcar depreciados

### Fase 2: Organização (Em Andamento)
- [ ] Criar estrutura de pastas
- [ ] Mover documentos para pastas apropriadas
- [ ] Consolidar documentos similares
- [ ] Criar índices (README.md) em cada pasta

### Fase 3: Consolidação
- [ ] Mesclar documentos duplicados
- [ ] Atualizar referências cruzadas
- [ ] Remover informações obsoletas
- [ ] Adicionar data de última atualização

### Fase 4: Depreciação
- [ ] Mover depreciados para `docs/deprecated/`
- [ ] Criar README explicando por que foram depreciados
- [ ] Manter por 3 meses antes de deletar

---

## 📝 Documentos para Consolidar

### Relatórios Temporários → `docs/deprecated/relatorios/`
- `RELATORIO_FINAL_NOTURNO_23_OUT.md`
- `SESSAO_NOTURNA_COMPLETA_23_OUT.md`
- `SESSAO_REVISAO_COMPLETA_26OUT2025.md`
- `RELATORIO_FINAL_COMPLETO.md`
- `RESUMO_EXECUTIVO_*` (vários)

### Correções Aplicadas → `docs/deprecated/correcoes_aplicadas/`
- `CORRECAO_CHAT_COMPLETA_27OUT2025.md`
- `CORRECOES_APLICADAS.md`
- `CORRECOES_CAMPANHAS.md`
- `CORRECOES_DEPARTAMENTO_E_MENSAGENS.md`
- `CORRECOES_FINAIS_AUDIO.md`
- `CORRECOES_TEMPO_REAL_NOTIFICACOES.md`

### Prompts e Templates → `docs/deprecated/prompts/`
- `PROMPT_*` (todos)
- `INSTRUCOES_*` (temporários)

### Análises Substituídas
- `ANALISE_MELHORIAS_COMPLETA.md` → Consolidar em análises específicas
- `RESUMO_REVISAO_COMPLETA_OUT2025.md` → Informação consolidada
- `MELHORIAS_APLICADAS_OUT_2025.md` → Informação consolidada

---

## 🔄 Documentos para Manter na Raiz

### Essenciais
- `README.md` - Visão geral do projeto
- `rules.md` - Regras de desenvolvimento
- `LEIA_PRIMEIRO.md` - Guia de início

### Especificações Principais
- `ALREA_*` - Especificações oficiais (manter na raiz por visibilidade)
- `ANALISE_COMPLETA_PROJETO_2025.md` - Referência arquitetural principal

### Guias Críticos
- `DEPLOY_CHECKLIST.md` - Usado frequentemente
- `GUIA_MIGRATIONS_FINAL.md` - Referência importante

---

## 📋 Checklist de Execução

### Passo 1: Criar Estrutura
```bash
mkdir -p docs/{arquitetura,modulos/{contatos,campanhas,chat},guias/troubleshooting,manutencao,seguranca,deprecated/{relatorios,correcoes_aplicadas,prompts}}
```

### Passo 2: Mover Documentos
- Mover por categoria para pastas apropriadas
- Manter links simbólicos ou atualizar referências

### Passo 3: Criar Índices
- README.md em cada pasta explicando conteúdo
- Links para documentos principais

### Passo 4: Consolidar
- Mesclar documentos similares
- Remover duplicações
- Atualizar datas

### Passo 5: Depreciar
- Mover para `deprecated/`
- Adicionar nota explicativa
- Marcar data de remoção futura

---

## ⚠️ Atenção

### Não Deletar Imediatamente
- Manter depreciados por 3 meses
- Verificar se há referências antes de deletar
- Criar backup antes de deletar

### Manter Histórico
- Git mantém histórico mesmo após mover/deletar
- Documentar mudanças em commits descritivos

---

## 📅 Cronograma

- **Semana 1:** Criar estrutura e mover documentos
- **Semana 2:** Consolidar e atualizar referências
- **Semana 3:** Revisar e validar
- **Semana 4:** Depreciar e arquivar

---

**Criado em:** 2025-11-17
**Status:** Em planejamento
**Próxima ação:** Criar estrutura de pastas

