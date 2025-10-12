"""
Remove o produto 'contacts' e suas associações
Contacts é uma feature, não um produto
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alrea_sense.settings')
django.setup()

from apps.billing.models import Product, PlanProduct

# Remover produto contacts
product = Product.objects.filter(slug='contacts').first()
if product:
    # Remover associações com planos
    PlanProduct.objects.filter(product=product).delete()
    
    # Remover produto
    product.delete()
    print("✅ Produto 'contacts' removido com sucesso")
else:
    print("ℹ️  Produto 'contacts' não encontrado")


