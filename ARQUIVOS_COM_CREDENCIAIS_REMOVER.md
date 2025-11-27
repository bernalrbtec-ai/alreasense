# ⚠️ ARQUIVOS COM CREDENCIAIS - REMOVER MANUALMENTE

Estes arquivos contêm credenciais e devem ser removidos manualmente após verificar se não são mais necessários:

## Arquivos com credenciais:

1. **NOVA_EVO_API_KEY.txt** - Contém API keys da Evolution
   - ⚠️ Se já foi aplicada no Railway, pode ser removida
   - ⚠️ NUNCA commitar no Git

2. **ENV_OTIMIZADO_RAILWAY.txt** - Contém SECRET_KEY e outras credenciais
   - ⚠️ Se já foi aplicado no Railway, pode ser removida
   - ⚠️ NUNCA commitar no Git

## Como remover:

```bash
# Verificar se credenciais já foram aplicadas no Railway
# Se sim, remover:
rm NOVA_EVO_API_KEY.txt
rm ENV_OTIMIZADO_RAILWAY.txt

# Adicionar ao .gitignore se ainda não estiver:
echo "NOVA_EVO_API_KEY.txt" >> .gitignore
echo "ENV_OTIMIZADO_RAILWAY.txt" >> .gitignore
```

## Arquivos já removidos:

✅ FORCE_DEPLOY.txt
✅ FORCE_REBUILD.txt
✅ railway_backend_logs.txt
✅ railway_full_logs.txt
✅ railway_logs_temp.txt
✅ DEBUG_502_RAILWAY.md
✅ FIX_PORTA_RAILWAY.md
✅ FIX_RAILWAY_FRONTEND_URGENTE.md
✅ CONFIGURACAO_RAILWAY_INTERFACE.md
✅ VERIFICAR_GIT.md
✅ SOLUCAO_RAILWAY_FRONTEND.md
✅ SOLUCAO_WORKER_TASKS.md
✅ Scripts .bat temporários
✅ Arquivos JSON de debug
✅ RESUMO_ALMOCO_27_OUT.txt

