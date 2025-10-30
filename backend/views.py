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
        # Get last 30 days, most recent first
        st_qs = ScreenTime.objects.filter(child=c).order_by('-date')
        children_screen_time[c] = list(st_qs)

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
        "screen_time_info": {
            "child_hash": "...", // required
            "date": "YYYY-MM-DD", // required, day for which data is sent
            "total_screen_time": 12345, // required, total seconds for the day
            "app_wise_data": { // required, app-wise and hour-wise usage
                "com.whatsapp": {"09": 1200, "10": 800, ...},
                "com.youtube": {"09": 600, ...},
                ...
            }
        },
        // other data can be present
    }
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    # Extract and store screen time info if present
    screen_time_info = payload.get('screen_time_info')
    screen_time_result = None
    if screen_time_info:
        from backend.models import ScreenTime
        try:
            obj, created = ScreenTime.store_from_dict(screen_time_info)
            screen_time_result = {'status': 'ok', 'created': created}
        except ValueError as e:
            screen_time_result = {'error': str(e)}

    # You can handle other data types here as needed

    return JsonResponse({'screen_time': screen_time_result or 'not provided'})
from django.shortcuts import render
