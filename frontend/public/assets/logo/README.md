# Logos da Plataforma

Esta pasta contém os logos da plataforma Alrea Flow.

## Arquivos necessários:

1. **logo.png** - Logo apenas (sem texto)
   - Tamanho recomendado: 200x200px ou maior (proporção 1:1)
   - Formato: PNG com fundo transparente
   - Uso: Quando `showText={false}` no componente Logo

2. **logo-with-text.png** - Logo com texto "Alrea Flow"
   - Tamanho recomendado: 300x100px ou maior (proporção 3:1)
   - Formato: PNG com fundo transparente
   - Uso: Quando `showText={true}` no componente Logo (padrão)

## Formatos aceitos:

- **PNG** (recomendado) - com fundo transparente
- **SVG** - também funciona, mas renomeie para .png ou ajuste o código

## Como adicionar seus logos:

1. Exporte seus logos do PSD/PDF para PNG:
   - Logo apenas: exporte como `logo.png`
   - Logo com texto: exporte como `logo-with-text.png`

2. Coloque os arquivos nesta pasta: `frontend/public/assets/logo/`

3. O componente Logo.tsx irá carregar automaticamente as imagens

4. Se as imagens não existirem, o sistema usa o SVG gerado como fallback

## Tamanhos suportados:

- **sm** (small): 24px altura
- **md** (medium): 32px altura (padrão)
- **lg** (large): 48px altura

Os logos serão redimensionados automaticamente mantendo a proporção.

