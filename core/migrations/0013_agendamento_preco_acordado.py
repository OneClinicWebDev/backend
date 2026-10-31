from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0012_alter_servico_options_servico_categoria_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="agendamento",
            name="preco_acordado",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=10,
                null=True,
            ),
        ),
    ]