"""
Migração inicial para o sistema de billing
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Product',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('slug', models.SlugField(help_text='Identificador único do produto', unique=True)),
                ('name', models.CharField(help_text='Nome do produto', max_length=100)),
                ('description', models.TextField(help_text='Descrição detalhada do produto')),
                ('is_active', models.BooleanField(default=True, help_text='Produto ativo na plataforma')),
                ('requires_ui_access', models.BooleanField(default=True, help_text='Produto requer acesso à UI (ex: API Only = False)')),
                ('addon_price', models.DecimalField(blank=True, decimal_places=2, help_text='Preço como add-on (R$/mês)', max_digits=10, null=True, validators=[django.core.validators.MinValueValidator(0)])),
                ('icon', models.CharField(default='📦', help_text='Emoji/ícone do produto', max_length=50)),
                ('color', models.CharField(default='#3B82F6', help_text='Cor hex do produto', max_length=7)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Produto',
                'verbose_name_plural': 'Produtos',
                'db_table': 'billing_product',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Plan',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('slug', models.SlugField(help_text='Identificador único do plano', unique=True)),
                ('name', models.CharField(help_text='Nome do plano', max_length=100)),
                ('description', models.TextField(help_text='Descrição do plano')),
                ('price', models.DecimalField(decimal_places=2, help_text='Preço mensal (R$)', max_digits=10, validators=[django.core.validators.MinValueValidator(0)])),
                ('is_active', models.BooleanField(default=True, help_text='Plano ativo para venda')),
                ('is_enterprise', models.BooleanField(default=False, help_text='Plano enterprise (sem limites)')),
                ('color', models.CharField(default='#3B82F6', help_text='Cor hex do plano', max_length=7)),
                ('sort_order', models.PositiveIntegerField(default=0, help_text='Ordem de exibição')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Plano',
                'verbose_name_plural': 'Planos',
                'db_table': 'billing_plan',
                'ordering': ['sort_order', 'price'],
            },
        ),
        migrations.CreateModel(
            name='PlanProduct',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_included', models.BooleanField(default=True, help_text='Produto incluído no plano')),
                ('limit_value', models.PositiveIntegerField(blank=True, help_text='Limite do produto (ex: 5000 análises/mês)', null=True)),
                ('limit_unit', models.CharField(blank=True, help_text='Unidade do limite (ex: \'análises/mês\', \'campanhas/mês\')', max_length=50, null=True)),
                ('is_addon_available', models.BooleanField(default=True, help_text='Permite adicionar este produto como add-on')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('plan', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='plan_products', to='billing.plan')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='plan_products', to='billing.product')),
            ],
            options={
                'verbose_name': 'Produto do Plano',
                'verbose_name_plural': 'Produtos dos Planos',
                'db_table': 'billing_plan_product',
                'ordering': ['plan__sort_order', 'product__name'],
            },
        ),
        migrations.CreateModel(
            name='TenantProduct',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('is_addon', models.BooleanField(default=False, help_text='Produto contratado como add-on')),
                ('addon_price', models.DecimalField(blank=True, decimal_places=2, help_text='Preço pago como add-on (R$/mês)', max_digits=10, null=True)),
                ('api_key', models.CharField(blank=True, help_text='API Key específica do produto (se aplicável)', max_length=255, null=True)),
                ('is_active', models.BooleanField(default=True, help_text='Produto ativo para o tenant')),
                ('activated_at', models.DateTimeField(default=django.utils.timezone.now, help_text='Data de ativação')),
                ('deactivated_at', models.DateTimeField(blank=True, help_text='Data de desativação', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tenant_products', to='billing.product')),
            ],
            options={
                'verbose_name': 'Produto do Tenant',
                'verbose_name_plural': 'Produtos dos Tenants',
                'db_table': 'billing_tenant_product',
                'ordering': ['-is_addon', 'product__name'],
            },
        ),
        migrations.CreateModel(
            name='BillingHistory',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('action', models.CharField(choices=[('plan_change', 'Mudança de Plano'), ('addon_add', 'Add-on Adicionado'), ('addon_remove', 'Add-on Removido'), ('price_change', 'Mudança de Preço'), ('product_activate', 'Produto Ativado'), ('product_deactivate', 'Produto Desativado')], max_length=20)),
                ('description', models.TextField(help_text='Descrição da ação')),
                ('old_value', models.JSONField(blank=True, help_text='Valor anterior', null=True)),
                ('new_value', models.JSONField(blank=True, help_text='Novo valor', null=True)),
                ('old_monthly_total', models.DecimalField(blank=True, decimal_places=2, help_text='Total mensal anterior', max_digits=10, null=True)),
                ('new_monthly_total', models.DecimalField(blank=True, decimal_places=2, help_text='Novo total mensal', max_digits=10, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, help_text='Usuário que realizou a ação', null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Histórico de Billing',
                'verbose_name_plural': 'Histórico de Billing',
                'db_table': 'billing_history',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='planproduct',
            constraint=models.UniqueConstraint(fields=('plan', 'product'), name='unique_plan_product'),
        ),
        migrations.AddConstraint(
            model_name='tenantproduct',
            constraint=models.UniqueConstraint(fields=('tenant', 'product'), name='unique_tenant_product'),
        ),
    ]