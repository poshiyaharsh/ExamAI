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
	subject = models.CharField(max_length=80, blank=True, default='', db_index=True)
	description = models.TextField(blank=True, default='')
	duration_minutes = models.PositiveIntegerField()
	total_marks = models.PositiveIntegerField(default=0)
	target_total_marks = models.PositiveIntegerField(null=True, blank=True)
	marks_shortfall = models.PositiveIntegerField(default=0)
	topics = models.JSONField(default=list)
	source_documents = models.JSONField(default=list, blank=True)
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
	is_reviewed = models.BooleanField(default=True)
	shuffle_questions = models.BooleanField(default=True)
	shuffle_options = models.BooleanField(default=True)
	random_subset_size = models.PositiveIntegerField(null=True, blank=True)
	max_warnings = models.PositiveIntegerField(default=3)
	allow_retakes = models.BooleanField(default=False)
	show_result_immediately = models.BooleanField(default=True)
	starts_at = models.DateTimeField(null=True, blank=True, db_index=True)
	ends_at = models.DateTimeField(null=True, blank=True, db_index=True)
	display_timezone = models.CharField(max_length=50, default='Asia/Kolkata')
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	@property
	def schedule_phase(self) -> str:
		from api.utils.schedule import get_exam_schedule_phase
		return get_exam_schedule_phase(self)

	def clean(self):
		from django.core.exceptions import ValidationError
		from api.utils.schedule import validate_exam_schedule
		try:
			validate_exam_schedule(
				self.starts_at,
				self.ends_at,
				self.duration_minutes or 60,
				is_publishing=(self.status == Exam.Status.PUBLISHED),
				raise_exception=True,
			)
		except ValidationError as ve:
			raise ve
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
			models.Index(fields=['institution', 'status', 'starts_at', 'ends_at']),
			models.Index(fields=['starts_at']),
			models.Index(fields=['ends_at']),
			models.Index(fields=['institution', 'status'], name='exam_inst_status_idx'),
			models.Index(fields=['institution', 'created_at'], name='exam_inst_created_idx'),
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
		MCQ = 'mcq', 'Multiple Choice'
		TRUE_FALSE = 'true_false', 'True / False'
		FILL_BLANK = 'fill_blank', 'Fill in the Blank'
		SHORT_ANSWER = 'short_answer', 'Short Answer'
		LONG_ANSWER = 'long_answer', 'Long Answer'
		# Backward-compatibility legacy values
		MCQ_SINGLE = 'MCQ_SINGLE', 'Multiple Choice (Single)'
		MCQ_MULTIPLE = 'MCQ_MULTIPLE', 'Multiple Choice (Multiple)'
		LEGACY_TRUE_FALSE = 'TRUE_FALSE', 'True / False (Upper)'
		LEGACY_SHORT_ANSWER = 'SHORT_ANSWER', 'Short Answer (Upper)'
		LEGACY_LONG_ANSWER = 'LONG_ANSWER', 'Long Answer (Upper)'
		TRUEFALSE = 'truefalse', 'True or False'
		FILLBLANK = 'fillblank', 'Fill in the Blank'
		SUBJECTIVE = 'subjective', 'Subjective'

	class Difficulty(models.TextChoices):
		EASY = 'easy', 'Easy'
		MEDIUM = 'medium', 'Medium'
		HARD = 'hard', 'Hard'
		# Backward-compatibility legacy values
		UPPER_EASY = 'EASY', 'Easy (Upper)'
		UPPER_MEDIUM = 'MEDIUM', 'Medium (Upper)'
		UPPER_HARD = 'HARD', 'Hard (Upper)'

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
	question_type = models.CharField(max_length=30, choices=QuestionType.choices, default=QuestionType.MCQ)
	difficulty = models.CharField(max_length=20, choices=Difficulty.choices, default=Difficulty.MEDIUM)
	text = models.TextField()
	explanation = models.TextField(blank=True, default='')
	marks = models.DecimalField(max_digits=6, decimal_places=2, default=1.0)
	negative_marks = models.DecimalField(max_digits=6, decimal_places=2, default=0.0)
	status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True)
	is_deleted = models.BooleanField(default=False, db_index=True)
	deleted_at = models.DateTimeField(null=True, blank=True)
	text_hash = models.CharField(max_length=64, db_index=True, blank=True, default='')
	active_hash = models.CharField(max_length=64, null=True, blank=True, db_index=True)
	version = models.PositiveIntegerField(default=1)
	times_used = models.PositiveIntegerField(default=0)
	last_used_at = models.DateTimeField(null=True, blank=True)
	tags = models.JSONField(default=list, blank=True)
	source = models.CharField(max_length=20, default='ai_generated', blank=True)
	accepted_answers = models.JSONField(default=list, blank=True)
	rubric = models.JSONField(default=list, blank=True)
	word_limit = models.PositiveIntegerField(null=True, blank=True)
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
				fields=['institution', 'subject', 'active_hash'],
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
			models.Index(fields=['institution', 'subject', 'question_type', 'difficulty', 'is_deleted', 'last_used_at'], name='q_bank_reuse_idx'),
		]

	def save(self, *args, **kwargs):
		if self.question_type:
			from api.utils.validate_paper import canonicalize_type
			self.question_type = canonicalize_type(self.question_type)
		if self.difficulty:
			from api.utils.validate_paper import canonicalize_difficulty
			self.difficulty = canonicalize_difficulty(self.difficulty)
		if not self.is_deleted and self.subject_id is not None and self.text_hash:
			self.active_hash = self.text_hash
		else:
			self.active_hash = None
		super().save(*args, **kwargs)

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
	attempt_number = models.PositiveIntegerField(default=1)
	started_at = models.DateTimeField(auto_now_add=True)
	submitted_at = models.DateTimeField(null=True, blank=True)
	expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
	status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_PROGRESS)
	submit_reason = models.CharField(max_length=30, blank=True, default='manual')
	violation_count = models.PositiveIntegerField(default=0)
	needs_finalize = models.BooleanField(default=False, db_index=True)
	question_order = models.JSONField(default=list, blank=True)
	option_orders = models.JSONField(default=dict, blank=True)
	active_session_token = models.CharField(max_length=64, blank=True, default='')
	max_score = models.FloatField(default=0)
	total_score = models.FloatField(default=0)

	class ReviewStatus(models.TextChoices):
		AUTO_EVALUATED = 'auto_evaluated', 'Auto Evaluated (Provisional)'
		IN_REVIEW = 'in_review', 'In Review'
		FINALIZED = 'finalized', 'Finalized'

	review_status = models.CharField(
		max_length=20,
		choices=ReviewStatus.choices,
		default=ReviewStatus.AUTO_EVALUATED,
		db_index=True,
	)
	reviewed_by = models.ForeignKey(
		User,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='reviewed_attempts',
	)
	finalized_at = models.DateTimeField(null=True, blank=True)
	version = models.PositiveIntegerField(default=1)
	auto_total = models.FloatField(default=0.0)
	final_total = models.FloatField(default=0.0)

	class Meta:
		unique_together = ('exam', 'student', 'attempt_number')
		indexes = [
			models.Index(fields=['institution', 'student']),
			models.Index(fields=['institution', 'exam']),
			models.Index(fields=['expires_at']),
			models.Index(fields=['institution', 'student', 'status'], name='att_inst_stud_status_idx'),
			models.Index(fields=['institution', 'status', 'submitted_at'], name='att_inst_stat_sub_idx'),
			models.Index(fields=['exam', 'status'], name='att_exam_status_idx'),
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
	class EvaluationStatus(models.TextChoices):
		EVALUATED_AI = 'evaluated_ai', 'Evaluated (AI)'
		EVALUATED_RULES = 'evaluated_rules', 'Evaluated (Rules)'
		PENDING_REVIEW = 'pending_review', 'Pending Review'
		FAILED = 'failed', 'Failed'
		REVIEWED = 'reviewed', 'Reviewed (Teacher)'

	attempt = models.ForeignKey(StudentAttempt, on_delete=models.CASCADE, related_name='answers')
	institution = models.ForeignKey(
		AdminInstitution,
		on_delete=models.CASCADE,
		related_name='student_answers',
		db_index=True,
	)
	question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='student_answers')
	answer_text = models.TextField(blank=True, default='')
	blank_answers = models.JSONField(default=list, blank=True)
	selected_option_order = models.JSONField(null=True, blank=True)
	is_correct = models.BooleanField(null=True, blank=True)
	score_awarded = models.FloatField(null=True, blank=True)
	ai_feedback = models.TextField(blank=True, default='')
	teacher_feedback = models.TextField(blank=True, default='')
	ai_suggested_score = models.FloatField(null=True, blank=True)
	ai_suggested_feedback = models.TextField(blank=True, default='')
	evaluation_status = models.CharField(
		max_length=20,
		choices=EvaluationStatus.choices,
		default=EvaluationStatus.PENDING_REVIEW,
		db_index=True,
	)
	evaluation_provider = models.CharField(max_length=50, blank=True, default='')
	evaluation_model = models.CharField(max_length=100, blank=True, default='')
	technical_error = models.TextField(blank=True, default='')
	saved_at = models.DateTimeField(auto_now=True)

	# Automatic evaluation baseline (rules or AI)
	auto_marks = models.FloatField(null=True, blank=True)
	auto_is_correct = models.BooleanField(null=True, blank=True)
	auto_feedback = models.TextField(blank=True, default='')
	auto_source = models.CharField(
		max_length=20,
		choices=[('rule', 'Rule'), ('ai', 'AI'), ('empty', 'Empty Check'), ('none', 'None')],
		default='none',
	)
	auto_evaluated_at = models.DateTimeField(null=True, blank=True)
	ai_status = models.CharField(
		max_length=20,
		choices=[
			('not_requested', 'Not Requested'),
			('running', 'Running'),
			('ready', 'Ready'),
			('failed', 'Failed'),
		],
		default='not_requested',
	)
	ai_confidence = models.FloatField(null=True, blank=True)

	# Faculty override fields
	final_marks = models.FloatField(null=True, blank=True)
	final_is_correct = models.CharField(
		max_length=20,
		choices=[('correct', 'Correct'), ('partial', 'Partially Correct'), ('wrong', 'Wrong')],
		blank=True,
		null=True,
		default='',
	)
	final_comment = models.TextField(blank=True, default='')
	overridden = models.BooleanField(default=False, db_index=True)
	overridden_by = models.ForeignKey(
		User,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='overridden_answers',
	)
	overridden_at = models.DateTimeField(null=True, blank=True)

	@property
	def effective_marks(self):
		if self.overridden and self.final_marks is not None:
			return float(self.final_marks)
		if self.auto_marks is not None:
			return float(self.auto_marks)
		return float(self.score_awarded or 0.0)

	@property
	def effective_is_correct(self):
		if self.overridden and self.final_is_correct:
			return self.final_is_correct == 'correct'
		if self.auto_is_correct is not None:
			return self.auto_is_correct
		return self.is_correct

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=['attempt', 'question'], name='unique_attempt_question'),
		]
		indexes = [
			models.Index(fields=['institution', 'attempt']),
			models.Index(fields=['evaluation_status']),
			models.Index(fields=['attempt', 'overridden']),
		]


class EvaluationChangeAuditLog(models.Model):
	institution = models.ForeignKey(
		AdminInstitution,
		on_delete=models.CASCADE,
		related_name='evaluation_audit_logs',
		db_index=True,
	)
	attempt = models.ForeignKey(
		StudentAttempt,
		on_delete=models.CASCADE,
		related_name='evaluation_audit_logs',
		db_index=True,
	)
	question = models.ForeignKey(
		Question,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='evaluation_audit_logs',
	)
	old_marks = models.FloatField(null=True, blank=True)
	new_marks = models.FloatField()
	old_correctness = models.CharField(max_length=20, blank=True, default='')
	new_correctness = models.CharField(max_length=20)
	reason = models.TextField()
	changed_by = models.ForeignKey(
		User,
		on_delete=models.CASCADE,
		related_name='faculty_evaluation_changes',
	)
	created_at = models.DateTimeField(auto_now_add=True, db_index=True)
	ip_address = models.GenericIPAddressField(null=True, blank=True)

	class Meta:
		ordering = ['-created_at']
		indexes = [
			models.Index(fields=['institution', 'attempt']),
			models.Index(fields=['attempt', 'question']),
		]


class AttemptEvent(models.Model):
	class EventType(models.TextChoices):
		FULLSCREEN_EXIT = 'fullscreen_exit', 'Fullscreen Exit'
		TAB_HIDDEN = 'tab_hidden', 'Tab Hidden'
		WINDOW_BLUR = 'window_blur', 'Window Blur'
		RELOAD = 'reload', 'Page Reload'
		CONCURRENT_TAB = 'concurrent_tab', 'Concurrent Tab Detected'
		HEARTBEAT = 'heartbeat', 'Heartbeat'
		CUSTOM = 'custom', 'Custom Violation'

	attempt = models.ForeignKey(StudentAttempt, on_delete=models.CASCADE, related_name='events', db_index=True)
	institution = models.ForeignKey(
		AdminInstitution,
		on_delete=models.CASCADE,
		related_name='attempt_events',
		db_index=True,
	)
	event_type = models.CharField(max_length=40, choices=EventType.choices)
	event_id = models.CharField(max_length=64, blank=True, default='', db_index=True)
	metadata = models.JSONField(default=dict, blank=True)
	timestamp = models.DateTimeField(default=timezone.now, db_index=True)

	class Meta:
		ordering = ['-timestamp']
		indexes = [
			models.Index(fields=['attempt', 'event_type']),
			models.Index(fields=['institution', 'timestamp']),
			models.Index(fields=['attempt', 'event_id']),
		]


class PaperGenerationJob(models.Model):
	class Status(models.TextChoices):
		QUEUED = 'queued', 'Queued'
		RUNNING = 'running', 'Running'
		COMPLETED = 'completed', 'Completed'
		COMPLETED_WITH_WARNINGS = 'completed_with_warnings', 'Completed with Warnings'
		FAILED = 'failed', 'Failed'
		CANCELLED = 'cancelled', 'Cancelled'

	institution = models.ForeignKey(
		AdminInstitution,
		on_delete=models.CASCADE,
		related_name='paper_generation_jobs',
		db_index=True,
	)
	faculty = models.ForeignKey(
		User,
		on_delete=models.CASCADE,
		related_name='paper_generation_jobs',
		db_index=True,
	)
	department = models.CharField(max_length=120, blank=True, default='', db_index=True)
	exam = models.ForeignKey(
		Exam,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='generation_jobs',
	)
	model = models.CharField(max_length=100)
	status = models.CharField(max_length=30, choices=Status.choices, default=Status.QUEUED, db_index=True)
	progress = models.PositiveIntegerField(default=0)
	current_step = models.CharField(max_length=255, default='Queued')
	error_message = models.TextField(blank=True, default='')
	warnings = models.JSONField(default=list, blank=True)
	question_count_requested = models.PositiveIntegerField(default=0)
	question_count_generated = models.PositiveIntegerField(default=0)
	target_marks = models.PositiveIntegerField(default=0)
	actual_marks = models.PositiveIntegerField(default=0)
	marks_shortfall = models.PositiveIntegerField(default=0)
	off_scope_rejected_count = models.PositiveIntegerField(default=0)
	retry_count = models.PositiveIntegerField(default=0)
	source_documents = models.JSONField(default=list, blank=True)
	is_cancelled = models.BooleanField(default=False)
	request_hash = models.CharField(max_length=64, blank=True, default='', db_index=True)
	created_at = models.DateTimeField(auto_now_add=True, db_index=True)
	started_at = models.DateTimeField(null=True, blank=True)
	completed_at = models.DateTimeField(null=True, blank=True)

	class Meta:
		ordering = ['-created_at']
		indexes = [
			models.Index(fields=['institution', 'faculty', 'status']),
			models.Index(fields=['institution', 'department', 'status']),
			models.Index(fields=['faculty', 'request_hash']),
		]


class Notification(models.Model):
	class NotificationType(models.TextChoices):
		INFO = 'info', 'Info'
		SUCCESS = 'success', 'Success'
		WARNING = 'warning', 'Warning'
		ERROR = 'error', 'Error'

	user = models.ForeignKey(
		User,
		on_delete=models.CASCADE,
		related_name='notifications',
		db_index=True,
	)
	institution = models.ForeignKey(
		AdminInstitution,
		on_delete=models.CASCADE,
		related_name='notifications',
		null=True,
		blank=True,
		db_index=True,
	)
	title = models.CharField(max_length=255)
	message = models.TextField()
	type = models.CharField(max_length=30, choices=NotificationType.choices, default=NotificationType.INFO)
	link = models.CharField(max_length=500, blank=True, default='')
	is_read = models.BooleanField(default=False, db_index=True)
	is_popup = models.BooleanField(default=False, db_index=True)
	popup_shown_at = models.DateTimeField(null=True, blank=True)
	popup_dismissed_at = models.DateTimeField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True, db_index=True)

	class Meta:
		ordering = ['-created_at']
		indexes = [
			models.Index(fields=['user', 'is_read', '-created_at']),
			models.Index(fields=['user', 'is_popup', 'popup_dismissed_at']),
		]


class UserNotificationPreference(models.Model):
	"""
	User-level preference for delivery channels (email, in-app popup).
	"""
	user = models.OneToOneField(
		User,
		on_delete=models.CASCADE,
		related_name='notification_preference',
	)
	email_notifications_enabled = models.BooleanField(default=True)
	popup_notifications_enabled = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		verbose_name = 'User Notification Preference'
		verbose_name_plural = 'User Notification Preferences'

	def __str__(self):
		return f'Pref: {self.user.username} (email={self.email_notifications_enabled}, popup={self.popup_notifications_enabled})'


