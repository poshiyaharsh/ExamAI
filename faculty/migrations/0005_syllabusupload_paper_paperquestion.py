from django.db import migrations, models
import django.db.models.deletion
import faculty.models


class Migration(migrations.Migration):

    dependencies = [
        ('admins', '0003_admindepartment'),
        ('faculty', '0004_facultyprofile_designation'),
    ]

    operations = [
        migrations.CreateModel(
            name='SyllabusUpload',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('original_file', models.FileField(upload_to=faculty.models.faculty_syllabus_upload_path)),
                ('original_filename', models.CharField(max_length=255)),
                ('content_type', models.CharField(blank=True, default='', max_length=120)),
                ('extracted_text', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('faculty', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='syllabus_uploads', to='faculty.facultyprofile')),
                ('institution', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='syllabus_uploads', to='admins.admininstitution')),
            ],
        ),
        migrations.CreateModel(
            name='Paper',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('syllabus_file', models.FileField(upload_to=faculty.models.faculty_syllabus_upload_path)),
                ('syllabus_filename', models.CharField(max_length=255)),
                ('extracted_syllabus_text', models.TextField()),
                ('ai_model', models.CharField(max_length=50)),
                ('topics', models.JSONField(default=list)),
                ('question_types', models.JSONField(default=list)),
                ('difficulty_distribution', models.JSONField(default=dict)),
                ('duration', models.PositiveIntegerField()),
                ('total_marks', models.PositiveIntegerField()),
                ('generated_questions', models.JSONField(default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('faculty', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='papers', to='faculty.facultyprofile')),
                ('institution', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='papers', to='admins.admininstitution')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='PaperQuestion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('question_number', models.PositiveIntegerField()),
                ('question_type', models.CharField(max_length=40)),
                ('difficulty', models.CharField(max_length=20)),
                ('marks', models.PositiveIntegerField()),
                ('question', models.TextField()),
                ('options', models.JSONField(blank=True, default=list)),
                ('answer', models.TextField(blank=True, default='')),
                ('paper', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='questions', to='faculty.paper')),
            ],
            options={
                'ordering': ['question_number'],
                'unique_together': {('paper', 'question_number')},
            },
        ),
    ]
