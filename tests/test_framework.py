#!/usr/bin/env python3
"""
Framework de Testes Avançado para ALREA Sense
"""
import requests
import json
import time
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

BASE_URL = "http://localhost:8000"

class TestStatus(Enum):
    PASSED = "✅ PASSED"
    FAILED = "❌ FAILED"
    SKIPPED = "⏭️ SKIPPED"
    ERROR = "💥 ERROR"

@dataclass
class TestResult:
    name: str
    status: TestStatus
    duration: float
    message: str
    details: Optional[Dict] = None

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
        passed = len([t for t in self.tests if t.status == TestStatus.PASSED])
        failed = len([t for t in self.tests if t.status == TestStatus.FAILED])
        errors = len([t for t in self.tests if t.status == TestStatus.ERROR])
        skipped = len([t for t in self.tests if t.status == TestStatus.SKIPPED])
        
        duration = (self.end_time - self.start_time).total_seconds() if self.end_time and self.start_time else 0
        
        return {
            'suite_name': self.name,
            'total': total,
            'passed': passed,
            'failed': failed,
            'errors': errors,
            'skipped': skipped,
            'success_rate': (passed / total * 100) if total > 0 else 0,
            'duration': duration
        }

class TestRunner:
    def __init__(self):
        self.suites: List[TestSuite] = []
        self.auth_token = None
        self.session = requests.Session()
    
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
                return TestResult(test_name, TestStatus.PASSED, duration, "Teste passou")
            else:
                return TestResult(test_name, TestStatus.FAILED, duration, "Teste falhou")
                
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(test_name, TestStatus.ERROR, duration, f"Erro: {str(e)}")
    
    def run_suite(self, suite: TestSuite):
        """Executar uma suíte de testes"""
        print(f"\n🧪 Executando suíte: {suite.name}")
        print("=" * 50)
        
        suite.start_time = datetime.now()
        
        for test_func in suite.tests:
            result = self.run_test(test_func, self)
            suite.add_test(result)
            
            status_icon = result.status.value
            print(f"{status_icon} {result.name} ({result.duration:.2f}s)")
            if result.message:
                print(f"   {result.message}")
        
        suite.end_time = datetime.now()
        
        # Resumo da suíte
        summary = suite.get_summary()
        print(f"\n📊 Resumo da suíte '{suite.name}':")
        print(f"   Total: {summary['total']}")
        print(f"   Passou: {summary['passed']}")
        print(f"   Falhou: {summary['failed']}")
        print(f"   Erros: {summary['errors']}")
        print(f"   Taxa de sucesso: {summary['success_rate']:.1f}%")
        print(f"   Duração: {summary['duration']:.2f}s")
    
    def generate_report(self, filename: str = None):
        """Gerar relatório HTML dos testes"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"test_report_{timestamp}.html"
        
        html_content = self._generate_html_report()
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"\n📄 Relatório gerado: {filename}")
    
    def _generate_html_report(self) -> str:
        """Gerar conteúdo HTML do relatório"""
        total_tests = sum(len(suite.tests) for suite in self.suites)
        total_passed = sum(len([t for t in suite.tests if t.status == TestStatus.PASSED]) for suite in self.suites)
        total_failed = sum(len([t for t in suite.tests if t.status == TestStatus.FAILED]) for suite in self.suites)
        total_errors = sum(len([t for t in suite.tests if t.status == TestStatus.ERROR]) for suite in self.suites)
        
        success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
        
        html = f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Relatório de Testes - ALREA Sense</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .summary-card {{ background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; }}
        .summary-card h3 {{ margin: 0 0 10px 0; color: #333; }}
        .summary-card .number {{ font-size: 2em; font-weight: bold; }}
        .passed {{ color: #28a745; }}
        .failed {{ color: #dc3545; }}
        .error {{ color: #fd7e14; }}
        .suite {{ margin-bottom: 30px; border: 1px solid #ddd; border-radius: 8px; overflow: hidden; }}
        .suite-header {{ background: #007bff; color: white; padding: 15px; font-weight: bold; }}
        .test {{ padding: 10px 15px; border-bottom: 1px solid #eee; }}
        .test:last-child {{ border-bottom: none; }}
        .test-name {{ font-weight: bold; }}
        .test-status {{ float: right; }}
        .test-duration {{ color: #666; font-size: 0.9em; }}
        .test-message {{ color: #666; font-size: 0.9em; margin-top: 5px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧪 Relatório de Testes - ALREA Sense</h1>
            <p>Gerado em: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}</p>
        </div>
        
        <div class="summary">
            <div class="summary-card">
                <h3>Total de Testes</h3>
                <div class="number">{total_tests}</div>
            </div>
            <div class="summary-card">
                <h3>Passou</h3>
                <div class="number passed">{total_passed}</div>
            </div>
            <div class="summary-card">
                <h3>Falhou</h3>
                <div class="number failed">{total_failed}</div>
            </div>
            <div class="summary-card">
                <h3>Erros</h3>
                <div class="number error">{total_errors}</div>
            </div>
            <div class="summary-card">
                <h3>Taxa de Sucesso</h3>
                <div class="number {'passed' if success_rate >= 80 else 'failed'}">{success_rate:.1f}%</div>
            </div>
        </div>
"""
        
        for suite in self.suites:
            summary = suite.get_summary()
            html += f"""
        <div class="suite">
            <div class="suite-header">
                {suite.name} - {summary['passed']}/{summary['total']} passou ({summary['success_rate']:.1f}%)
            </div>
"""
            
            for test in suite.tests:
                status_class = test.status.name.lower()
                html += f"""
            <div class="test">
                <div class="test-name">{test.name}</div>
                <div class="test-status {status_class}">{test.status.value}</div>
                <div class="test-duration">Duração: {test.duration:.2f}s</div>
                {f'<div class="test-message">{test.message}</div>' if test.message else ''}
            </div>
"""
            
            html += "        </div>"
        
        html += """
    </div>
</body>
</html>
"""
        return html
