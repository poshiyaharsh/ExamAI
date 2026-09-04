from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('faculty', '0006_paper_publish_fields'),
        ('students', '0003_studentprofile_institution'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExamAttempt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('answers', models.JSONField(default=dict)),
                ('score', models.PositiveIntegerField(default=0)),
                ('max_score', models.PositiveIntegerField(default=0)),
                ('status', models.CharField(choices=[('started', 'Started'), ('submitted', 'Submitted')], default='started', max_length=20)),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('submitted_at', models.DateTimeField(blank=True, null=True)),
                ('paper', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attempts', to='faculty.paper')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exam_attempts', to='students.studentprofile')),
            ],
            options={'ordering': ['-started_at']},
        ),
        migrations.AddIndex(
            model_name='examattempt',
            index=models.Index(fields=['student', 'paper', 'status'], name='students_ex_student_6939f7_idx'),
        ),
    ]
