# 🧹 LIMPEZA DE DOCUMENTAÇÃO

## ✅ Arquivos Mantidos (Essenciais)

### **Principais:**
- `README.md` - Readme principal do projeto
- `rules.md` - Regras de desenvolvimento
- `DOCUMENTACAO_CONSOLIDADA.md` - **Documentação principal consolidada**
- `OTIMIZACOES_PERFORMANCE_CHAT.md` - Otimizações de performance
- `ANALISE_WEBSOCKET_EVOLUTION.md` - Análise WebSocket vs Webhooks

### **Específicos:**
- `LEIA_PRIMEIRO.md` - Guia de início rápido
- `PROXIMAS_FEATURES_CHAT.md` - Features planejadas
- `GUIA_RAPIDO_CAMPANHAS_EMAIL.md` - Campanhas de email
- `INDEX_CAMPANHAS_EMAIL.md` - Índice de campanhas
- `IMPLEMENTACAO_SISTEMA_MIDIA.md` - Sistema de mídia
- `ANALISE_COMPLETA_PROJETO_2025.md` - Análise arquitetural

## ❌ Arquivos para Deletar (Redundantes/Obsoletos)

**Total:** ~150 arquivos .md redundantes

**Categorias:**
- Relatórios antigos (Out/2025, Set/2025)
- Análises obsoletas
- Guias redundantes
- Resumos consolidados
- Troubleshooting antigo
- Prompts de implementação
- Correções já aplicadas

**Comando para deletar:**
```bash
# Listar arquivos a deletar
Get-ChildItem -Path . -Filter "*.md" -File | Where-Object { 
    $_.Name -notmatch "(README|rules|DOCUMENTACAO_CONSOLIDADA|OTIMIZACOES|ANALISE_WEBSOCKET|LEIA_PRIMEIRO|PROXIMAS_FEATURES|GUIA_RAPIDO_CAMPANHAS|INDEX_CAMPANHAS|IMPLEMENTACAO_SISTEMA_MIDIA|ANALISE_COMPLETA_PROJETO)" 
} | Select-Object Name
```

## 📝 Nota

Todos os arquivos mantidos têm informações consolidadas em `DOCUMENTACAO_CONSOLIDADA.md`.

**Próximo passo:** Executar limpeza manual ou criar script para deletar arquivos obsoletos.

