#!/usr/bin/env python
"""
Script para listar arquivos no bucket S3/MinIO.
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

def list_s3_files():
    """Lista todos os arquivos no bucket."""
    
    print("\n" + "="*60)
    print("📂 ARQUIVOS NO S3/MinIO")
    print("="*60)
    
    bucket_name = settings.S3_BUCKET
    endpoint_url = settings.S3_ENDPOINT_URL
    
    print(f"\n📋 Configurações:")
    print(f"   Bucket: {bucket_name}")
    print(f"   Endpoint: {endpoint_url}")
    
    # Criar cliente S3
    try:
        s3_client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
            config=Config(
                signature_version='s3v4',
                s3={'addressing_style': 'path'}
            )
        )
        print("\n✅ Cliente S3 criado!")
        
    except Exception as e:
        print(f"\n❌ Erro ao criar cliente S3: {e}")
        return
    
    # Verificar se bucket existe
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        print(f"✅ Bucket '{bucket_name}' existe!")
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '404':
            print(f"❌ Bucket '{bucket_name}' NÃO existe!")
            return
        else:
            print(f"❌ Erro ao verificar bucket: {error_code}")
            return
    
    # Listar arquivos
    print(f"\n📂 Listando arquivos no bucket...")
    
    try:
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket_name)
        
        total_files = 0
        total_size = 0
        
        print("\n" + "-"*60)
        
        for page in pages:
            if 'Contents' not in page:
                continue
                
            for obj in page['Contents']:
                total_files += 1
                total_size += obj['Size']
                
                size_mb = obj['Size'] / 1024 / 1024
                modified = obj['LastModified'].strftime('%Y-%m-%d %H:%M:%S')
                
                print(f"\n📄 Arquivo #{total_files}:")
                print(f"   Key: {obj['Key']}")
                print(f"   Size: {size_mb:.2f} MB ({obj['Size']} bytes)")
                print(f"   Modified: {modified}")
        
        print("\n" + "-"*60)
        print(f"\n📊 RESUMO:")
        print(f"   Total de arquivos: {total_files}")
        print(f"   Tamanho total: {total_size / 1024 / 1024:.2f} MB")
        
        if total_files == 0:
            print("\n⚠️  Bucket está VAZIO!")
        
    except Exception as e:
        print(f"\n❌ Erro ao listar arquivos: {e}")


if __name__ == '__main__':
    list_s3_files()




