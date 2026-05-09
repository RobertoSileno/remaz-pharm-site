import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def seed_default_pharmacy_inventory(apps, schema_editor):
    Pharmacy = apps.get_model('core', 'Pharmacy')
    Medicine = apps.get_model('core', 'Medicine')
    PharmacyInventory = apps.get_model('core', 'PharmacyInventory')
    CartItem = apps.get_model('core', 'CartItem')

    pharmacy, created = Pharmacy.objects.get_or_create(
        name='Remaz Pharm',
        defaults={'is_active': True}
    )

    for medicine in Medicine.objects.all():
        inventory, created = PharmacyInventory.objects.get_or_create(
            pharmacy=pharmacy,
            medicine=medicine,
            defaults={
                'price': medicine.price,
                'stock': 10,
                'is_available': True,
            }
        )
        CartItem.objects.filter(medicine=medicine, inventory__isnull=True).update(inventory=inventory)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_order_orderitem_prescription_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Pharmacy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('cnpj', models.CharField(blank=True, max_length=18, null=True, unique=True)),
                ('phone', models.CharField(blank=True, max_length=20, null=True)),
                ('state', models.CharField(blank=True, max_length=2, null=True)),
                ('city', models.CharField(blank=True, max_length=100, null=True)),
                ('district', models.CharField(blank=True, max_length=100, null=True)),
                ('street', models.CharField(blank=True, max_length=150, null=True)),
                ('number', models.CharField(blank=True, max_length=20, null=True)),
                ('complement', models.CharField(blank=True, max_length=150, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('owner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pharmacies', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Farmacia',
                'verbose_name_plural': 'Farmacias',
            },
        ),
        migrations.CreateModel(
            name='PharmacyInventory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('stock', models.PositiveIntegerField(default=0)),
                ('is_available', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('medicine', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pharmacy_inventory', to='core.medicine')),
                ('pharmacy', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='inventory_items', to='core.pharmacy')),
            ],
            options={
                'verbose_name': 'Estoque da farmacia',
                'verbose_name_plural': 'Estoques das farmacias',
                'unique_together': {('pharmacy', 'medicine')},
            },
        ),
        migrations.AddField(
            model_name='cartitem',
            name='inventory',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='cart_items', to='core.pharmacyinventory'),
        ),
        migrations.AddField(
            model_name='order',
            name='pharmacy',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='orders', to='core.pharmacy'),
        ),
        migrations.AddField(
            model_name='order',
            name='delivery_method',
            field=models.CharField(choices=[('delivery', 'Receber em casa'), ('pickup', 'Retirar na farmacia')], default='delivery', max_length=20),
        ),
        migrations.AddField(
            model_name='order',
            name='prescription_file',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='pharmacy_notes',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.RunPython(seed_default_pharmacy_inventory, noop_reverse),
    ]
