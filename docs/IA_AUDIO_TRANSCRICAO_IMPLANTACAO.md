# Implantacao: Transcricao de Audio + IA (Config + Testes)

Este documento orienta a implantacao da transcricao de audio e da IA de triagem, incluindo:
- pagina de configuracao por tenant
- area de teste na aplicacao
- fluxo N8N para transcricao

## Objetivo

- Habilitar transcricao automatica com politicas por tenant.
- Permitir testes manuais via UI antes de ativar N8N em producao.

## 1) Backend - Configuracoes por Tenant

### Campos sugeridos (Tenant AI Settings)

- `ai_enabled` (bool)
- `audio_transcription_enabled` (bool)
- `transcription_auto` (bool)
- `transcription_min_seconds` (int)
- `transcription_max_mb` (int)
- `triage_enabled` (bool)
- `agent_model` (string)
- `n8n_audio_webhook_url` (string, obrigatorio quando transcricao ativa)
- `n8n_triage_webhook_url` (string, obrigatorio quando triagem ativa)

### Endpoints sugeridos

- `GET /api/ai/settings/` (admin tenant)
- `PUT /api/ai/settings/` (admin tenant)
- `POST /api/ai/transcribe/test/` (admin tenant)

## 2) UI - Pagina de Configuracao da IA

### Local

- Menu: **Configuracoes → IA / Assistentes**
- Apenas **admins do tenant** (IsAdminUser + IsTenantMember)

### Campos da tela

- Toggle **Ativar IA**
- Toggle **Transcricao automatica**
- Limites (segundos min / MB max)
- Toggle **Triagem**
- Modelo padrao (ex.: `llama3.1:8b`)
- Botao **Salvar**

### Regras de webhook

- Se **Transcricao** estiver habilitada, `n8n_audio_webhook_url` e obrigatorio.
- Se **Triagem** estiver habilitada, `n8n_triage_webhook_url` e obrigatorio.

## 3) UI - Area de Teste

### Local

- Menu: **IA → Testes**

### Funcoes

- Teste de **transcricao** (upload de audio)
- Teste de **prompt/triagem**
- Historico de execucoes

## 4) N8N - Fluxo Transcricao

### Entrada (Webhook)

Payload esperado:

```
{
  "action": "transcribe",
  "tenant_id": "...",
  "conversation_id": "...",
  "message_id": "...",
  "media_url": "...",
  "duration_ms": 12345,
  "size_bytes": 123456,
  "direction": "incoming"
}
```

### Passos

1. Receber webhook
2. Baixar audio (GET media_url)
3. Enviar ao Whisper (API interna)
4. Retornar transcricao ao backend

### Saida

```
{
  "status": "done",
  "transcript_text": "...",
  "language_detected": "pt",
  "model_name": "whisper-small",
  "processing_time_ms": 1200
}
```

## 5) Checklist de validacao

- [ ] UI de configuracao salva e retorna valores
- [ ] Upload de audio no teste retorna transcricao
- [ ] N8N recebe payload de transcricao (webhook de audio)
- [ ] Transcricao salva e aparece no chat

## Observacoes

- Comecar com **automatico apenas quando IA habilitada**.
- Manter botao manual sempre disponivel.
