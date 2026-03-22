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

# Create your models here.
