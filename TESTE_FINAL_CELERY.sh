#!/bin/bash

echo "🧪 TESTANDO CELERY WORKER NO RAILWAY"
echo "===================================="
echo ""

echo "1️⃣ Verificando health check..."
curl -s https://alreasense-backend-production.up.railway.app/api/health/ | jq '.celery'

echo ""
echo "===================================="
echo ""
echo "✅ Se retornou:"
echo '   {
     "status": "healthy",
     "active_workers": 1
   }'
echo ""
echo "   = CELERY FUNCIONANDO! 🎉"
echo ""
echo "❌ Se retornou:"
echo '   {
     "status": "unhealthy",
     "error": "No workers available"
   }'
echo ""
echo "   = Celery ainda não está rodando. Aguarde mais 1-2 min."
echo ""
echo "===================================="
echo ""
echo "2️⃣ Próximo passo:"
echo "   - Acesse: https://alreasense-production.up.railway.app"
echo "   - Vá em 'Campanhas'"
echo "   - Inicie uma campanha"
echo "   - Deve começar a enviar! 🚀"
echo ""

