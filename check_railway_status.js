// Script para verificar qual versão está no Railway
const https = require('https');

const BACKEND_URL = 'https://alreasense-backend-production.up.railway.app';

async function checkRailwayStatus() {
  console.log('🔍 Verificando status do Railway...\n');
  
  // 1. Health check
  console.log('1️⃣ Health Check:');
  try {
    const response = await fetch(`${BACKEND_URL}/health/`);
    const data = await response.json();
    console.log(`   ✅ Status: ${data.status || 'OK'}`);
    if (data.timestamp) {
      console.log(`   ⏰ Timestamp: ${data.timestamp}`);
    }
  } catch (error) {
    console.log(`   ❌ Erro: ${error.message}`);
  }
  
  // 2. Verificar se API está respondendo
  console.log('\n2️⃣ API Status:');
  try {
    const response = await fetch(`${BACKEND_URL}/api/`);
    console.log(`   Status: ${response.status} ${response.statusText}`);
  } catch (error) {
    console.log(`   ❌ Erro: ${error.message}`);
  }
  
  // 3. Informações úteis
  console.log('\n📋 Informações:');
  console.log(`   🌐 URL: ${BACKEND_URL}`);
  console.log(`   🔗 GitHub: https://github.com/bernalrbtec-ai/alreasense`);
  console.log(`   📦 Último commit local: Use "git log --oneline -1"`);
  
  console.log('\n💡 Para ver o deploy no Railway:');
  console.log('   1. Acesse: https://railway.app');
  console.log('   2. Entre no projeto "AlreaSense - Backend"');
  console.log('   3. Aba "Deployments"');
  console.log('   4. Veja o status do último deploy');
  
  console.log('\n⚠️  Se o Railway estiver pausado (GitHub incident):');
  console.log('   - Status: https://status.railway.app');
  console.log('   - Aguarde ou faça deploy manual');
}

checkRailwayStatus();


