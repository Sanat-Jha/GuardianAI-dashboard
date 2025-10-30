from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
import json

from accounts.models import Child


@login_required
def dashboard_view(request):
    guardian = request.user
    children = guardian.children.all()

    # Import here to avoid circular import
    from backend.models import ScreenTime

    # Build a dict: child -> list of ScreenTime (last 30 days)
    children_screen_time = {}
    for c in children:
        st_qs = ScreenTime.objects.filter(child=c).order_by('-date')
        children_screen_time[c] = list(st_qs)

    # No need to fetch location/site logs here; use related_name in template

    if request.method == 'POST':
        # handle create child form
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        date_of_birth = request.POST.get('date_of_birth') or None
        # create the child and automatically link it to guardian
        child = guardian.create_child(first_name=first_name, last_name=last_name, date_of_birth=date_of_birth)
        messages.success(request, f'Child created with hash: {child.child_hash}')
        return redirect('backend:dashboard')

    return render(request, 'accounts/dashboard.html', {
        'children': children,
        'children_screen_time': children_screen_time,
    })


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
from django.shortcuts import render
