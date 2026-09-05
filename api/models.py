from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone


class PasswordResetOTP(models.Model):
	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_reset_otps')
	otp_hash = models.CharField(max_length=255)
	reset_token_hash = models.CharField(max_length=255, blank=True, default='')
	expires_at = models.DateTimeField()
	reset_token_expires_at = models.DateTimeField(null=True, blank=True)
	is_verified = models.BooleanField(default=False)
	is_used = models.BooleanField(default=False)
	created_at = models.DateTimeField(auto_now_add=True)

	def set_otp(self, otp):
		self.otp_hash = make_password(otp)

	def check_otp(self, otp):
		return check_password(otp, self.otp_hash)

	def set_reset_token(self, token):
		self.reset_token_hash = make_password(token)

	def check_reset_token(self, token):
		if not self.reset_token_hash:
			return False
		return check_password(token, self.reset_token_hash)

	@property
	def is_otp_expired(self):
		return timezone.now() > self.expires_at

	@property
	def is_reset_token_expired(self):
		if not self.reset_token_expires_at:
			return True
		return timezone.now() > self.reset_token_expires_at


class Exam(models.Model):
	class Status(models.TextChoices):
		DRAFT = 'draft', 'Draft'
		PUBLISHED = 'published', 'Published'
		CLOSED = 'closed', 'Closed'

	title = models.CharField(max_length=255)
	created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_exams')
	duration_minutes = models.PositiveIntegerField()
	total_marks = models.PositiveIntegerField()
	topics = models.JSONField(default=list)
	difficulty_distribution = models.JSONField(default=dict)
	question_types = models.JSONField(default=list)
	ai_model_used = models.CharField(max_length=100)
	source_syllabus_text = models.TextField(blank=True, default='')
	status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
	starts_at = models.DateTimeField(null=True, blank=True)
	ends_at = models.DateTimeField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)


class Question(models.Model):
	class QuestionType(models.TextChoices):
		MCQ = 'mcq', 'Multiple Choice'
		TRUEFALSE = 'truefalse', 'True or False'
		FILLBLANK = 'fillblank', 'Fill in the Blank'
		SUBJECTIVE = 'subjective', 'Subjective'

	class Difficulty(models.TextChoices):
		EASY = 'easy', 'Easy'
		MEDIUM = 'medium', 'Medium'
		HARD = 'hard', 'Hard'

	exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='questions')
	order = models.PositiveIntegerField()
	question_type = models.CharField(max_length=20, choices=QuestionType.choices)
	difficulty = models.CharField(max_length=10, choices=Difficulty.choices)
	text = models.TextField()
	options = models.JSONField(null=True, blank=True)
	correct_answer = models.JSONField(null=True, blank=True)
	model_answer = models.TextField(blank=True, default='')
	marks = models.PositiveIntegerField()
	topic = models.CharField(max_length=255, blank=True, default='')


class StudentAttempt(models.Model):
	class Status(models.TextChoices):
		IN_PROGRESS = 'in_progress', 'In Progress'
		SUBMITTED = 'submitted', 'Submitted'
		AUTO_SUBMITTED = 'auto_submitted', 'Auto Submitted'
		EVALUATED = 'evaluated', 'Evaluated'

	exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='attempts')
	student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='exam_attempts')
	started_at = models.DateTimeField(auto_now_add=True)
	submitted_at = models.DateTimeField(null=True, blank=True)
	status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_PROGRESS)
	total_score = models.FloatField(default=0)

	class Meta:
		unique_together = ('exam', 'student')


class StudentAnswer(models.Model):
	attempt = models.ForeignKey(StudentAttempt, on_delete=models.CASCADE, related_name='answers')
	question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='student_answers')
	answer_text = models.TextField(blank=True, default='')
	is_correct = models.BooleanField(null=True, blank=True)
	score_awarded = models.FloatField(null=True, blank=True)
	ai_feedback = models.TextField(blank=True, default='')

# Create your models here.
