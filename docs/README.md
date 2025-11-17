# 📚 Documentação Consolidada - ALREA SENSE

> **Última atualização:** 2025-11-17

## 🎯 Documentos Principais

### 🚀 Início Rápido
- **[README.md](../README.md)** - Visão geral e quick start
- **[rules.md](../rules.md)** - Regras de desenvolvimento e arquitetura
- **[LEIA_PRIMEIRO.md](../LEIA_PRIMEIRO.md)** - Guia de início para novos desenvolvedores

### 📖 Documentação Técnica

#### Arquitetura e Design
- **[ANALISE_COMPLETA_PROJETO_2025.md](../ANALISE_COMPLETA_PROJETO_2025.md)** - Análise arquitetural completa
- **[IMPLEMENTACAO_SISTEMA_MIDIA.md](../IMPLEMENTACAO_SISTEMA_MIDIA.md)** - Sistema de mídia e anexos
- **[ARQUITETURA_NOTIFICACOES.md](../ARQUITETURA_NOTIFICACOES.md)** - Sistema de notificações

#### Módulos Principais

**Contatos**
- **[ALREA_CONTACTS_SPEC.md](../ALREA_CONTACTS_SPEC.md)** - Especificação completa do módulo
- **[ANALISE_FLUXO_CONTATOS.md](../ANALISE_FLUXO_CONTATOS.md)** - Análise do fluxo (importação, edição, exclusão)
- **[PLANO_IMPORTACAO_CAMPANHAS_CSV.md](../PLANO_IMPORTACAO_CAMPANHAS_CSV.md)** - Importação CSV de contatos
- **[COMO_VISUALIZAR_CUSTOM_FIELDS.md](../COMO_VISUALIZAR_CUSTOM_FIELDS.md)** - Campos customizados

**Campanhas**
- **[ALREA_CAMPAIGNS_TECHNICAL_SPEC.md](../ALREA_CAMPAIGNS_TECHNICAL_SPEC.md)** - Especificação técnica
- **[ALREA_CAMPAIGNS_STATUS.md](../ALREA_CAMPAIGNS_STATUS.md)** - Status atual
- **[ALREA_CAMPAIGNS_RULES.md](../ALREA_CAMPAIGNS_RULES.md)** - Regras de negócio
- **[WEBSOCKET_CAMPAIGNS.md](../WEBSOCKET_CAMPAIGNS.md)** - WebSocket para campanhas

**Chat**
- **[ANALISE_SISTEMA_CHAT_COMPLETA.md](../ANALISE_SISTEMA_CHAT_COMPLETA.md)** - Análise completa do chat
- **[IMPLEMENTACAO_ANEXOS_FLOW_CHAT.md](../IMPLEMENTACAO_ANEXOS_FLOW_CHAT.md)** - Sistema de anexos no chat
- **[MELHORIAS_UX_CHAT.md](../MELHORIAS_UX_CHAT.md)** - Melhorias de UX

**Segurança**
- **[ANALISE_SEGURANCA_COMPLETA.md](../ANALISE_SEGURANCA_COMPLETA.md)** - Análise de segurança
- **[README_SEGURANCA_URGENTE.md](../README_SEGURANCA_URGENTE.md)** - Guia rápido de segurança
- **[REFATORACAO_COMPLETA.md](../REFATORACAO_COMPLETA.md)** - Refatorações de segurança aplicadas

### 🔧 Guias Operacionais

#### Deploy e Infraestrutura
- **[DEPLOY_CHECKLIST.md](../DEPLOY_CHECKLIST.md)** - Checklist de deploy
- **[CONFIGURAR_WORKER_RAILWAY.md](../CONFIGURAR_WORKER_RAILWAY.md)** - Configuração de workers
- **[GUIA_MIGRATIONS_FINAL.md](../GUIA_MIGRATIONS_FINAL.md)** - Guia de migrations

#### Troubleshooting
- **[TROUBLESHOOTING_RABBITMQ_CHAT.md](../TROUBLESHOOTING_RABBITMQ_CHAT.md)** - Problemas com RabbitMQ
- **[TROUBLESHOOTING_WEBHOOK_EVENTOS.md](../TROUBLESHOOTING_WEBHOOK_EVENTOS.md)** - Problemas com webhooks
- **[DIAGNOSTICO_WEBHOOK_RAILWAY.md](../DIAGNOSTICO_WEBHOOK_RAILWAY.md)** - Diagnóstico de webhooks

#### Manutenção
- **[COMO_LIMPAR_CHAT.md](../COMO_LIMPAR_CHAT.md)** - Como limpar dados do chat
- **[LIMPAR_FILA_RABBITMQ.md](../LIMPAR_FILA_RABBITMQ.md)** - Limpar filas RabbitMQ
- **[REDUZIR_LOGS_RAILWAY.md](../REDUZIR_LOGS_RAILWAY.md)** - Reduzir logs no Railway

### 📋 Especificações e Planos

#### Produtos e Features
- **[ALREA_PRODUCTS_STRATEGY.md](../ALREA_PRODUCTS_STRATEGY.md)** - Estratégia de produtos
- **[ALREA_SCHEDULED_MESSAGES_SPEC.md](../ALREA_SCHEDULED_MESSAGES_SPEC.md)** - Mensagens agendadas
- **[PROXIMAS_FEATURES_CHAT.md](../PROXIMAS_FEATURES_CHAT.md)** - Próximas features do chat

#### Integrações
- **[ALREA_ASAAS_INTEGRATION.md](../ALREA_ASAAS_INTEGRATION.md)** - Integração com Asaas
- **[WEBHOOK_EVOLUTION_SETUP.md](../WEBHOOK_EVOLUTION_SETUP.md)** - Setup de webhooks Evolution API

---

## 📁 Estrutura de Documentação

```
docs/
├── README.md (este arquivo)
├── arquitetura/        # Documentos de arquitetura
├── guias/              # Guias operacionais
├── especificacoes/     # Especificações técnicas
└── deprecated/         # Documentos depreciados (arquivados)
```

---

## ⚠️ Documentos Depreciados

Os seguintes documentos foram marcados como depreciados e movidos para `docs/deprecated/`:

### Relatórios Antigos (Out/2025)
- `RELATORIO_FINAL_NOTURNO_23_OUT.md`
- `SESSAO_NOTURNA_COMPLETA_23_OUT.md`
- `SESSAO_REVISAO_COMPLETA_26OUT2025.md`
- `DEPLOY_REALIZADO_27_OUT_ALMOCO.md`

### Análises Substituídas
- `ANALISE_MELHORIAS_COMPLETA.md` → Substituído por análises específicas
- `RESUMO_REVISAO_COMPLETA_OUT2025.md` → Informação consolidada
- `MELHORIAS_APLICADAS_OUT_2025.md` → Informação consolidada

### Troubleshooting Resolvido
- `PROBLEMA_WEBHOOK_RESOLVIDO.md` → Problema resolvido
- `CORRECAO_CHAT_COMPLETA_27OUT2025.md` → Correções aplicadas
- `CORRECOES_APLICADAS.md` → Correções aplicadas

### Guias Temporários
- `AÇÕES_AGORA.md` → Ações concluídas
- `PROXIMOS_PASSOS_AGORA.md` → Próximos passos atualizados
- `LEIA_ISTO_PRIMEIRO_OUT2025.md` → Substituído por `LEIA_PRIMEIRO.md`

---

## 🔍 Como Encontrar Documentação

### Por Tópico

**Arquitetura:**
- Análise completa → `ANALISE_COMPLETA_PROJETO_2025.md`
- Sistema de mídia → `IMPLEMENTACAO_SISTEMA_MIDIA.md`
- Notificações → `ARQUITETURA_NOTIFICACOES.md`

**Desenvolvimento:**
- Regras → `rules.md`
- Guia de início → `LEIA_PRIMEIRO.md`
- Migrations → `GUIA_MIGRATIONS_FINAL.md`

**Operações:**
- Deploy → `DEPLOY_CHECKLIST.md`
- Troubleshooting → Ver seção de troubleshooting
- Manutenção → Ver seção de manutenção

**Módulos:**
- Contatos → `ALREA_CONTACTS_SPEC.md`
- Campanhas → `ALREA_CAMPAIGNS_TECHNICAL_SPEC.md`
- Chat → `ANALISE_SISTEMA_CHAT_COMPLETA.md`

---

## 📝 Convenções

### Nomenclatura
- `ALREA_*` - Especificações oficiais
- `ANALISE_*` - Análises técnicas
- `GUIA_*` - Guias operacionais
- `IMPLEMENTACAO_*` - Documentação de implementação
- `TROUBLESHOOTING_*` - Resolução de problemas
- `RESUMO_*` - Resumos executivos

### Status dos Documentos
- ✅ **Atual** - Documento atual e mantido
- ⚠️ **Depreciado** - Informação antiga, verificar antes de usar
- ❌ **Removido** - Documento deletado (informação consolidada)

---

## 🤝 Contribuindo com Documentação

1. **Novos documentos:** Criar em `docs/` com nome descritivo
2. **Atualizações:** Atualizar data no cabeçalho
3. **Depreciação:** Mover para `docs/deprecated/` e atualizar este README
4. **Consolidação:** Mesclar informações similares em um único documento

---

## 📞 Suporte

Para dúvidas sobre documentação:
1. Verificar este README primeiro
2. Buscar no repositório por palavras-chave
3. Consultar `LEIA_PRIMEIRO.md` para visão geral
4. Abrir issue no GitHub se necessário

---

**Última revisão:** 2025-11-17
**Próxima revisão:** 2025-12-17

