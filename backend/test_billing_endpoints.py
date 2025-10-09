#!/usr/bin/env python
"""
Script de teste para validar endpoints de billing ANTES de fazer commit
Conforme regra: "Sempre criar scripts de teste e executar simulações locais ANTES de fazer commit/push"
"""

import os
import sys
import django
import requests
from rich.console import Console
from rich.table import Table

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.tenancy.models import Tenant

console = Console()
User = get_user_model()

def test_billing_endpoints():
    """Testa todos os endpoints de billing"""
    
    console.print("\n[bold cyan]🧪 TESTANDO ENDPOINTS DE BILLING[/bold cyan]\n")
    
    # 1. Criar token de autenticação
    console.print("[yellow]1. Criando token de autenticação...[/yellow]")
    try:
        user = User.objects.filter(is_superuser=True).first()
        if not user:
            console.print("[red]❌ Nenhum superuser encontrado![/red]")
            return
        
        # Fazer login via API
        response = requests.post('http://localhost:8000/api/auth/login/', json={
            'email': 'admin@alreasense.com',
            'password': 'admin123'
        })
        
        if response.status_code != 200:
            console.print(f"[red]❌ Login falhou: {response.status_code}[/red]")
            console.print(response.text)
            return
        
        token = response.json().get('access')
        headers = {'Authorization': f'Bearer {token}'}
        console.print(f"[green]✅ Token obtido[/green]")
        
    except Exception as e:
        console.print(f"[red]❌ Erro ao obter token: {e}[/red]")
        return
    
    # 2. Testar endpoints
    endpoints = [
        ('GET', '/api/billing/products/', 'Lista de produtos'),
        ('GET', '/api/billing/products/available/', 'Produtos disponíveis para add-on'),
        ('GET', '/api/billing/plans/', 'Lista de planos'),
        ('GET', '/api/billing/tenant-products/', 'Produtos do tenant'),
        ('GET', '/api/billing/billing/summary/', 'Resumo de billing'),
        ('GET', '/api/billing/history/', 'Histórico de billing'),
    ]
    
    table = Table(title="Resultados dos Testes")
    table.add_column("Endpoint", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Descrição", style="yellow")
    table.add_column("Resultado", style="white")
    
    all_passed = True
    
    for method, endpoint, description in endpoints:
        try:
            url = f'http://localhost:8000{endpoint}'
            
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json={})
            
            if response.status_code in [200, 201]:
                data = response.json()
                
                # Verificar se retornou array onde esperado
                if 'products' in endpoint or 'plans' in endpoint or 'history' in endpoint:
                    if isinstance(data, list):
                        status_icon = "✅"
                        result = f"{len(data)} itens"
                    elif isinstance(data, dict) and 'results' in data:
                        status_icon = "✅"
                        result = f"{len(data['results'])} itens"
                    else:
                        status_icon = "⚠️"
                        result = f"Não é lista: {type(data)}"
                elif 'summary' in endpoint:
                    status_icon = "✅"
                    result = f"Plano: {data.get('plan', {}).get('name', 'N/A')}"
                else:
                    status_icon = "✅"
                    result = "OK"
                
                table.add_row(endpoint, status_icon, description, result)
            else:
                all_passed = False
                table.add_row(endpoint, "❌", description, f"Status {response.status_code}")
                
        except Exception as e:
            all_passed = False
            table.add_row(endpoint, "❌", description, str(e))
    
    console.print(table)
    
    # 3. Resumo final
    console.print()
    if all_passed:
        console.print("[bold green]✅ TODOS OS TESTES PASSARAM![/bold green]")
        console.print("[green]Sistema pronto para commit/push[/green]")
    else:
        console.print("[bold red]❌ ALGUNS TESTES FALHARAM![/bold red]")
        console.print("[red]NÃO FAÇA COMMIT/PUSH ATÉ CORRIGIR OS ERROS[/red]")
    
    return all_passed

if __name__ == "__main__":
    try:
        passed = test_billing_endpoints()
        sys.exit(0 if passed else 1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Teste interrompido pelo usuário[/yellow]")
        sys.exit(1)

