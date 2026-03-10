# Impacto em quem já está usando (instâncias e usuários)

Resposta direta: **não vai quebrar o que já está funcionando** se você fizer a migração dos planos como abaixo. Sem migração, **quem hoje só tem Flow deixa de poder criar novas instâncias** (as que já existem continuam normais).

---

## 1. O que NÃO muda (não dá problema)

| Situação | Impacto |
|----------|--------|
| **Instâncias já criadas** | Continuam funcionando. Ninguém perde instâncias existentes; o código não remove nada. |
| **Usuários já criados** | Continuam normais. Ninguém é desativado ou bloqueado. |
| **Uso do dia a dia** | Chat, conversas, agenda, contatos e respostas rápidas seguem iguais para quem já tem acesso. Campanhas continuam no produto Flow. |

---

## 2. O que PODE mudar (e como evitar problema)

### 2.1 Criar **novas** instâncias WhatsApp

- **Quem hoje tem plano só com produto Flow (sem Chat):**  
  Depois do deploy, **não vai mais conseguir criar nova instância**.  
  As que já existem continuam funcionando.

- **Como não impactar quem já usa:**  
  Incluir o produto **Chat** nos mesmos planos que hoje têm **Flow** (e que precisam de instâncias).  
  No Chat, configurar o **limite de instâncias** igual (ou maior) ao que o plano tinha no Flow.  
  Assim o tenant passa a ter o produto “pai” (Chat) e os limites continuam vindo dele, sem perder funcionalidade.

### 2.2 Criar **novos** usuários

- O limite de **número de usuários** só é aplicado quando:
  1. O tenant tem o produto **Chat**, e  
  2. No plano, no produto Chat, está preenchido **Limite de usuários** (`limit_value_secondary`).

- **Se o plano não tem Chat:** a checagem nem roda → **zero impacto** em quem já usa.  
- **Se o plano tem Chat mas não tem “Limite de usuários” configurado:** o limite vem `NULL` → continua **ilimitado** como hoje → **zero impacto**.  
- **Só há impacto** quando você, na tela de Planos, preencher explicitamente o limite de usuários para o Chat. Até lá, ninguém que já usa é bloqueado ao criar usuário.

---

## 3. Resumo: vai dar problema em quem está usando?

- **Instâncias já em uso:** não.  
- **Usuários já em uso:** não.  
- **Criar nova instância:** só dá “problema” para quem tem plano **só com Flow** (sem Chat). Evita-se isso **incluindo o Chat nesses planos** e mantendo o limite de instâncias no Chat.  
- **Criar novo usuário:** só é limitado se o plano tiver **Chat** e você configurar **Limite de usuários** no Chat. Enquanto não configurar, ninguém é impactado.

Ou seja: **não impacta o que está funcionando**, desde que os planos que hoje têm Flow (e precisam de instâncias) passem a ter também o Chat, com o limite de instâncias configurado no Chat. O número de usuários só passa a limitar quando você preencher esse limite no plano (Chat).
