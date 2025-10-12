#!/usr/bin/env python3
import requests
import json

# Test Evolution API
headers = {
    'apikey': '584B4A4A-0815-AC86-DC39-C38FC27E8E17',
    'Content-Type': 'application/json'
}

try:
    response = requests.get('https://evo.rbtec.com.br/instance/fetchInstances', headers=headers, timeout=5)
    print(f'Status: {response.status_code}')
    
    if response.status_code == 200:
        instances = response.json()
        print(f'Instâncias retornadas pela API: {len(instances)}')
        
        print('\nPrimeiras 5 instâncias:')
        for i, inst in enumerate(instances[:5]):
            print(f'- {i+1}. {inst.get("instanceName", "N/A")} (status: {inst.get("instance", {}).get("status", "N/A")})')
    else:
        print(f'Erro na API: {response.text}')
        
except Exception as e:
    print(f'Erro na requisição: {e}')
