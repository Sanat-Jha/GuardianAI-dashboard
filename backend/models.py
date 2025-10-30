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
