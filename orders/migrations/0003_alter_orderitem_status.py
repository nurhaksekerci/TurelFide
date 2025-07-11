# Generated by Django 5.2.1 on 2025-06-01 12:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0002_orderitem_status_alter_order_status_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='orderitem',
            name='status',
            field=models.CharField(choices=[('waiting', 'Bekliyor'), ('rootstock_planting_sent', 'Anaç Gönderildi'), ('rootstock_planting_confirmed', 'Anaç Onaylandı'), ('rootstock_planting_planted', 'Anaç Ekildi'), ('scion_planting_sent', 'Kalem Gönderildi'), ('scion_planting_confirmed', 'Kalem Onaylandı'), ('scion_planting_planted', 'Kalem Ekildi'), ('grafting_sent', 'Aşıya Gönderildi'), ('grafting_confirmed', 'Aşı Onaylandı'), ('grafting_planted', 'Aşı Ekildi'), ('head_formation_sent', 'Kafa Kesime Gönderildi'), ('head_formation_confirmed', 'Kafa Kesime Onaylandı'), ('head_formation_formed', 'Kafa Kesime Ekildi'), ('cutting_sent', 'Bekleme Odasına Gönderildi'), ('cutting_confirmed', 'Bekleme Odasına Onaylandı'), ('cutting_cut', 'Bekleme Odasında'), ('ready_for_shipment', 'Sevkiyata Hazır')], default='waiting', max_length=30, verbose_name='Durum'),
        ),
    ]
