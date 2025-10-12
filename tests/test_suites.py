#!/usr/bin/env python3
"""
Suítes de Testes Específicas para ALREA Sense
"""
import requests
import json
import time
from test_framework import TestRunner, TestSuite, TestStatus, TestResult

class AuthenticationTests:
    """Testes de Autenticação"""
    
    @staticmethod
    def test_superadmin_login(runner: TestRunner) -> bool:
        """Testar login do superadmin"""
        return runner.login("superadmin@alreasense.com", "admin123")
    
    @staticmethod
    def test_client_login(runner: TestRunner) -> bool:
        """Testar login de cliente"""
        return runner.login("paulo@rbtec.com", "senha123")
    
    @staticmethod
    def test_invalid_login(runner: TestRunner) -> bool:
        """Testar login inválido"""
        try:
            response = runner.session.post("http://localhost:8000/api/auth/login/", json={
                "email": "invalid@test.com",
                "password": "wrongpassword"
            })
            return response.status_code == 400  # Deve retornar erro
        except:
            return False
    
    @staticmethod
    def test_token_validation(runner: TestRunner) -> bool:
        """Testar se token é válido"""
        if not runner.auth_token:
            return False
        
        try:
            response = runner.session.get("http://localhost:8000/api/health/")
            return response.status_code == 200
        except:
            return False

class APITests:
    """Testes de APIs"""
    
    @staticmethod
    def test_plans_api(runner: TestRunner) -> bool:
        """Testar API de planos"""
        try:
            response = runner.session.get("http://localhost:8000/api/billing/plans/")
            if response.status_code != 200:
                return False
            
            data = response.json()
            plans = data.get('results', data)
            
            # Verificar se tem pelo menos 4 planos
            if len(plans) < 4:
                return False
            
            # Verificar estrutura dos planos
            required_fields = ['id', 'name', 'slug', 'price']
            for plan in plans:
                for field in required_fields:
                    if field not in plan:
                        return False
            
            return True
        except:
            return False
    
    @staticmethod
    def test_products_api(runner: TestRunner) -> bool:
        """Testar API de produtos"""
        try:
            response = runner.session.get("http://localhost:8000/api/billing/products/")
            if response.status_code != 200:
                return False
            
            data = response.json()
            products = data.get('results', data)
            
            # Verificar se tem pelo menos 3 produtos
            if len(products) < 3:
                return False
            
            # Verificar produtos específicos
            product_slugs = [p['slug'] for p in products]
            required_products = ['flow', 'sense', 'api_public']
            
            for required in required_products:
                if required not in product_slugs:
                    return False
            
            return True
        except:
            return False
    
    @staticmethod
    def test_tenants_api(runner: TestRunner) -> bool:
        """Testar API de tenants"""
        try:
            response = runner.session.get("http://localhost:8000/api/tenants/tenants/")
            if response.status_code != 200:
                return False
            
            data = response.json()
            tenants = data.get('results', data)
            
            # Verificar se tem pelo menos 2 tenants
            if len(tenants) < 2:
                return False
            
            # Verificar estrutura dos tenants
            required_fields = ['id', 'name', 'status']
            for tenant in tenants:
                for field in required_fields:
                    if field not in tenant:
                        return False
            
            return True
        except:
            return False

class CRUDTests:
    """Testes de CRUD"""
    
    @staticmethod
    def test_create_tenant(runner: TestRunner) -> bool:
        """Testar criação de tenant"""
        try:
            tenant_data = {
                "name": "Cliente Teste CRUD",
                "plan": "starter",
                "status": "active",
                "admin_first_name": "João",
                "admin_last_name": "Silva",
                "admin_email": "joao.crud@teste.com",
                "admin_phone": "11999999999",
                "admin_password": "senha123",
                "notify_email": True,
                "notify_whatsapp": False
            }
            
            response = runner.session.post("http://localhost:8000/api/tenants/tenants/", json=tenant_data)
            
            if response.status_code == 201:
                # Salvar ID para limpeza posterior
                tenant_id = response.json().get('id')
                runner._test_tenant_id = tenant_id
                return True
            
            return False
        except:
            return False
    
    @staticmethod
    def test_update_tenant(runner: TestRunner) -> bool:
        """Testar atualização de tenant"""
        try:
            if not hasattr(runner, '_test_tenant_id'):
                return False
            
            update_data = {
                "name": "Cliente Teste CRUD Atualizado",
                "status": "trial"
            }
            
            response = runner.session.patch(
                f"http://localhost:8000/api/tenants/tenants/{runner._test_tenant_id}/",
                json=update_data
            )
            
            return response.status_code == 200
        except:
            return False
    
    @staticmethod
    def test_delete_tenant(runner: TestRunner) -> bool:
        """Testar exclusão de tenant"""
        try:
            if not hasattr(runner, '_test_tenant_id'):
                return False
            
            response = runner.session.delete(
                f"http://localhost:8000/api/tenants/tenants/{runner._test_tenant_id}/"
            )
            
            return response.status_code == 204
        except:
            return False

class PerformanceTests:
    """Testes de Performance"""
    
    @staticmethod
    def test_api_response_time(runner: TestRunner) -> bool:
        """Testar tempo de resposta das APIs"""
        try:
            apis = [
                "/api/billing/plans/",
                "/api/billing/products/",
                "/api/tenants/tenants/",
                "/api/health/"
            ]
            
            max_response_time = 2.0  # 2 segundos máximo
            
            for api in apis:
                start_time = time.time()
                response = runner.session.get(f"http://localhost:8000{api}")
                response_time = time.time() - start_time
                
                if response.status_code != 200 or response_time > max_response_time:
                    return False
            
            return True
        except:
            return False
    
    @staticmethod
    def test_concurrent_requests(runner: TestRunner) -> bool:
        """Testar requisições concorrentes"""
        import threading
        import queue
        
        results = queue.Queue()
        
        def make_request():
            try:
                response = runner.session.get("http://localhost:8000/api/health/")
                results.put(response.status_code == 200)
            except:
                results.put(False)
        
        # Fazer 10 requisições concorrentes
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        # Aguardar todas as threads
        for thread in threads:
            thread.join()
        
        # Verificar resultados
        success_count = 0
        while not results.empty():
            if results.get():
                success_count += 1
        
        return success_count >= 8  # Pelo menos 80% devem passar

class IntegrationTests:
    """Testes de Integração"""
    
    @staticmethod
    def test_full_workflow(runner: TestRunner) -> bool:
        """Testar fluxo completo: login -> buscar dados -> criar tenant -> editar -> deletar"""
        try:
            # 1. Login
            if not runner.login("superadmin@alreasense.com", "admin123"):
                return False
            
            # 2. Buscar planos
            response = runner.session.get("http://localhost:8000/api/billing/plans/")
            if response.status_code != 200:
                return False
            
            plans = response.json().get('results', response.json())
            if len(plans) == 0:
                return False
            
            # 3. Criar tenant
            tenant_data = {
                "name": "Cliente Workflow Test",
                "plan": plans[0]['slug'],
                "status": "active",
                "admin_first_name": "Workflow",
                "admin_last_name": "Test",
                "admin_email": "workflow@teste.com",
                "admin_phone": "11999999999",
                "admin_password": "senha123",
                "notify_email": True,
                "notify_whatsapp": False
            }
            
            response = runner.session.post("http://localhost:8000/api/tenants/tenants/", json=tenant_data)
            if response.status_code != 201:
                return False
            
            tenant_id = response.json().get('id')
            
            # 4. Editar tenant
            update_data = {"name": "Cliente Workflow Test Atualizado"}
            response = runner.session.patch(
                f"http://localhost:8000/api/tenants/tenants/{tenant_id}/",
                json=update_data
            )
            if response.status_code != 200:
                return False
            
            # 5. Deletar tenant
            response = runner.session.delete(
                f"http://localhost:8000/api/tenants/tenants/{tenant_id}/"
            )
            if response.status_code != 204:
                return False
            
            return True
        except:
            return False

def create_test_suites() -> list:
    """Criar todas as suítes de teste"""
    suites = []
    
    # Suíte de Autenticação
    auth_suite = TestSuite("Autenticação")
    auth_suite.tests = [
        AuthenticationTests.test_superadmin_login,
        AuthenticationTests.test_client_login,
        AuthenticationTests.test_invalid_login,
        AuthenticationTests.test_token_validation,
    ]
    suites.append(auth_suite)
    
    # Suíte de APIs
    api_suite = TestSuite("APIs")
    api_suite.tests = [
        APITests.test_plans_api,
        APITests.test_products_api,
        APITests.test_tenants_api,
    ]
    suites.append(api_suite)
    
    # Suíte de CRUD
    crud_suite = TestSuite("CRUD Operations")
    crud_suite.tests = [
        CRUDTests.test_create_tenant,
        CRUDTests.test_update_tenant,
        CRUDTests.test_delete_tenant,
    ]
    suites.append(crud_suite)
    
    # Suíte de Performance
    perf_suite = TestSuite("Performance")
    perf_suite.tests = [
        PerformanceTests.test_api_response_time,
        PerformanceTests.test_concurrent_requests,
    ]
    suites.append(perf_suite)
    
    # Suíte de Integração
    integration_suite = TestSuite("Integração")
    integration_suite.tests = [
        IntegrationTests.test_full_workflow,
    ]
    suites.append(integration_suite)
    
    return suites

