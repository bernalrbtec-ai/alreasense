#!/usr/bin/env python3
"""
Executor Principal de Testes
"""
import sys
import os
from datetime import datetime
from test_framework import TestRunner
from test_suites import create_test_suites

def main():
    print("🚀 ALREA Sense - Sistema de Testes Avançado")
    print("=" * 60)
    
    # Criar runner
    runner = TestRunner()
    
    # Criar suítes de teste
    suites = create_test_suites()
    
    # Executar todas as suítes
    total_start_time = datetime.now()
    
    for suite in suites:
        runner.run_suite(suite)
        runner.suites.append(suite)
    
    total_end_time = datetime.now()
    total_duration = (total_end_time - total_start_time).total_seconds()
    
    # Resumo geral
    print("\n" + "=" * 60)
    print("📊 RESUMO GERAL DOS TESTES")
    print("=" * 60)
    
    total_tests = sum(len(suite.tests) for suite in suites)
    total_passed = sum(len([t for t in suite.tests if t.status.value.startswith("✅")]) for suite in suites)
    total_failed = sum(len([t for t in suite.tests if t.status.value.startswith("❌")]) for suite in suites)
    total_errors = sum(len([t for t in suite.tests if t.status.value.startswith("💥")]) for suite in suites)
    
    success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
    
    print(f"Total de Testes: {total_tests}")
    print(f"✅ Passou: {total_passed}")
    print(f"❌ Falhou: {total_failed}")
    print(f"💥 Erros: {total_errors}")
    print(f"📈 Taxa de Sucesso: {success_rate:.1f}%")
    print(f"⏱️ Duração Total: {total_duration:.2f}s")
    
    # Gerar relatório
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_filename = f"test_report_{timestamp}.html"
    runner.generate_report(report_filename)
    
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
    exit_code = main()
    sys.exit(exit_code)

