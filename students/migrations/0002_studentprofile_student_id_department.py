from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='studentprofile',
            name='department',
            field=models.CharField(blank=True, default='', max_length=120),
        ),
        migrations.AddField(
            model_name='studentprofile',
            name='student_id',
            field=models.CharField(blank=True, max_length=13, null=True, unique=True),
        ),
    ]
