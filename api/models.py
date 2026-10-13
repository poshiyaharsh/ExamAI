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


from admins.models import AdminInstitution


class Exam(models.Model):
	class Status(models.TextChoices):
		GENERATING = 'generating', 'Generating'
		DRAFT = 'draft', 'Draft'
		FAILED = 'failed', 'Failed'
		PUBLISHED = 'published', 'Published'
		CLOSED = 'closed', 'Closed'

	institution = models.ForeignKey(
		AdminInstitution,
		on_delete=models.CASCADE,
		related_name='exams',
		db_index=True,
	)
	title = models.CharField(max_length=255)
	created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_exams')
	department = models.CharField(max_length=120, blank=True, default='', db_index=True)
	duration_minutes = models.PositiveIntegerField()
	total_marks = models.PositiveIntegerField()
	topics = models.JSONField(default=list)
	difficulty_distribution = models.JSONField(default=dict)
	question_types = models.JSONField(default=list)
	ai_model_used = models.CharField(max_length=100)
	source_syllabus_text = models.TextField(blank=True, default='')
	status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
	error_message = models.TextField(blank=True, default='')
	seed = models.PositiveIntegerField(null=True, blank=True)
	request_hash = models.CharField(max_length=64, blank=True, default='', db_index=True)
	validation_report = models.JSONField(default=dict, blank=True)
	is_immutable = models.BooleanField(default=False)
	starts_at = models.DateTimeField(null=True, blank=True)
	ends_at = models.DateTimeField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def clean(self):
		from django.core.exceptions import ValidationError
		if self.starts_at and self.ends_at and self.starts_at > self.ends_at:
			raise ValidationError({'ends_at': 'Exam end date cannot precede start date.'})
		if self.institution_id and self.created_by_id:
			fac_profile = getattr(self.created_by, 'faculty_profile', None)
			if fac_profile and fac_profile.institution_id and fac_profile.institution_id != self.institution_id:
				raise ValidationError({'institution': 'Exam institution must match creating faculty institution.'})

	def save(self, *args, **kwargs):
		super().save(*args, **kwargs)
		if self.institution_id:
			try:
				from api.tenant import bump_tenant_cache_version
				bump_tenant_cache_version(self.institution_id)
			except Exception:
				pass

	def delete(self, *args, **kwargs):
		inst_id = self.institution_id
		res = super().delete(*args, **kwargs)
		if inst_id:
			try:
				from api.tenant import bump_tenant_cache_version
				bump_tenant_cache_version(inst_id)
			except Exception:
				pass
		return res

	class Meta:
		ordering = ['-created_at']
		indexes = [
			models.Index(fields=['institution', 'department', 'status']),
			models.Index(fields=['institution', 'created_by']),
			models.Index(fields=['institution', 'request_hash']),
		]


class Subject(models.Model):
	institution = models.ForeignKey(
		AdminInstitution,
		on_delete=models.CASCADE,
		related_name='subjects',
		db_index=True,
	)
	department = models.CharField(max_length=120, db_index=True)
	name = models.CharField(max_length=200)
	code = models.CharField(max_length=50, blank=True, default='')
	created_by = models.ForeignKey(
		User,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='created_subjects',
	)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['name']
		constraints = [
			models.UniqueConstraint(
				fields=['institution', 'department', 'name'],
				name='unique_subject_per_inst_dept_name',
			),
		]
		indexes = [
			models.Index(fields=['institution', 'department']),
		]

	def __str__(self):
		return f"{self.name} ({self.department})"


class Topic(models.Model):
	institution = models.ForeignKey(
		AdminInstitution,
		on_delete=models.CASCADE,
		related_name='topics',
		db_index=True,
	)
	subject = models.ForeignKey(
		Subject,
		on_delete=models.CASCADE,
		related_name='topics',
	)
	name = models.CharField(max_length=200)
	created_by = models.ForeignKey(
		User,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='created_topics',
	)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['name']
		constraints = [
			models.UniqueConstraint(
				fields=['subject', 'name'],
				name='unique_topic_per_subject_name',
			),
		]
		indexes = [
			models.Index(fields=['institution', 'subject']),
		]

	def __str__(self):
		return f"{self.subject.name} - {self.name}"


class Question(models.Model):
	class QuestionType(models.TextChoices):
		MCQ_SINGLE = 'MCQ_SINGLE', 'Multiple Choice (Single)'
		MCQ_MULTIPLE = 'MCQ_MULTIPLE', 'Multiple Choice (Multiple)'
		TRUE_FALSE = 'TRUE_FALSE', 'True / False'
		SHORT_ANSWER = 'SHORT_ANSWER', 'Short Answer'
		LONG_ANSWER = 'LONG_ANSWER', 'Long Answer'
		# Backward-compatibility legacy values
		MCQ = 'mcq', 'Multiple Choice'
		TRUEFALSE = 'truefalse', 'True or False'
		FILLBLANK = 'fillblank', 'Fill in the Blank'
		SUBJECTIVE = 'subjective', 'Subjective'

	class Difficulty(models.TextChoices):
		EASY = 'EASY', 'Easy'
		MEDIUM = 'MEDIUM', 'Medium'
		HARD = 'HARD', 'Hard'
		# Backward-compatibility legacy values
		LEGACY_EASY = 'easy', 'Easy'
		LEGACY_MEDIUM = 'medium', 'Medium'
		LEGACY_HARD = 'hard', 'Hard'

	class Status(models.TextChoices):
		DRAFT = 'DRAFT', 'Draft'
		ACTIVE = 'ACTIVE', 'Active'
		ARCHIVED = 'ARCHIVED', 'Archived'

	institution = models.ForeignKey(
		AdminInstitution,
		on_delete=models.CASCADE,
		related_name='questions',
		db_index=True,
	)
	department = models.CharField(max_length=120, db_index=True, blank=True, default='')
	subject = models.ForeignKey(
		Subject,
		on_delete=models.CASCADE,
		related_name='questions',
		null=True,
		blank=True,
	)
	topic = models.ForeignKey(
		Topic,
		on_delete=models.SET_NULL,
		related_name='questions',
		null=True,
		blank=True,
	)
	topic_text = models.CharField(max_length=255, blank=True, default='')
	exam = models.ForeignKey(
		Exam,
		on_delete=models.CASCADE,
		related_name='questions',
		null=True,
		blank=True,
	)
	order = models.PositiveIntegerField(default=1)
	question_type = models.CharField(max_length=30, choices=QuestionType.choices, default=QuestionType.MCQ_SINGLE)
	difficulty = models.CharField(max_length=20, choices=Difficulty.choices, default=Difficulty.MEDIUM)
	text = models.TextField()
	explanation = models.TextField(blank=True, default='')
	marks = models.DecimalField(max_digits=6, decimal_places=2, default=1.0)
	negative_marks = models.DecimalField(max_digits=6, decimal_places=2, default=0.0)
	status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True)
	is_deleted = models.BooleanField(default=False, db_index=True)
	deleted_at = models.DateTimeField(null=True, blank=True)
	text_hash = models.CharField(max_length=64, db_index=True, blank=True, default='')
	version = models.PositiveIntegerField(default=1)
	times_used = models.PositiveIntegerField(default=0)
	last_used_at = models.DateTimeField(null=True, blank=True)
	tags = models.JSONField(default=list, blank=True)
	created_by = models.ForeignKey(
		User,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='created_questions',
	)
	created_at = models.DateTimeField(default=timezone.now, db_index=True)
	updated_at = models.DateTimeField(auto_now=True)

	# Legacy fields preserved so exam attempts and serializers continue to function
	options = models.JSONField(null=True, blank=True)
	correct_answer = models.JSONField(null=True, blank=True)
	model_answer = models.TextField(blank=True, default='')

	class Meta:
		ordering = ['-created_at', 'order']
		constraints = [
			models.UniqueConstraint(
				fields=['institution', 'subject', 'text_hash'],
				condition=models.Q(is_deleted=False, subject__isnull=False) & ~models.Q(text_hash=''),
				name='unique_active_question_per_inst_subject_hash',
			),
			models.CheckConstraint(
				condition=models.Q(marks__gt=0),
				name='question_marks_gt_zero',
			),
			models.CheckConstraint(
				condition=models.Q(negative_marks__gte=0) & models.Q(negative_marks__lte=models.F('marks')),
				name='question_negative_marks_valid',
			),
		]
		indexes = [
			models.Index(fields=['institution', 'subject', 'topic', 'difficulty', 'status']),
			models.Index(fields=['institution', 'department']),
			models.Index(fields=['institution', 'question_type']),
			models.Index(fields=['institution', 'created_at']),
			models.Index(fields=['institution', 'exam']),
			models.Index(fields=['institution', 'department', 'status', 'is_deleted']),
			models.Index(fields=['exam', 'order']),
		]

	def __str__(self):
		return f"Q{self.id} ({self.get_question_type_display()}): {self.text[:40]}"


class Option(models.Model):
	question = models.ForeignKey(
		Question,
		on_delete=models.CASCADE,
		related_name='option_items',
	)
	text = models.TextField()
	is_correct = models.BooleanField(default=False)
	order = models.PositiveIntegerField(default=1)

	class Meta:
		ordering = ['order', 'id']

	def __str__(self):
		return f"Q{self.question_id} Opt: {self.text[:30]} ({'Correct' if self.is_correct else 'Wrong'})"


class QuestionImportLog(models.Model):
	institution = models.ForeignKey(
		AdminInstitution,
		on_delete=models.CASCADE,
		related_name='question_import_logs',
		db_index=True,
	)
	created_by = models.ForeignKey(
		User,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
	)
	filename = models.CharField(max_length=255)
	file_format = models.CharField(max_length=10)
	total_rows = models.PositiveIntegerField(default=0)
	imported_count = models.PositiveIntegerField(default=0)
	duplicate_count = models.PositiveIntegerField(default=0)
	failed_count = models.PositiveIntegerField(default=0)
	error_details = models.JSONField(default=list, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']


class QuestionAuditLog(models.Model):
	institution = models.ForeignKey(
		AdminInstitution,
		on_delete=models.CASCADE,
		related_name='question_audit_logs',
		db_index=True,
	)
	question = models.ForeignKey(
		Question,
		on_delete=models.CASCADE,
		related_name='audit_logs',
	)
	user = models.ForeignKey(
		User,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
	)
	action = models.CharField(max_length=30)
	changes = models.JSONField(default=dict, blank=True)
	timestamp = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-timestamp']



class StudentAttempt(models.Model):
	class Status(models.TextChoices):
		IN_PROGRESS = 'in_progress', 'In Progress'
		SUBMITTED = 'submitted', 'Submitted'
		AUTO_SUBMITTED = 'auto_submitted', 'Auto Submitted'
		EVALUATED = 'evaluated', 'Evaluated'

	exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='attempts')
	institution = models.ForeignKey(
		AdminInstitution,
		on_delete=models.CASCADE,
		related_name='attempts',
		db_index=True,
	)
	student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='exam_attempts')
	started_at = models.DateTimeField(auto_now_add=True)
	submitted_at = models.DateTimeField(null=True, blank=True)
	status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_PROGRESS)
	total_score = models.FloatField(default=0)

	class Meta:
		unique_together = ('exam', 'student')
		indexes = [
			models.Index(fields=['institution', 'student']),
			models.Index(fields=['institution', 'exam']),
		]

	def save(self, *args, **kwargs):
		super().save(*args, **kwargs)
		if self.institution_id:
			try:
				from api.tenant import bump_tenant_cache_version
				bump_tenant_cache_version(self.institution_id)
			except Exception:
				pass

	def delete(self, *args, **kwargs):
		inst_id = self.institution_id
		res = super().delete(*args, **kwargs)
		if inst_id:
			try:
				from api.tenant import bump_tenant_cache_version
				bump_tenant_cache_version(inst_id)
			except Exception:
				pass
		return res


class StudentAnswer(models.Model):
	attempt = models.ForeignKey(StudentAttempt, on_delete=models.CASCADE, related_name='answers')
	institution = models.ForeignKey(
		AdminInstitution,
		on_delete=models.CASCADE,
		related_name='student_answers',
		db_index=True,
	)
	question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='student_answers')
	answer_text = models.TextField(blank=True, default='')
	is_correct = models.BooleanField(null=True, blank=True)
	score_awarded = models.FloatField(null=True, blank=True)
	ai_feedback = models.TextField(blank=True, default='')

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=['attempt', 'question'], name='unique_attempt_question'),
		]
		indexes = [
			models.Index(fields=['institution', 'attempt']),
		]
