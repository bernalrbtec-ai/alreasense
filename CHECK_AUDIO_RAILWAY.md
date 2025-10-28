# 🎵 DIAGNÓSTICO DE ÁUDIO - RAILWAY

## 📝 COMANDO CORRETO (rodar NO Railway):

### Opção 1: Railway Shell (mais fácil)
```bash
railway shell
```

Depois, dentro do shell:
```bash
cd /app
python backend/diagnose_audio_attachments.py
```

### Opção 2: Comando Único
```bash
railway shell -c "cd /app && python backend/diagnose_audio_attachments.py"
```

### Opção 3: Via API do Railway (se as opções acima não funcionarem)
```bash
railway logs --tail 100 | grep -i audio
```

---

## 🔍 ALTERNATIVA RÁPIDA: Ver os últimos logs

Se quiser ver rapidamente se há mensagens de áudio chegando:

```bash
railway logs --tail 200 | findstr /i "audio DOWNLOAD"
```

Procure por:
- `📥 [DOWNLOAD]` - Indica que está tentando baixar
- `✅ [STORAGE]` - Indica que salvou com sucesso
- `❌` - Indica erro

---

## 🎯 O QUE FAZER AGORA:

1. **Rode:**
   ```bash
   railway shell -c "cd /app && python backend/diagnose_audio_attachments.py"
   ```

2. **Copie TODA a saída aqui**

3. **Ou me mostre os logs recentes:**
   ```bash
   railway logs --tail 200
   ```

---

## 🚨 SE NÃO FUNCIONAR:

Me mostre o último áudio que você enviou pelo WhatsApp (hora, se possível) para eu buscar nos logs do Railway!

