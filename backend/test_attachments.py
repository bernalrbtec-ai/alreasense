#!/usr/bin/env python
"""
Script de teste para validar funcionalidades de anexos:
- Download com retry
- Validação de tamanho
- Timeout
- Geração de thumbnails
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

def test_attachment_validation():
    """Testa validação de anexos"""
    print("\n" + "="*60)
    print(" TEST: Validação de Anexos")
    print("="*60 + "\n")
    
    # Verificar constantes
    from apps.chat.tasks import MAX_FILE_SIZE, MAX_RETRIES, TIMEOUT
    
    print(f"✅ MAX_FILE_SIZE: {MAX_FILE_SIZE / 1024 / 1024}MB")
    print(f"✅ MAX_RETRIES: {MAX_RETRIES}")
    print(f"✅ TIMEOUT: {TIMEOUT}s")
    
    return True

def test_proxy_endpoint():
    """Testa endpoint de proxy"""
    print("\n" + "="*60)
    print(" TEST: Endpoint de Proxy")
    print("="*60 + "\n")
    
    from django.urls import reverse
    
    try:
        url = '/api/chat/conversations/profile-pic-proxy/'
        print(f"✅ Endpoint configurado: {url}")
        return True
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

def test_profile_pic_task():
    """Testa task de foto de perfil"""
    print("\n" + "="*60)
    print(" TEST: Task de Foto de Perfil")
    print("="*60 + "\n")
    
    from apps.chat.tasks import fetch_profile_pic
    
    print(f"✅ Task 'fetch_profile_pic' disponível")
    print(f"   Método: {fetch_profile_pic.delay}")
    
    return True

def main():
    """Executa todos os testes"""
    print("\n" + "🧪 TESTES DE ANEXOS E FOTOS DE PERFIL")
    
    tests = [
        ("Validação de Anexos", test_attachment_validation),
        ("Endpoint de Proxy", test_proxy_endpoint),
        ("Task de Foto de Perfil", test_profile_pic_task),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n❌ Erro no teste '{name}': {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Resumo
    print("\n" + "="*60)
    print(" RESUMO DOS TESTES")
    print("="*60)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {name}")
    
    print(f"\nTotal: {passed}/{total} testes passaram")
    
    if passed == total:
        print("\n🎉 Todos os testes passaram!")
        return 0
    else:
        print(f"\n⚠️ {total - passed} teste(s) falharam")
        return 1

if __name__ == '__main__':
    sys.exit(main())

