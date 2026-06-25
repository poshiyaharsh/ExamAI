from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('faculty', '0003_facultyprofile_institution'),
    ]

    operations = [
        migrations.AddField(
            model_name='facultyprofile',
            name='designation',
            field=models.CharField(blank=True, default='', max_length=120),
        ),
    ]