# 🎯 PROMPT DE IMPLEMENTAÇÃO: Auto-detecção de Estado pelo DDD

## 📋 **CONTEXTO**

O sistema ALREA Sense permite importação de contatos via CSV. Atualmente, o sistema:
- ✅ Detecta colunas DDD separadas
- ✅ Combina DDD + Telefone automaticamente
- ✅ Valida estados contra lista VALID_STATES
- ❌ **NÃO** infere o estado baseado no DDD

## 🎯 **OBJETIVO**

Implementar funcionalidade para **detectar automaticamente o estado (UF) baseado no DDD** quando:
1. A coluna DDD vier separada no CSV
2. A coluna Estado/UF estiver vazia ou não existir
3. O telefone estiver no formato correto

## 📊 **REGRA DE NEGÓCIO**

**Prioridade de preenchimento do campo `state`:**

1. **Prioridade ALTA:** Estado informado explicitamente na coluna Estado/UF
2. **Prioridade MÉDIA:** Estado inferido pelo DDD (quando coluna Estado vazia)
3. **Prioridade BAIXA:** Deixar null se DDD inválido ou não mapeado

**Importante:**
- Se o CSV já tem coluna Estado preenchida, **NÃO** sobrescrever
- Se DDD não corresponder ao estado informado, gerar **WARNING** (não bloquear)
- Se DDD não for encontrado no mapeamento, deixar estado vazio (não bloquear import)

## 🗺️ **MAPEAMENTO DDD → ESTADO (Brasil)**

```python
DDD_TO_STATE_MAP = {
    # São Paulo
    '11': 'SP', '12': 'SP', '13': 'SP', '14': 'SP', '15': 'SP',
    '16': 'SP', '17': 'SP', '18': 'SP', '19': 'SP',
    
    # Rio de Janeiro
    '21': 'RJ', '22': 'RJ', '24': 'RJ',
    
    # Espírito Santo
    '27': 'ES', '28': 'ES',
    
    # Minas Gerais
    '31': 'MG', '32': 'MG', '33': 'MG', '34': 'MG',
    '35': 'MG', '37': 'MG', '38': 'MG',
    
    # Paraná
    '41': 'PR', '42': 'PR', '43': 'PR', '44': 'PR',
    '45': 'PR', '46': 'PR',
    
    # Santa Catarina
    '47': 'SC', '48': 'SC', '49': 'SC',
    
    # Rio Grande do Sul
    '51': 'RS', '53': 'RS', '54': 'RS', '55': 'RS',
    
    # Distrito Federal
    '61': 'DF',
    
    # Goiás
    '62': 'GO', '64': 'GO',
    
    # Tocantins
    '63': 'TO',
    
    # Mato Grosso
    '65': 'MT', '66': 'MT',
    
    # Mato Grosso do Sul
    '67': 'MS',
    
    # Acre
    '68': 'AC',
    
    # Rondônia
    '69': 'RO',
    
    # Bahia
    '71': 'BA', '73': 'BA', '74': 'BA', '75': 'BA', '77': 'BA',
    
    # Sergipe
    '79': 'SE',
    
    # Pernambuco
    '81': 'PE', '87': 'PE',
    
    # Alagoas
    '82': 'AL',
    
    # Paraíba
    '83': 'PB',
    
    # Rio Grande do Norte
    '84': 'RN',
    
    # Ceará
    '85': 'CE', '88': 'CE',
    
    # Piauí
    '86': 'PI', '89': 'PI',
    
    # Pará
    '91': 'PA', '93': 'PA', '94': 'PA',
    
    # Amazonas
    '92': 'AM', '97': 'AM',
    
    # Roraima
    '95': 'RR',
    
    # Amapá
    '96': 'AP',
    
    # Maranhão
    '98': 'MA', '99': 'MA',
}
```

## 📁 **ARQUIVOS A MODIFICAR**

### **1. `backend/apps/contacts/utils.py`**

**Adicionar:**
```python
# No topo do arquivo, após imports

DDD_TO_STATE_MAP = {
    # [Incluir mapeamento completo acima]
}

def get_state_from_ddd(ddd):
    """
    Retorna a UF (estado) baseado no DDD
    
    Args:
        ddd (str|int): DDD de 2 dígitos
        
    Returns:
        str|None: Sigla do estado (ex: 'SP') ou None se não encontrado
        
    Examples:
        >>> get_state_from_ddd('11')
        'SP'
        >>> get_state_from_ddd(21)
        'RJ'
        >>> get_state_from_ddd('99')
        'MA'
        >>> get_state_from_ddd('00')
        None
    """
    if not ddd:
        return None
    
    ddd_str = str(ddd).strip()
    
    # Remover caracteres não numéricos
    ddd_clean = ''.join(filter(str.isdigit, ddd_str))
    
    # Se DDD tiver mais de 2 dígitos, pegar apenas os 2 primeiros
    # (pode ser telefone completo)
    if len(ddd_clean) > 2:
        ddd_clean = ddd_clean[:2]
    
    return DDD_TO_STATE_MAP.get(ddd_clean)


def extract_ddd_from_phone(phone):
    """
    Extrai o DDD de um telefone no formato E.164 ou brasileiro
    
    Args:
        phone (str): Telefone em qualquer formato
        
    Returns:
        str|None: DDD de 2 dígitos ou None
        
    Examples:
        >>> extract_ddd_from_phone('+5511999998888')
        '11'
        >>> extract_ddd_from_phone('11999998888')
        '11'
        >>> extract_ddd_from_phone('(11) 99999-8888')
        '11'
        >>> extract_ddd_from_phone('999998888')
        None
    """
    if not phone:
        return None
    
    # Remover formatação
    clean = re.sub(r'[^\d]', '', phone)
    
    # Se começar com 55 (código do Brasil), remover
    if clean.startswith('55') and len(clean) >= 12:
        clean = clean[2:]  # Remove '55'
    
    # DDD são os primeiros 2 dígitos
    if len(clean) >= 10:  # Mínimo: DDD (2) + número (8)
        return clean[:2]
    
    return None


def get_state_from_phone(phone):
    """
    Conveniência: extrai DDD do telefone e retorna o estado
    
    Args:
        phone (str): Telefone em qualquer formato
        
    Returns:
        str|None: Sigla do estado ou None
        
    Examples:
        >>> get_state_from_phone('+5511999998888')
        'SP'
        >>> get_state_from_phone('21988887777')
        'RJ'
    """
    ddd = extract_ddd_from_phone(phone)
    return get_state_from_ddd(ddd) if ddd else None
```

---

### **2. `backend/apps/contacts/services.py`**

#### **2.1. Adicionar import no topo do arquivo:**

```python
from .utils import normalize_phone, get_state_from_ddd, extract_ddd_from_phone
```

#### **2.2. Modificar método `_validate_row()` (linha ~247)**

**Adicionar validação de conflito DDD vs Estado:**

```python
def _validate_row(self, row, row_number):
    """
    Valida uma linha do CSV e retorna warnings
    
    Args:
        row: Dicionário com dados da linha
        row_number: Número da linha (para mensagens)
        
    Returns:
        list: Lista de warnings (não bloqueia import)
    """
    warnings = []
    
    # ... [código existente de validação de phone e email] ...
    
    # Validar state
    state = row.get('state') or row.get('estado') or row.get('uf')
    if state and state.upper() not in VALID_STATES:
        warnings.append({
            'row': row_number,
            'field': 'state',
            'value': state,
            'error': 'Estado/UF inválido (será ignorado)',
            'severity': 'warning'
        })
    
    # 🆕 NOVO: Validar conflito DDD vs Estado
    ddd = row.get('ddd') or row.get('DDD')
    phone = row.get('phone') or row.get('telefone')
    
    # Se não tem DDD separado, tentar extrair do telefone
    if not ddd and phone:
        ddd = extract_ddd_from_phone(phone)
    
    if ddd and state:
        state_from_ddd = get_state_from_ddd(ddd)
        if state_from_ddd and state_from_ddd.upper() != state.upper():
            warnings.append({
                'row': row_number,
                'field': 'state_ddd_mismatch',
                'value': f'DDD={ddd}, Estado={state}',
                'error': f'DDD {ddd} pertence a {state_from_ddd}, mas estado informado é {state}. Priorizando estado informado.',
                'severity': 'warning'
            })
    
    return warnings
```

#### **2.3. Modificar método `_create_contact()` (linha ~425)**

**Adicionar lógica de inferência de estado pelo DDD:**

```python
def _create_contact(self, row):
    """
    Cria um novo contato
    
    Args:
        row: Dicionário com dados do contato (já mapeado)
        
    Returns:
        Contact: Contato criado
    """
    # ... [código existente até city/state] ...
    
    city = row.get('city', '').strip() or None
    state = row.get('state', '').strip() or None
    
    # 🆕 NOVO: Inferir estado pelo DDD se não fornecido
    if not state:
        # Tentar obter DDD (pode estar em 'ddd' ou extrair de 'phone')
        ddd = row.get('ddd')
        if not ddd:
            # Tentar extrair do telefone normalizado
            phone_for_ddd = row.get('phone', '').strip()
            if phone_for_ddd:
                ddd = extract_ddd_from_phone(phone_for_ddd)
        
        # Se encontrou DDD, inferir estado
        if ddd:
            state = get_state_from_ddd(ddd)
            if state:
                # Log para auditoria
                print(f"  ℹ️  Estado '{state}' inferido pelo DDD {ddd}")
    
    contact = Contact.objects.create(
        tenant=self.tenant,
        name=row.get('name', '').strip(),
        phone=normalize_phone(row.get('phone', '')),
        email=row.get('email') or None,
        birth_date=self._parse_date(row.get('birth_date')),
        gender=row.get('gender') or None,
        city=city,
        state=state.upper() if state and len(state) == 2 else None,  # Normalizar para maiúscula
        country=row.get('country') or 'BR',
        zipcode=row.get('zipcode'),
        last_purchase_date=self._parse_date(row.get('last_purchase_date')),
        last_purchase_value=self._parse_decimal(row.get('last_purchase_value')),
        notes=row.get('notes'),
    )
    
    # ... [resto do código existente para tags] ...
    
    return contact
```

#### **2.4. Modificar método `_update_contact()` (linha ~460)**

**Adicionar lógica similar para atualização:**

```python
def _update_contact(self, contact, row):
    """
    Atualiza um contato existente
    
    Args:
        contact: Instância do contato a atualizar
        row: Dicionário com novos dados (já mapeado)
        
    Returns:
        Contact: Contato atualizado
    """
    # ... [código existente de atualização de campos] ...
    
    # State
    state = row.get('state') or row.get('estado') or row.get('uf')
    
    # 🆕 NOVO: Inferir estado pelo DDD se não fornecido E se contato não tem estado
    if not state and not contact.state:
        ddd = row.get('ddd')
        if not ddd:
            phone_for_ddd = row.get('phone', '').strip()
            if phone_for_ddd:
                ddd = extract_ddd_from_phone(phone_for_ddd)
        
        if ddd:
            state = get_state_from_ddd(ddd)
            if state:
                print(f"  ℹ️  Estado '{state}' inferido pelo DDD {ddd} (atualização)")
    
    if state and len(state) == 2:
        contact.state = state.upper()
    
    # ... [resto do código existente] ...
    
    return contact
```

---

### **3. `backend/apps/contacts/serializers.py`**

#### **3.1. Adicionar import no topo do arquivo:**

```python
from .utils import normalize_phone, get_state_from_ddd, extract_ddd_from_phone
```

#### **3.2. Modificar método `create()` da classe `ContactSerializer` (linha ~124)**

**Adicionar inferência de estado antes de criar:**

```python
def create(self, validated_data):
    """
    Cria novo contato
    
    🆕 NOVO: Infere estado pelo DDD se não fornecido
    """
    # Extrair tags e lists
    tag_ids = validated_data.pop('tag_ids', [])
    list_ids = validated_data.pop('list_ids', [])
    
    # 🆕 NOVO: Inferir estado pelo DDD se não fornecido
    if not validated_data.get('state'):
        phone = validated_data.get('phone')
        if phone:
            ddd = extract_ddd_from_phone(phone)
            if ddd:
                state = get_state_from_ddd(ddd)
                if state:
                    validated_data['state'] = state
                    # Log para auditoria
                    print(f"  ℹ️  Estado '{state}' inferido pelo DDD {ddd} (cadastro individual)")
    
    # Criar contato
    contact = Contact.objects.create(**validated_data)
    
    # Associar tags e lists
    if tag_ids:
        contact.tags.set(tag_ids)
    if list_ids:
        contact.lists.set(list_ids)
    
    return contact
```

#### **3.3. Modificar método `update()` da classe `ContactSerializer` (linha ~140)**

**Adicionar inferência de estado na atualização:**

```python
def update(self, instance, validated_data):
    """
    Atualiza contato existente
    
    🆕 NOVO: Infere estado pelo DDD se não fornecido E se contato não tem estado
    """
    # Extrair tags e lists
    tag_ids = validated_data.pop('tag_ids', None)
    list_ids = validated_data.pop('list_ids', None)
    
    # 🆕 NOVO: Inferir estado pelo DDD se:
    # 1. Estado não está sendo enviado no update (validated_data não tem 'state')
    # 2. Contato ainda não tem estado (instance.state é None)
    # 3. Telefone está sendo atualizado ou já existe
    if 'state' not in validated_data and not instance.state:
        phone = validated_data.get('phone', instance.phone)
        if phone:
            ddd = extract_ddd_from_phone(phone)
            if ddd:
                state = get_state_from_ddd(ddd)
                if state:
                    validated_data['state'] = state
                    print(f"  ℹ️  Estado '{state}' inferido pelo DDD {ddd} (atualização individual)")
    
    # Atualizar campos
    for attr, value in validated_data.items():
        setattr(instance, attr, value)
    instance.save()
    
    # Atualizar tags e lists
    if tag_ids is not None:
        instance.tags.set(tag_ids)
    if list_ids is not None:
        instance.lists.set(list_ids)
    
    return instance
```

---

## ✅ **CHECKLIST DE IMPLEMENTAÇÃO**

### **Parte 1: utils.py**
- [ ] Adicionar constante `DDD_TO_STATE_MAP` com 67 mapeamentos
- [ ] Criar função `get_state_from_ddd(ddd)`
- [ ] Criar função `extract_ddd_from_phone(phone)`
- [ ] Criar função `get_state_from_phone(phone)` (conveniência)
- [ ] Testar funções no shell Django

### **Parte 2: services.py (Importação CSV)**
- [ ] Adicionar imports das novas funções
- [ ] Modificar `_validate_row()` para detectar conflitos DDD vs Estado
- [ ] Modificar `_create_contact()` para inferir estado se vazio
- [ ] Modificar `_update_contact()` para inferir estado se vazio
- [ ] Adicionar logs informativos quando estado for inferido

### **Parte 3: serializers.py (Cadastro Individual via API)**
- [ ] Adicionar imports das novas funções
- [ ] Modificar `ContactSerializer.create()` para inferir estado se vazio
- [ ] Modificar `ContactSerializer.update()` para inferir estado se vazio
- [ ] Adicionar logs informativos quando estado for inferido

### **Parte 4: Testes**

**Testes de Importação CSV:**
- [ ] Testar CSV com DDD + Telefone, sem Estado → Deve inferir
- [ ] Testar CSV com DDD + Estado correto → Deve manter estado
- [ ] Testar CSV com DDD + Estado conflitante → Deve gerar warning e manter estado
- [ ] Testar CSV sem DDD, com telefone completo → Deve extrair DDD e inferir
- [ ] Testar CSV com DDD inválido → Deve deixar estado vazio (não quebrar)

**Testes de Cadastro Individual (API):**
- [ ] POST /contacts/ com telefone completo, sem estado → Deve inferir estado
- [ ] POST /contacts/ com telefone e estado → Deve manter estado informado
- [ ] PUT /contacts/{id}/ atualizando telefone em contato sem estado → Deve inferir
- [ ] PUT /contacts/{id}/ em contato que já tem estado → NÃO deve alterar estado
- [ ] POST /contacts/ com telefone de DDD inválido → Deve deixar estado null (não quebrar)

---

## 📋 **EXEMPLOS DE CASOS DE USO**

### **Caso 1: CSV com DDD separado, sem Estado**
```csv
Nome;DDD;Telefone;Cidade
João Silva;11;999998888;
Maria Santos;21;988887777;Rio de Janeiro
Pedro Costa;47;977776666;
```

**Resultado esperado:**
- João Silva → Estado: **SP** (inferido do DDD 11)
- Maria Santos → Estado: **RJ** (inferido do DDD 21), Cidade: Rio de Janeiro
- Pedro Costa → Estado: **SC** (inferido do DDD 47)

### **Caso 2: CSV com Estado preenchido (prioridade)**
```csv
Nome;DDD;Telefone;Estado
Ana Lima;11;999998888;SP
Carlos Souza;21;988887777;RJ
```

**Resultado esperado:**
- Ana Lima → Estado: **SP** (mantém o informado, DDD confirma)
- Carlos Souza → Estado: **RJ** (mantém o informado, DDD confirma)
- Sem warnings (DDDs conferem)

### **Caso 3: Conflito DDD vs Estado**
```csv
Nome;DDD;Telefone;Estado
Mariana;11;999998888;RJ
```

**Resultado esperado:**
- Mariana → Estado: **RJ** (mantém o informado, prioridade ALTA)
- ⚠️ **Warning:** "DDD 11 pertence a SP, mas estado informado é RJ. Priorizando estado informado."

### **Caso 4: Telefone completo, sem DDD separado**
```csv
Nome;Telefone
Roberto;11999998888
Fernanda;+5521988887777
```

**Resultado esperado:**
- Roberto → Estado: **SP** (extraído DDD 11 do telefone)
- Fernanda → Estado: **RJ** (extraído DDD 21 do telefone E.164)

---

## 🎯 **CRITÉRIOS DE SUCESSO**

A implementação estará completa quando:

1. ✅ CSV com DDD separado e sem Estado → Estado inferido automaticamente
2. ✅ CSV com Estado preenchido → Estado mantido (não sobrescrito)
3. ✅ Conflito DDD vs Estado → Warning gerado, estado informado mantido
4. ✅ Telefone completo sem DDD separado → DDD extraído, estado inferido
5. ✅ DDD inválido ou não mapeado → Import não quebra, estado fica null
6. ✅ Logs informativos quando estado for inferido
7. ✅ Testes manuais passando em todos os casos acima

---

## 🧪 **COMANDOS PARA TESTAR**

### **1. Testar funções utilitárias no shell Django:**
```bash
docker exec -it alrea_sense_backend_local python manage.py shell
```

```python
from apps.contacts.utils import get_state_from_ddd, extract_ddd_from_phone, get_state_from_phone

# Testar mapeamento DDD → Estado
print(get_state_from_ddd('11'))  # Deve retornar 'SP'
print(get_state_from_ddd('21'))  # Deve retornar 'RJ'
print(get_state_from_ddd('47'))  # Deve retornar 'SC'
print(get_state_from_ddd('99'))  # Deve retornar 'MA'
print(get_state_from_ddd('00'))  # Deve retornar None

# Testar extração de DDD do telefone
print(extract_ddd_from_phone('+5511999998888'))     # '11'
print(extract_ddd_from_phone('11999998888'))        # '11'
print(extract_ddd_from_phone('(11) 99999-8888'))    # '11'

# Testar conveniência
print(get_state_from_phone('+5511999998888'))  # 'SP'
print(get_state_from_phone('21988887777'))     # 'RJ'
```

### **2. Criar CSV de teste:**
```bash
# No Windows PowerShell
@"
Nome;DDD;Telefone;Cidade;Estado
João Silva;11;999998888;;
Maria Santos;21;988887777;Rio de Janeiro;
Pedro Costa;47;977776666;Joinville;SC
Ana Conflito;11;999998888;;RJ
"@ | Out-File -Encoding UTF8 teste_ddd.csv
```

### **3. Testar cadastro individual via API:**

**Criar contato SEM estado (deve inferir por DDD):**
```bash
curl -X POST http://localhost:8000/api/contacts/contacts/ \
  -H "Authorization: Bearer SEU_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Teste DDD SP",
    "phone": "11999998888",
    "email": "teste@exemplo.com"
  }'

# Resposta esperada: state = "SP"
```

**Criar contato COM estado (deve manter):**
```bash
curl -X POST http://localhost:8000/api/contacts/contacts/ \
  -H "Authorization: Bearer SEU_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Teste Estado RJ",
    "phone": "21988887777",
    "state": "RJ"
  }'

# Resposta esperada: state = "RJ" (mantém)
```

**Atualizar telefone em contato sem estado:**
```bash
curl -X PATCH http://localhost:8000/api/contacts/contacts/{ID}/ \
  -H "Authorization: Bearer SEU_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "47977776666"
  }'

# Resposta esperada: state = "SC" (inferido)
```

### **4. Testar import CSV via API:**
```bash
# (Usar Postman, Insomnia ou frontend para fazer upload do CSV)
# Endpoint: POST /api/contacts/contacts/import_csv/
```

---

## 📚 **REFERÊNCIAS**

- **Lista oficial de DDDs:** [Anatel](https://www.anatel.gov.br/setorregulado/plano-de-numeracao-brasileiro)
- **Arquivo modificado:** `backend/apps/contacts/utils.py`
- **Arquivo modificado:** `backend/apps/contacts/services.py`
- **Models:** `backend/apps/contacts/models.py` (Contact.state)

---

## ⚠️ **OBSERVAÇÕES IMPORTANTES**

1. **Manutenção:** Novos DDDs são raros no Brasil (último foi em 2016), mas o mapeamento deve ser atualizado se houver mudanças
2. **Apenas Brasil:** Esta lógica só funciona para números brasileiros (+55)
3. **DDD ≠ Cidade:** Um DDD pode cobrir múltiplas cidades (ex: DDD 11 = São Paulo + Grande SP)
4. **Não sobrescrever:** NUNCA sobrescrever estado já preenchido, apenas inferir quando vazio
5. **Performance:** O mapeamento é um dicionário (O(1)), sem impacto em performance

---

**✅ FIM DO PROMPT DE IMPLEMENTAÇÃO**

