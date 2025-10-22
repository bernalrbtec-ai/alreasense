#!/usr/bin/env python
"""
Script para verificar e criar bucket no MinIO (Railway).
"""
import os
import sys
import django

# Adicionar o backend ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from django.conf import settings
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

def check_and_create_bucket():
    """Verifica se bucket existe e cria se necessário."""
    
    print("\n" + "="*60)
    print("🪣  VERIFICAÇÃO E CRIAÇÃO DE BUCKET S3/MinIO")
    print("="*60)
    
    # Configurações
    bucket_name = settings.S3_BUCKET
    endpoint_url = settings.S3_ENDPOINT_URL
    access_key = settings.S3_ACCESS_KEY
    secret_key = settings.S3_SECRET_KEY
    region = settings.S3_REGION
    
    print(f"\n📋 Configurações:")
    print(f"   Bucket: {bucket_name}")
    print(f"   Endpoint: {endpoint_url}")
    print(f"   Region: {region}")
    print(f"   Access Key: {access_key[:10]}...")
    
    # Criar cliente S3
    try:
        s3_client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(
                signature_version='s3v4',
                s3={'addressing_style': 'path'}
            )
        )
        print("\n✅ Cliente S3 criado com sucesso!")
        
    except Exception as e:
        print(f"\n❌ Erro ao criar cliente S3: {e}")
        return False
    
    # Verificar se bucket existe
    print(f"\n🔍 Verificando se bucket '{bucket_name}' existe...")
    
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        print(f"✅ Bucket '{bucket_name}' já existe!")
        
        # Listar alguns objetos para confirmar acesso
        print(f"\n📂 Listando objetos no bucket...")
        response = s3_client.list_objects_v2(Bucket=bucket_name, MaxKeys=5)
        
        if 'Contents' in response:
            print(f"✅ Bucket tem {len(response.get('Contents', []))} objetos (amostra)")
            for obj in response.get('Contents', [])[:5]:
                print(f"   - {obj['Key']} ({obj['Size']} bytes)")
        else:
            print(f"ℹ️  Bucket está vazio")
        
        return True
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        
        if error_code == '404':
            print(f"⚠️  Bucket '{bucket_name}' NÃO existe!")
            
            # Tentar criar bucket
            print(f"\n🔨 Tentando criar bucket '{bucket_name}'...")
            
            try:
                s3_client.create_bucket(Bucket=bucket_name)
                print(f"✅ Bucket '{bucket_name}' criado com sucesso!")
                
                # Configurar CORS para permitir uploads do frontend
                cors_configuration = {
                    'CORSRules': [
                        {
                            'AllowedHeaders': ['*'],
                            'AllowedMethods': ['GET', 'PUT', 'POST', 'DELETE'],
                            'AllowedOrigins': ['*'],
                            'ExposeHeaders': ['ETag'],
                            'MaxAgeSeconds': 3600
                        }
                    ]
                }
                
                try:
                    s3_client.put_bucket_cors(
                        Bucket=bucket_name,
                        CORSConfiguration=cors_configuration
                    )
                    print(f"✅ CORS configurado no bucket!")
                except Exception as cors_error:
                    print(f"⚠️  Erro ao configurar CORS (não crítico): {cors_error}")
                
                # Tornar bucket público para leitura (opcional)
                try:
                    bucket_policy = {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Sid": "PublicReadGetObject",
                                "Effect": "Allow",
                                "Principal": "*",
                                "Action": "s3:GetObject",
                                "Resource": f"arn:aws:s3:::{bucket_name}/*"
                            }
                        ]
                    }
                    import json
                    s3_client.put_bucket_policy(
                        Bucket=bucket_name,
                        Policy=json.dumps(bucket_policy)
                    )
                    print(f"✅ Política de bucket configurada (leitura pública)!")
                except Exception as policy_error:
                    print(f"⚠️  Erro ao configurar política (não crítico): {policy_error}")
                
                return True
                
            except ClientError as create_error:
                print(f"❌ Erro ao criar bucket: {create_error}")
                return False
                
        elif error_code == '403':
            print(f"❌ Acesso negado ao bucket '{bucket_name}'!")
            print(f"   Verifique as credenciais S3_ACCESS_KEY e S3_SECRET_KEY")
            return False
        else:
            print(f"❌ Erro desconhecido: {error_code} - {e}")
            return False
    
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        return False


def test_upload():
    """Testa upload de arquivo."""
    
    print("\n" + "="*60)
    print("🧪  TESTE DE UPLOAD")
    print("="*60)
    
    bucket_name = settings.S3_BUCKET
    
    # Criar cliente S3
    s3_client = boto3.client(
        's3',
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
        config=Config(
            signature_version='s3v4',
            s3={'addressing_style': 'path'}
        )
    )
    
    # Testar upload de arquivo de teste
    test_key = "test/test-file.txt"
    test_content = b"Hello from Alrea Sense! This is a test file."
    
    print(f"\n📤 Fazendo upload de arquivo de teste...")
    print(f"   Key: {test_key}")
    
    try:
        s3_client.put_object(
            Bucket=bucket_name,
            Key=test_key,
            Body=test_content,
            ContentType='text/plain'
        )
        print(f"✅ Upload realizado com sucesso!")
        
        # Gerar presigned URL para download
        print(f"\n🔗 Gerando presigned URL para download...")
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': test_key},
            ExpiresIn=300
        )
        print(f"✅ URL gerada: {url[:80]}...")
        
        # Deletar arquivo de teste
        print(f"\n🗑️  Removendo arquivo de teste...")
        s3_client.delete_object(Bucket=bucket_name, Key=test_key)
        print(f"✅ Arquivo removido!")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste de upload: {e}")
        return False


if __name__ == '__main__':
    print("\n🚀 Iniciando verificação do S3/MinIO...\n")
    
    # Verificar e criar bucket
    bucket_ok = check_and_create_bucket()
    
    if bucket_ok:
        # Testar upload
        upload_ok = test_upload()
        
        if upload_ok:
            print("\n" + "="*60)
            print("✅ TUDO FUNCIONANDO!")
            print("="*60)
            print("\n✨ O bucket está pronto para receber uploads!")
            print("\n")
        else:
            print("\n❌ Falha no teste de upload")
            sys.exit(1)
    else:
        print("\n❌ Falha na verificação/criação do bucket")
        sys.exit(1)


