# 🛠️ Scripts de Gerenciamento de Campanhas

Scripts Python para gerenciar campanhas durante deploys e emergências.

---

## 📋 Scripts Disponíveis

### 1. 🚨 **emergency_stop_campaigns.py** - Parada Emergencial

**Quando usar:**
- Sistema apresentando problemas críticos
- Necessidade de parar TODAS as campanhas imediatamente
- Antes de fazer manutenção urgente no banco de dados

**Como usar:**
```bash
python emergency_stop_campaigns.py
```

**O que faz:**
- Lista todas as campanhas em execução
- Pede confirmação (digite "SIM")
- Pausa TODAS as campanhas instantaneamente
- Cria logs de parada emergencial

**⚠️ ATENÇÃO:**
- Mensagens que estiverem sendo enviadas serão interrompidas
- Use apenas em emergências reais

---

### 2. 🔧 **recover_campaigns.py** - Recovery de Campanhas

**Quando usar:**
- Após um deploy que interrompeu campanhas
- Campanhas ficaram "travadas" (status running mas sem enviar)
- Precisa retomar campanhas pausadas

**Como usar:**
```bash
python recover_campaigns.py
```

**O que faz:**
- Detecta campanhas travadas (sem atividade por 5+ minutos)
- Lista campanhas pausadas
- Oferece ações:
  1. Pausar campanhas travadas
  2. Retomar todas as campanhas pausadas
  3. Retomar campanha específica
  4. Ver logs de uma campanha

**💡 Dica:**
- Execute após cada deploy
- Verifique se Celery Worker está rodando antes de retomar

---

### 3. 📊 **monitor_campaigns.py** - Monitor em Tempo Real

**Quando usar:**
- Durante execução de campanhas importantes
- Monitorar progresso em tempo real
- Detectar problemas rapidamente

**Como usar:**
```bash
python monitor_campaigns.py
```

**O que faz:**
- Atualiza a cada 5 segundos
- Mostra estatísticas gerais:
  - Campanhas em execução / pausadas
  - Total de mensagens enviadas / entregues / falhadas
- Mostra detalhes de cada campanha ativa:
  - Barra de progresso visual
  - Taxa de entrega
  - Tempo desde última mensagem
- Pressione Ctrl+C para sair

**💡 Dica:**
- Deixe rodando em um terminal separado durante campanhas grandes

---

## 📅 Workflow Recomendado para Deploy

### **Antes do Deploy:**

```bash
# 1. Monitorar campanhas ativas
python monitor_campaigns.py

# 2. Se houver campanhas críticas rodando:
#    Opção A: Aguardar completar
#    Opção B: Pausar manualmente no painel
#    Opção C: Usar parada emergencial
python emergency_stop_campaigns.py
```

### **Durante o Deploy:**

```bash
# Deploy automático pelo Railway
# Tempo estimado: 3-5 minutos
```

### **Após o Deploy:**

```bash
# 1. Verificar campanhas travadas
python recover_campaigns.py

# 2. Escolher ação:
#    - Pausar campanhas travadas (opção 1)
#    - Retomar campanhas pausadas (opção 2)

# 3. Monitorar retomada
python monitor_campaigns.py
```

---

## 🎯 Cenários Comuns

### **Cenário 1: Deploy Simples (sem campanhas rodando)**
```bash
# Nenhuma ação necessária
# Apenas verificar se sistema subiu corretamente
python recover_campaigns.py  # Verificar status
```

### **Cenário 2: Deploy com 1-2 Campanhas Pequenas**
```bash
# 1. Pausar no painel admin
# 2. Fazer deploy
# 3. Retomar no painel admin
```

### **Cenário 3: Deploy com Campanhas Grandes/Múltiplas**
```bash
# 1. Parada emergencial
python emergency_stop_campaigns.py

# 2. Fazer deploy

# 3. Recovery
python recover_campaigns.py
# Escolher opção 2 (Retomar todas)
```

### **Cenário 4: Campanha Travada (não está enviando)**
```bash
# 1. Verificar status
python recover_campaigns.py

# 2. Pausar campanha travada (opção 1)

# 3. Verificar logs (opção 4)

# 4. Corrigir problema (ex: reiniciar Celery)

# 5. Retomar (opção 3)
```

---

## ⚠️ Troubleshooting

### **Problema: Campanha retomada mas não envia mensagens**

**Possíveis causas:**
1. Celery Worker não está rodando
2. Redis não está acessível
3. Instância Evolution desconectada

**Solução:**
```bash
# Verificar Celery Worker no Railway:
# Dashboard → AlreaSense - Backend → Logs
# Procurar por: "celery worker" ou "Task process_campaign"

# Se necessário, fazer redeploy do Worker
```

### **Problema: Mensagens duplicadas após retomar**

**Causa:**
- Task foi executada 2x (antes e depois do deploy)

**Solução:**
- Sistema tem proteção contra duplicação (message_id único)
- Mensagens não serão enviadas 2x para o mesmo contato

### **Problema: Script não conecta no banco**

**Causa:**
- URL do banco incorreta
- IP mudou (Railway)

**Solução:**
```bash
# Atualizar DATABASE_URL nos scripts
# Pegar nova URL no Railway Dashboard → Database → Connect
```

---

## 🔐 Segurança

**⚠️ IMPORTANTE:**
- Esses scripts conectam diretamente no banco de produção
- Use com cuidado
- Sempre confirme antes de executar ações destrutivas
- Mantenha backups do banco antes de operações críticas

---

## 📞 Suporte

Em caso de dúvidas ou problemas:
1. Verificar logs no Railway Dashboard
2. Usar `recover_campaigns.py` opção 4 para ver logs detalhados
3. Consultar documentação do Celery

---

**Criado para Alrea Sense - Sistema de Campanhas WhatsApp**  
Versão 1.0 - Outubro 2025

