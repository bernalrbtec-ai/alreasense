# Roteiro da Landing Page – ALREA SENSE

> Guia para criar a landing page com prints (screenshots) e descrições das principais funções da aplicação.

---

## 1. Visão geral do produto

**ALREA SENSE** é uma plataforma SaaS multi-tenant para:
- **Análise de sentimento e satisfação** em conversas do WhatsApp
- **Atendimento unificado** (chat, departamentos, respostas rápidas)
- **Gestão de contatos e campanhas** (envio em massa, métricas)
- **Relatórios e experimentos de IA** (prompts, métricas de áudio/transcrição)

**Público:** empresas que usam WhatsApp para atendimento e querem análise de sentimento, campanhas e relatórios.

---

## 2. Estrutura sugerida da landing page

| # | Seção | Conteúdo |
|---|--------|----------|
| 1 | **Hero** | Título, subtítulo, CTA (ex: "Começar" / "Solicitar demo") |
| 2 | **Problema / Benefício** | 1–2 frases sobre dor e solução |
| 3 | **Funcionalidades principais** | Blocos com print + título + descrição (3–6 blocos) |
| 4 | **Stack / Diferenciais** | Tecnologia, segurança, multi-tenant |
| 5 | **CTA final** | Repetir chamada para ação |
| 6 | **Rodapé** | Links, contato, termos |

---

## 3. Roteiro de prints e descrições por funcionalidade

Para cada funcionalidade: **1 screenshot** + **título** + **descrição curta** (1–3 frases).

---

### 3.1 Login

- **Rota:** `/login` (sem estar logado).
- **Print:** Tela de login com logo, campos e-mail/senha e botão "Entrar".
- **Título sugerido:** "Acesso seguro e simples"
- **Descrição:** "Login por e-mail e senha. Acesso isolado por tenant (multi-tenant). Após o login, o usuário é redirecionado para Dashboard (admin/gerente) ou Chat (agente)."

**Como capturar:** Abrir app em `http://localhost:5173/login` (ou URL de staging), fazer screenshot da tela inteira.

---

### 3.2 Dashboard

- **Rota:** `/dashboard` (usuário admin/gerente logado).
- **Print:** Dashboard com cards de resumo (tarefas, conversas, mensagens não lidas, etc.) e possivelmente lista de tarefas pendentes / semana.
- **Título sugerido:** "Visão geral do seu negócio"
- **Descrição:** "Painel com tarefas pendentes, conversas ativas e mensagens não lidas. Atualização em tempo real via WebSocket. Diferentes visões para admin/gerente e agente."

**Como capturar:** Login como admin → ir em Dashboard → screenshot com cards e lista de tarefas visíveis.

---

### 3.3 Chat (Flow / Atendimento)

- **Rota:** `/chat`.
- **Print:** Layout estilo WhatsApp: lista de conversas à esquerda e janela de chat à direita (com abas de departamento se houver).
- **Título sugerido:** "Chat unificado no estilo WhatsApp"
- **Descrição:** "Atendimento por departamentos, lista de conversas e janela de chat com mensagens, anexos, áudio e indicadores de leitura. Mensagens em tempo real via WebSocket."

**Como capturar:** Login com usuário que tem acesso ao chat → abrir uma conversa → screenshot mostrando lista + chat (desktop).

---

### 3.4 Contatos

- **Rota:** `/contacts`.
- **Print:** Lista/grade de contatos com busca, filtros, tags e botões de importar/exportar.
- **Título sugerido:** "Base de contatos centralizada"
- **Descrição:** "Cadastro e importação de contatos (CSV), tags, estágio de vida (lifecycle), segmentação RFM e campos customizados. Histórico de interações e uso em campanhas."

**Como capturar:** Menu Contatos → tela com tabela ou cards de contatos e barra de busca/filtros.

---

### 3.5 Campanhas

- **Rota:** `/campaigns`.
- **Print:** Lista de campanhas com status (rascunho, agendada, em execução, pausada, concluída) e métricas (enviadas, entregues, lidas, falhas).
- **Título sugerido:** "Campanhas de WhatsApp sob controle"
- **Descrição:** "Criação de campanhas com mensagens, seleção de contatos, agendamento e rotação por instâncias (Evolution API). Acompanhamento de progresso, taxa de entrega e leitura em tempo real."

**Como capturar:** Menu Campanhas → lista de campanhas com pelo menos um card visível (nome, status, números).

---

### 3.6 Conexões (Evolution API)

- **Rota:** `/connections`.
- **Print:** Lista de instâncias WhatsApp com status (conectado/desconectado), opção de gerar QR Code e dados da API.
- **Título sugerido:** "Múltiplas conexões WhatsApp"
- **Descrição:** "Gestão de instâncias da Evolution API: vincular números, gerar QR Code para conexão e monitorar status. Suporte a várias instâncias por tenant."

**Como capturar:** Menu Conexões → tela com pelo menos uma instância e botão/QR de conexão.

---

### 3.7 Agenda / Tarefas

- **Rota:** `/agenda`.
- **Print:** Calendário (mês/semana/dia) com tarefas e eventos, ou lista de tarefas com filtros.
- **Título sugerido:** "Agenda e tarefas integradas"
- **Descrição:** "Calendário com visões mês, semana e dia. Tarefas vinculadas a contatos e departamentos, com prazos e responsáveis. Integração com o fluxo de atendimento."

**Como capturar:** Menu Agenda → escolher visão (mês ou semana) com tarefas visíveis.

---

### 3.8 Respostas rápidas

- **Rota:** `/quick-replies`.
- **Print:** Lista de respostas rápidas com atalhos (ex.: /comando) e conteúdo da mensagem.
- **Título sugerido:** "Respostas rápidas para o time"
- **Descrição:** "Catálogo de respostas pré-definidas com atalhos. Os agentes usam no chat para agilizar atendimento e padronizar mensagens."

**Como capturar:** Menu Respostas Rápidas → lista de itens com atalho e texto.

---

### 3.9 Experimentos (Sense – IA)

- **Rota:** `/experiments`.
- **Print:** Abas "Prompts" e "Experimentos", lista de versões de prompt e execuções (replay).
- **Título sugerido:** "Experimentos de IA e análise de sentimento"
- **Descrição:** "Gestão de prompts de análise (sentimento, emoção, satisfação) e execução de experimentos (replay em mensagens). A/B de prompts para melhorar a qualidade da análise."

**Como capturar:** Menu Experimentos (usuário com produto Sense) → tela com prompts e/ou runs.

---

### 3.10 Relatórios

- **Rota:** `/reports` (acesso admin).
- **Print:** Gráficos e métricas (ex.: áudio processado, latência, uso de modelos, por departamento/usuário).
- **Título sugerido:** "Relatórios e métricas de uso"
- **Descrição:** "Métricas de transcrição, qualidade, latência e uso de modelos de IA. Relatórios por período, departamento e usuário para gestão e otimização."

**Como capturar:** Login como admin → Relatórios → screenshot com gráficos (Recharts) visíveis.

---

### 3.11 Planos e Billing

- **Rota:** `/billing`.
- **Print:** Plano atual do tenant, produtos incluídos (Flow, Sense, etc.) e limite de uso (ex.: contatos, instâncias).
- **Título sugerido:** "Planos e cobrança transparente"
- **Descrição:** "Visualização do plano atual, produtos ativos (Flow, Sense, etc.) e limites. Integração com Stripe para cobrança e gestão da assinatura."

**Como capturar:** Menu Planos → tela com plano e lista de produtos/limites.

---

### 3.12 Configurações

- **Rota:** `/configurations`.
- **Print:** Página de configurações (perfil, notificações, horário comercial, departamentos, etc.).
- **Título sugerido:** "Configurações do tenant e do time"
- **Descrição:** "Configurações gerais da conta: perfil, notificações, horário de atendimento, departamentos e usuários. Ajustes por tenant."

**Como capturar:** Menu Configurações → screenshot da área principal (abas ou seções visíveis).

---

## 4. Ordem recomendada para a landing (blocos de features)

Sugestão de ordem na página, do mais “visível” para o usuário ao mais “backend”:

1. **Chat** – coração do atendimento  
2. **Contatos** – base para campanhas e atendimento  
3. **Campanhas** – envio em massa e métricas  
4. **Conexões** – como conectar o WhatsApp  
5. **Agenda** – organização do time  
6. **Respostas rápidas** – produtividade no chat  
7. **Dashboard** – visão geral  
8. **Experimentos (IA)** – diferencial Sense  
9. **Relatórios** – decisão e métricas  
10. **Planos / Billing** – transparência comercial  
11. **Login** – pode ficar no hero ou em “Como começar”

---

## 5. Checklist para produção dos prints

- [ ] Ambiente limpo: dados de demonstração ou staging, sem informações reais de clientes.
- [ ] Resolução consistente: ex.: 1280×720 ou 1920×1080; mesmo tamanho para todos.
- [ ] Navegador: modo claro ou escuro definido (ex.: sempre claro na landing).
- [ ] Sem dados sensíveis: sem tokens, e-mails reais, telefones reais nos prints.
- [ ] Legendas opcionais: se quiser, número da seção (ex.: "3.3 Chat") no próprio asset ou na legenda da landing.

---

## 6. Textos sugeridos para hero e CTA

**Hero (título):**  
"Análise de sentimento e atendimento WhatsApp em uma única plataforma"

**Subtítulo:**  
"Chat unificado, campanhas, contatos e relatórios com IA. Multi-tenant, Evolution API e tempo real."

**CTA principal:**  
"Começar" ou "Solicitar demonstração"

**CTA secundário:**  
"Ver funcionalidades" (âncora para a seção de features)

---

## 7. Onde salvar os assets

Sugestão de estrutura:

```
frontend/public/
  landing/
    screenshots/
      login.png
      dashboard.png
      chat.png
      contacts.png
      campaigns.png
      connections.png
      agenda.png
      quick-replies.png
      experiments.png
      reports.png
      billing.png
      configurations.png
```

Se a landing for uma página estática fora do app (ex.: outro repo ou site), use a mesma nomenclatura e referencie este roteiro.

---

## 8. Próximos passos

1. **Capturar os screenshots** seguindo a seção 3 e o checklist da seção 5.  
2. **Escrever os textos finais** da landing (ajustando tom de voz e tamanho).  
3. **Implementar a landing** (página estática no frontend ou site separado).  
4. **Revisar** links, CTAs e responsividade (mobile).

---

*Documento criado com base na leitura do projeto ALREA SENSE (README, docs, rotas e páginas do frontend).*  
*Última atualização: 2025-02-15.*
