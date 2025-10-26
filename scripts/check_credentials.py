#!/usr/bin/env python3
"""
Script para verificar se há credenciais hardcoded no código
Usado pelo pre-commit hook
"""
import re
import sys
from pathlib import Path

# Padrões de credenciais conhecidas (partial matching)
KNOWN_SECRETS = [
    '584B4A4A-0815',  # Evolution API Key (partial)
    'u2gh8aomMEdq',   # S3 Access Key (partial)
    'zSMwLiOH1fUR',   # S3 Secret Key (partial)
    '75jkOmkcjQmQ',   # RabbitMQ credentials (partial)
]

# Padrões genéricos de secrets
SECRET_PATTERNS = [
    r'api[_-]?key\s*=\s*["\'][A-Z0-9-]{20,}["\']',
    r'secret[_-]?key\s*=\s*["\'][A-Za-z0-9+/]{20,}["\']',
    r'password\s*=\s*["\'][^"\']{8,}["\']',
    r'token\s*=\s*["\'][A-Za-z0-9._-]{20,}["\']',
]

# Arquivos a ignorar
IGNORE_PATTERNS = [
    '.git/',
    'node_modules/',
    'venv/',
    '__pycache__/',
    '.pytest_cache/',
    'staticfiles/',
    'media/',
    '.secrets.baseline',
    'check_credentials.py',  # Este próprio arquivo
]

def should_ignore(filepath):
    """Verifica se arquivo deve ser ignorado"""
    return any(pattern in str(filepath) for pattern in IGNORE_PATTERNS)

def check_file(filepath):
    """Verifica um arquivo por credenciais"""
    issues = []
    
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            
        for line_num, line in enumerate(lines, 1):
            # Ignorar linhas comentadas
            if line.strip().startswith('#') or line.strip().startswith('//'):
                continue
                
            # Verificar secrets conhecidos
            for secret in KNOWN_SECRETS:
                if secret in line:
                    issues.append({
                        'file': str(filepath),
                        'line': line_num,
                        'type': 'Known Secret',
                        'content': line.strip()[:80]
                    })
                    
            # Verificar padrões genéricos
            for pattern in SECRET_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    # Ignorar se for variável de ambiente
                    if 'os.environ' in line or 'config(' in line or 'getenv' in line:
                        continue
                    issues.append({
                        'file': str(filepath),
                        'line': line_num,
                        'type': 'Potential Secret',
                        'content': line.strip()[:80]
                    })
                    
    except Exception as e:
        pass  # Ignorar erros de leitura
        
    return issues

def main():
    """Main function"""
    all_issues = []
    
    # Buscar em todos os arquivos Python, JS, TS
    extensions = ['*.py', '*.js', '*.ts', '*.tsx', '*.jsx']
    
    for ext in extensions:
        for filepath in Path('.').rglob(ext):
            if should_ignore(filepath):
                continue
            issues = check_file(filepath)
            all_issues.extend(issues)
            
    # Reportar resultados
    if all_issues:
        print("❌ CREDENCIAIS ENCONTRADAS NO CÓDIGO:")
        print("=" * 60)
        for issue in all_issues:
            print(f"\n🚨 {issue['type']}")
            print(f"   Arquivo: {issue['file']}:{issue['line']}")
            print(f"   Conteúdo: {issue['content']}")
        print("\n" + "=" * 60)
        print(f"Total: {len(all_issues)} issue(s) encontrada(s)")
        print("\n⚠️  AÇÃO NECESSÁRIA:")
        print("1. Remova as credenciais do código")
        print("2. Use variáveis de ambiente")
        print("3. Adicione ao .gitignore se necessário")
        sys.exit(1)
    else:
        print("✅ Nenhuma credencial hardcoded encontrada")
        sys.exit(0)

if __name__ == '__main__':
    main()

