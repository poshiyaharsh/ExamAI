from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('admins', '0002_admininstitution'),
        ('students', '0002_studentprofile_student_id_department'),
    ]

    operations = [
        migrations.AddField(
            model_name='studentprofile',
            name='institution',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='student_profiles',
                to='admins.admininstitution',
            ),
        ),
    ]
