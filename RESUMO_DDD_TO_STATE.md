# ✅ **RESUMO: INFERÊNCIA DE ESTADO POR DDD**

## 🎯 **RESPOSTA À SUA PERGUNTA:**

> "isso vai acontecer durante a importação e no cadastro individual?"

**SIM! A funcionalidade vai funcionar em AMBOS os casos:**

---

## 📍 **ONDE VAI FUNCIONAR:**

```
┌─────────────────────────────────────────────────────────────────┐
│                    APLICAÇÃO FRONTEND                            │
└─────────────────────────────────────────────────────────────────┘
                            │
            ┌───────────────┴───────────────┐
            │                               │
            ▼                               ▼
┌────────────────────────┐      ┌────────────────────────┐
│  📥 IMPORTAÇÃO CSV     │      │  ✍️  CADASTRO MANUAL   │
│  (Massa - Múltiplos)   │      │  (Individual - Um)     │
└────────────────────────┘      └────────────────────────┘
            │                               │
            │                               │
            ▼                               ▼
┌────────────────────────┐      ┌────────────────────────┐
│ ContactImportService   │      │  ContactSerializer     │
│ • _create_contact()    │      │  • create()            │
│ • _update_contact()    │      │  • update()            │
│ ✅ INFERÊNCIA DDD→UF   │      │  ✅ INFERÊNCIA DDD→UF  │
└────────────────────────┘      └────────────────────────┘
            │                               │
            └───────────────┬───────────────┘
                            ▼
                ┌──────────────────────┐
                │  Contact (Model)     │
                │  state = "SP" 🎉    │
                └──────────────────────┘
```

---

## 📦 **ARQUIVOS QUE SERÃO MODIFICADOS:**

### **1. `backend/apps/contacts/utils.py`** ⭐ CORE
- ✅ Adicionar mapeamento completo `DDD_TO_STATE_MAP` (67 DDDs)
- ✅ Criar `get_state_from_ddd(ddd)` → Retorna UF
- ✅ Criar `extract_ddd_from_phone(phone)` → Extrai DDD do telefone
- ✅ Criar `get_state_from_phone(phone)` → Conveniência

### **2. `backend/apps/contacts/services.py`** 📥 IMPORTAÇÃO CSV
- ✅ Importar funções de `utils.py`
- ✅ Modificar `_validate_row()` → Detectar conflitos DDD vs Estado
- ✅ Modificar `_create_contact()` → Inferir estado se vazio
- ✅ Modificar `_update_contact()` → Inferir estado se vazio

### **3. `backend/apps/contacts/serializers.py`** ✍️ CADASTRO INDIVIDUAL
- ✅ Importar funções de `utils.py`
- ✅ Modificar `ContactSerializer.create()` → Inferir estado se vazio
- ✅ Modificar `ContactSerializer.update()` → Inferir estado se vazio

---

## 🔄 **CENÁRIOS DE USO:**

### **CENÁRIO 1: Importação CSV com DDD separado**
```csv
Nome;DDD;Telefone;Cidade;Estado
João;11;999998888;;
```
**Resultado:** Estado = **SP** (inferido do DDD 11) ✅

---

### **CENÁRIO 2: Cadastro via API sem estado**
```json
POST /api/contacts/contacts/
{
  "name": "Maria",
  "phone": "21988887777"
}
```
**Resultado:** Estado = **RJ** (inferido do DDD 21) ✅

---

### **CENÁRIO 3: Atualização de telefone via API**
```json
PATCH /api/contacts/contacts/{id}/
{
  "phone": "47977776666"
}
```
**Se contato não tinha estado:**
**Resultado:** Estado = **SC** (inferido do DDD 47) ✅

---

### **CENÁRIO 4: Estado já informado (prioridade)**
```csv
Nome;DDD;Telefone;Estado
Pedro;11;999998888;SP
```
**Resultado:** Estado = **SP** (mantém informado, não sobrescreve) ✅

---

### **CENÁRIO 5: Conflito DDD vs Estado**
```csv
Nome;DDD;Telefone;Estado
Ana;11;999998888;RJ
```
**Resultado:** 
- Estado = **RJ** (mantém informado)
- ⚠️ Warning: "DDD 11 pertence a SP, mas estado informado é RJ"

---

## 📊 **RESUMO TÉCNICO:**

| Ponto de Entrada | Arquivo | Método | Status |
|------------------|---------|--------|--------|
| **Import CSV (preview)** | services.py | `preview_csv()` | ✅ Valida conflitos |
| **Import CSV (create)** | services.py | `_create_contact()` | ✅ Infere estado |
| **Import CSV (update)** | services.py | `_update_contact()` | ✅ Infere estado |
| **API Create** | serializers.py | `create()` | ✅ Infere estado |
| **API Update/Patch** | serializers.py | `update()` | ✅ Infere estado |

---

## 🎯 **REGRA DE PRIORIDADE:**

```
┌─────────────────────────────────────────────┐
│  PRIORIDADE DE PREENCHIMENTO DO "state"    │
├─────────────────────────────────────────────┤
│  1️⃣  ALTA    → Estado informado pelo usuário│
│  2️⃣  MÉDIA   → Estado inferido pelo DDD      │
│  3️⃣  BAIXA   → Deixar null (DDD inválido)   │
└─────────────────────────────────────────────┘
```

**Regra de Ouro:** 
- ✅ **NUNCA** sobrescrever estado já existente
- ✅ **SEMPRE** inferir quando estado estiver vazio
- ✅ **AVISAR** quando houver conflito (warning, não erro)

---

## 🧪 **COMO TESTAR:**

### **Teste 1: Cadastro via API (Postman/Insomnia)**
```bash
POST http://localhost:8000/api/contacts/contacts/
Authorization: Bearer {seu_token}
Content-Type: application/json

{
  "name": "Teste SP",
  "phone": "11999998888"
}

# Verificar: state deve ser "SP"
```

### **Teste 2: Importação CSV**
```csv
Nome;DDD;Telefone
Teste RJ;21;988887777
Teste SC;47;977776666
```
**Importar via:** `POST /api/contacts/contacts/import_csv/`
**Verificar:** Estados devem ser RJ e SC

### **Teste 3: Shell Django**
```bash
docker exec -it alrea_sense_backend_local python manage.py shell
```
```python
from apps.contacts.utils import get_state_from_ddd

print(get_state_from_ddd('11'))  # SP
print(get_state_from_ddd('21'))  # RJ
print(get_state_from_ddd('47'))  # SC
```

---

## 📋 **CHECKLIST RÁPIDO:**

- [ ] **utils.py:** Mapeamento DDD→Estado (67 DDDs)
- [ ] **utils.py:** Funções de extração e conversão
- [ ] **services.py:** Inferência na importação CSV
- [ ] **serializers.py:** Inferência no cadastro individual
- [ ] **Testar:** CSV com DDD separado
- [ ] **Testar:** API POST sem estado
- [ ] **Testar:** API PATCH em contato sem estado
- [ ] **Testar:** Conflito DDD vs Estado (warning)

---

## 🎉 **BENEFÍCIOS:**

1. ✅ **Auto-completar dados** - Contatos mais completos automaticamente
2. ✅ **Validação inteligente** - Detecta inconsistências DDD vs Estado
3. ✅ **Experiência do usuário** - Menos campos obrigatórios no form
4. ✅ **Qualidade de dados** - Base mais rica para segmentação
5. ✅ **Funciona em ambos** - Import CSV + Cadastro individual

---

## 📄 **DOCUMENTAÇÃO COMPLETA:**

👉 **Ver arquivo:** `PROMPT_IMPLEMENTACAO_DDD_TO_STATE.md`

**Contém:**
- Código completo para implementar
- Todos os cenários de teste
- Comandos para validar
- Exemplos de uso

---

**✅ RESUMO: SIM, VAI FUNCIONAR EM AMBOS OS LUGARES!**



