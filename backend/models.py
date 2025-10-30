from django.db import models
from django.utils import timezone
from accounts.models import Child

import json

class ScreenTime(models.Model):
	"""
	Stores per-child, per-day screen time data for the last 30 days.
	- One row per child per day.
	- app_wise_data: JSON: {app_name: {hour: seconds, ...}, ...}
	- total_screen_time: total seconds for the day
	- created/updated: for housekeeping
	Automatically deletes records older than 30 days on save.
	"""
	child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name='screen_time')
	date = models.DateField()
	total_screen_time = models.PositiveIntegerField(default=0, help_text="Total screen time in seconds for the day")
	app_wise_data = models.JSONField(default=dict, help_text="App-wise screen time: {app: {hour: seconds, ...}, ...}")
	created = models.DateTimeField(auto_now_add=True)
	updated = models.DateTimeField(auto_now=True)

	class Meta:
		unique_together = ('child', 'date')
		ordering = ['-date']

	def save(self, *args, **kwargs):
		super().save(*args, **kwargs)
		# Cleanup: keep only last 30 days for this child
		cutoff = timezone.now().date() - timezone.timedelta(days=30)
		ScreenTime.objects.filter(child=self.child, date__lt=cutoff).delete()

	def __str__(self):
		return f"{self.child} - {self.date}"

	@staticmethod
	def prune_old_data():
		cutoff = timezone.now().date() - timezone.timedelta(days=30)
		ScreenTime.objects.filter(date__lt=cutoff).delete()

	@staticmethod
	def store_from_dict(data):
		"""
		Store or update screen time data from a dict with keys:
		child_hash, date, total_screen_time, app_wise_data
		Returns (ScreenTime instance, created: bool) or raises ValueError.
		"""
		from accounts.models import Child
		child_hash = data.get('child_hash')
		date = data.get('date')
		total_screen_time = data.get('total_screen_time')
		app_wise_data = data.get('app_wise_data')
		if not child_hash or not date or total_screen_time is None or app_wise_data is None:
			raise ValueError('child_hash, date, total_screen_time, and app_wise_data are required')
		try:
			child = Child.objects.get(child_hash=child_hash)
		except Child.DoesNotExist:
			raise ValueError('unknown child_hash')
		obj, created = ScreenTime.objects.update_or_create(
			child=child,
			date=date,
			defaults={
				'total_screen_time': total_screen_time,
				'app_wise_data': app_wise_data,
			}
		)
		ScreenTime.prune_old_data()
		return obj, created