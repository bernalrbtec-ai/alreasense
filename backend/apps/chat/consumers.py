"""
⚠️ DEPRECATED: Este arquivo contém ChatConsumer (V1) que foi substituído por ChatConsumerV2.

Este arquivo é mantido apenas para compatibilidade, mas NÃO deve ser usado.
Use ChatConsumerV2 de consumers_v2.py ao invés.

Motivos da depreciação:
- ChatConsumer cria 1 conexão WebSocket por conversa
- ChatConsumerV2 usa 1 conexão WebSocket por usuário com subscribe/unsubscribe
- ChatConsumerV2 é mais escalável e eficiente

Este arquivo pode ser removido em versões futuras após garantir que não há dependências.
"""
# ⚠️ DEPRECATED - Não usar. Use ChatConsumerV2 de consumers_v2.py
