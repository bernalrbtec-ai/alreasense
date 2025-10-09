#!/bin/bash
# Script para setup completo do banco de dados do zero

echo "🔥 SETUP COMPLETO - BANCO ZERADO"
echo "=================================="

# 1. Deletar migrations antigas
echo ""
echo "1️⃣ Limpando migrations..."
find /app/apps/*/migrations -name "*.py" ! -name "__init__.py" -delete
echo "   ✓ Migrations antigas deletadas"

# 2. Criar migrations do zero
echo ""
echo "2️⃣ Criando migrations..."
python manage.py makemigrations
echo "   ✓ Migrations criadas"

# 3. Aplicar migrations
echo ""
echo "3️⃣ Aplicando migrations..."
python manage.py migrate
echo "   ✓ Banco de dados criado"

# 4. Criar superuser
echo ""
echo "4️⃣ Criando superuser..."
python create_superuser.py
echo "   ✓ Superuser criado"

# 5. Seed produtos
echo ""
echo "5️⃣ Seed de produtos..."
python manage.py seed_products
echo "   ✓ Produtos criados"

# 6. Seed campanhas
echo ""
echo "6️⃣ Seed de campanhas..."
python manage.py seed_campaigns
echo "   ✓ Feriados e contatos criados"

echo ""
echo "=================================="
echo "✅ SETUP COMPLETO!"
echo "=================================="
echo "📋 Acesso:"
echo "   Email: admin@alrea.com"
echo "   Senha: admin123"
echo "   URL: http://localhost:5173"
echo "=================================="

