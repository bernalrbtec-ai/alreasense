# 🏗️ ALREA Sense - Esclarecimento de Arquitetura

> **Data:** 2025-10-10  
> **Correções Aplicadas**

---

## ✅ CORREÇÕES REALIZADAS

### 1. **Servidor Evolution API**

#### ❌ Antes (INCORRETO):
- Aba "Servidor Evolution" em `/configurations` (área do cliente)
- Cada cliente poderia configurar seu próprio servidor

#### ✅ Agora (CORRETO):
- Servidor Evolution configurado APENAS pelo **SUPERADMIN**
- Localização: `/admin/evolution` (exclusivo para superadmin)
- **Todos os clientes usam de forma TRANSPARENTE**
- Cliente não vê nem tem acesso a essa configuração

---

### 2. **Módulo Contacts**

#### ❌ Antes (INCORRETO):
- Contacts como "produto" separado
- Item no menu apenas quando produto ativo

#### ✅ Agora (CORRETO):
- Contacts é uma **FEATURE** compartilhada
- Aparece no menu de **Flow** e **Sense**
- Não é um produto cobrado separadamente

---

## 📊 ARQUITETURA CORRETA

### Produtos e Features

```
🔵 ALREA Flow (Produto - Campanhas WhatsApp)
├── 👥 Contatos (Feature compartilhada)
├── 💬 Mensagens
└── 📱 Conexões WhatsApp

🟣 ALREA Sense (Produto - Análise de Sentimento)
├── 👥 Contatos (Feature compartilhada)
└── 🧪 Experimentos

🟢 ALREA API (Produto - Integração)
└── 📚 API Docs
```

---

## 🔐 CONTROLE DE ACESSO

### 🔴 SUPERADMIN (Admin do Sistema)

**Acesso:**
- ✅ Todos os produtos e clientes
- ✅ Gerenciar produtos e planos
- ✅ **Configurar Servidor Evolution** (`/admin/evolution`)
- ✅ Gerenciar clientes (tenants)
- ✅ Status do sistema

**Menu Superadmin:**
```
/admin/tenants      → Clientes
/admin/products     → Produtos
/admin/plans        → Planos
/admin/evolution    → ⭐ Servidor de Instância (Evolution API)
/admin/system       → Status do Sistema
/admin/notifications → Notificações
```

---

### 🟦 ADMIN (Admin do Cliente)

**Acesso:**
- ✅ Dados do seu tenant apenas
- ✅ Gerenciar contatos do seu tenant
- ✅ Gerenciar instâncias WhatsApp do seu tenant
- ✅ Configurar SMTP do seu tenant
- ✅ Ver seu plano
- ❌ **NÃO vê servidor Evolution** (transparente)

**Menu Cliente (exemplo com Flow ativo):**
```
/dashboard          → Dashboard
/contacts           → 👥 Contatos
/messages           → 💬 Mensagens
/connections        → 📱 Conexões
/billing            → Planos
/configurations     → ⚙️ Configurações
  ├── Instâncias WhatsApp
  ├── Configurações SMTP
  └── Meu Plano
```

---

## 🌐 FLUXO DE FUNCIONAMENTO

### Criação de Instância WhatsApp

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Cliente acessa /configurations → Instâncias WhatsApp    │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Cliente clica em "Nova Instância"                       │
│    - Preenche: Nome, Telefone                              │
│    - NÃO precisa saber do servidor Evolution               │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Backend (transparente para o cliente):                  │
│    - Busca servidor Evolution configurado pelo superadmin  │
│    - Cria instância no Evolution API                       │
│    - Salva no banco com tenant_id do cliente               │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. Cliente vê QR Code e conecta WhatsApp                   │
│    - Processo totalmente transparente                       │
│    - Não sabe qual servidor está usando                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 ESTRUTURA DE CONFIGURAÇÕES

### `/configurations` (Área do Cliente)

#### ✅ Abas Disponíveis:

**1. Instâncias WhatsApp**
- Criar/editar/excluir instâncias
- Gerar QR Code
- Verificar status
- Desconectar

**2. Configurações SMTP**
- Configurar servidor SMTP próprio
- Testar configuração
- Múltiplas configurações

**3. Meu Plano**
- Ver detalhes do plano atual
- Ver produtos incluídos
- Ver limites

#### ❌ Removido:
- ~~Servidor Evolution~~ (movido para `/admin/evolution`)

---

### `/admin/evolution` (Exclusivo Superadmin)

**Configurações Globais:**
- URL Base do servidor Evolution
- API Key Master
- Webhook URL
- Testar conexão
- Ver quantidade de instâncias criadas

**Características:**
- ⭐ **Uma configuração para todos os clientes**
- ⭐ **Transparente para clientes**
- ⭐ **Gerenciado centralmente**

---

## 🔄 BACKEND - Como Funciona

### Endpoint de Criação de Instância

```python
# apps/notifications/views.py
class WhatsAppInstanceViewSet(viewsets.ModelViewSet):
    def perform_create(self, serializer):
        # 1. Verifica limite do tenant
        tenant = self.request.tenant
        can_create, message = tenant.can_create_instance()
        if not can_create:
            raise ValidationError({'error': message})
        
        # 2. Salva instância com tenant
        instance = serializer.save(
            tenant=tenant,
            created_by=self.request.user
        )
        
        # 3. Cria no Evolution (transparente)
        # O método generate_qr_code busca o servidor Evolution global
        # configurado pelo superadmin automaticamente
```

### Busca do Servidor Evolution

```python
# apps/notifications/models.py
def generate_qr_code(self):
    # Busca servidor Evolution GLOBAL (configurado pelo superadmin)
    evolution_server = EvolutionConnection.objects.filter(
        is_active=True
    ).first()
    
    # Cliente não sabe qual servidor está usando
    # Tudo acontece de forma transparente
```

---

## 🎯 BENEFÍCIOS DESTA ARQUITETURA

### Para o Superadmin:
- ✅ Controle centralizado do servidor Evolution
- ✅ Atualizar servidor sem impactar clientes
- ✅ Métricas globais de uso
- ✅ Facilidade de manutenção

### Para o Cliente:
- ✅ Experiência simples e direta
- ✅ Não precisa configurar servidor
- ✅ Não precisa API keys
- ✅ Foco no negócio (criar instâncias e usar)

### Para o Sistema:
- ✅ Escalabilidade (múltiplos clientes, um servidor)
- ✅ Manutenção simplificada
- ✅ Custos reduzidos
- ✅ Segurança (clientes não têm acesso a credenciais master)

---

## 📝 CHECKLIST DE VERIFICAÇÃO

- [x] Produto "contacts" removido do billing
- [x] Contacts aparece em Flow e Sense
- [x] Aba "Servidor Evolution" removida de `/configurations`
- [x] Evolution API permanece em `/admin/evolution` (superadmin only)
- [x] Backend usa servidor Evolution global automaticamente
- [x] Frontend compilado e deployado
- [x] Documentação atualizada

---

## 🚀 RESULTADO FINAL

### Configurações do Cliente (`/configurations`)
```
📱 Instâncias WhatsApp  → Gerenciar minhas instâncias
📧 Configurações SMTP   → Meu servidor de email
💳 Meu Plano            → Ver detalhes do plano
```

### Admin do Sistema (`/admin/evolution`)
```
🌐 Servidor de Instância
   ├── URL: https://evo.rbtec.com.br
   ├── API Key: ********
   ├── Status: ✅ Ativo
   └── Instâncias Criadas: 15
```

---

**✅ Arquitetura corrigida e funcionando perfeitamente!**


