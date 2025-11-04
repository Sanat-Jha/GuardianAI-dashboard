from django.db import models
from django.utils import timezone
from accounts.models import Child


import json


class ScreenTime(models.Model):
    """
    Stores per-child, per-day screen time data for the last 365 days (1 year).
    - One row per child per day.
    - app_wise_data: JSON: {app_name: {hour: seconds, ...}, ...}
    - total_screen_time: total seconds for the day
    - created/updated: for housekeeping
    Automatically deletes records older than 365 days on save.
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
        # Cleanup: keep only last 365 days (1 year) for this child
        cutoff = timezone.now().date() - timezone.timedelta(days=365)
        ScreenTime.objects.filter(child=self.child, date__lt=cutoff).delete()


    def __str__(self):
        return f"{self.child} - {self.date}"


    @staticmethod
    def prune_old_data():
        cutoff = timezone.now().date() - timezone.timedelta(days=365)
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



class LocationHistory(models.Model):
    """
    Stores per-child location history for the last 365 days (1 year).
    Each entry: child, timestamp, latitude, longitude.
    Automatically prunes entries older than 365 days on save.
    """
    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name='location_history')
    timestamp = models.DateTimeField()
    latitude = models.FloatField()
    longitude = models.FloatField()
    created = models.DateTimeField(auto_now_add=True)


    class Meta:
        ordering = ['-timestamp']


    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cutoff = timezone.now() - timezone.timedelta(days=365)
        LocationHistory.objects.filter(child=self.child, timestamp__lt=cutoff).delete()


    @staticmethod
    def store_from_dict(data):
        """
        Expects dict with: child_hash, timestamp (iso), latitude, longitude
        """
        from accounts.models import Child
        child_hash = data.get('child_hash')
        timestamp = data.get('timestamp')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        if not child_hash or not timestamp or latitude is None or longitude is None:
            raise ValueError('child_hash, timestamp, latitude, longitude required')
        try:
            child = Child.objects.get(child_hash=child_hash)
        except Child.DoesNotExist:
            raise ValueError('unknown child_hash')
        obj = LocationHistory.objects.create(
            child=child,
            timestamp=timestamp,
            latitude=latitude,
            longitude=longitude
        )
        LocationHistory.prune_old_data()
        return obj


    @staticmethod
    def prune_old_data():
        cutoff = timezone.now() - timezone.timedelta(days=365)
        LocationHistory.objects.filter(timestamp__lt=cutoff).delete()



class SiteAccessLog(models.Model):
    """
    Stores per-child site access/block events for the last 365 days (1 year).
    Each entry: child, timestamp, url, accessed (bool)
    Automatically prunes entries older than 365 days on save.
    """
    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name='site_access_logs')
    timestamp = models.DateTimeField()
    url = models.TextField()
    accessed = models.BooleanField(help_text='True if accessed, False if blocked')
    created = models.DateTimeField(auto_now_add=True)


    class Meta:
        ordering = ['-timestamp']


    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cutoff = timezone.now() - timezone.timedelta(days=365)
        SiteAccessLog.objects.filter(child=self.child, timestamp__lt=cutoff).delete()


    @staticmethod
    def store_from_list(child_hash, log_list):
        """
        Expects child_hash and a list of dicts: {timestamp, url, accessed}
        """
        from accounts.models import Child
        if not child_hash or not isinstance(log_list, list):
            raise ValueError('child_hash and list of logs required')
        try:
            child = Child.objects.get(child_hash=child_hash)
        except Child.DoesNotExist:
            raise ValueError('unknown child_hash')
        objs = []
        for entry in log_list:
            timestamp = entry.get('timestamp')
            url = entry.get('url')
            accessed = entry.get('accessed')
            if not timestamp or url is None or accessed is None:
                continue
            obj = SiteAccessLog.objects.create(
                child=child,
                timestamp=timestamp,
                url=url,
                accessed=bool(accessed)
            )
            objs.append(obj)
        SiteAccessLog.prune_old_data()
        return objs


    @staticmethod
    def prune_old_data():
        cutoff = timezone.now() - timezone.timedelta(days=365)
        SiteAccessLog.objects.filter(timestamp__lt=cutoff).delete()
