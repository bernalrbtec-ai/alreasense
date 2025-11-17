#!/usr/bin/env python3
"""
Script para identificar e remover documentos markdown depreciados
"""

import os
import shutil
from pathlib import Path
from datetime import datetime

# Documentos essenciais que NUNCA devem ser removidos
ESSENCIAIS = {
    'README.md',
    'rules.md',
    'LEIA_PRIMEIRO.md',
    'DOCUMENTACAO_CONSOLIDADA.md',
    'ANALISE_COMPLETA_PROJETO_2025.md',
    'IMPLEMENTACAO_SISTEMA_MIDIA.md',
    'OTIMIZACOES_PERFORMANCE_CHAT.md',
    'ANALISE_WEBSOCKET_EVOLUTION.md',
    'PROXIMAS_FEATURES_CHAT.md',
    'GUIA_RAPIDO_CAMPANHAS_EMAIL.md',
    'INDEX_CAMPANHAS_EMAIL.md',
    'ARQUITETURA_NOTIFICACOES.md',
}

# Padrões de documentos depreciados
DEPRECIADOS_PATTERNS = [
    # Relatórios temporários antigos
    'RELATORIO_FINAL_NOTURNO_23_OUT.md',
    'SESSAO_NOTURNA_COMPLETA_23_OUT.md',
    'SESSAO_REVISAO_COMPLETA_26OUT2025.md',
    'DEPLOY_REALIZADO_27_OUT_ALMOCO.md',
    'RELATORIO_FINAL_COMPLETO.md',
    'RESUMO_EXECUTIVO_AUDITORIA.md',
    'RESUMO_EXECUTIVO_CAMPANHAS_EMAIL.md',
    'RESUMO_EXECUTIVO_MIGRACAO_WAHA.md',
    'RESUMO_EXECUTIVO_SEGURANCA.md',
    'RESUMO_ALMOCO_27_OUT.txt',
    'RESUMO_ALMOÇO_GRUPOS.md',
    
    # Correções já aplicadas
    'CORRECAO_CHAT_COMPLETA_27OUT2025.md',
    'CORRECOES_APLICADAS.md',
    'CORRECOES_CAMPANHAS.md',
    'CORRECOES_DEPARTAMENTO_E_MENSAGENS.md',
    'CORRECOES_FINAIS_AUDIO.md',
    'CORRECOES_TEMPO_REAL_NOTIFICACOES.md',
    'CORRECAO_AUDIO_PTT_COMPLETA.md',
    'CORRECAO_MARCACAO_LEITURA.md',
    'CORRECAO_COMUNIDADES_LID.md',
    'CORRECAO_ID_GRUPOS.md',
    'CORRECOES_IMPLEMENTADAS.md',
    
    # Análises substituídas
    'ANALISE_MELHORIAS_COMPLETA.md',
    'RESUMO_REVISAO_COMPLETA_OUT2025.md',
    'MELHORIAS_APLICADAS_OUT_2025.md',
    'MELHORIAS_IMPLEMENTADAS.md',
    'MELHORIAS_SUGERIDAS.md',
    'MUDANCAS_APLICADAS.md',
    
    # Prompts e templates temporários
    'PROMPT_DASHBOARD_COMPLETO.md',
    'PROMPT_IMPLEMENTACAO_DDD_TO_STATE.md',
    'PROMPT_INDICADOR_ESTADO_FRONTEND.md',
    'PROMPT_INDICADORES_COMBINADOS_FRONTEND.md',
    'PROMPT_UPDATE_WEBHOOK_METHOD.md',
    'INSTRUCOES_FRONTEND_ANEXOS.md',
    'INSTRUCOES_ROTACAO_RAPIDA.txt',
    
    # Guias temporários
    'AÇÕES_AGORA.md',
    'PROXIMOS_PASSOS_AGORA.md',
    'LEIA_ISTO_PRIMEIRO_OUT2025.md',
    'LEIA_ISTO_PRIMEIRO.md',
    'LIMPAR_DOCUMENTACAO.md',
    
    # Troubleshooting resolvido
    'PROBLEMA_WEBHOOK_RESOLVIDO.md',
    'DIAGNOSTICO_AUDIO_ANEXOS.md',
    'DIAGNOSTICO_FOTO_PERFIL.md',
    'DIAGNOSTICO_INSTANCIAS.md',
    'DIAGNOSTICO_WEBHOOK_RAILWAY.md',
    'CHECK_AUDIO_RAILWAY.md',
    
    # Resumos consolidados
    'RESUMO_CORRECAO_MIGRATIONS.md',
    'RESUMO_CORRECAO_NOMES_GRUPOS.md',
    'RESUMO_CORRECOES_DIA.md',
    'RESUMO_DDD_TO_STATE.md',
    'RESUMO_EDICAO_INSTANCIAS_CLIENTE.md',
    'RESUMO_EDICAO_TAGS_LISTAS_CONTATO.md',
    'RESUMO_IMPLEMENTACAO_COMPLETA.md',
    'RESUMO_PROBLEMAS_ATUAIS.md',
    
    # Documentos de sessão antigos
    'SESSION_COMPLETE_SUMMARY.md',
    'FINAL_SUMMARY.md',
    'FINAL_FIXES_SUMMARY.md',
    'ENTREGA_FINAL.md',
    
    # Análises antigas substituídas
    'ANALISE_ARQUITETURA_PRODUTOS.md',
    'ANALISE_BOTOES_CAMPANHA.md',
    'ANALISE_CHAT_MELHORIAS_CORRECOES.md',
    'ANALISE_CHAT_REDIS_REACOES.md',
    'ANALISE_COMPLETA_ANEXOS.md',
    'ANALISE_CRIACAO_INSTANCIA_EVOLUTION.md',
    'ANALISE_FLUXO_WEBHOOK_GLOBAL.md',
    'ANALISE_IMPLEMENTACAO_CALENDARIO.md',
    'ANALISE_MELHORIAS_CHAT.md',
    'ANALISE_MIGRACAO_EVOLUTION_PARA_WAHA.md',
    'ANALISE_MULTIPLAS_INSTANCIAS_CAMPANHA.md',
    'ANALISE_PERFORMANCE_DETALHADA.md',
    'ANALISE_PROBLEMA_EVOLUTION_CONFIG.md',
    'ANALISE_RABBITMQ_FINAL.md',
    'ANALISE_RECEBIMENTO_ANEXOS.md',
    'ANALISE_REDIS_VS_RABBITMQ_CHAT.md',
    'ANALISE_REACOES_IMPLEMENTACAO.md',
    'ANALISE_RESPOSTAS_CAMPANHA.md',
    'ANALISE_TEMPO_REAL_CHAT.md',
    'ANALISE_WEBHOOK_GLOBAL_EVOLUTION.md',
    
    # Implementações antigas
    'IMPLEMENTACAO_COMPLETA.md',
    'IMPLEMENTACAO_COMPLETA_BACKEND.md',
    'IMPLEMENTACAO_FINALIZADA.md',
    'IMPLEMENTACAO_BOTAO_CANCELAR.md',
    'IMPLEMENTACAO_DEPARTAMENTOS.md',
    'IMPLEMENTACAO_WEBHOOK_ENTREGAS.md',
    
    # Guias antigos
    'GUIA_EXECUCAO_SQL_DIRETO.md',
    'GUIA_TESTE_PERFORMANCE.md',
    'GUIA_TESTE_RABBITMQ_RAILWAY.md',
    'GUIA_TESTE_WEBHOOK_V2.md',
    'GUIA_VISUAL_CELERY_RAILWAY.md',
    'GUIA_APLICAR_ENV_OTIMIZADO.md',
    'GUIA_CORRECAO_NOMES.md',
    'GUIA_TESTE_IMPORTACAO_CAMPANHA.md',
    'GUIA_TESTE_LOCAL.md',
    
    # Outros depreciados
    'AUDITORIA_CODIGO_DUPLICADO_CHAT.md',
    'AUDITORIA_COMPLETA_2025.md',
    'CACHE_INTELIGENTE_MIDIA.md',
    'CHANGELOG_WEBHOOK_AUTOMATICO.md',
    'CHANGELOG_LOCAL.md',
    'COMPARACAO_FLUXOS_ENVIO_RECEBIMENTO.md',
    'COMPARACAO_TECNICA_EVOLUTION_WAHA.md',
    'CONFIG_RAILWAY_RAPIDA.md',
    'DEBUG_WEBSOCKET.md',
    'DESCOBERTA_LID_PARTICIPANTE.md',
    'DEPLOY_MONITORING_REPORT.md',
    'DEPLOY_REDIS_STREAMS.md',
    'EXPLICACAO_OPT_IN_OUT_PADRAO.md',
    'EXPLICACAO_RESILIENCIA_PROCESS_INCOMING_MEDIA.md',
    'FIX_AUDIO_PLAYER_UX.md',
    'FIX_RABBITMQ_URL_RAILWAY.md',
    'FIX_TEMPO_REAL_CONVERSAS.md',
    'FIX_TEMPO_REAL_CONVERSAS_V2.md',
    'FIX_TENANT_PLAN_UPDATE.md',
    'INVESTIGACAO_CAMPANHA_ISSUES.md',
    'LIMPAR_FILA_RABBITMQ.md',
    'LOGS_WEBHOOK_MONITORAMENTO.md',
    'MELHORIAS_ATUALIZACAO_CONVERSAS.md',
    'MELHORIAS_UX_CHAT.md',
    'MIGRACAO_REDIS_STREAMS_RESUMO.md',
    'OTIMIZACOES_PERFORMANCE_CHAT.md',  # Já consolidado
    'PERFORMANCE_UPGRADE_SUMMARY.md',
    'PLANO_MIGRACAO_RABBITMQ_REDIS_CHAT.md',
    'REDIS_CHAT_COMPARTILHADO.md',
    'REDUZIR_LOGS_RAILWAY.md',
    'REFATORACAO_COMPLETA.md',  # Já consolidado em segurança
    'REFATORACAO_EVOLUTION_CONFIG_27OCT2025.md',
    'REFATORACAO_RECEBIMENTO_ANEXOS.md',
    'REVISAO_COMPLETA_E_MELHORIAS.md',
    'REVISAO_SISTEMA_MIDIA.md',
    'ROTACAO_CREDENCIAIS_URGENTE.md',
    'ROTACAO_EVO_API_KEY.md',
    'SETUP_NOVO_EVOLUTION.md',
    'SOLUÇÃO_COMPLETA_GRUPOS.md',
    'STATUS_FRONTEND.md',
    'STATUS_SISTEMA_MIDIA.md',
    'SUMARIO_REFATORACAO_SEGURANCA.md',
    'TESTE_CELERY_RAILWAY.md',
    'TESTE_PERFORMANCE_APOS_LIMPEZA.md',
    'TESTE_WEBHOOK_COMPLETO.md',
    'TOAST_STANDARDIZATION_SUMMARY.md',
    'TROUBLESHOOTING_RABBITMQ_CHAT.md',
    'TROUBLESHOOTING_WEBHOOK_EVENTOS.md',
    'VERIFICACAO_CORS_ROTAS_APIS.md',
    'VERIFICACAO_IPV6_RAILWAY.md',
    'WEBHOOK_FLOW_PRIORIZADO.md',
]

# Padrões de arquivos para manter (ALREA_* são especificações oficiais)
MANTER_PATTERNS = [
    'ALREA_',
    'ANALISE_COMPLETA_PROJETO',
    'ANALISE_FLUXO_CONTATOS',
    'ANALISE_SEGURANCA_COMPLETA',
    'ANALISE_SISTEMA_CHAT_COMPLETA',
    'ARQUITETURA_',
    'COMO_',
    'DEPLOY_CHECKLIST',
    'GUIA_MIGRATIONS_FINAL',
    'GUIA_RAPIDO',
    'IMPLEMENTACAO_SISTEMA_MIDIA',
    'IMPLEMENTACAO_VARIAVEIS_DINAMICAS',
    'PLANO_IMPORTACAO_CAMPANHAS_CSV',
    'README',
    'rules',
    'LEIA_PRIMEIRO',
    'DOCUMENTACAO_CONSOLIDADA',
    'CONFIGURAR_WORKER',
    'COMO_LIMPAR',
    'WEBSOCKET_CAMPAIGNS',
]

def main():
    root = Path('.')
    deprecated_dir = root / 'docs' / 'deprecated'
    deprecated_dir.mkdir(parents=True, exist_ok=True)
    
    # Criar subpastas
    (deprecated_dir / 'relatorios').mkdir(exist_ok=True)
    (deprecated_dir / 'correcoes_aplicadas').mkdir(exist_ok=True)
    (deprecated_dir / 'prompts').mkdir(exist_ok=True)
    (deprecated_dir / 'analises_antigas').mkdir(exist_ok=True)
    (deprecated_dir / 'guias_antigos').mkdir(exist_ok=True)
    (deprecated_dir / 'outros').mkdir(exist_ok=True)
    
    # Encontrar todos os .md
    md_files = list(root.glob('*.md'))
    
    to_remove = []
    to_keep = []
    
    for md_file in md_files:
        filename = md_file.name
        
        # Sempre manter essenciais
        if filename in ESSENCIAIS:
            to_keep.append(filename)
            continue
        
        # Verificar se deve manter por padrão
        should_keep = any(pattern in filename for pattern in MANTER_PATTERNS)
        
        # Verificar se está na lista de depreciados
        is_deprecated = filename in DEPRECIADOS_PATTERNS
        
        if is_deprecated and not should_keep:
            to_remove.append(md_file)
        else:
            to_keep.append(filename)
    
    # Categorizar para mover
    relatorios = []
    correcoes = []
    prompts = []
    analises = []
    guias = []
    outros = []
    
    for file in to_remove:
        name = file.name.lower()
        if 'relatorio' in name or 'resumo' in name or 'sessao' in name:
            relatorios.append(file)
        elif 'correcao' in name or 'correcoes' in name or 'fix' in name:
            correcoes.append(file)
        elif 'prompt' in name or 'instrucoes' in name:
            prompts.append(file)
        elif 'analise' in name:
            analises.append(file)
        elif 'guia' in name or 'teste' in name or 'checklist' in name:
            guias.append(file)
        else:
            outros.append(file)
    
    # Mostrar resumo
    print(f"\n📊 RESUMO DA LIMPEZA\n")
    print(f"Total de arquivos .md encontrados: {len(md_files)}")
    print(f"Arquivos essenciais (mantidos): {len(to_keep)}")
    print(f"Arquivos depreciados (remover): {len(to_remove)}\n")
    
    print(f"📁 Categorização:")
    print(f"  - Relatórios: {len(relatorios)}")
    print(f"  - Correções aplicadas: {len(correcoes)}")
    print(f"  - Prompts/Templates: {len(prompts)}")
    print(f"  - Análises antigas: {len(analises)}")
    print(f"  - Guias antigos: {len(guias)}")
    print(f"  - Outros: {len(outros)}\n")
    
    if not to_remove:
        print("✅ Nenhum arquivo para remover!")
        return
    
    # Confirmar
    print("📋 Arquivos que serão removidos:\n")
    for file in sorted(to_remove, key=lambda x: x.name):
        print(f"  - {file.name}")
    
    print(f"\n⚠️  ATENÇÃO: {len(to_remove)} arquivos serão movidos para docs/deprecated/")
    # Execução automática (usuário autorizou remoção)
    print("✅ Executando remoção automática...\n")
    
    # Mover arquivos
    moved = 0
    errors = []
    
    for file in relatorios:
        try:
            dest = deprecated_dir / 'relatorios' / file.name
            shutil.move(str(file), str(dest))
            moved += 1
        except Exception as e:
            errors.append((file.name, str(e)))
    
    for file in correcoes:
        try:
            dest = deprecated_dir / 'correcoes_aplicadas' / file.name
            shutil.move(str(file), str(dest))
            moved += 1
        except Exception as e:
            errors.append((file.name, str(e)))
    
    for file in prompts:
        try:
            dest = deprecated_dir / 'prompts' / file.name
            shutil.move(str(file), str(dest))
            moved += 1
        except Exception as e:
            errors.append((file.name, str(e)))
    
    for file in analises:
        try:
            dest = deprecated_dir / 'analises_antigas' / file.name
            shutil.move(str(file), str(dest))
            moved += 1
        except Exception as e:
            errors.append((file.name, str(e)))
    
    for file in guias:
        try:
            dest = deprecated_dir / 'guias_antigos' / file.name
            shutil.move(str(file), str(dest))
            moved += 1
        except Exception as e:
            errors.append((file.name, str(e)))
    
    for file in outros:
        try:
            dest = deprecated_dir / 'outros' / file.name
            shutil.move(str(file), str(dest))
            moved += 1
        except Exception as e:
            errors.append((file.name, str(e)))
    
    # Resultado
    print(f"\n✅ {moved} arquivos movidos para docs/deprecated/")
    
    if errors:
        print(f"\n⚠️  {len(errors)} erros:")
        for filename, error in errors:
            print(f"  - {filename}: {error}")
    
    # Criar README na pasta deprecated
    readme_content = f"""# 📦 Documentos Depreciados

Esta pasta contém documentos que foram movidos por estarem fora de uso ou substituídos por versões mais recentes.

**Data da depreciação:** {datetime.now().strftime('%Y-%m-%d')}

## 📁 Estrutura

- `relatorios/` - Relatórios temporários antigos
- `correcoes_aplicadas/` - Correções já implementadas
- `prompts/` - Prompts e templates temporários
- `analises_antigas/` - Análises substituídas
- `guias_antigos/` - Guias temporários
- `outros/` - Outros documentos depreciados

## ⚠️ Atenção

Estes documentos são mantidos apenas para referência histórica. 
**Não use como referência para desenvolvimento atual.**

Para documentação atual, consulte `docs/README.md`.

## 🗑️ Remoção Futura

Estes documentos serão removidos após 3 meses da depreciação.
"""
    
    (deprecated_dir / 'README.md').write_text(readme_content, encoding='utf-8')
    print(f"\n📝 README.md criado em docs/deprecated/")
    print(f"\n✅ Limpeza concluída!")

if __name__ == '__main__':
    main()

