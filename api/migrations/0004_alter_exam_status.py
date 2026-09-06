from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0003_exam_error_message'),
    ]

    operations = [
        migrations.AlterField(
            model_name='exam',
            name='status',
            field=models.CharField(
                choices=[
                    ('generating', 'Generating'),
                    ('draft', 'Draft'),
                    ('failed', 'Failed'),
                    ('published', 'Published'),
                    ('closed', 'Closed'),
                ],
                default='draft',
                max_length=20,
            ),
        ),
    ]
