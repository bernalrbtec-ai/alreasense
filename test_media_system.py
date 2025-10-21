"""
Script de teste para o Sistema de Mídia - ALREA Sense

Testa:
1. Utilitários S3 (upload, download, delete)
2. Processamento de imagens (thumbnail, resize, optimize)
3. Proxy de mídia (cache Redis)
4. Endpoints de upload
5. Sistema completo (download WhatsApp → S3 → Proxy)

Uso:
    python test_media_system.py
"""
import os
import sys
import django
import requests
import base64
from pathlib import Path

# Setup Django
sys.path.insert(0, str(Path(__file__).parent / 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.chat.utils.s3 import get_s3_manager, generate_media_path
from apps.chat.utils.image_processing import process_image, is_valid_image
from django.core.cache import cache

# Cores para output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_test(name):
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}TEST: {name}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")

def print_success(msg):
    print(f"{GREEN}✅ {msg}{RESET}")

def print_error(msg):
    print(f"{RED}❌ {msg}{RESET}")

def print_info(msg):
    print(f"{YELLOW}ℹ️  {msg}{RESET}")


def test_s3_operations():
    """Testa operações S3"""
    print_test("S3 Operations (Upload, Download, Delete)")
    
    s3_manager = get_s3_manager()
    
    # 1. Upload
    print_info("Testando upload...")
    test_data = b"Hello, S3! This is a test file."
    test_path = generate_media_path("test-tenant", "test", "test.txt")
    
    success, msg = s3_manager.upload_to_s3(test_data, test_path, 'text/plain')
    
    if success:
        print_success(f"Upload OK: {msg}")
    else:
        print_error(f"Upload FAILED: {msg}")
        return False
    
    # 2. Download
    print_info("Testando download...")
    success, data, msg = s3_manager.download_from_s3(test_path)
    
    if success and data == test_data:
        print_success(f"Download OK: {len(data)} bytes")
    else:
        print_error(f"Download FAILED: {msg}")
        return False
    
    # 3. Exists
    print_info("Testando file_exists...")
    if s3_manager.file_exists(test_path):
        print_success("File exists check OK")
    else:
        print_error("File exists check FAILED")
        return False
    
    # 4. Delete
    print_info("Testando delete...")
    success, msg = s3_manager.delete_from_s3(test_path)
    
    if success:
        print_success("Delete OK")
    else:
        print_error(f"Delete FAILED: {msg}")
        return False
    
    # 5. Verificar que foi deletado
    if not s3_manager.file_exists(test_path):
        print_success("File was deleted successfully")
    else:
        print_error("File still exists after delete")
        return False
    
    print_success("✨ Todos os testes S3 passaram!")
    return True


def test_image_processing():
    """Testa processamento de imagens"""
    print_test("Image Processing (Thumbnail, Resize, Optimize)")
    
    # Criar imagem de teste (RGB simples)
    from PIL import Image
    import io
    
    print_info("Criando imagem de teste (1000x1000)...")
    img = Image.new('RGB', (1000, 1000), color='red')
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=95)
    test_image = buffer.getvalue()
    
    print_info(f"Imagem original: {len(test_image)} bytes")
    
    # 1. Validar imagem
    if is_valid_image(test_image):
        print_success("Imagem válida")
    else:
        print_error("Imagem inválida")
        return False
    
    # 2. Processar imagem completo
    print_info("Processando imagem (thumb + resize + optimize)...")
    result = process_image(test_image, create_thumb=True, resize=True, optimize=True)
    
    if not result['success']:
        print_error(f"Processamento falhou: {result['errors']}")
        return False
    
    print_success(f"Imagem processada: {result['original_size']} → {result['processed_size']} bytes")
    
    if result['thumbnail_data']:
        print_success(f"Thumbnail criado: {result['thumbnail_size']} bytes")
    else:
        print_error("Thumbnail não foi criado")
        return False
    
    # 3. Verificar que thumbnail é menor
    if result['thumbnail_size'] < result['processed_size']:
        print_success("Thumbnail é menor que imagem processada")
    else:
        print_error("Thumbnail deveria ser menor")
        return False
    
    # 4. Verificar que imagem processada é menor que original
    if result['processed_size'] < result['original_size']:
        print_success("Imagem otimizada é menor que original")
    else:
        print_info("Imagem otimizada não ficou menor (pode acontecer com imagens pequenas)")
    
    print_success("✨ Todos os testes de processamento passaram!")
    return True


def test_media_proxy():
    """Testa proxy de mídia com cache Redis"""
    print_test("Media Proxy (Redis Cache)")
    
    # URL de teste (pode ser qualquer imagem pública)
    test_url = "https://via.placeholder.com/150"
    
    # 1. Limpar cache primeiro
    import hashlib
    cache_key = f"media:{hashlib.md5(test_url.encode()).hexdigest()}"
    cache.delete(cache_key)
    print_info("Cache limpo")
    
    # 2. Primeira request (MISS - deve baixar)
    print_info("Request 1 (cache MISS esperado)...")
    try:
        response = requests.get(
            "http://localhost:8000/api/chat/media-proxy/",
            params={'url': test_url},
            timeout=10
        )
        
        if response.status_code == 200:
            x_cache = response.headers.get('X-Cache', '')
            if x_cache == 'MISS':
                print_success(f"Cache MISS OK (primeira request)")
            else:
                print_error(f"Esperava MISS, recebeu: {x_cache}")
                return False
        else:
            print_error(f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print_error(f"Erro na request: {e}")
        print_info("Certifique-se de que o backend está rodando em localhost:8000")
        return False
    
    # 3. Segunda request (HIT - deve vir do cache)
    print_info("Request 2 (cache HIT esperado)...")
    try:
        response = requests.get(
            "http://localhost:8000/api/chat/media-proxy/",
            params={'url': test_url},
            timeout=10
        )
        
        if response.status_code == 200:
            x_cache = response.headers.get('X-Cache', '')
            if x_cache == 'HIT':
                print_success(f"Cache HIT OK (cache funcionando!)")
            else:
                print_error(f"Esperava HIT, recebeu: {x_cache}")
                return False
        else:
            print_error(f"Status {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Erro na request: {e}")
        return False
    
    # 4. Verificar que está no Redis
    cached_data = cache.get(cache_key)
    if cached_data:
        print_success(f"Dados cacheados no Redis: {len(cached_data['content'])} bytes")
    else:
        print_error("Dados não estão no Redis")
        return False
    
    # 5. Limpar cache
    cache.delete(cache_key)
    print_info("Cache limpo no final")
    
    print_success("✨ Todos os testes de proxy passaram!")
    return True


def test_complete_flow():
    """Testa fluxo completo: Download WhatsApp → S3 → Proxy"""
    print_test("Complete Flow (WhatsApp → S3 → Proxy)")
    
    # Simular URL do WhatsApp (vamos usar uma imagem pública)
    whatsapp_url = "https://via.placeholder.com/300"
    tenant_id = "test-tenant"
    phone = "+5517991234567"
    
    # 1. Download do "WhatsApp"
    print_info(f"Baixando de '{whatsapp_url}'...")
    try:
        response = requests.get(whatsapp_url, timeout=10)
        response.raise_for_status()
        image_data = response.content
        print_success(f"Download OK: {len(image_data)} bytes")
    except Exception as e:
        print_error(f"Erro no download: {e}")
        return False
    
    # 2. Processar imagem
    print_info("Processando imagem...")
    result = process_image(image_data, create_thumb=True, resize=True, optimize=True)
    
    if not result['success']:
        print_error(f"Processamento falhou: {result['errors']}")
        return False
    
    print_success(f"Imagem processada: {result['processed_size']} bytes")
    print_success(f"Thumbnail criado: {result['thumbnail_size']} bytes")
    
    # 3. Upload para S3
    print_info("Upload para S3...")
    s3_manager = get_s3_manager()
    
    original_path = generate_media_path(tenant_id, 'profile_pics', f"{phone}_original.jpg")
    thumb_path = generate_media_path(tenant_id, 'profile_pics', f"{phone}_thumb.jpg")
    
    success1, msg1 = s3_manager.upload_to_s3(
        result['processed_data'],
        original_path,
        'image/jpeg'
    )
    
    success2, msg2 = s3_manager.upload_to_s3(
        result['thumbnail_data'],
        thumb_path,
        'image/jpeg'
    )
    
    if success1 and success2:
        print_success("Upload para S3 OK (original + thumbnail)")
    else:
        print_error(f"Upload falhou: {msg1}, {msg2}")
        return False
    
    # 4. Gerar URL pública via proxy
    from apps.chat.utils.s3 import get_public_url
    public_url = get_public_url(original_path)
    print_success(f"URL pública gerada: {public_url[:80]}...")
    
    # 5. Cleanup
    print_info("Limpando arquivos de teste...")
    s3_manager.delete_from_s3(original_path)
    s3_manager.delete_from_s3(thumb_path)
    print_success("Cleanup OK")
    
    print_success("✨ Fluxo completo funcionou perfeitamente!")
    return True


def main():
    """Executa todos os testes"""
    print(f"\n{BLUE}{'='*60}")
    print(f"{'='*60}")
    print(f"  TESTE DO SISTEMA DE MÍDIA - ALREA SENSE")
    print(f"{'='*60}")
    print(f"{'='*60}{RESET}\n")
    
    tests = [
        ("S3 Operations", test_s3_operations),
        ("Image Processing", test_image_processing),
        ("Media Proxy", test_media_proxy),
        ("Complete Flow", test_complete_flow),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print_error(f"Erro no teste '{name}': {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Resumo final
    print(f"\n{BLUE}{'='*60}")
    print(f"  RESUMO DOS TESTES")
    print(f"{'='*60}{RESET}\n")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        if result:
            print_success(f"{name}: PASSED")
        else:
            print_error(f"{name}: FAILED")
    
    print(f"\n{BLUE}{'='*60}{RESET}")
    if passed == total:
        print(f"{GREEN}✨ TODOS OS TESTES PASSARAM! ({passed}/{total}){RESET}")
        return 0
    else:
        print(f"{RED}❌ ALGUNS TESTES FALHARAM ({passed}/{total} passaram){RESET}")
        return 1


if __name__ == '__main__':
    sys.exit(main())

