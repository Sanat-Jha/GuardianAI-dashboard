from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth import authenticate
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
import json

from accounts.models import Child


from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, Count

@login_required
def dashboard_view(request):
    guardian = request.user
    children = guardian.children.all()

    # Import here to avoid circular import
    from backend.models import ScreenTime

    # Build a dict: child -> structured data
    children_data = {}
    
    for c in children:
        # Get screen time records (last 30 days)
        st_qs = ScreenTime.objects.filter(child=c).order_by('-date')[:30]
        screen_time_list = list(st_qs)
        
        # Calculate statistics
        total_time = sum([st.total_screen_time for st in st_qs])
        avg_time = total_time / len(st_qs) if st_qs else 0
        
        # Format time strings
        total_hours = total_time / 3600
        avg_hours = avg_time / 3600
        
        # Get app-wise breakdown
        app_breakdown = {}
        for st in st_qs:
            if st.app_wise_data:
                try:
                    apps_data = json.loads(st.app_wise_data)
                    for app, time in apps_data.items():
                        app_breakdown[app] = app_breakdown.get(app, 0) + int(time)
                except:
                    pass
        
        # Get top 5 apps
        sorted_apps = sorted(app_breakdown.items(), key=lambda x: x[1], reverse=True)[:5]
        top_apps = [{'name': app[0], 'time': app[1], 'hours': round(app[1]/3600, 1)} for app in sorted_apps]
        
        # Location data
        locations = c.location_history.order_by('-timestamp')[:20]
        location_count = c.location_history.count()
        
        # Site access logs
        site_logs = c.site_access_logs.order_by('-timestamp')[:30]
        site_count = c.site_access_logs.count()
        blocked_count = c.site_access_logs.filter(accessed=False).count()
        accessed_count = c.site_access_logs.filter(accessed=True).count()
        
        # Recent activity (last 7 days)
        from datetime import datetime, timedelta
        seven_days_ago = timezone.now() - timedelta(days=7)
        recent_screen_time = ScreenTime.objects.filter(child=c, date__gte=seven_days_ago)
        recent_total = sum([st.total_screen_time for st in recent_screen_time])
        recent_avg = recent_total / 7 if recent_screen_time.exists() else 0
        
        children_data[c] = {
            'child': c,
            'screen_time_list': screen_time_list,
            'stats': {
                'total_screen_time': total_time,
                'total_screen_time_hours': f"{total_hours:.1f}h",
                'avg_screen_time': avg_time,
                'avg_screen_time_formatted': f"{avg_hours:.1f}h",
                'recent_avg_formatted': f"{recent_avg/3600:.1f}h/day",
                'location_count': location_count,
                'site_access_count': site_count,
                'blocked_sites': blocked_count,
                'accessed_sites': accessed_count,
                'block_rate': f"{(blocked_count/site_count*100):.0f}%" if site_count > 0 else "0%",
            },
            'top_apps': top_apps,
            'locations': locations,
            'site_logs': site_logs,
            'has_data': st_qs.exists() or locations.exists() or site_logs.exists(),
        }

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        date_of_birth = request.POST.get('date_of_birth') or None
        child = guardian.create_child(first_name=first_name, last_name=last_name, date_of_birth=date_of_birth)
        messages.success(request, f'Child profile created successfully! ID: {child.child_hash}')
        return redirect('backend:dashboard')

    return render(request, 'dashboard/dashboard.html', {
        'children': children,
        'children_data': children_data,
    })


# API endpoint for chart data
@login_required
def child_chart_data(request, child_hash):
    from backend.models import Child, ScreenTime
    import json
    
    try:
        child = Child.objects.get(child_hash=child_hash, guardians=request.user)
        st_qs = ScreenTime.objects.filter(child=child).order_by('-date')[:30]
        
        # Prepare data for line chart (screen time over days)
        dates = []
        screen_times = []
        for st in reversed(list(st_qs)):
            dates.append(st.date.strftime('%m/%d'))
            screen_times.append(round(st.total_screen_time / 3600, 2))  # Convert to hours
        
        # Prepare data for pie chart (app breakdown)
        app_breakdown = {}
        for st in st_qs:
            if st.app_wise_data:
                try:
                    # app_wise_data is already a dict (JSONField auto-deserializes)
                    apps_data = st.app_wise_data
                    
                    # Handle nested structure: {app: {hour: seconds, ...}, ...}
                    for app, time_data in apps_data.items():
                        if isinstance(time_data, dict):
                            # Sum all hours for this app
                            total_time = sum(int(v) for v in time_data.values())
                            app_breakdown[app] = app_breakdown.get(app, 0) + total_time
                        else:
                            # If it's just a number
                            app_breakdown[app] = app_breakdown.get(app, 0) + float(time_data)
                except Exception as e:
                    # Skip if parsing fails
                    print(f"Error parsing app data: {e}")
                    continue
        
        # Get top 5 apps
        sorted_apps = sorted(app_breakdown.items(), key=lambda x: x[1], reverse=True)[:5]
        app_labels = [app[0] for app in sorted_apps] if sorted_apps else ['No Data']
        app_times = [round(app[1] / 3600, 2) for app in sorted_apps] if sorted_apps else [0]  # Convert to hours
        
        return JsonResponse({
            'line_chart': {
                'labels': dates if dates else ['No Data'],
                'data': screen_times if screen_times else [0],
            },
            'pie_chart': {
                'labels': app_labels,
                'data': app_times,
            }
        })
    except Child.DoesNotExist:
        return JsonResponse({'error': 'Child not found'}, status=404)
    except Exception as e:
        # Log the error and return a proper JSON response
        import traceback
        print(f"Error in child_chart_data: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'error': str(e),
            'line_chart': {'labels': ['No Data'], 'data': [0]},
            'pie_chart': {'labels': ['No Data'], 'data': [0]}
        }, status=500)


@csrf_exempt
def api_login(request):
    """Mobile app login endpoint.

    Expects POST JSON: {"email": "...", "password": "..."}
    Returns JSON with guardian info and children list on success.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    email = payload.get('email')
    password = payload.get('password')
    if not email or not password:
        return JsonResponse({'error': 'email and password required'}, status=400)

    user = authenticate(request, email=email, password=password)
    if user is None:
        return JsonResponse({'error': 'invalid credentials'}, status=401)

    # build children list
    children = []
    for c in user.children.all():
        children.append({
            'child_hash': c.child_hash,
            'first_name': c.first_name,
            'last_name': c.last_name,
            'date_of_birth': str(c.date_of_birth) if c.date_of_birth else None,
        })

    return JsonResponse({'status': 'ok', 'children': children})


@csrf_exempt
def api_ingest(request):
    """
    Ingest endpoint for the mobile app to POST metrics for a child.

    Expects POST JSON with this schema:
    {
        "screen_time_info": { ... },
        "location_info": { ... },
        "site_access_info": { ... },
        // other data can be present
    }
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    from backend.models import ScreenTime, LocationHistory, SiteAccessLog

    # Extract and store screen time info if present
    screen_time_info = payload.get('screen_time_info')
    screen_time_result = None
    if screen_time_info:
        try:
            obj, created = ScreenTime.store_from_dict(screen_time_info)
            screen_time_result = {'status': 'ok', 'created': created}
        except ValueError as e:
            screen_time_result = {'error': str(e)}

    # Extract and store location info if present
    location_info = payload.get('location_info')
    location_result = None
    if location_info:
        try:
            obj = LocationHistory.store_from_dict(location_info)
            location_result = {'status': 'ok'}
        except ValueError as e:
            location_result = {'error': str(e)}

    # Extract and store site access info if present
    site_access_info = payload.get('site_access_info')
    site_access_result = None
    if site_access_info:
        # Expecting: {"child_hash": ..., "logs": [ {timestamp, url, accessed}, ... ]}
        child_hash = site_access_info.get('child_hash')
        logs = site_access_info.get('logs')
        try:
            objs = SiteAccessLog.store_from_list(child_hash, logs)
            site_access_result = {'status': 'ok', 'count': len(objs)}
        except ValueError as e:
            site_access_result = {'error': str(e)}

    return JsonResponse({
        'screen_time': screen_time_result or 'not provided',
        'location': location_result or 'not provided',
        'site_access': site_access_result or 'not provided',
    })
