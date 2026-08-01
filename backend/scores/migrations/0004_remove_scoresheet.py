from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scores', '0003_song_scorevariant'),
    ]

    operations = [
        migrations.DeleteModel(
            name='ScoreSheet',
        ),
        migrations.AddConstraint(
            model_name='scorevariant',
            constraint=models.UniqueConstraint(
                fields=('song', 'transpose_semitones'),
                name='uniq_song_semitones',
            ),
        ),
    ]
