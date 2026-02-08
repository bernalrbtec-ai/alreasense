# Registro de retorno pela secretária (Bia)

Quando a Bia registra um retorno (fora do horário, após confirmar assunto e departamento), o backend cria evento na agenda. Regras:

## Duplicidade

- **Mesmo departamento:** Se já existir retorno pendente para essa conversa no **mesmo departamento**, não criar outro; unificar (atualizar assunto/descrição se fizer sentido ou manter um único evento).
- **Departamentos diferentes:** Se o cliente pedir retorno para **outro departamento**, criar **novo evento** (um por departamento por conversa).

## Template

- **Reutilizar** o template de título/descrição da "tarefa de fora do horário" (`AfterHoursTaskConfig`), quando existir para o tenant/departamento. Mesma lógica de variáveis (contact_name, message_content, next_open_time, etc.).

## Validação

- **Só criar quando** `business_hours.is_open === false` (retorno só fora do horário).
- **department_id:** Se for um departamento válido do tenant, criar a tarefa vinculada a esse departamento. Se **não for válido** (inválido ou vazio), criar de forma **geral** (sem departamento ou fallback para tarefa “geral” do tenant).

## Fluxo (resumo)

1. Bia confirma assunto e departamento e diz que registrou.
2. Bia envia no final da resposta (linhas removidas do texto ao cliente): `REGISTRAR_RETORNO`, `ASSUNTO_RETORNO: ...`, `DEPARTAMENTO_RETORNO: uuid`.
3. n8n extrai e envia no JSON: `register_return`, `return_subject`, `return_department_id`.
4. Backend: se `register_return` e fora do horário, valida departamento; verifica duplicidade (já existe retorno pendente mesmo departamento? unificar). Senão, cria tarefa com template de fora do horário; se departamento inválido, cria tarefa geral.
