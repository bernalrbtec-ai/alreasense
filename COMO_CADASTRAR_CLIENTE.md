# 👥 COMO CADASTRAR CLIENTES NO ALREA

## 🎯 Diferença: Admin vs Cliente

```
┌─────────────────────────────────────────────────┐
│ ADMIN (Você)                                    │
├─────────────────────────────────────────────────┤
│ ✅ Acesso total ao sistema                      │
│ ✅ Configura servidores (Evolution, SMTP)       │
│ ✅ Cadastra clientes (tenants)                  │
│ ✅ Define planos e produtos para cada cliente   │
│ ✅ Cria usuários para os clientes               │
│ ✅ Vê dados de todos os clientes                │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ CLIENTE (Seus clientes)                         │
├─────────────────────────────────────────────────┤
│ ✅ Login próprio (email/senha)                  │
│ ✅ Vê apenas seus dados                         │
│ ✅ Usa apenas produtos liberados pelo admin     │
│ ✅ Interface simplificada (sem Admin)           │
│ ✅ Pode criar campanhas, contatos, etc.         │
│ ❌ NÃO vê outros clientes                       │
│ ❌ NÃO configura servidores                     │
└─────────────────────────────────────────────────┘
```

---

## 📋 COMO CADASTRAR UM NOVO CLIENTE (4 passos)

### 1️⃣ Criar Tenant (Empresa do Cliente)

1. Acesse: **http://localhost:5173**
2. Login: `admin@alrea.com` / `admin123`
3. Clique em **Admin** (canto superior direito)
4. Vá em **Tenants** → **Adicionar Tenant**
5. Preencha:
   ```
   Nome: Empresa XYZ Ltda
   Plano: Starter (ou Pro, Enterprise, etc)
   Status: Active
   UI Access: ✅ (Sim - cliente terá interface web)
   ```
6. **Salvar**

---

### 2️⃣ Criar Usuário para o Cliente

1. No Admin, vá em **Usuários** → **Adicionar usuário**
2. Preencha:
   ```
   Email: contato@empresaxyz.com
   Username: contato@empresaxyz.com (pode ser igual ao email)
   Senha: SenhaDoCliente123
   Confirmar senha: SenhaDoCliente123
   ```
3. Em **"Tenant & Role"**:
   ```
   Tenant: Empresa XYZ Ltda  ← Selecione o tenant criado
   Role: admin  ← Administrador do tenant (não superadmin)
   ```
4. **Salvar**

---

### 3️⃣ Ativar Produtos para o Cliente (Opcional - Add-ons)

Se o cliente contratou produtos além do plano base:

1. No Admin, vá em **Produtos dos Tenants** → **Adicionar**
2. Preencha:
   ```
   Tenant: Empresa XYZ Ltda
   Produto: ALREA API Pública  ← Exemplo de add-on
   É Add-on: ✅
   Preço Add-on: 79.00
   Ativo: ✅
   ```
3. **Salvar**

---

### 4️⃣ Cliente Faz Login

Agora o cliente pode acessar:

1. URL: **http://localhost:5173** (ou seu domínio)
2. Login: `contato@empresaxyz.com` / `SenhaDoCliente123`
3. Cliente verá apenas:
   - Dashboard
   - Produtos liberados (Flow, Sense, etc)
   - Seus próprios dados
   - **NÃO verá "Admin"** no menu

---

## 🎨 O QUE O CLIENTE VÊ vs ADMIN

### ADMIN (Superuser):
```
Menu:
├── 🏠 Dashboard
├── 📤 Campanhas (se tiver Flow)
├── 💬 Análises (se tiver Sense)
├── 👥 Contatos
├── 🔗 Conexões
├── 💳 Billing
└── ⚙️ Admin  ← SÓ ADMIN VÊ ISSO
    ├── Tenants
    ├── Usuários
    ├── Produtos
    ├── Planos
    ├── Servidor Evolution
    ├── Configurações SMTP
    └── Notificações
```

### CLIENTE (Tenant User):
```
Menu:
├── 🏠 Dashboard
├── 📤 Campanhas  ← Se tiver produto Flow
├── 💬 Análises   ← Se tiver produto Sense
├── 👥 Contatos
├── 🔗 Conexões
└── 💳 Billing
    ❌ NÃO tem "Admin"
```

---

## 💡 EXEMPLO PRÁTICO

**Caso:** Cliente "Loja ABC" contratou plano **Pro**

**Plano Pro inclui:**
- ✅ ALREA Flow (campanhas WhatsApp)
- ✅ ALREA Sense (análises IA)
- ❌ API Pública (não incluída, mas pode contratar como add-on)

**Passos:**

1. **Criar Tenant:**
   - Nome: `Loja ABC`
   - Plano: `Pro`
   - Status: `Active`

2. **Criar Usuário:**
   - Email: `contato@lojaabc.com`
   - Senha: `abc123`
   - Tenant: `Loja ABC`
   - Role: `admin` (admin do tenant, não superadmin)

3. **Cliente contrata API Pública como add-on (+R$ 79/mês):**
   - Admin → Produtos dos Tenants → Adicionar
   - Tenant: `Loja ABC`
   - Produto: `ALREA API Pública`
   - É Add-on: ✅
   - Preço: `79.00`
   - Gerar API Key: (será gerado automaticamente)

**Resultado:**
- Cliente paga: R$ 149 (Pro) + R$ 79 (API) = **R$ 228/mês**
- Cliente tem acesso a: Flow + Sense + API Pública
- Cliente loga com: `contato@lojaabc.com` / `abc123`

---

## 🔐 FLUXO DE ACESSO

```
1. Admin cadastra Tenant
   ↓
2. Admin cadastra Usuário do Tenant
   ↓
3. Admin envia credenciais para o cliente
   ↓
4. Cliente faz login
   ↓
5. Sistema valida produtos ativos
   ↓
6. Cliente vê apenas produtos do seu plano
```

---

## ⚡ TESTAR AGORA

**Para testar o sistema de campanhas:**

1. Use o tenant padrão: `Default Tenant`
2. Usuário: `admin@alrea.com` / `admin123`
3. Configure instância WhatsApp
4. Rode: `docker-compose -f docker-compose.local.yml exec backend python manage.py test_campaign_send`

**Para testar multi-tenant:**

1. Crie um novo tenant via Admin
2. Crie um usuário para esse tenant
3. Faça logout e login com o novo usuário
4. Veja que só aparece dados desse tenant!

---

**Pronto para cadastrar clientes!** 🚀

