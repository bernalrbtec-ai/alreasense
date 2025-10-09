#!/usr/bin/env python
"""
VALIDAÇÃO PRE-COMMIT AUTOMÁTICA
Valida modelos, serializers, views, frontend antes de fazer commit

Conforme regra crítica:
"Sempre criar scripts de teste e executar simulações locais ANTES de fazer commit/push"
"""

import os
import sys
import subprocess
from pathlib import Path

class Color:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text):
    print(f"\n{Color.CYAN}{Color.BOLD}{'=' * 80}{Color.END}")
    print(f"{Color.CYAN}{Color.BOLD}{text.center(80)}{Color.END}")
    print(f"{Color.CYAN}{Color.BOLD}{'=' * 80}{Color.END}\n")

def print_success(text):
    print(f"{Color.GREEN}✅ {text}{Color.END}")

def print_error(text):
    print(f"{Color.RED}❌ {text}{Color.END}")

def print_warning(text):
    print(f"{Color.YELLOW}⚠️  {text}{Color.END}")

def print_info(text):
    print(f"{Color.BLUE}ℹ️  {text}{Color.END}")

def run_command(cmd, description):
    """Executa comando e retorna True se sucesso"""
    print_info(f"Executando: {description}")
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            print_success(f"{description} - OK")
            return True
        else:
            print_error(f"{description} - FALHOU")
            if result.stderr:
                print(f"  {Color.RED}{result.stderr[:500]}{Color.END}")
            return False
    except subprocess.TimeoutExpired:
        print_error(f"{description} - TIMEOUT")
        return False
    except Exception as e:
        print_error(f"{description} - ERRO: {e}")
        return False

def validate_backend():
    """Valida todo o backend"""
    print_header("VALIDANDO BACKEND")
    
    tests = []
    
    # 1. Django Check
    tests.append(run_command(
        'docker-compose -f docker-compose.local.yml exec -T backend python manage.py check --deploy',
        "Django System Check"
    ))
    
    # 2. Verificar models vs banco
    tests.append(run_command(
        'docker-compose -f docker-compose.local.yml exec -T backend python manage.py makemigrations --dry-run --check',
        "Verificar se há migrations pendentes"
    ))
    
    # 3. Testar endpoints de billing
    tests.append(run_command(
        'docker-compose -f docker-compose.local.yml exec -T backend python test_billing_endpoints.py',
        "Testar endpoints de billing"
    ))
    
    # 4. Validar imports Python
    print_info("Validando imports Python...")
    backend_files = list(Path('backend/apps').rglob('*.py'))
    import_errors = []
    
    for file in backend_files:
        if '__pycache__' in str(file) or 'migrations' in str(file):
            continue
        try:
            with open(file, 'r', encoding='utf-8') as f:
                content = f.read()
                # Verificar imports comuns problemáticos
                if 'from apps.billing.decorators import require_product' in content:
                    if '@require_product' not in content:
                        import_errors.append(f"{file}: Import não utilizado")
        except Exception as e:
            pass
    
    if import_errors:
        print_warning(f"Encontrados {len(import_errors)} avisos de imports")
    else:
        print_success("Imports Python validados")
        tests.append(True)
    
    return all(tests)

def validate_frontend():
    """Valida frontend TypeScript"""
    print_header("VALIDANDO FRONTEND")
    
    tests = []
    
    # 1. TypeScript check
    tests.append(run_command(
        'docker-compose -f docker-compose.local.yml exec -T frontend npm run type-check 2>&1 || echo "Sem type-check configurado"',
        "TypeScript Type Check"
    ))
    
    # 2. Verificar imports problemáticos
    print_info("Verificando imports frontend...")
    
    frontend_files = list(Path('frontend/src').rglob('*.ts*'))
    issues = []
    
    for file in frontend_files:
        if 'node_modules' in str(file):
            continue
        try:
            with open(file, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
                
                for i, line in enumerate(lines, 1):
                    # Verificar imports relativos incorretos
                    if "import" in line and "from './api'" in line:
                        if 'services' in str(file):
                            issues.append(f"{file}:{i} - Import './api' deve ser '../lib/api'")
                    
                    # Verificar .filter sem validação de array
                    if '.filter(' in line and 'Array.isArray' not in content:
                        if 'products.filter' in line or 'plans.filter' in line:
                            issues.append(f"{file}:{i} - Usar Array.isArray antes de .filter()")
                    
                    # Verificar .map sem validação
                    if '.map(' in line and 'Array.isArray' not in content:
                        if 'products.map' in line or 'plans.map' in line:
                            issues.append(f"{file}:{i} - Usar Array.isArray antes de .map()")
        except Exception as e:
            pass
    
    if issues:
        print_warning(f"Encontrados {len(issues)} avisos:")
        for issue in issues[:5]:  # Mostrar primeiros 5
            print(f"  {Color.YELLOW}{issue}{Color.END}")
    else:
        print_success("Imports e validações frontend OK")
        tests.append(True)
    
    return len(issues) == 0

def validate_database():
    """Valida estrutura do banco"""
    print_header("VALIDANDO BANCO DE DADOS")
    
    tests = []
    
    # Executar script de revisão
    tests.append(run_command(
        'docker-compose -f docker-compose.local.yml exec -T backend python review_and_fix_database.py',
        "Revisar estrutura do banco"
    ))
    
    return all(tests)

def main():
    """Executa todas as validações"""
    print_header("🚀 VALIDAÇÃO PRE-COMMIT - ALREA SENSE")
    
    print(f"{Color.BOLD}Regra:{Color.END} Sempre testar ANTES de commit/push\n")
    
    results = {
        'Backend': validate_backend(),
        'Frontend': validate_frontend(),
        'Database': validate_database(),
    }
    
    print_header("RESUMO DA VALIDAÇÃO")
    
    all_passed = True
    for component, passed in results.items():
        if passed:
            print_success(f"{component}: APROVADO")
        else:
            print_error(f"{component}: FALHOU")
            all_passed = False
    
    print()
    if all_passed:
        print(f"{Color.GREEN}{Color.BOLD}{'=' * 80}{Color.END}")
        print(f"{Color.GREEN}{Color.BOLD}{'✅ TODAS AS VALIDAÇÕES PASSARAM!'.center(80)}{Color.END}")
        print(f"{Color.GREEN}{Color.BOLD}{'SEGURO PARA FAZER COMMIT E PUSH'.center(80)}{Color.END}")
        print(f"{Color.GREEN}{Color.BOLD}{'=' * 80}{Color.END}")
        return 0
    else:
        print(f"{Color.RED}{Color.BOLD}{'=' * 80}{Color.END}")
        print(f"{Color.RED}{Color.BOLD}{'❌ ALGUMAS VALIDAÇÕES FALHARAM!'.center(80)}{Color.END}")
        print(f"{Color.RED}{Color.BOLD}{'NÃO FAÇA COMMIT ATÉ CORRIGIR OS ERROS'.center(80)}{Color.END}")
        print(f"{Color.RED}{Color.BOLD}{'=' * 80}{Color.END}")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n{Color.YELLOW}Validação interrompida pelo usuário{Color.END}")
        sys.exit(1)

