# Generated manually to fix existing campaign intervals

from django.db import migrations


def fix_existing_campaign_intervals(apps, schema_editor):
    """
    Corrige intervalos de campanhas existentes que estão fora dos limites (20s-420s)
    """
    Campaign = apps.get_model('campaigns', 'Campaign')
    
    # Campanhas com interval_min < 20
    campaigns_min = Campaign.objects.filter(interval_min__lt=20)
    print(f"🔧 Ajustando {campaigns_min.count()} campanhas com interval_min < 20s")
    campaigns_min.update(interval_min=20)
    
    # Campanhas com interval_min > 420
    campaigns_min_max = Campaign.objects.filter(interval_min__gt=420)
    print(f"🔧 Ajustando {campaigns_min_max.count()} campanhas com interval_min > 420s")
    campaigns_min_max.update(interval_min=420)
    
    # Campanhas com interval_max < 20
    campaigns_max = Campaign.objects.filter(interval_max__lt=20)
    print(f"🔧 Ajustando {campaigns_max.count()} campanhas com interval_max < 20s")
    campaigns_max.update(interval_max=20)
    
    # Campanhas com interval_max > 420
    campaigns_max_max = Campaign.objects.filter(interval_max__gt=420)
    print(f"🔧 Ajustando {campaigns_max_max.count()} campanhas com interval_max > 420s")
    campaigns_max_max.update(interval_max=420)
    
    # Campanhas onde interval_min > interval_max
    from django.db.models import F
    campaigns_invalid = Campaign.objects.filter(interval_min__gt=F('interval_max'))
    print(f"🔧 Ajustando {campaigns_invalid.count()} campanhas com interval_min > interval_max")
    for campaign in campaigns_invalid:
        # Se interval_min > interval_max, ajustar interval_max para interval_min
        campaign.interval_max = campaign.interval_min
        campaign.save()
    
    print(f"✅ Migration de intervalos concluída!")


def reverse_fix_intervals(apps, schema_editor):
    """
    Reversão da migration (não faz nada, pois não temos como saber os valores originais)
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('campaigns', '0006_add_last_instance_name'),
    ]

    operations = [
        migrations.RunPython(
            fix_existing_campaign_intervals,
            reverse_fix_intervals,
        ),
    ]
