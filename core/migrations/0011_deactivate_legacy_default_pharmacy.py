from django.db import migrations


def deactivate_legacy_default_pharmacy(apps, schema_editor):
    Pharmacy = apps.get_model('core', 'Pharmacy')
    Pharmacy.objects.filter(name='Remaz Pharm', owner__isnull=True).update(is_active=False)


def reactivate_legacy_default_pharmacy(apps, schema_editor):
    Pharmacy = apps.get_model('core', 'Pharmacy')
    Pharmacy.objects.filter(name='Remaz Pharm', owner__isnull=True).update(is_active=True)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_alter_paymenttransaction_status'),
    ]

    operations = [
        migrations.RunPython(deactivate_legacy_default_pharmacy, reactivate_legacy_default_pharmacy),
    ]
