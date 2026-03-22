from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('admins', '0002_admininstitution'),
    ]

    operations = [
        migrations.CreateModel(
            name='AdminDepartment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('department_name', models.CharField(max_length=120)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'institution',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='departments',
                        to='admins.admininstitution',
                    ),
                ),
            ],
            options={
                'ordering': ['department_name'],
                'constraints': [
                    models.UniqueConstraint(
                        fields=('institution', 'department_name'),
                        name='unique_department_per_institution',
                    )
                ],
            },
        ),
    ]
