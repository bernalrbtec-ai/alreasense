# Stitch Skills – Revisão de design da UI

As [Stitch Skills](https://github.com/google-labs-code/stitch-skills) do Google Labs foram instaladas no projeto para ajudar a **revisar e padronizar o design da UI**.

## Onde estão instaladas

As skills ficam em:

```
Sense/.agents/skills/
├── design-md/       # Design system → DESIGN.md
├── shadcn-ui/       # Boas práticas com componentes UI (React + Tailwind)
└── stitch-design/   # Ponto único para trabalho de design (prompts, design system)
```

O CLI **skills** instalou para Cursor (e outros agentes) em `~\Sense\.agents\skills\`. O Cursor usa essas pastas automaticamente.

## Skills instaladas e uso na revisão de UI

| Skill | Uso na revisão de UI |
|-------|----------------------|
| **design-md** | Analisa o projeto e gera um `DESIGN.md` com o design system (cores, tipografia, atmosfera, geometria). Use para documentar o sistema de design e depois **revisar a UI contra esse documento**. |
| **stitch-design** | Melhora prompts de UI/UX, sintetiza design system (ex.: `.stitch/DESIGN.md`) e orienta geração/edição de telas. Útil para **consistência visual** e **linguagem de design**. |
| **shadcn-ui** | Guia para componentes acessíveis e customizáveis (React + Tailwind). Ajuda em **padrões de componentes**, acessibilidade e boas práticas, mesmo sem usar shadcn no projeto. |

## Como usar para “revisar todo o design da UI”

Basta pedir em linguagem natural no chat do Cursor. O agente escolhe a skill pela descrição. Exemplos:

- *“Revisa o design da UI do frontend e sugere melhorias de consistência.”*
- *“Gera um DESIGN.md com o design system do nosso app (cores, tipografia, componentes).”*
- *“Analisa os componentes de UI em `frontend/src` e sugere melhorias de acessibilidade e padrões.”*
- *“Quero padronizar a paleta e os espaçamentos; usa as stitch skills para documentar e revisar.”*

## Dependências opcionais (Stitch MCP)

- **design-md** e **stitch-design** foram pensados para projetos que usam o **Stitch MCP** (ferramenta de design do Google).  
- No nosso projeto (React + Tailwind, sem Stitch), as skills ainda ajudam: o agente usa as **instruções e conceitos** (design system, DESIGN.md, UX keywords) para revisar e documentar a UI.  
- Se no futuro você configurar o [Stitch MCP](https://stitch.withgoogle.com/), as skills passam a usar também listagem de projetos, telas e geração via Stitch.

## Instalar mais skills do repositório

Listar skills disponíveis:

```bash
npx skills add google-labs-code/stitch-skills --list
```

Instalar uma skill específica (ex.: `enhance-prompt`):

```bash
npx skills add google-labs-code/stitch-skills --skill enhance-prompt -y
```

Com `-g` (ou `--global`) a instalação é em `~/.agents/skills/` (usuário); sem `-g` continua no projeto (`Sense/.agents/skills/`).

## Compartilhar com o time

A pasta `.agents` está no repositório. Quem clonar o Sense já terá as mesmas skills. Se preferir que cada dev instale só localmente, adicione no `.gitignore`:

```
.agents/
```

e use `npx skills add ...` na máquina de cada um.
