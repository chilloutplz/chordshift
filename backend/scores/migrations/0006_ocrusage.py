from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scores', '0005_scorevariant_chord_font_size_song_chord_font_size'),
    ]

    operations = [
        migrations.CreateModel(
            name='OcrUsage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('month', models.CharField(help_text='YYYY-MM', max_length=7, unique=True)),
                ('count', models.PositiveIntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-month'],
            },
        ),
    ]
