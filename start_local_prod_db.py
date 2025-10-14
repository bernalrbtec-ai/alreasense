#!/usr/bin/env python
"""
Script simples para iniciar ambiente local com banco de produção
"""
import subprocess
import time

def start_local_with_prod_db():
    print("="*80)
    print("INICIANDO AMBIENTE LOCAL COM BANCO DE PRODUCAO")
    print("="*80)
    
    # 1. Parar containers existentes
    print("Parando containers existentes...")
    subprocess.run("docker compose down", shell=True)
    
    # 2. Rodar com banco de produção
    print("Iniciando containers com banco de producao...")
    result = subprocess.run("docker compose -f docker-compose.prod-db.yml up --build -d", shell=True)
    
    if result.returncode != 0:
        print("ERRO: Falha ao iniciar containers")
        return False
    
    # 3. Aguardar serviços
    print("Aguardando servicos ficarem prontos...")
    time.sleep(15)
    
    print("\nAMBIENTE INICIADO COM SUCESSO!")
    print("="*80)
    print("URLs disponiveis:")
    print("  - Frontend: http://localhost:80")
    print("  - Backend: http://localhost:8000")
    print("  - Admin: http://localhost:8000/admin/")
    print()
    print("Login com usuarios de producao:")
    print("  - paulo.bernal@alrea.ai")
    print("  - paulo.bernal@rbtec.com.br")
    print("  - thiago-bal@hotmail.com")
    print()
    print("ATENCAO: Voce esta usando dados REAIS de producao!")
    print("Para parar: docker compose down")
    
    return True

if __name__ == '__main__':
    start_local_with_prod_db()
