from django.contrib import admin
from .models import ScreenTime, AppScreenTime, LocationHistory, SiteAccessLog, App

# Register your models here.

@admin.register(ScreenTime)
class ScreenTimeAdmin(admin.ModelAdmin):
    list_display = ('child', 'date', 'total_screen_time', 'created')
    list_filter = ('date', 'child')
    search_fields = ('child__first_name', 'child__last_name', 'child__child_hash')
    date_hierarchy = 'date'


@admin.register(AppScreenTime)
class AppScreenTimeAdmin(admin.ModelAdmin):
    list_display = ('screen_time', 'app', 'hour', 'seconds', 'created')
    list_filter = ('hour', 'app')
    search_fields = ('app__app_name', 'app__domain', 'screen_time__child__first_name')


@admin.register(LocationHistory)
class LocationHistoryAdmin(admin.ModelAdmin):
    list_display = ('child', 'timestamp', 'latitude', 'longitude')
    list_filter = ('child', 'timestamp')
    search_fields = ('child__first_name', 'child__last_name', 'child__child_hash')
    date_hierarchy = 'timestamp'


@admin.register(SiteAccessLog)
class SiteAccessLogAdmin(admin.ModelAdmin):
    list_display = ('child', 'timestamp', 'url', 'accessed')
    list_filter = ('accessed', 'child', 'timestamp')
    search_fields = ('child__first_name', 'child__last_name', 'url')
    date_hierarchy = 'timestamp'


@admin.register(App)
class AppAdmin(admin.ModelAdmin):
    list_display = ('app_name', 'domain', 'blocked_count')
    search_fields = ('app_name', 'domain')
    ordering = ('-blocked_count', 'app_name')
