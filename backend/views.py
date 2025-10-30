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

    if request.method == 'POST':
        # handle create child form
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        date_of_birth = request.POST.get('date_of_birth') or None
        # create the child and automatically link it to guardian
        child = guardian.create_child(first_name=first_name, last_name=last_name, date_of_birth=date_of_birth)
        messages.success(request, f'Child created with hash: {child.child_hash}')
        return redirect('backend:dashboard')

    return render(request, 'accounts/dashboard.html', {'children': children})


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
    """Ingest endpoint for the mobile app to POST metrics for a child.

    Expects POST JSON containing at least `child_hash` and arbitrary metrics.
    For now we just print the received payload and return a success response.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    child_hash = payload.get('child_hash')
    print('INGEST RECEIVED:', payload)

    # Optionally validate child exists
    if child_hash:
        try:
            child = Child.objects.get(child_hash=child_hash)
        except Child.DoesNotExist:
            return JsonResponse({'error': 'unknown child_hash'}, status=404)

    # For now just acknowledge
    return JsonResponse({'status': 'ok', 'received': payload})
from django.shortcuts import render
