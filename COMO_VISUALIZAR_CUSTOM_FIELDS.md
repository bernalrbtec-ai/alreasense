# 📍 ONDE FICAM SALVOS OS CAMPOS CUSTOMIZADOS

**Resposta rápida:** No campo `custom_fields` do modelo `Contact` (JSONField no PostgreSQL)

---

## 🗄️ NO BANCO DE DADOS

### **Tabela:** `contacts_contact`
### **Campo:** `custom_fields` (tipo: JSONB no PostgreSQL)

**Estrutura:**
```json
{
  "clinica": "Hospital Veterinário Santa Inês",
  "valor": "R$ 1.500,00",
  "data_compra": "25/03/2024"
}
```

---

## 🔍 COMO VISUALIZAR

### **1. Via API (Recomendado)**

#### **Buscar um contato específico:**
```bash
GET /api/contacts/contacts/{contact_id}/
```

**Resposta:**
```json
{
  "id": "uuid",
  "name": "Maria Silva",
  "phone": "+5511999999999",
  "custom_fields": {
    "clinica": "Hospital Veterinário Santa Inês",
    "valor": "R$ 1.500,00"
  }
}
```

#### **Listar contatos com custom_fields:**
```bash
GET /api/contacts/contacts/
```

Todos os contatos retornam o campo `custom_fields` na resposta.

---

### **2. Via Django Shell**

```python
from apps.contacts.models import Contact

# Buscar contato
contact = Contact.objects.get(phone="+5511999999999")

# Ver custom_fields
print(contact.custom_fields)
# → {'clinica': 'Hospital Veterinário Santa Inês', 'valor': 'R$ 1.500,00'}

# Acessar campo específico
print(contact.custom_fields.get('clinica'))
# → 'Hospital Veterinário Santa Inês'
```

#### **Buscar contatos com campo customizado específico:**
```python
# Contatos que têm campo "clinica"
contacts = Contact.objects.filter(
    custom_fields__has_key='clinica'
)

# Contatos com valor específico
contacts = Contact.objects.filter(
    custom_fields__clinica='Hospital Veterinário Santa Inês'
)
```

---

### **3. Via Script de Verificação**

Execute o script criado:
```bash
cd backend
python verificar_custom_fields.py
```

Ou via Django shell:
```bash
python manage.py shell < verificar_custom_fields.py
```

---

### **4. Via Admin Django (se configurado)**

1. Acesse `/admin/contacts/contact/`
2. Abra um contato
3. Veja o campo "Custom Fields" na seção "Observações"

---

## 📊 EXEMPLO PRÁTICO

### **CSV Importado:**
```csv
Nome;DDD;Telefone;Clinica;Valor
Maria Silva;11;999999999;Hospital Veterinário Santa Inês;R$ 1.500,00
```

### **Como fica no banco:**

**Tabela:** `contacts_contact`

| id | name | phone | custom_fields |
|---|---|---|---|
| uuid | Maria Silva | +5511999999999 | `{"clinica": "Hospital Veterinário Santa Inês", "valor": "R$ 1.500,00"}` |

### **Como usar nas mensagens:**

```
{{saudacao}}, {{primeiro_nome}}! Você comprou na {{clinica}}.
```

**Renderiza:**
```
Boa tarde, Maria! Você comprou na Hospital Veterinário Santa Inês.
```

---

## 🔧 QUERIES ÚTEIS

### **Buscar contatos com campo específico:**
```python
# Contatos com campo "clinica"
Contact.objects.filter(custom_fields__has_key='clinica')

# Contatos com valor específico de "clinica"
Contact.objects.filter(custom_fields__clinica='Hospital Veterinário Santa Inês')

# Contatos com qualquer campo customizado
Contact.objects.exclude(custom_fields={})
```

### **Contar campos customizados:**
```python
# Quantos contatos têm campo "clinica"
Contact.objects.filter(custom_fields__has_key='clinica').count()

# Listar todos os campos customizados únicos
all_keys = set()
for contact in Contact.objects.exclude(custom_fields={}):
    all_keys.update(contact.custom_fields.keys())
print(all_keys)
```

---

## ✅ RESUMO

**Onde ficam salvos:**
- ✅ Campo `custom_fields` (JSONField) na tabela `contacts_contact`
- ✅ Disponível via API em `GET /api/contacts/contacts/{id}/`
- ✅ Acessível via Django ORM: `contact.custom_fields`

**Como visualizar:**
1. Via API (mais fácil)
2. Via Django shell
3. Via script `verificar_custom_fields.py`
4. Via Admin Django

**Como usar:**
- Nas mensagens: `{{clinica}}`, `{{valor}}`, etc.
- Via API: `contact.custom_fields['clinica']`
- Via ORM: `contact.custom_fields.get('clinica')`

