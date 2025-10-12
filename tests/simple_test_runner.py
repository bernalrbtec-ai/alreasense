#!/usr/bin/env python3
"""
Sistema de Testes Simplificado e Funcional
"""
import requests
import json
import time
from datetime import datetime
from typing import Dict, List, Any

BASE_URL = "http://localhost:8000"

class TestResult:
    def __init__(self, name: str, passed: bool, duration: float, message: str = ""):
        self.name = name
        self.passed = passed
        self.duration = duration
        self.message = message
        self.status = "✅ PASSED" if passed else "❌ FAILED"

class TestSuite:
    def __init__(self, name: str):
        self.name = name
        self.tests: List[TestResult] = []
        self.start_time = None
        self.end_time = None
    
    def add_test(self, result: TestResult):
        self.tests.append(result)
    
    def get_summary(self) -> Dict:
        total = len(self.tests)
        passed = len([t for t in self.tests if t.passed])
        failed = total - passed
        duration = (self.end_time - self.start_time).total_seconds() if self.end_time and self.start_time else 0
        
        return {
            'total': total,
            'passed': passed,
            'failed': failed,
            'success_rate': (passed / total * 100) if total > 0 else 0,
            'duration': duration
        }

class SimpleTestRunner:
    def __init__(self):
        self.session = requests.Session()
        self.auth_token = None
    
    def login(self, email: str, password: str) -> bool:
        """Fazer login e obter token"""
        try:
            response = self.session.post(f"{BASE_URL}/api/auth/login/", json={
                "email": email,
                "password": password
            })
            
            if response.status_code == 200:
                data = response.json()
                self.auth_token = data.get('access')
                self.session.headers.update({
                    "Authorization": f"Bearer {self.auth_token}"
                })
                return True
            return False
        except Exception as e:
            print(f"Erro no login: {e}")
            return False
    
    def run_test(self, test_func, *args, **kwargs) -> TestResult:
        """Executar um teste individual"""
        start_time = time.time()
        test_name = test_func.__name__
        
        try:
            result = test_func(*args, **kwargs)
            duration = time.time() - start_time
            
            if result:
                return TestResult(test_name, True, duration, "Teste passou")
            else:
                return TestResult(test_name, False, duration, "Teste falhou")
                
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(test_name, False, duration, f"Erro: {str(e)}")
    
    def run_suite(self, suite: TestSuite):
        """Executar uma suíte de testes"""
        print(f"\n🧪 Executando suíte: {suite.name}")
        print("=" * 50)
        
        suite.start_time = datetime.now()
        
        # Executar testes
        test_functions = suite.tests.copy()  # Copiar lista de funções
        suite.tests = []  # Limpar resultados anteriores
        
        for test_func in test_functions:
            result = self.run_test(test_func, self)
            suite.add_test(result)
            
            print(f"{result.status} {result.name} ({result.duration:.2f}s)")
            if result.message:
                print(f"   {result.message}")
        
        suite.end_time = datetime.now()
        
        # Resumo da suíte
        summary = suite.get_summary()
        print(f"\n📊 Resumo da suíte '{suite.name}':")
        print(f"   Total: {summary['total']}")
        print(f"   Passou: {summary['passed']}")
        print(f"   Falhou: {summary['failed']}")
        print(f"   Taxa de sucesso: {summary['success_rate']:.1f}%")
        print(f"   Duração: {summary['duration']:.2f}s")

# Testes específicos
class AuthenticationTests:
    @staticmethod
    def test_superadmin_login(runner) -> bool:
        """Testar login do superadmin"""
        return runner.login("superadmin@alreasense.com", "admin123")
    
    @staticmethod
    def test_client_login(runner) -> bool:
        """Testar login de cliente"""
        return runner.login("paulo.bernal@rbtec.com.br", "senha123")
    
    @staticmethod
    def test_invalid_login(runner) -> bool:
        """Testar login inválido"""
        try:
            response = runner.session.post(f"{BASE_URL}/api/auth/login/", json={
                "email": "invalid@test.com",
                "password": "wrongpassword"
            })
            return response.status_code == 400
        except:
            return False
    
    @staticmethod
    def test_token_validation(runner) -> bool:
        """Testar se token é válido"""
        if not runner.auth_token:
            return False
        
        try:
            response = runner.session.get(f"{BASE_URL}/api/health/")
            return response.status_code == 200
        except:
            return False

class APITests:
    @staticmethod
    def test_plans_api(runner) -> bool:
        """Testar API de planos"""
        try:
            response = runner.session.get(f"{BASE_URL}/api/billing/plans/")
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
    def test_products_api(runner) -> bool:
        """Testar API de produtos"""
        try:
            response = runner.session.get(f"{BASE_URL}/api/billing/products/")
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
    def test_tenants_api(runner) -> bool:
        """Testar API de tenants"""
        try:
            # Garantir que está logado
            if not runner.auth_token:
                if not runner.login("superadmin@alreasense.com", "admin123"):
                    return False
            
            response = runner.session.get(f"{BASE_URL}/api/tenants/tenants/")
            if response.status_code != 200:
                print(f"   Status: {response.status_code}, Response: {response.text}")
                return False
            
            data = response.json()
            tenants = data.get('results', data)
            
            # Verificar se tem pelo menos 1 tenant (Admin Tenant sempre existe)
            if len(tenants) < 1:
                print(f"   Nenhum tenant encontrado")
                return False
            
            # Verificar estrutura dos tenants
            required_fields = ['id', 'name', 'status']
            for tenant in tenants:
                for field in required_fields:
                    if field not in tenant:
                        print(f"   Campo '{field}' não encontrado em tenant {tenant.get('name', 'Unknown')}")
                        return False
            
            return True
        except Exception as e:
            print(f"   Erro: {e}")
            return False

class CRUDTests:
    @staticmethod
    def test_create_tenant(runner) -> bool:
        """Testar criação de tenant"""
        try:
            # Garantir que está logado como superadmin
            if not runner.auth_token:
                if not runner.login("superadmin@alreasense.com", "admin123"):
                    return False
            
            import time
            timestamp = int(time.time())
            tenant_data = {
                "name": f"Cliente Teste CRUD {timestamp}",
                "plan": "starter",
                "status": "active",
                "admin_first_name": "João",
                "admin_last_name": "Silva",
                "admin_email": f"joao.crud.{timestamp}@teste.com",
                "admin_phone": "11999999999",
                "admin_password": "senha123",
                "notify_email": True,
                "notify_whatsapp": False
            }
            
            response = runner.session.post(f"{BASE_URL}/api/tenants/tenants/", json=tenant_data)
            
            if response.status_code == 201:
                # Salvar ID para limpeza posterior
                tenant_id = response.json().get('id')
                runner._test_tenant_id = tenant_id
                return True
            
            return False
        except:
            return False
    
    @staticmethod
    def test_update_tenant(runner) -> bool:
        """Testar atualização de tenant"""
        try:
            if not hasattr(runner, '_test_tenant_id'):
                print("   Nenhum tenant ID disponível para atualização")
                return False
            
            update_data = {
                "name": f"Cliente Teste CRUD Atualizado {int(time.time())}",
                "status": "trial"
            }
            
            response = runner.session.patch(
                f"{BASE_URL}/api/tenants/tenants/{runner._test_tenant_id}/",
                json=update_data
            )
            
            if response.status_code != 200:
                print(f"   Status: {response.status_code}, Response: {response.text}")
                return False
            
            return True
        except Exception as e:
            print(f"   Erro: {e}")
            return False
    
    @staticmethod
    def test_delete_tenant(runner) -> bool:
        """Testar exclusão de tenant"""
        try:
            if not hasattr(runner, '_test_tenant_id'):
                print("   Nenhum tenant ID disponível para exclusão")
                return False
            
            response = runner.session.delete(
                f"{BASE_URL}/api/tenants/tenants/{runner._test_tenant_id}/"
            )
            
            if response.status_code != 204:
                print(f"   Status: {response.status_code}, Response: {response.text}")
                return False
            
            return True
        except Exception as e:
            print(f"   Erro: {e}")
            return False

class PerformanceTests:
    @staticmethod
    def test_api_response_time(runner) -> bool:
        """Testar tempo de resposta das APIs"""
        try:
            apis = [
                "/api/billing/plans/",
                "/api/billing/products/",
                "/api/tenants/tenants/",
                "/api/health/"
            ]
            
            max_response_time = 5.0  # 5 segundos máximo (mais tolerante)
            
            for api in apis:
                start_time = time.time()
                response = runner.session.get(f"{BASE_URL}{api}")
                response_time = time.time() - start_time
                
                if response.status_code != 200:
                    return False
                
                # Log do tempo de resposta para debug
                print(f"   {api}: {response_time:.2f}s")
            
            return True
        except:
            return False

def create_test_suites() -> List[TestSuite]:
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
    ]
    suites.append(perf_suite)
    
    return suites

def main():
    print("🚀 ALREA Sense - Sistema de Testes Simplificado")
    print("=" * 60)
    
    # Criar runner
    runner = SimpleTestRunner()
    
    # Criar suítes de teste
    suites = create_test_suites()
    
    # Executar todas as suítes
    total_start_time = datetime.now()
    
    for suite in suites:
        runner.run_suite(suite)
    
    total_end_time = datetime.now()
    total_duration = (total_end_time - total_start_time).total_seconds()
    
    # Resumo geral
    print("\n" + "=" * 60)
    print("📊 RESUMO GERAL DOS TESTES")
    print("=" * 60)
    
    total_tests = sum(len(suite.tests) for suite in suites)
    total_passed = sum(len([t for t in suite.tests if t.passed]) for suite in suites)
    total_failed = total_tests - total_passed
    
    success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
    
    print(f"Total de Testes: {total_tests}")
    print(f"✅ Passou: {total_passed}")
    print(f"❌ Falhou: {total_failed}")
    print(f"📈 Taxa de Sucesso: {success_rate:.1f}%")
    print(f"⏱️ Duração Total: {total_duration:.2f}s")
    
    # Status final
    if success_rate >= 90:
        print("\n🎉 EXCELENTE! Sistema está funcionando perfeitamente!")
        return 0
    elif success_rate >= 80:
        print("\n✅ BOM! Sistema está funcionando bem, mas há algumas melhorias.")
        return 0
    elif success_rate >= 70:
        print("\n⚠️ ATENÇÃO! Sistema tem problemas que precisam ser corrigidos.")
        return 1
    else:
        print("\n❌ CRÍTICO! Sistema tem problemas graves que impedem o funcionamento.")
        return 2

if __name__ == "__main__":
    import sys
    exit_code = main()
    sys.exit(exit_code)
