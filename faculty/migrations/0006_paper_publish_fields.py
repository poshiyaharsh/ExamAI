from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('faculty', '0005_syllabusupload_paper_paperquestion'),
    ]

    operations = [
        migrations.AddField(
            model_name='paper',
            name='is_published',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='paper',
            name='published_at',
            field=models.DateTimeField(auto_now_add=True, blank=True, null=True),
        ),
    ]
