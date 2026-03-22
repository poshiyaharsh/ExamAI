from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('faculty', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='facultyprofile',
            name='department',
            field=models.CharField(blank=True, default='', max_length=120),
        ),
        migrations.AddField(
            model_name='facultyprofile',
            name='employee_id',
            field=models.CharField(blank=True, max_length=12, null=True, unique=True),
        ),
    ]
