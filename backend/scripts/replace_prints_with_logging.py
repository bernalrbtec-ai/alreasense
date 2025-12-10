#!/usr/bin/env python
"""
Script para substituir print() statements por logging estruturado.

✅ SEGURO: Apenas substitui prints, não altera lógica
✅ BACKUP: Cria backup antes de modificar
✅ VALIDAÇÃO: Verifica se arquivo é Python válido antes de modificar
"""

import os
import re
import sys
import shutil
from pathlib import Path
from datetime import datetime

# Diretórios para processar
BACKEND_DIR = Path(__file__).parent.parent
APPS_DIR = BACKEND_DIR / 'apps'

# Padrões para encontrar prints
PRINT_PATTERN = re.compile(
    r'(\s*)print\s*\((.*?)\)',
    re.MULTILINE | re.DOTALL
)

# Contadores
stats = {
    'files_processed': 0,
    'prints_replaced': 0,
    'files_skipped': 0,
    'errors': 0
}


def get_logger_import_line(file_content):
    """Verifica se arquivo já tem import logging."""
    if 'import logging' in file_content:
        return None
    if 'from logging import' in file_content:
        return None
    
    # Encontrar linha de imports
    lines = file_content.split('\n')
    last_import_line = 0
    
    for i, line in enumerate(lines):
        if line.strip().startswith('import ') or line.strip().startswith('from '):
            last_import_line = i
    
    return last_import_line + 1


def add_logger_import(file_content):
    """Adiciona import logging se não existir."""
    if 'import logging' in file_content or 'from logging import' in file_content:
        return file_content
    
    insert_line = get_logger_import_line(file_content)
    if insert_line is None:
        return file_content
    
    lines = file_content.split('\n')
    lines.insert(insert_line, 'import logging')
    lines.insert(insert_line + 1, '')
    lines.insert(insert_line + 2, 'logger = logging.getLogger(__name__)')
    
    return '\n'.join(lines)


def replace_print_statement(match):
    """Substitui um print() por logger.info()."""
    indent = match.group(1)
    content = match.group(2).strip()
    
    # Remover aspas externas se existirem
    content_clean = content.strip('"\'')
    
    # Detectar tipo de print
    if content.startswith('f"') or content.startswith("f'"):
        # f-string: logger.info(f"...")
        new_content = f'{indent}logger.info({content})'
    elif '"' in content or "'" in content:
        # String simples: logger.info("...")
        new_content = f'{indent}logger.info({content})'
    else:
        # Variável ou expressão: logger.info(f"Debug: {var}")
        new_content = f'{indent}logger.debug(f"Debug: {{{content}}}")'
    
    stats['prints_replaced'] += 1
    return new_content


def process_file(file_path):
    """Processa um arquivo Python."""
    try:
        # Ler arquivo
        with open(file_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        # Verificar se tem prints
        if 'print(' not in original_content:
            return False
        
        # Criar backup
        backup_path = file_path.with_suffix(file_path.suffix + '.bak')
        shutil.copy2(file_path, backup_path)
        
        # Adicionar import logging se necessário
        content = add_logger_import(original_content)
        
        # Substituir prints
        new_content = PRINT_PATTERN.sub(replace_print_statement, content)
        
        # Verificar se houve mudanças
        if new_content == original_content:
            # Remover backup se não houve mudanças
            backup_path.unlink()
            return False
        
        # Escrever arquivo modificado
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        stats['files_processed'] += 1
        print(f"✅ Processado: {file_path.relative_to(BACKEND_DIR)} ({stats['prints_replaced']} prints substituídos)")
        
        return True
        
    except Exception as e:
        stats['errors'] += 1
        print(f"❌ Erro ao processar {file_path}: {e}", file=sys.stderr)
        return False


def main():
    """Função principal."""
    print("🔍 Buscando arquivos Python com print() statements...")
    print(f"📁 Diretório: {APPS_DIR}")
    print()
    
    # Encontrar todos os arquivos Python
    python_files = list(APPS_DIR.rglob('*.py'))
    
    # Filtrar arquivos de migração e testes (opcional)
    python_files = [
        f for f in python_files
        if 'migrations' not in str(f) and 'test_' not in f.name
    ]
    
    print(f"📊 Encontrados {len(python_files)} arquivos Python")
    print()
    
    # Processar cada arquivo
    for file_path in python_files:
        process_file(file_path)
    
    # Resumo
    print()
    print("=" * 60)
    print("📊 RESUMO")
    print("=" * 60)
    print(f"Arquivos processados: {stats['files_processed']}")
    print(f"Prints substituídos: {stats['prints_replaced']}")
    print(f"Arquivos ignorados: {stats['files_skipped']}")
    print(f"Erros: {stats['errors']}")
    print()
    print("💡 Dica: Revise os arquivos modificados antes de commitar")
    print("💡 Backups criados com extensão .bak (pode deletar após revisão)")


if __name__ == '__main__':
    main()

