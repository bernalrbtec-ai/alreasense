# Revisão: cadastro e uso do telefone com DDD

## Pronto para produção

**Sim.** O fluxo de telefone (país + DDD no Brasil + número) está maduro para produção:

- **Brasil**: dropdown DDD (17 padrão) + “Outro” + número; validação E.164; não envia DDD incompleto.
- **Internacional**: dropdown País (Brasil primeiro, 30+ países) + número nacional; mínimo 6 dígitos; E.164 preservado no front e no backend.
- **Formulários**: ContactModal, ContactsPage e NewConversationModal validam com `isValidE164`; mensagens de erro claras; não enviam vazio.
- **Backend**: `normalize_phone` preserva números que já começam com `+`; modelo aceita E.164; serializer reutiliza a normalização.
- **Limitação conhecida**: países fora da lista (ex.: +963) são exibidos como Brasil no parse; opção “Outro” com código manual é melhoria futura.

---

## O que foi revisado

- `frontend/src/lib/phoneDDD.ts` – constantes e helpers
- `frontend/src/components/PhoneInputWithDDD.tsx` – componente com dropdown DDD
- Uso em ContactModal, ContactsPage e NewConversationModal
- Alinhamento com backend (Contact.phone E.164, normalize_phone, serializer)

---

## Checklist produção (revisão final)

- **Validação no submit**: ContactModal e ContactsPage validam `isValidE164(phone)` (Brasil ou internacional) antes de enviar; mensagem clara se telefone vazio ou inválido.
- **E.164 no front**: `phoneDDD.ts` exporta `E164_REGEX`, `isValidE164()` e `isValidBrazilianE164()`; formulários usam `isValidE164`.
- **“Outro” com 1 dígito**: `buildE164` exige DDD com 2 dígitos; não envia E.164 inválido.
- **Selecionar “Outro”**: ao escolher “Outro” no dropdown, chama-se `notify('', numberPart)`; o `useEffect` só sincroniza DDD quando `value` não é vazio, evitando reverter “Outro”.
- **Internacional**: dropdown País (Brasil primeiro); internacional com mínimo 6 dígitos no nacional (`buildE164International`); ContactsPage preserva `+` ao normalizar; NewConversationModal usa `getEffectivePhone` e `normalizePhone` que respeitam país.
- **Backend**: serializer `validate_phone` chama `normalize_phone`; quando o valor já começa com `+`, `normalize_phone` devolve como está (não adiciona 55). Modelo exige E.164; front não envia vazio nem formato inválido.

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
| Contato com telefone internacional | País no dropdown; valor E.164 preservado no front e no backend (normalize_phone mantém +) | OK |
| País não listado (ex.: +963) | Parse devolve Brasil como fallback; exibição pode ser enganosa; não corrompe se usuário não salvar | Limitação conhecida; opção “Outro” é melhoria futura |

---

### 3. **Validação E.164 antes do submit (produção)**

- Em **ContactModal** e **ContactsPage**: antes do toast de loading e da API, valida-se nome e telefone. Telefone deve ser não vazio e `isValidE164(formData.phone)` (Brasil ou internacional). Caso contrário, toast de erro orientando formato internacional. Evita 400 e melhora o feedback.

### 4. **Bug “Outro” revertendo**

- Ao selecionar “Outro” no dropdown, não se chamava `onChange`, então o `value` continuava com o E.164 anterior e o `useEffect` (que sincroniza a partir de `value`) recolocava um DDD da lista e “Outro” sumia. Correção: (1) ao selecionar “Outro”, chamar `notify('', numberPart)` para o parent receber `''`; (2) no `useEffect`, só atualizar `selectedDddKey`/`otherDdd` quando `value` for não vazio; assim, com `value === ''` mantém-se a escolha “Outro”.

---

## Revisão internacional e edge cases

### Correções aplicadas (internacional + não quebrar)

1. **ContactsPage – envio de telefone internacional**  
   Se `formData.phone` já vinha com `+` (E.164), a normalização colocava `55` na frente e corrompia (ex.: +54… virava +5554…).  
   Agora: se `formData.phone.trim().startsWith('+')`, usa-se só `+` + dígitos; caso contrário mantém a lógica Brasil (55 + dígitos).

2. **NewConversationModal – effectivePhone**  
   `rawInputToE164(phoneInput)` assumia sempre Brasil: "541112345678" virava +55541112345678.  
   Agora: para 10+ dígitos usa-se `parseE164ToCountryAndNational`; se reconhecer país (dial + national ≥ 6), monta E.164 com `buildE164International`; senão continua com `rawInputToE164` (Brasil).

3. **NewConversationModal – normalizePhone**  
   Qualquer número sem `+` ganhava +55, corrompendo internacionais.  
   Agora: se já começa com `+`, devolve `+` + dígitos; senão, usa `parseE164ToCountryAndNational` e só trata como Brasil (`+55` + dígitos) quando os dígitos realmente começam com o dial do país retornado (evita tratar 963… como Brasil).

4. **NewConversationModal – handleStartConversationWithPhone**  
   O handler usava só `rawInputToE164`/`normalizePhone`, sem a lógica internacional.  
   Agora: usa a mesma função `getEffectivePhone(phoneInput)` usada no uso para exibição/validação.

5. **countryCodes.ts**  
   Export de `isKnownCountryDial` para uso futuro (ex.: só permitir países conhecidos).  
   Ordem de parse: length desc, depois dial asc (54 antes de 55 para 54…).

### Edge cases cobertos

- Número já em E.164 com `+` (BR ou internacional): preservado no envio e na validação.
- Busca por número internacional no modal (ex.: 54…): effectivePhone e normalizePhone não forçam +55.
- País desconhecido (não na lista): parse continua devolvendo default BR; possível melhoria futura é opção “Outro” com código manual.

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
