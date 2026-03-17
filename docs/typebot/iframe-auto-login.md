## Auto-login do Typebot Builder via token (para iframe)

### O problema
O Builder (`typebot.alrea.ai`) usa autenticação de UI (NextAuth). A **API key** só autentica **API admin** e não cria sessão no navegador, então o iframe cai na tela de login e falha com `workspace.listWorkspaces` “You must be logged in”.

### Solução (self-host Docker)
Adicionar no Typebot Builder um endpoint que:
- recebe um **JWT HS256** emitido pelo Sense
- valida assinatura/expiração
- cria uma **sessão NextAuth** no banco (Prisma)
- seta o cookie `next-auth.session-token` com `SameSite=None; Secure`
- redireciona para `/pt-BR/typebots/<internalId>/edit`

### Variáveis necessárias
No **Sense (backend)**:
- `TYPEBOT_BUILDER_BASE=https://typebot.alrea.ai`
- `SENSE_IFRAME_LOGIN_SECRET=<um segredo forte compartilhado com o Typebot>`

No **Typebot Builder**:
- `SENSE_IFRAME_LOGIN_SECRET=<mesmo valor do Sense>`
- `NEXTAUTH_URL=https://typebot.alrea.ai`
- `NEXTAUTH_SECRET=<já usado pelo Typebot>`
- `DATABASE_URL=<postgres do typebot>`

### Endpoint esperado no Typebot
`GET /api/sense/iframe-login?token=<jwt>&returnTo=/<locale>/typebots/<id>/edit`

### Pseudocódigo (Next.js API Route)
Coloque algo equivalente a isto no Builder (ajuste conforme versão do Typebot):

```ts
import type { NextApiRequest, NextApiResponse } from "next";
import jwt from "jsonwebtoken";
import crypto from "crypto";
import { prisma } from "@/lib/prisma"; // ajuste para o prisma do Typebot

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  const token = String(req.query.token || "");
  const returnTo = String(req.query.returnTo || "/");
  const secret = process.env.SENSE_IFRAME_LOGIN_SECRET || "";
  if (!secret) return res.status(500).send("missing secret");

  let payload: any;
  try {
    payload = jwt.verify(token, secret, { audience: "typebot-builder", issuer: "sense" });
  } catch {
    return res.status(401).send("invalid token");
  }

  // 1) Escolha um usuário serviço do Typebot (recomendado)
  // Exemplo: buscar por email fixo configurado em env
  const email = process.env.SENSE_SERVICE_USER_EMAIL!;
  const user = await prisma.user.findUnique({ where: { email } });
  if (!user) return res.status(500).send("service user missing");

  // 2) Criar sessão NextAuth no banco
  const sessionToken = crypto.randomBytes(32).toString("hex");
  const expires = new Date(Date.now() + 1000 * 60 * 60); // 1h
  await prisma.session.create({
    data: { sessionToken, userId: user.id, expires },
  });

  // 3) Setar cookie para o iframe (cross-site)
  res.setHeader("Set-Cookie", [
    `next-auth.session-token=${sessionToken}; Path=/; HttpOnly; Secure; SameSite=None`,
  ]);

  res.writeHead(302, { Location: returnTo });
  res.end();
}
```

### Nginx / headers
No vhost do builder, manter:
- `proxy_hide_header X-Frame-Options;`
- `Content-Security-Policy: frame-ancestors 'self' https://chat.alrea.ai` (ou seu domínio do Sense)

### Lado do Sense (já implementado)
O Sense expõe:
- `POST /api/chat/flows/<id>/typebot_builder_login_url/` → `{ loginUrl }`

E o frontend usa o `loginUrl` como `iframe.src`.

