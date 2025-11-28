#!/usr/bin/env python
"""
Script para identificar todos os print() statements no código de produção.

Uso:
    python scripts/find_print_statements.py
    
    # Apenas listar
    python scripts/find_print_statements.py --list-only
    
    # Excluir scripts de teste
    python scripts/find_print_statements.py --exclude-tests
"""
import os
import re
import sys
from pathlib import Path
from collections import defaultdict

# Diretórios a ignorar
IGNORE_DIRS = {
    '__pycache__',
    'venv',
    '.git',
    'node_modules',
    'staticfiles',
    'migrations',  # Migrations podem ter print() temporários
}

# Arquivos a ignorar (scripts de teste/debug)
IGNORE_FILES = {
    'test_*.py',
    '*_test.py',
    'debug_*.py',
    '*_debug.py',
    'check_*.py',
    'fix_*.py',
    'create_*.py',
    'setup_*.py',
    'monitor_*.py',
    'analyze_*.py',
}

# Diretórios de produção (onde print() é CRÍTICO)
PRODUCTION_DIRS = {
    'apps/',
    'alrea_sense/',
}

def should_ignore_file(filepath: Path) -> bool:
    """Verifica se arquivo deve ser ignorado"""
    filename = filepath.name
    
    # Verificar padrões de nome
    for pattern in IGNORE_FILES:
        if pattern.startswith('*'):
            if filename.endswith(pattern[1:]):
                return True
        elif pattern.endswith('*'):
            if filename.startswith(pattern[:-1]):
                return True
        elif pattern in filename:
            return True
    
    return False

def should_ignore_dir(dirpath: Path) -> bool:
    """Verifica se diretório deve ser ignorado"""
    return any(ignore in str(dirpath) for ignore in IGNORE_DIRS)

def is_production_code(filepath: Path) -> bool:
    """Verifica se é código de produção (crítico)"""
    return any(prod_dir in str(filepath) for prod_dir in PRODUCTION_DIRS)

def find_print_statements(root_dir: Path, exclude_tests: bool = False):
    """Encontra todos os print() statements"""
    results = {
        'total': 0,
        'production': 0,
        'scripts': 0,
        'by_file': defaultdict(list),
        'by_type': defaultdict(int),
    }
    
    # Padrão regex para print()
    print_pattern = re.compile(r'print\s*\(', re.MULTILINE)
    
    for filepath in root_dir.rglob('*.py'):
        # Ignorar diretórios
        if should_ignore_dir(filepath):
            continue
        
        # Ignorar arquivos de teste se solicitado
        if exclude_tests and should_ignore_file(filepath):
            continue
        
        try:
            content = filepath.read_text(encoding='utf-8')
        except Exception as e:
            print(f"⚠️ Erro ao ler {filepath}: {e}", file=sys.stderr)
            continue
        
        # Encontrar todos os print()
        matches = list(print_pattern.finditer(content))
        
        if matches:
            relative_path = filepath.relative_to(root_dir)
            
            # Extrair linhas com print()
            lines = content.split('\n')
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                line_content = lines[line_num - 1].strip()
                
                # Classificar tipo de print()
                if 'logger' in line_content.lower() or 'logging' in line_content.lower():
                    print_type = 'logging_related'
                elif 'debug' in line_content.lower():
                    print_type = 'debug'
                elif 'error' in line_content.lower():
                    print_type = 'error'
                else:
                    print_type = 'general'
                
                results['by_file'][str(relative_path)].append({
                    'line': line_num,
                    'content': line_content,
                    'type': print_type,
                })
                
                results['total'] += 1
                results['by_type'][print_type] += 1
                
                if is_production_code(filepath):
                    results['production'] += 1
                else:
                    results['scripts'] += 1
    
    return results

def print_report(results: dict, list_only: bool = False):
    """Imprime relatório dos print() encontrados"""
    print("=" * 80)
    print("🔍 RELATÓRIO: Print() Statements no Código")
    print("=" * 80)
    print()
    
    print(f"📊 RESUMO:")
    print(f"   Total de print() encontrados: {results['total']}")
    print(f"   Em código de produção: {results['production']} ⚠️ CRÍTICO")
    print(f"   Em scripts/testes: {results['scripts']}")
    print()
    
    print(f"📈 Por tipo:")
    for print_type, count in sorted(results['by_type'].items(), key=lambda x: -x[1]):
        print(f"   {print_type}: {count}")
    print()
    
    if list_only:
        print("📁 Arquivos com print() (top 20):")
        sorted_files = sorted(
            results['by_file'].items(),
            key=lambda x: len(x[1]),
            reverse=True
        )[:20]
        
        for filepath, prints in sorted_files:
            print(f"   {filepath}: {len(prints)} print()")
    else:
        print("📁 DETALHES POR ARQUIVO:")
        print()
        
        # Ordenar por número de print() (mais críticos primeiro)
        sorted_files = sorted(
            results['by_file'].items(),
            key=lambda x: (is_production_code(Path(x[0])), len(x[1])),
            reverse=True
        )
        
        for filepath, prints in sorted_files:
            is_prod = is_production_code(Path(filepath))
            marker = "🔴" if is_prod else "🟡"
            
            print(f"{marker} {filepath} ({len(prints)} print())")
            
            for print_info in prints[:5]:  # Mostrar apenas primeiros 5
                print(f"   Linha {print_info['line']}: {print_info['content'][:70]}")
            
            if len(prints) > 5:
                print(f"   ... e mais {len(prints) - 5} print()")
            print()

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Encontrar print() statements no código')
    parser.add_argument('--list-only', action='store_true', help='Apenas listar arquivos')
    parser.add_argument('--exclude-tests', action='store_true', help='Excluir scripts de teste')
    parser.add_argument('--root', default='.', help='Diretório raiz (default: .)')
    
    args = parser.parse_args()
    
    root_dir = Path(args.root).resolve()
    
    if not root_dir.exists():
        print(f"❌ Diretório não encontrado: {root_dir}", file=sys.stderr)
        sys.exit(1)
    
    results = find_print_statements(root_dir, exclude_tests=args.exclude_tests)
    
    if results['total'] == 0:
        print("✅ Nenhum print() encontrado!")
        return
    
    print_report(results, list_only=args.list_only)
    
    # Exit code baseado em print() em produção
    if results['production'] > 0:
        print()
        print("⚠️ ATENÇÃO: Encontrados print() em código de produção!")
        print("   Execute: python scripts/replace_print_with_logging.py")
        sys.exit(1)
    else:
        print()
        print("✅ Nenhum print() em código de produção (apenas em scripts)")
        sys.exit(0)

if __name__ == '__main__':
    main()

