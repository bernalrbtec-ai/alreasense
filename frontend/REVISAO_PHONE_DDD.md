# Revisão: cadastro e uso do telefone com DDD

## O que foi revisado

- `frontend/src/lib/phoneDDD.ts` – constantes e helpers
- `frontend/src/components/PhoneInputWithDDD.tsx` – componente com dropdown DDD
- Uso em ContactModal, ContactsPage e NewConversationModal
- Alinhamento com backend (Contact.phone E.164, normalize_phone, serializer)

---

## Checklist produção (revisão final)

- **Validação no submit**: ContactModal e ContactsPage validam `isValidBrazilianE164(phone)` antes de enviar; mensagem clara se telefone vazio ou inválido.
- **E.164 no front**: `phoneDDD.ts` exporta `E164_BR_REGEX` e `isValidBrazilianE164()` para uso consistente.
- **“Outro” com 1 dígito**: `buildE164` exige DDD com 2 dígitos; não envia E.164 inválido.
- **Selecionar “Outro”**: ao escolher “Outro” no dropdown, chama-se `notify('', numberPart)` para o parent receber `''`; o `useEffect` só sincroniza DDD quando `value` não é vazio, evitando reverter “Outro” para o DDD anterior.
- **Backend**: serializer usa `normalize_phone`; modelo exige E.164; front não envia vazio nem formato inválido.

---

## Correções aplicadas

### 1. **PhoneInputWithDDD – useEffect e closure**

No `useEffect` que sincroniza a partir de `value`, era usada a variável `selectedDddKey` (que não está nas dependências), o que podia gerar closure desatualizada. Ao receber um `value` com DDD da lista, devemos sempre limpar `otherDdd` ao sair de “Outro”, sem depender de `selectedDddKey`. Ajuste: na branch em que `p.ddd` está na lista, apenas `setOtherDdd('')`, removendo o `if (selectedDddKey === VALUE_OTHER_DDD)`.

### 2. **“Outro” com 1 dígito**

Com “Outro” selecionado e apenas 1 dígito no DDD, o componente enviava E.164 (ex.: `+551999991234`), gerando DDD inválido. Ajuste: em `buildE164` exige-se `d.length === 2`; caso contrário retorna `''`. Assim, com “Outro” e 1 dígito o parent recebe string vazia e o envio fica bloqueado até completar 2 dígitos.

---

## Edge cases e comportamento

| Caso | Comportamento | Observação |
|------|----------------|------------|
| Número só com 8–9 dígitos (sem DDD) | `rawInputToE164` usa `defaultDdd` (17) | OK |
| 10–11 dígitos (DDD+number) | Tratado como DDD + número; `+55` é prefixado | OK |
| 12+ dígitos começando com 55 | Tratado como E.164 completo | OK |
| Busca com espaços/hífens (ex.: "17 99999-1234") | `isPhoneQuery` remove caracteres; `rawInputToE164` normaliza | OK |
| Limpar busca no NewConversationModal | Bloco de telefone some; usuário precisa digitar de novo | Aceitável |
| Contato com telefone internacional (não +55) | Hoje o fluxo é Brasil (+55). Número não-BR seria interpretado como DDD+number e ao montar de novo ganharia +55, corrompendo o valor | **Limitação conhecida**: suporte apenas Brasil; internacional não é garantido |

---

### 3. **Validação E.164 antes do submit (produção)**

- Em **ContactModal** e **ContactsPage**: antes de abrir o toast de loading e chamar a API, valida-se nome e telefone. Telefone deve ser não vazio e `isValidBrazilianE164(formData.phone)`. Caso contrário, exibe toast de erro com mensagem orientando a informar DDD e número (ex.: 17 99999-9999). Assim evita-se 400 do backend e melhora o feedback ao usuário.

### 4. **Bug “Outro” revertendo**

- Ao selecionar “Outro” no dropdown, não se chamava `onChange`, então o `value` continuava com o E.164 anterior e o `useEffect` (que sincroniza a partir de `value`) recolocava um DDD da lista e “Outro” sumia. Correção: (1) ao selecionar “Outro”, chamar `notify('', numberPart)` para o parent receber `''`; (2) no `useEffect`, só atualizar `selectedDddKey`/`otherDdd` quando `value` for não vazio; assim, com `value === ''` mantém-se a escolha “Outro”.

---

## Melhorias opcionais (não aplicadas)

1. **Número com 8 ou 9 dígitos**  
   Poderia validar no front (e desabilitar enviar) até ter 8 ou 9 dígitos no número; o backend já aceita pelo regex E.164.

2. **Internacional**  
   Se no futuro for necessário suportar outros países: detectar `value` que não começa com `+55` e não passar por `buildE164` com +55; exibir campo livre ou fluxo separado.

3. **Acessibilidade**  
   Labels com `sr-only` já existem; pode-se expor um label visível “DDD” ao lado do select se o design permitir.

4. **NewConversationModal – sincronizar searchQuery**  
   Ao editar só no PhoneInputWithDDD, `searchQuery` continua sendo o texto da busca. Não é obrigatório sincronizar; o fluxo atual é aceitável.

---

## Validação backend

- `Contact.phone`: `RegexValidator(r'^\+?[1-9]\d{1,14}$')` – E.164 genérico.
- Números gerados pelo componente (+55 + 2 + 8 ou 9 dígitos) estão dentro do esperado.
