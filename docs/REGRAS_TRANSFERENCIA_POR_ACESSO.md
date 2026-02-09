# Regras de transferência por acesso ao departamento

Documento para fechar a regra de negócio. **SEM CÓDIGO** — só desenho da regra.

---

## 1. Quem pode transferir

- **Admin:** pode transferir qualquer conversa para qualquer departamento e, se quiser, para um agente específico (vê todos os departamentos e todos os atendentes).
- **Gerente:** mesmo critério que definirmos para “vê atendentes” (ex.: só dos departamentos que gerencia, ou todos — a definir).
- **Agente:** segue as regras abaixo.

---

## 2. O que o agente vê na transferência

### 2.1 Lista de departamentos

- O agente **vê todos os departamentos** do tenant no dropdown “Novo Departamento”.
- Ex.: mesmo tendo acesso só a Financeiro, ele vê Financeiro, Comercial, Suporte, etc.
- Objetivo: poder **encaminhar** a conversa para qualquer área; não precisa ter acesso à área para mandar para lá.

### 2.2 Dropdown de atendente (Novo Agente)

Comportamento depende do **departamento selecionado** no dropdown de departamento:

| Situação | Dropdown "Novo Agente" |
|----------|------------------------|
| **Nenhum departamento selecionado** | Desabilitado (ex.: texto "Selecione um departamento"). |
| **Departamento ao qual o agente TEM acesso** (ex.: Financeiro) | **Habilitado.** Mostra a lista de atendentes daquele departamento. Pode escolher "Manter no mesmo departamento" + um colega, ou só o departamento. |
| **Departamento ao qual o agente NÃO TEM acesso** (ex.: Comercial) | **Desabilitado.** Não mostra lista de atendentes. Texto sugerido: "Atendentes não visíveis para você" (ou similar). O agente só pode confirmar "Transferir para o departamento [Comercial]" (conversa cai na fila do Comercial, sem escolher pessoa). |

---

## 3. Resumo visual do fluxo (agente)

```
[Novo Departamento: ▼ Comercial    ]   ← Pode escolher qualquer departamento

[Novo Agente:        ▼ Desabilitado   ]   ← "Atendentes não visíveis para você"
```

- Botão **Transferir** fica habilitado quando há pelo menos um departamento escolhido (ou “manter no mesmo” quando já existe departamento atual).  
- Para departamento sem acesso: **não** é obrigatório escolher agente; o envio é só “para o departamento”.

```
[Novo Departamento: ▼ Financeiro   ]   ← Departamento que ele acessa

[Novo Agente:        ▼ João Silva  ]   ← Lista de colegas do Financeiro (habilitado)
                  (ou "Manter no mesmo departamento" + escolher colega)
```

---

## 4. Regras de backend (resumo conceitual)

- **Listar departamentos para o modal:** todos os departamentos do tenant (ou os que a política do sistema permitir para listagem em transferência).
- **Listar atendentes por departamento:**  
  - Se o usuário for **admin** (e gerente, se aplicável): pode retornar atendentes de qualquer departamento.  
  - Se o usuário for **agente**: retornar atendentes **apenas** dos departamentos aos quais o agente pertence. Para departamentos que ele não acessa, não enviar lista (ou enviar vazia); no front, dropdown fica **desabilitado** com o texto combinado (ex.: "Atendentes não visíveis para você").
- **Executar a transferência:**  
  - Permitir transferência “só para departamento” (sem agente) para qualquer departamento que o agente possa escolher na lista.  
  - Se vier “agente” no payload, validar que o agente pertence ao departamento informado e que o usuário que está transferindo tem permissão para atribuir àquele agente (ex.: pertence ao mesmo departamento que o agente).

---

## 5. Casos de uso fechados

| Ação do agente (só Financeiro) | Permitido? | Comportamento |
|--------------------------------|------------|---------------|
| Transferir para Comercial (só departamento) | Sim | Dropdown de agente desabilitado; conversa vai para a fila do Comercial. |
| Transferir para Financeiro + escolher colega João | Sim | Dropdown de agente habilitado; pode escolher João (ou outro do Financeiro). |
| Transferir para Comercial e tentar escolher alguém do Comercial | Não | Dropdown desabilitado; não há opção de escolher atendente do Comercial. |

---

## 6. Textos sugeridos na interface (para implementação futura)

- Dropdown de agente **desabilitado** (departamento sem acesso):  
  **"Atendentes não visíveis para você"**
- Dropdown de agente **desabilitado** (nenhum departamento selecionado):  
  **"Selecione um departamento"** (ou manter texto atual do produto).

---

Documento fechado para regra de negócio. Implementação seguirá este desenho.
