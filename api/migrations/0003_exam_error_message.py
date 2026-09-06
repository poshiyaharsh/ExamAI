from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0002_exam_question_studentattempt_studentanswer'),
    ]

    operations = [
        migrations.AddField(
            model_name='exam',
            name='error_message',
            field=models.TextField(blank=True, default=''),
        ),
    ]