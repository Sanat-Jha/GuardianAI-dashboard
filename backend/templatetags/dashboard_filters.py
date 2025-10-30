# backend/templatetags/dashboard_filters.py
from django import template

register = template.Library()

@register.filter
def div(value, arg):
    """Divide the value by the arg."""
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError, TypeError):
        return 0

@register.filter
def get_item(dictionary, key):
    """Get item from dictionary."""
    return dictionary.get(key)

@register.filter
def seconds_to_hours(seconds):
    """Convert seconds to hours with 1 decimal place."""
    try:
        hours = float(seconds) / 3600
        return f"{hours:.1f}h"
    except (ValueError, TypeError):
        return "0.0h"
