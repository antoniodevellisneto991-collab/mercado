from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_alter_ajuste_id_alter_entrada_id_alter_fornecedor_id_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='fornecedor',
            options={'ordering': ['nome'], 'verbose_name_plural': 'fornecedores'},
        ),
    ]
