# Qwen 2.5: modelos para RTX 5060 Ti 16GB (com Whisper)

A VRAM é compartilhada com o Whisper. Estimativas de uso:

| Componente | VRAM aproximada |
|------------|-----------------|
| Whisper (base/small) | ~1–2 GB |
| Whisper (medium) | ~2–3 GB |
| Whisper (large) | ~3–5 GB |
| **Reserva sugerida para Whisper** | **~3–4 GB** |
| **Disponível para o LLM** | **~12–13 GB** |

---

## Recomendações por cenário

### Cenário 1: Whisper + LLM na mesma sessão (recomendado)
- **Qwen2.5-7B-Instruct** em **INT4** (GPTQ ou AWQ): ~**8–8,5 GB**
- Sobra ~7–8 GB para contexto + geração + Whisper
- **Modelo sugerido:** `Qwen/Qwen2.5-7B-Instruct` (quantize para 4-bit no backend) ou `Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4`

### Cenário 2: Mais margem para Whisper ou inferência mais rápida
- **Qwen2.5-3B-Instruct**: ~**2–3 GB** (FP16) ou ~**1,5–2 GB** (INT4)
- Deixa bastante espaço para Whisper large e contexto longo
- Trade-off: menos capacidade que o 7B para tarefas complexas

### Cenário 3: Máximo de capacidade na 16 GB (Whisper pequeno ou carregado só quando necessário)
- **Qwen2.5-14B-Instruct** em **INT4**: ~**13 GB**
- Só viável se o Whisper for small/base ou se não rodar ao mesmo tempo que o LLM
- Risco de OOM se ambos estiverem carregados com contexto grande

---

## Variantes úteis (Hugging Face)

| Modelo | VRAM (ref.) | Uso típico |
|--------|-------------|------------|
| **Qwen/Qwen2.5-7B-Instruct** | ~8 GB (INT4) / ~12 GB (BF16) | Melhor custo-benefício para Bia na 5060 Ti |
| **Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4** | ~5–6 GB | 7B já quantizado, menos carga no backend |
| **Qwen/Qwen2.5-7B-Instruct-AWQ** | ~5–6 GB | Alternativa AWQ ao GPTQ |
| **Qwen/Qwen2.5-3B-Instruct** | ~2–3 GB (BF16) / ~1,5 GB (INT4) | Leve, boa margem para Whisper |
| **Qwen/Qwen2.5-1.5B-Instruct** | ~1 GB | Testes ou ambientes muito limitados |
| **Qwen/Qwen2.5-14B-Instruct** | ~13 GB (INT4) | Só com Whisper pequeno ou sem compartilhar VRAM |

---

## Resumo prático para a Bia

- **Recomendação principal:** **Qwen2.5-7B-Instruct** em **4-bit** (ou variante GPTQ/AWQ 7B).
- **Prompt:** usar `prompt_secretaria_bia_qwen.txt` no system message (`role: system`).
- **Backend:** garantir que o chat use o template do Qwen (`apply_chat_template` com `system` + `user` + `assistant`). O conteúdo do system message é o texto completo do arquivo (sem o cabeçalho de comentário `#`, se o backend não suportar).

Se quiser mais folga para Whisper ou respostas mais rápidas, testar **Qwen2.5-3B-Instruct**; para mais qualidade (e Whisper pequeno), avaliar **14B em INT4** com monitoramento de VRAM.
