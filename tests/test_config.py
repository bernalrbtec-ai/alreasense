#!/usr/bin/env python3
"""
Configurações de Teste
"""
import os
from dataclasses import dataclass
from typing import List

@dataclass
class TestConfig:
    """Configuração dos testes"""
    
    # URLs
    base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost"
    
    # Credenciais de teste
    superadmin_email: str = "superadmin@alreasense.com"
    superadmin_password: str = "admin123"
    client_email: str = "paulo@rbtec.com"
    client_password: str = "senha123"
    
    # Timeouts
    api_timeout: float = 10.0
    max_response_time: float = 2.0
    
    # Dados de teste
    test_tenant_name: str = "Cliente Teste"
    test_admin_email: str = "teste@exemplo.com"
    test_admin_password: str = "senha123"
    
    # Configurações de performance
    concurrent_requests: int = 10
    min_success_rate: float = 80.0
    
    # Configurações de relatório
    generate_html_report: bool = True
    report_directory: str = "test_reports"
    
    @classmethod
    def from_env(cls) -> 'TestConfig':
        """Carregar configuração das variáveis de ambiente"""
        return cls(
            base_url=os.getenv('TEST_BASE_URL', cls.base_url),
            frontend_url=os.getenv('TEST_FRONTEND_URL', cls.frontend_url),
            superadmin_email=os.getenv('TEST_SUPERADMIN_EMAIL', cls.superadmin_email),
            superadmin_password=os.getenv('TEST_SUPERADMIN_PASSWORD', cls.superadmin_password),
            client_email=os.getenv('TEST_CLIENT_EMAIL', cls.client_email),
            client_password=os.getenv('TEST_CLIENT_PASSWORD', cls.client_password),
            api_timeout=float(os.getenv('TEST_API_TIMEOUT', cls.api_timeout)),
            max_response_time=float(os.getenv('TEST_MAX_RESPONSE_TIME', cls.max_response_time)),
        )

# Configuração global
config = TestConfig.from_env()

