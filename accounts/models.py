from django.db import models
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.utils import timezone
from django.core.mail import send_mail
from django.db import transaction
import secrets


class GuardianManager(BaseUserManager):
	"""Manager for Guardian users."""
	use_in_migrations = True

	def create_user(self, email, password=None, **extra_fields):
		"""Create and save a Guardian with the given email and password."""
		if not email:
			raise ValueError('The Email must be set')
		email = self.normalize_email(email)
		guardian = self.model(email=email, **extra_fields)
		guardian.set_password(password)
		guardian.save(using=self._db)
		return guardian

	def create_superuser(self, email, password=None, **extra_fields):
		extra_fields.setdefault('is_staff', True)
		extra_fields.setdefault('is_superuser', True)
		extra_fields.setdefault('is_active', True)

		if extra_fields.get('is_staff') is not True:
			raise ValueError('Superuser must have is_staff=True.')
		if extra_fields.get('is_superuser') is not True:
			raise ValueError('Superuser must have is_superuser=True.')

		return self.create_user(email, password, **extra_fields)


class ChildManager(BaseUserManager):
	"""Manager for Child objects. 
    s unique child_hash on create."""

	def _generate_unique_hash(self):
		# token_urlsafe produces URL-safe base64 string; length 12 is a reasonable size.
		return secrets.token_urlsafe(12)

	def create_user(self, password=None, **extra_fields):
		"""Create and save a Child with a unique child_hash."""
		# generate a unique hash
		child_hash = self._generate_unique_hash()
		# loop until unique (very unlikely to loop more than once)
		while self.model.objects.filter(child_hash=child_hash).exists():
			child_hash = self._generate_unique_hash()

		child = self.model(child_hash=child_hash, **extra_fields)
		if password:
			child.set_password(password)
		child.save(using=self._db)
		return child


class Guardian(AbstractBaseUser, PermissionsMixin):
	"""A guardian (parent) account.

	Guardians can register themselves and then attach children using the
	child's unique hash via `add_child`.
	"""
	email = models.EmailField(unique=True, max_length=255)
	full_name = models.CharField(max_length=255, blank=True)
	is_staff = models.BooleanField(default=False)
	is_active = models.BooleanField(default=True)
	date_joined = models.DateTimeField(default=timezone.now)

	# Override Permission/Group relations from PermissionsMixin to avoid reverse accessor clashes
	groups = models.ManyToManyField(
		'auth.Group',
		related_name='guardian_set',
		blank=True,
		help_text='The groups this guardian belongs to.'
	)
	user_permissions = models.ManyToManyField(
		'auth.Permission',
		related_name='guardian_user_set',
		blank=True,
		help_text='Specific permissions for this guardian.'
	)

	# relationship: a guardian can have many children and a child can have many guardians
	children = models.ManyToManyField('Child', related_name='guardians', blank=True)

	objects = GuardianManager()

	USERNAME_FIELD = 'email'
	REQUIRED_FIELDS = []

	class Meta:
		verbose_name = 'guardian'
		verbose_name_plural = 'guardians'

	def __str__(self):
		return self.email

	# Auth helper methods
	def get_full_name(self):
		return self.full_name or self.email

	def get_short_name(self):
		return self.full_name.split(' ')[0] if self.full_name else self.email

	def email_user(self, subject, message, from_email=None, **kwargs):
		send_mail(subject, message, from_email, [self.email], **kwargs)

	def add_child(self, child_hash):
		"""Attach a child to this guardian using the child's unique hash.

		Returns the Child instance when successful. Raises Child.DoesNotExist
		if no child with that hash exists.
		"""
		child = Child.objects.get(child_hash=child_hash)
		# use the related manager to add (no-op if already present)
		self.children.add(child)
		return child

	def create_child(self, first_name=None, last_name=None, date_of_birth=None, password=None, **extra_fields):
		"""Create a new Child and attach it to this guardian.

		This enforces that the guardian instance is saved (has a primary key).
		Typical use: called from authenticated guardian objects (e.g. request.user.create_child(...)).

		Returns the created Child instance.
		"""
		# Ensure guardian is a persisted user (reasonable proxy for "logged in")
		if self.pk is None:
			raise ValueError('Guardian must be saved/persisted before creating children.')

		# If caller passes is_authenticated attribute (e.g. request.user), prefer that check
		if hasattr(self, 'is_authenticated') and not getattr(self, 'is_authenticated'):
			raise PermissionError('Only an authenticated guardian may create a child.')

		child_data = {
			'first_name': first_name or '',
			'last_name': last_name or '',
			'date_of_birth': date_of_birth,
		}
		# include any other fields caller provided
		child_data.update(extra_fields)

		# Create and link the child atomically
		with transaction.atomic():
			child = Child.objects.create_user(password=password, **child_data)
			# link to guardian
			self.children.add(child)

		return child


class Child(AbstractBaseUser, PermissionsMixin):
	"""A child account with a unique hash identifier.

	The `child_hash` field is generated automatically and can be given to a
	guardian so they can register (link) themselves to this child using
	`Guardian.add_child(child_hash)`.
	"""
	child_hash = models.CharField(max_length=64, unique=True, db_index=True)
	first_name = models.CharField(max_length=150, blank=True)
	last_name = models.CharField(max_length=150, blank=True)
	date_of_birth = models.DateField(null=True, blank=True)
	is_active = models.BooleanField(default=True)
	date_joined = models.DateTimeField(default=timezone.now)
	restricted_apps = models.JSONField(default=dict, blank=True, help_text='Dictionary of restricted apps with time limits: {"package.name": hours}')

	# Override Permission/Group relations from PermissionsMixin to avoid reverse accessor clashes
	groups = models.ManyToManyField(
		'auth.Group',
		related_name='child_set',
		blank=True,
		help_text='The groups this child belongs to.'
	)
	user_permissions = models.ManyToManyField(
		'auth.Permission',
		related_name='child_user_set',
		blank=True,
		help_text='Specific permissions for this child.'
	)

	objects = ChildManager()

	# Allow child_hash to be used as the login identifier when needed
	USERNAME_FIELD = 'child_hash'
	REQUIRED_FIELDS = []

	class Meta:
		verbose_name = 'child'
		verbose_name_plural = 'children'

	def __str__(self):
		if self.first_name or self.last_name:
			return f"{self.first_name} {self.last_name}".strip()
		return self.child_hash

	def get_full_name(self):
		return f"{self.first_name} {self.last_name}".strip() or self.child_hash

	def get_short_name(self):
		return self.first_name or self.child_hash

	def email_user(self, subject, message, from_email=None, **kwargs):
		# Children may not always have an email; placeholder to match Guardian API
		pass

	def save(self, *args, **kwargs):
		# Ensure a unique child_hash is present before saving
		if not self.child_hash:
			# Use manager to generate a unique hash
			manager = self.__class__.objects
			child_hash = manager._generate_unique_hash()
			while self.__class__.objects.filter(child_hash=child_hash).exists():
				child_hash = manager._generate_unique_hash()
			self.child_hash = child_hash
		super().save(*args, **kwargs)

