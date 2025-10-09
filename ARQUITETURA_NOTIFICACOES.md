# 📬 Arquitetura de Notificações - ALREA Sense

## 🎯 Como Funciona

### Visão Geral

O sistema de notificações tem **dois níveis**:

1. **Configuração (Admin)** - `/admin/notifications`
2. **Uso (Sistema)** - Envio automático para clientes

---

## 🔧 Configuração pelo Admin

### Página: Admin > Notificações

#### 1. 📧 **Servidores SMTP**
- Admin cadastra servidores de email
- Define qual é o **padrão** (checkbox)
- Testa antes de salvar
- **Uso**: Sistema usa o servidor padrão para enviar emails aos clientes

```
Exemplo:
- Nome: Gmail ALREA
- Host: smtp.gmail.com
- Porta: 587
- From: notificacoes@alrea.com
- ☑️ Servidor Padrão
```

#### 2. 💬 **Instâncias WhatsApp**
- Admin cadastra instâncias WhatsApp
- Gera QR Code e conecta
- Define qual é a **padrão** (checkbox)
- **Uso**: Sistema usa a instância padrão para enviar mensagens aos clientes

```
Exemplo:
- Nome: WhatsApp Notificações
- ☑️ Instância Padrão
→ Gerar QR Code
→ Escanear com WhatsApp
→ Conectado!
```

#### 3. 📝 **Templates de Notificação**
- Admin cria templates reutilizáveis
- Define tipo: Email ou WhatsApp
- Define categoria: Boas-vindas, Alerta, etc.
- **Uso**: Sistema usa templates para enviar notificações formatadas

---

## 🚀 Uso pelo Sistema

### Envio Automático

Quando o sistema precisa enviar uma notificação:

```python
# Exemplo: Boas-vindas a novo usuário
def enviar_boas_vindas(user):
    # 1. Busca template
    template = NotificationTemplate.objects.get(
        category='welcome',
        type='email'
    )
    
    # 2. Busca servidor SMTP padrão
    smtp = SMTPConfig.objects.get(is_default=True)
    
    # 3. Envia email
    send_email(
        to=user.email,
        subject=template.subject,
        body=template.content,
        smtp_config=smtp
    )
```

```python
# Exemplo: Alerta via WhatsApp
def enviar_alerta_whatsapp(user, mensagem):
    # 1. Busca instância WhatsApp padrão
    instance = WhatsAppInstance.objects.get(
        is_default=True,
        connection_state='open'
    )
    
    # 2. Envia mensagem
    send_whatsapp_message(
        to=user.phone_number,
        message=mensagem,
        instance=instance
    )
```

---

## 📊 Estrutura

### Modelos

```python
# Servidor de Email
SMTPConfig
  - name: "Gmail ALREA"
  - host: "smtp.gmail.com"
  - is_default: True  ← Usado pelo sistema

# Instância WhatsApp  
WhatsAppInstance
  - friendly_name: "WhatsApp Notificações"
  - is_default: True  ← Usado pelo sistema
  - connection_state: "open"

# Template
NotificationTemplate
  - name: "Boas-vindas"
  - type: "email"
  - category: "welcome"
  - content: "Olá {{nome}}, bem-vindo..."
```

---

## 🎯 Cenários de Uso

### 1. Novo Cliente (Tenant)
```
Sistema:
1. Cliente se cadastra
2. Sistema busca template "welcome" (email)
3. Sistema busca SMTP padrão
4. Envia email de boas-vindas
```

### 2. Alerta de Limite
```
Sistema:
1. Tenant atinge 90% do limite de mensagens
2. Sistema busca WhatsApp padrão
3. Envia alerta: "Você está próximo do limite..."
```

### 3. Renovação de Plano
```
Sistema:
1. Data de renovação se aproxima
2. Sistema busca template "billing_reminder"
3. Envia por Email (SMTP padrão) E WhatsApp (instância padrão)
```

---

## ⚙️ Configuração Recomendada

### Setup Inicial (Admin)

1. **Configurar SMTP:**
   ```
   Admin > Notificações > Servidor SMTP
   → Novo Servidor SMTP
   → Preencher dados (Gmail, SendGrid, etc)
   → ☑️ Definir como padrão
   → Testar envio
   → Salvar
   ```

2. **Configurar WhatsApp:**
   ```
   Admin > Notificações > Instâncias WhatsApp
   → Nova Instância
   → Nome: "Notificações ALREA"
   → ☑️ Definir como padrão
   → Salvar
   → Gerar QR Code
   → Escanear com WhatsApp
   → Conectado!
   ```

3. **Criar Templates:**
   ```
   Admin > Notificações > Templates
   → Novo Template
   → Nome: "Boas-vindas"
   → Tipo: Email
   → Categoria: Welcome
   → Conteúdo: "Olá {{nome}}..."
   → Salvar
   ```

---

## 🔐 Segurança

- ✅ Apenas **admins/staff** podem configurar servidores
- ✅ Credenciais SMTP armazenadas de forma segura
- ✅ API Keys WhatsApp criptografadas (se necessário)
- ✅ Tenants **não veem** configurações de infraestrutura

---

## 📈 Escalabilidade

### Múltiplos Servidores

Você pode ter:
- ✅ Múltiplos servidores SMTP (Gmail, SendGrid, AWS SES)
- ✅ Múltiplas instâncias WhatsApp
- ✅ Apenas **1 padrão** de cada tipo por vez

### Fallback

Se o servidor padrão falhar:
```python
# Buscar próximo disponível
smtp = SMTPConfig.objects.filter(
    is_active=True
).exclude(
    id=failed_smtp_id
).first()
```

---

## ✅ Status Atual

```
✅ Estrutura completa implementada
✅ Admin pode configurar SMTP
✅ Admin pode configurar WhatsApp
✅ Sistema usa servidores padrão
✅ Templates funcionando
✅ Histórico de envios
```

---

**Resumo:** Admin configura → Sistema usa → Clientes recebem! 🎯

