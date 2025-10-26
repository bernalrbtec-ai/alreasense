#!/usr/bin/env python3
"""
🔐 SCRIPT DE CORREÇÃO DE SEGURANÇA URGENTE
===========================================

Este script corrige automaticamente as vulnerabilidades críticas de segurança
identificadas na análise de segurança.

⚠️  ATENÇÃO: Execute este script DEPOIS de rotacionar as credenciais!

Uso:
    python CORRECAO_SEGURANCA_URGENTE.py --execute

Flags:
    --dry-run     : Simula as mudanças sem aplicá-las (padrão)
    --execute     : Executa as correções
    --backup      : Cria backup antes de modificar
"""

import os
import re
import shutil
from pathlib import Path
from datetime import datetime
import argparse

class SecurityFixer:
    def __init__(self, dry_run=True, backup=True):
        self.dry_run = dry_run
        self.backup = backup
        self.fixes_applied = []
        self.issues_found = []
        
    def log(self, message, level="INFO"):
        icon = {
            "INFO": "ℹ️",
            "SUCCESS": "✅",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "FIX": "🔧"
        }.get(level, "•")
        print(f"{icon} {message}")
        
    def backup_file(self, filepath):
        """Cria backup de um arquivo antes de modificá-lo"""
        if not self.backup:
            return
            
        backup_dir = Path("backups/security_fix_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        backup_path = backup_dir / filepath
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        
        shutil.copy2(filepath, backup_path)
        self.log(f"Backup criado: {backup_path}", "INFO")
        
    def find_hardcoded_credentials(self):
        """Busca credenciais hardcoded no código"""
        self.log("🔍 Buscando credenciais hardcoded...", "INFO")
        
        patterns = [
            (r'584B4A4A-0815-AC86-DC39-C38FC27E8E17', 'Evolution API Key'),
            (r'u2gh8aomMEdqPFW1JIlTn7VcCUhRCobL', 'S3 Access Key'),
            (r'zSMwLiOH1fURqSNX8zMtMYKBjrScDQYynCW2TbI2UuXM7Bti', 'S3 Secret Key'),
            (r'75jkOmkcjQmQLFs3:~CiJnJU1I-1k~GS\.vRf4qj8-EqeurdvJ', 'RabbitMQ Credentials'),
            (r"N;\.!iB5@sw\?D2wJPr\{Ysmt5\]\[R%5\.aHyAuvNpM_@DOb:OX\*<\.f", 'Django SECRET_KEY'),
        ]
        
        files_to_check = [
            'backend/alrea_sense/settings.py',
            'backend/apps/connections/webhook_views.py',
            'backend/apps/chat/utils/storage.py',
            'backend/simulate_evolution_config.py',
            'backend/create_evolution_connection.py',
            'backend/test_evolution_api.py',
            'test_groups_correct.py',
            'test_evolution_direct.py',
        ]
        
        for filepath in files_to_check:
            if not Path(filepath).exists():
                continue
                
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                
            for pattern, cred_name in patterns:
                matches = re.finditer(pattern, content)
                for match in matches:
                    line_num = content[:match.start()].count('\n') + 1
                    self.issues_found.append({
                        'file': filepath,
                        'line': line_num,
                        'credential': cred_name,
                        'severity': 'CRITICAL'
                    })
                    self.log(f"ENCONTRADO: {cred_name} em {filepath}:{line_num}", "WARNING")
                    
    def fix_settings_defaults(self):
        """Remove credenciais hardcoded dos defaults em settings.py"""
        self.log("🔧 Corrigindo defaults em settings.py...", "FIX")
        
        filepath = Path('backend/alrea_sense/settings.py')
        if not filepath.exists():
            self.log("settings.py não encontrado", "ERROR")
            return
            
        if self.backup:
            self.backup_file(filepath)
            
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        original_content = content
        
        # Fix Evolution API Key
        content = re.sub(
            r"EVOLUTION_API_KEY = config\('EVOLUTION_API_KEY', default='[^']*'\)",
            "EVOLUTION_API_KEY = config('EVOLUTION_API_KEY')",
            content
        )
        
        # Fix S3 Keys
        content = re.sub(
            r"S3_ACCESS_KEY = config\('S3_ACCESS_KEY', default='[^']*'\)",
            "S3_ACCESS_KEY = config('S3_ACCESS_KEY')",
            content
        )
        content = re.sub(
            r"S3_SECRET_KEY = config\('S3_SECRET_KEY', default='[^']*'\)",
            "S3_SECRET_KEY = config('S3_SECRET_KEY')",
            content
        )
        
        # Fix RabbitMQ
        content = re.sub(
            r"RABBITMQ_URL = config\('RABBITMQ_PRIVATE_URL', default='amqp://[^']*'\)",
            "RABBITMQ_URL = config('RABBITMQ_PRIVATE_URL')",
            content
        )
        
        # Fix SECRET_KEY
        content = re.sub(
            r"SECRET_KEY = config\('SECRET_KEY', default='[^']*'\)",
            "SECRET_KEY = config('SECRET_KEY')",
            content
        )
        
        # Fix CORS
        content = re.sub(
            r"CORS_ALLOW_ALL_ORIGINS = True  # Temporarily True to fix Railway CORS issue",
            "CORS_ALLOW_ALL_ORIGINS = False  # ✅ FIXED: Never allow all origins in production",
            content
        )
        
        if content != original_content:
            if not self.dry_run:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.log("settings.py corrigido!", "SUCCESS")
            else:
                self.log("settings.py seria corrigido (dry-run)", "INFO")
            self.fixes_applied.append('settings.py: Removed hardcoded defaults')
        else:
            self.log("Nenhuma alteração necessária em settings.py", "INFO")
            
    def fix_views_api_key_exposure(self):
        """Corrige exposição de API key nos endpoints"""
        self.log("🔧 Corrigindo exposição de API key em views.py...", "FIX")
        
        filepath = Path('backend/apps/connections/views.py')
        if not filepath.exists():
            self.log("views.py não encontrado", "ERROR")
            return
            
        if self.backup:
            self.backup_file(filepath)
            
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        modified = False
        new_lines = []
        
        for i, line in enumerate(lines):
            # Mascarar API key no GET
            if "'api_key': api_key_value" in line and i > 100:  # GET endpoint
                indent = len(line) - len(line.lstrip())
                new_lines.append(' ' * indent + "# ✅ SECURITY FIX: Mask API key\n")
                new_lines.append(' ' * indent + "api_key_masked = '****' + (api_key_value[-4:] if api_key_value and len(api_key_value) > 4 else '')\n")
                new_lines.append(line.replace('api_key_value', 'api_key_masked'))
                modified = True
            # Mascarar API key no POST test endpoint
            elif "'api_key': api_key" in line and i > 200:  # Test endpoint
                indent = len(line) - len(line.lstrip())
                new_lines.append(' ' * indent + "# ✅ SECURITY FIX: Never return API key in response\n")
                new_lines.append(line.replace("'api_key': api_key", "'api_key': '****' + (api_key[-4:] if len(api_key) > 4 else '')"))
                modified = True
            else:
                new_lines.append(line)
                
        if modified:
            if not self.dry_run:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.writelines(new_lines)
                self.log("views.py corrigido!", "SUCCESS")
            else:
                self.log("views.py seria corrigido (dry-run)", "INFO")
            self.fixes_applied.append('views.py: Masked API key in responses')
        else:
            self.log("Nenhuma alteração necessária em views.py", "INFO")
            
    def remove_hardcoded_keys_from_files(self):
        """Remove chaves hardcoded de arquivos específicos"""
        self.log("🔧 Removendo chaves hardcoded de arquivos...", "FIX")
        
        files_to_fix = {
            'backend/apps/connections/webhook_views.py': [
                (r"'api_key': '584B4A4A-0815-AC86-DC39-C38FC27E8E17'", "'api_key': settings.EVOLUTION_API_KEY")
            ],
            'backend/simulate_evolution_config.py': [
                (r"api_key='584B4A4A-0815-AC86-DC39-C38FC27E8E17'", "api_key=settings.EVOLUTION_API_KEY")
            ],
            'backend/create_evolution_connection.py': [
                (r"api_key = '584B4A4A-0815-AC86-DC39-C38FC27E8E17'", "api_key = os.environ.get('EVOLUTION_API_KEY', '')")
            ],
            'backend/test_evolution_api.py': [
                (r"'apikey': '584B4A4A-0815-AC86-DC39-C38FC27E8E17'", "'apikey': os.environ.get('EVOLUTION_API_KEY', '')")
            ],
            'backend/apps/chat/utils/storage.py': [
                (r"S3_ACCESS_KEY = getattr\(settings, 'S3_ACCESS_KEY', '[^']*'\)", "S3_ACCESS_KEY = getattr(settings, 'S3_ACCESS_KEY')"),
                (r"S3_SECRET_KEY = getattr\(settings, 'S3_SECRET_KEY', '[^']*'\)", "S3_SECRET_KEY = getattr(settings, 'S3_SECRET_KEY')")
            ],
        }
        
        for filepath, replacements in files_to_fix.items():
            path = Path(filepath)
            if not path.exists():
                self.log(f"Arquivo não encontrado: {filepath}", "WARNING")
                continue
                
            if self.backup:
                self.backup_file(path)
                
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            original_content = content
            
            for pattern, replacement in replacements:
                content = re.sub(pattern, replacement, content)
                
            if content != original_content:
                if not self.dry_run:
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    self.log(f"{filepath} corrigido!", "SUCCESS")
                else:
                    self.log(f"{filepath} seria corrigido (dry-run)", "INFO")
                self.fixes_applied.append(f'{filepath}: Removed hardcoded credentials')
            else:
                self.log(f"Nenhuma alteração necessária em {filepath}", "INFO")
                
    def add_security_middleware(self):
        """Adiciona middleware de segurança"""
        self.log("🔧 Adicionando security headers middleware...", "FIX")
        
        middleware_content = '''"""
Security middleware for sensitive operations audit
"""
import logging
from django.utils import timezone
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger(__name__)

class SecurityAuditMiddleware:
    """
    Middleware to log sensitive operations for security audit
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.sensitive_paths = [
            '/api/connections/evolution/config/',
            '/api/connections/evolution/test/',
            '/admin/',
        ]
        
    def __call__(self, request):
        # Log sensitive endpoint access
        if any(path in request.path for path in self.sensitive_paths):
            user = request.user if not isinstance(request.user, AnonymousUser) else 'Anonymous'
            logger.warning(
                f"🔐 SENSITIVE ENDPOINT ACCESS: "
                f"Path={request.path} "
                f"Method={request.method} "
                f"User={user} "
                f"IP={self.get_client_ip(request)}"
            )
            
        response = self.get_response(request)
        
        # Add security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        return response
        
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
'''
        
        middleware_path = Path('backend/apps/common/security_middleware.py')
        middleware_path.parent.mkdir(parents=True, exist_ok=True)
        
        if not self.dry_run:
            with open(middleware_path, 'w', encoding='utf-8') as f:
                f.write(middleware_content)
            self.log("Security middleware criado!", "SUCCESS")
            self.log("⚠️  ATENÇÃO: Adicione 'apps.common.security_middleware.SecurityAuditMiddleware' ao MIDDLEWARE em settings.py", "WARNING")
        else:
            self.log("Security middleware seria criado (dry-run)", "INFO")
            
        self.fixes_applied.append('Created security audit middleware')
        
    def create_pre_commit_config(self):
        """Cria configuração de pre-commit hooks"""
        self.log("🔧 Criando pre-commit configuration...", "FIX")
        
        precommit_config = '''# See https://pre-commit.com for more information
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: check-merge-conflict
      - id: detect-private-key

  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
        exclude: package-lock.json

  - repo: local
    hooks:
      - id: check-hardcoded-credentials
        name: Check for hardcoded credentials
        entry: python scripts/check_credentials.py
        language: system
        pass_filenames: false
'''
        
        if not self.dry_run:
            with open('.pre-commit-config.yaml', 'w', encoding='utf-8') as f:
                f.write(precommit_config)
            self.log("Pre-commit config criado!", "SUCCESS")
            self.log("⚠️  Execute: pip install pre-commit && pre-commit install", "WARNING")
        else:
            self.log("Pre-commit config seria criado (dry-run)", "INFO")
            
        self.fixes_applied.append('Created pre-commit configuration')
        
    def generate_report(self):
        """Gera relatório das correções"""
        self.log("\n" + "="*60, "INFO")
        self.log("📊 RELATÓRIO DE CORREÇÕES", "INFO")
        self.log("="*60, "INFO")
        
        self.log(f"\n🔍 Issues encontrados: {len(self.issues_found)}", "WARNING")
        for issue in self.issues_found:
            self.log(
                f"  • {issue['severity']}: {issue['credential']} em {issue['file']}:{issue['line']}", 
                "WARNING"
            )
            
        self.log(f"\n🔧 Correções aplicadas: {len(self.fixes_applied)}", "SUCCESS")
        for fix in self.fixes_applied:
            self.log(f"  • {fix}", "SUCCESS")
            
        self.log("\n⚠️  PRÓXIMOS PASSOS MANUAIS:", "WARNING")
        self.log("1. Rotacione TODAS as credenciais no Railway:", "WARNING")
        self.log("   - railway variables set EVOLUTION_API_KEY='nova-chave'", "WARNING")
        self.log("   - railway variables set S3_ACCESS_KEY='nova-chave'", "WARNING")
        self.log("   - railway variables set S3_SECRET_KEY='nova-chave'", "WARNING")
        self.log("   - railway variables set SECRET_KEY='nova-chave'", "WARNING")
        self.log("", "INFO")
        self.log("2. Atualize .env local com as novas credenciais", "WARNING")
        self.log("", "INFO")
        self.log("3. Adicione security middleware ao MIDDLEWARE em settings.py:", "WARNING")
        self.log("   'apps.common.security_middleware.SecurityAuditMiddleware',", "WARNING")
        self.log("", "INFO")
        self.log("4. Instale e configure pre-commit hooks:", "WARNING")
        self.log("   pip install pre-commit", "WARNING")
        self.log("   pre-commit install", "WARNING")
        self.log("   pre-commit run --all-files", "WARNING")
        self.log("", "INFO")
        self.log("5. Audite logs de acesso recentes", "WARNING")
        self.log("", "INFO")
        self.log("6. Considere limpar Git history (veja documentação)", "WARNING")
        self.log("", "INFO")
        
def main():
    parser = argparse.ArgumentParser(description='Fix security vulnerabilities')
    parser.add_argument('--execute', action='store_true', help='Execute fixes (default is dry-run)')
    parser.add_argument('--no-backup', action='store_true', help='Skip backup creation')
    args = parser.parse_args()
    
    fixer = SecurityFixer(dry_run=not args.execute, backup=not args.no_backup)
    
    print("\n" + "="*60)
    print("🔐 CORREÇÃO DE SEGURANÇA URGENTE")
    print("="*60)
    print(f"Modo: {'EXECUÇÃO' if args.execute else 'DRY-RUN (simulação)'}")
    print(f"Backup: {'SIM' if fixer.backup else 'NÃO'}")
    print("="*60 + "\n")
    
    if not args.execute:
        print("⚠️  Executando em modo DRY-RUN (nenhuma alteração será feita)")
        print("⚠️  Use --execute para aplicar as correções\n")
    
    # Execute fixes
    fixer.find_hardcoded_credentials()
    fixer.fix_settings_defaults()
    fixer.fix_views_api_key_exposure()
    fixer.remove_hardcoded_keys_from_files()
    fixer.add_security_middleware()
    fixer.create_pre_commit_config()
    
    # Generate report
    fixer.generate_report()
    
    if not args.execute:
        print("\n⚠️  Nenhuma alteração foi feita (modo DRY-RUN)")
        print("⚠️  Execute com --execute para aplicar as correções\n")
    else:
        print("\n✅ Correções aplicadas com sucesso!")
        print("⚠️  Execute os passos manuais listados acima\n")

if __name__ == '__main__':
    main()

