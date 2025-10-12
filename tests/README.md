# 🧪 Sistema de Testes ALREA Sense

## Visão Geral

Este é um sistema de testes automatizados e abrangente para a aplicação ALREA Sense, incluindo testes de API, integração, performance e regressão.

## Estrutura

```
tests/
├── test_framework.py      # Framework base de testes
├── test_suites.py         # Suítes de testes específicas
├── test_config.py         # Configurações de teste
├── run_tests.py          # Executor principal
└── README.md             # Esta documentação
```

## Tipos de Testes

### 1. **Testes de Autenticação**
- Login do superadmin
- Login de cliente
- Validação de token
- Teste de credenciais inválidas

### 2. **Testes de API**
- API de planos (CRUD)
- API de produtos (CRUD)
- API de tenants (CRUD)
- Validação de estrutura de dados

### 3. **Testes de CRUD**
- Criação de tenant
- Atualização de tenant
- Exclusão de tenant
- Validação de dados

### 4. **Testes de Performance**
- Tempo de resposta das APIs
- Requisições concorrentes
- Limites de timeout

### 5. **Testes de Integração**
- Fluxo completo de trabalho
- Integração entre componentes
- Cenários end-to-end

## Como Executar

### Execução Básica
```bash
python tests/run_tests.py
```

### Execução com Configurações Personalizadas
```bash
# Definir variáveis de ambiente
export TEST_BASE_URL="http://localhost:8000"
export TEST_SUPERADMIN_EMAIL="admin@test.com"
export TEST_SUPERADMIN_PASSWORD="password123"

# Executar testes
python tests/run_tests.py
```

### Execução de Suítes Específicas
```python
from tests.test_framework import TestRunner
from tests.test_suites import AuthenticationTests

runner = TestRunner()
runner.login("superadmin@alreasense.com", "admin123")

# Executar apenas testes de autenticação
result = runner.run_test(AuthenticationTests.test_superadmin_login)
print(result)
```

## Relatórios

O sistema gera relatórios HTML detalhados com:

- **Resumo Executivo**: Taxa de sucesso, tempo total, estatísticas
- **Detalhes por Suíte**: Resultados individuais de cada categoria
- **Métricas de Performance**: Tempos de resposta, concorrência
- **Logs de Erro**: Detalhes de falhas e exceções

### Exemplo de Relatório
```html
📊 RESUMO GERAL DOS TESTES
Total de Testes: 15
✅ Passou: 14
❌ Falhou: 1
💥 Erros: 0
📈 Taxa de Sucesso: 93.3%
⏱️ Duração Total: 12.45s
```

## Configurações

### Variáveis de Ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `TEST_BASE_URL` | `http://localhost:8000` | URL base da API |
| `TEST_FRONTEND_URL` | `http://localhost` | URL do frontend |
| `TEST_SUPERADMIN_EMAIL` | `superadmin@alreasense.com` | Email do superadmin |
| `TEST_SUPERADMIN_PASSWORD` | `admin123` | Senha do superadmin |
| `TEST_API_TIMEOUT` | `10.0` | Timeout das requisições (segundos) |
| `TEST_MAX_RESPONSE_TIME` | `2.0` | Tempo máximo de resposta (segundos) |

### Configuração Personalizada

```python
from tests.test_config import TestConfig

# Criar configuração personalizada
config = TestConfig(
    base_url="https://api.exemplo.com",
    api_timeout=15.0,
    max_response_time=3.0
)
```

## Adicionando Novos Testes

### 1. Criar Nova Suíte
```python
class MinhaSuite:
    @staticmethod
    def test_nova_funcionalidade(runner: TestRunner) -> bool:
        try:
            # Seu teste aqui
            response = runner.session.get("/api/minha-api/")
            return response.status_code == 200
        except:
            return False
```

### 2. Adicionar à Suíte
```python
def create_test_suites():
    suites = []
    
    minha_suite = TestSuite("Minha Suíte")
    minha_suite.tests = [
        MinhaSuite.test_nova_funcionalidade,
    ]
    suites.append(minha_suite)
    
    return suites
```

## Integração com CI/CD

### GitHub Actions
```yaml
name: Testes ALREA Sense
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - name: Install dependencies
        run: pip install requests
      - name: Start Docker
        run: docker-compose up -d
      - name: Wait for services
        run: sleep 30
      - name: Run tests
        run: python tests/run_tests.py
      - name: Upload reports
        uses: actions/upload-artifact@v2
        with:
          name: test-reports
          path: test_report_*.html
```

## Monitoramento Contínuo

### Execução Periódica
```bash
# Executar testes a cada hora
0 * * * * cd /path/to/alrea-sense && python tests/run_tests.py

# Executar testes diários às 6h
0 6 * * * cd /path/to/alrea-sense && python tests/run_tests.py
```

### Alertas
```python
# Exemplo de integração com Slack
def send_slack_alert(success_rate):
    if success_rate < 80:
        # Enviar alerta para Slack
        pass
```

## Troubleshooting

### Problemas Comuns

1. **Timeout de Conexão**
   - Verificar se o Docker está rodando
   - Aumentar `TEST_API_TIMEOUT`

2. **Falha de Autenticação**
   - Verificar credenciais em `test_config.py`
   - Confirmar se usuários existem no banco

3. **Erro 404**
   - Verificar se as rotas da API estão corretas
   - Confirmar se o backend está saudável

### Debug
```python
# Habilitar logs detalhados
import logging
logging.basicConfig(level=logging.DEBUG)

# Executar teste individual
runner = TestRunner()
runner.login("superadmin@alreasense.com", "admin123")
result = runner.run_test(APITests.test_plans_api)
print(f"Resultado: {result}")
```

## Métricas de Qualidade

### Critérios de Aprovação
- **Taxa de Sucesso**: ≥ 90% (Excelente)
- **Taxa de Sucesso**: ≥ 80% (Bom)
- **Taxa de Sucesso**: ≥ 70% (Atenção)
- **Taxa de Sucesso**: < 70% (Crítico)

### KPIs
- Tempo médio de resposta das APIs
- Taxa de sucesso por categoria
- Cobertura de funcionalidades
- Estabilidade do sistema

## Contribuição

Para adicionar novos testes:

1. Identifique a funcionalidade a ser testada
2. Crie testes unitários e de integração
3. Adicione à suíte apropriada
4. Documente o teste
5. Execute e valide os resultados
6. Submeta um pull request

---

**Desenvolvido para ALREA Sense** 🚀

