from django.db import models
from django.utils import timezone
from accounts.models import Child


import json


class ScreenTime(models.Model):
    """
    Stores per-child, per-day screen time data for the last 365 days (1 year).
    - One row per child per day.
    - app_wise_data: JSON: {app_domain: {hour: seconds, ...}, ...} (legacy, kept for compatibility)
    - total_screen_time: total seconds for the day
    - created/updated: for housekeeping
    Automatically deletes records older than 365 days on save.
    Note: App-wise data is now stored in AppScreenTime model with proper App references.
    """
    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name='screen_time')
    date = models.DateField()
    total_screen_time = models.PositiveIntegerField(default=0, help_text="Total screen time in seconds for the day")
    app_wise_data = models.JSONField(default=dict, blank=True, help_text="Legacy: App-wise screen time. Use AppScreenTime model instead.")
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

    def get_app_breakdown(self):
        """
        Get app-wise screen time breakdown from AppScreenTime entries.
        Returns dict: {app_domain: total_seconds, ...}
        Falls back to app_wise_data if no AppScreenTime entries exist.
        """
        app_breakdown = {}
        
        # Try to get data from AppScreenTime entries (preferred)
        app_screen_times = self.app_screen_times.select_related('app').all()
        if app_screen_times.exists():
            for ast in app_screen_times:
                domain = ast.app.domain
                app_breakdown[domain] = app_breakdown.get(domain, 0) + ast.seconds
            return app_breakdown
        
        # Fallback to legacy app_wise_data
        if self.app_wise_data:
            for app_domain, hourly_data in self.app_wise_data.items():
                if isinstance(hourly_data, dict):
                    # Sum all hours for this app
                    total_time = sum(int(v) for v in hourly_data.values() if isinstance(v, (int, float)))
                    app_breakdown[app_domain] = total_time
                elif isinstance(hourly_data, (int, float)):
                    app_breakdown[app_domain] = int(hourly_data)
        
        return app_breakdown

    def get_app_hourly_breakdown(self):
        """
        Get detailed app-wise hourly breakdown from AppScreenTime entries.
        Returns dict: {app_domain: {hour: seconds, ...}, ...}
        Falls back to app_wise_data if no AppScreenTime entries exist.
        """
        app_hourly = {}
        
        # Try to get data from AppScreenTime entries (preferred)
        app_screen_times = self.app_screen_times.select_related('app').all()
        if app_screen_times.exists():
            for ast in app_screen_times:
                domain = ast.app.domain
                if domain not in app_hourly:
                    app_hourly[domain] = {}
                app_hourly[domain][str(ast.hour)] = ast.seconds
            return app_hourly
        
        # Fallback to legacy app_wise_data
        return self.app_wise_data if self.app_wise_data else {}


    @staticmethod
    def prune_old_data():
        cutoff = timezone.now().date() - timezone.timedelta(days=365)
        ScreenTime.objects.filter(date__lt=cutoff).delete()


    @staticmethod
    def store_from_dict(data):
        """
        Store or update screen time data from a dict with keys:
        child_hash, date, total_screen_time, app_wise_data
        
        app_wise_data format: {app_domain: {hour: seconds, ...}, ...}
        
        For each app_domain in app_wise_data:
        1. Gets or creates an App entry (tries to fetch from Play Store if new)
        2. Creates/updates AppScreenTime entries for each hour
        
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
        
        # Create or update the ScreenTime record
        obj, created = ScreenTime.objects.update_or_create(
            child=child,
            date=date,
            defaults={
                'total_screen_time': total_screen_time,
                'app_wise_data': app_wise_data,  # Keep legacy data for backward compatibility
            }
        )
        
        # Process app_wise_data and create App & AppScreenTime entries
        if isinstance(app_wise_data, dict):
            for app_domain, hourly_data in app_wise_data.items():
                if not isinstance(hourly_data, dict):
                    continue
                
                # Get or create App entry
                try:
                    app = App.objects.get(domain=app_domain)
                except App.DoesNotExist:
                    # Try to create from Play Store data
                    try:
                        app = App.create_from_package(app_domain)
                        print(f"Created new App entry for {app_domain}: {app.app_name}")
                    except ValueError as e:
                        # If Play Store fetch fails, create a basic entry
                        print(f"Play Store fetch failed for {app_domain}, creating basic entry: {e}")
                        app = App.objects.create(
                            domain=app_domain,
                            app_name=app_domain.split('.')[-1].title(),  # Use last part of domain as name
                            icon_url='',  # Empty icon URL
                        )
                
                # Store hourly data in AppScreenTime
                for hour_str, seconds in hourly_data.items():
                    try:
                        hour = int(hour_str)
                        if 0 <= hour <= 23:
                            AppScreenTime.objects.update_or_create(
                                screen_time=obj,
                                app=app,
                                hour=hour,
                                defaults={'seconds': int(seconds)}
                            )
                    except (ValueError, TypeError) as e:
                        print(f"Skipping invalid hour data: {hour_str}={seconds}, error: {e}")
                        continue
        
        ScreenTime.prune_old_data()
        return obj, created



class AppScreenTime(models.Model):
    """
    Stores hourly app screen time data linking ScreenTime records to specific Apps.
    - Each entry: screen_time (parent), app, hour (0-23), seconds
    - Replaces the JSON storage in ScreenTime.app_wise_data with proper relational data
    """
    screen_time = models.ForeignKey('ScreenTime', on_delete=models.CASCADE, related_name='app_screen_times')
    app = models.ForeignKey('App', on_delete=models.CASCADE, related_name='screen_time_entries')
    hour = models.PositiveSmallIntegerField(help_text="Hour of day (0-23)")
    seconds = models.PositiveIntegerField(help_text="Screen time in seconds for this app during this hour")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('screen_time', 'app', 'hour')
        ordering = ['hour']

    def __str__(self):
        return f"{self.app.app_name} - {self.screen_time.date} - Hour {self.hour}: {self.seconds}s"



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


class App(models.Model):
    """
    Stores information about mobile applications including block counts.
    """
    domain = models.CharField(max_length=255, unique=True)
    app_name = models.CharField(max_length=255)
    icon_url = models.URLField()
    blocked_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.app_name

    @staticmethod
    def create_from_package(package_name):
        """
        Creates or updates app entry using Google Play Store data.
        Returns App instance or raises ValueError.
        """
        try:
            from google_play_scraper import app
            result = app(package_name)
            obj, created = App.objects.update_or_create(
                domain=package_name,
                defaults={
                    'app_name': result['title'],
                    'icon_url': result['icon']
                }
            )
            return obj
        except Exception as e:
            raise ValueError(f'Failed to fetch app data: {str(e)}')

    def update_block_count(self, increment=True):
        """
        Updates blocked_count by +1 or -1
        """
        if increment:
            self.blocked_count = models.F('blocked_count') + 1
        else:
            self.blocked_count = models.F('blocked_count') - 1
        self.save()