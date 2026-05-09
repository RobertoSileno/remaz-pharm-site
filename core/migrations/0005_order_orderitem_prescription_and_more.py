# This migration mirrors the order tables already applied in the current database.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_alter_medicine_image'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('pending', 'Aguardando confirmacao'), ('waiting_prescription', 'Aguardando analise da receita'), ('approved', 'Aprovado'), ('rejected', 'Recusado'), ('completed', 'Concluido'), ('cancelled', 'Cancelado')], default='pending', max_length=30)),
                ('payment_method', models.CharField(choices=[('pix', 'Pix'), ('credit_card', 'Cartao de credito'), ('debit_card', 'Cartao de debito'), ('cash', 'Dinheiro na entrega')], max_length=20)),
                ('total', models.DecimalField(decimal_places=2, max_digits=10)),
                ('requires_prescription', models.BooleanField(default=False)),
                ('customer_name', models.CharField(max_length=200)),
                ('customer_email', models.EmailField(blank=True, max_length=254, null=True)),
                ('customer_phone', models.CharField(max_length=20)),
                ('cep', models.CharField(max_length=12)),
                ('state', models.CharField(max_length=2)),
                ('city', models.CharField(max_length=100)),
                ('neighborhood', models.CharField(max_length=100)),
                ('street', models.CharField(max_length=150)),
                ('number', models.CharField(max_length=20)),
                ('complement', models.CharField(blank=True, max_length=150, null=True)),
                ('notes', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='orders', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Pedido',
                'verbose_name_plural': 'Pedidos',
                'ordering': ('-created_at',),
            },
        ),
        migrations.CreateModel(
            name='OrderItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('medicine_name', models.CharField(max_length=200)),
                ('medicine_price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('quantity', models.PositiveIntegerField()),
                ('tarja', models.CharField(blank=True, max_length=10, null=True)),
                ('medicine', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.medicine')),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='core.order')),
            ],
        ),
    ]
