from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth import authenticate
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.conf import settings
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
        # Get screen time records (last 30 days) for statistics calculation
        st_qs = ScreenTime.objects.filter(child=c).order_by('-date')[:30]
        
        # Calculate statistics
        total_time = sum([st.total_screen_time for st in st_qs])
        avg_time = total_time / len(st_qs) if st_qs else 0
        
        # Format time strings
        total_hours = total_time / 3600
        avg_hours = avg_time / 3600
        
        # Get app-wise breakdown
        app_breakdown = {}
        for st in st_qs:
            # Use the new helper method to get app breakdown
            breakdown = st.get_app_breakdown()
            for app_domain, time in breakdown.items():
                app_breakdown[app_domain] = app_breakdown.get(app_domain, 0) + time
        
        # Get all apps sorted by usage time (not limited to top 5)
        sorted_apps = sorted(app_breakdown.items(), key=lambda x: x[1], reverse=True)
        
        # Fetch App objects to get names and icons
        from backend.models import App
        top_apps = []
        for app_domain, time_seconds in sorted_apps:
            try:
                app = App.objects.get(domain=app_domain)
                top_apps.append({
                    'domain': app_domain,
                    'name': app.app_name,
                    'icon_url': app.icon_url,
                    'time': time_seconds,
                    'hours': round(time_seconds/3600, 1)
                })
            except App.DoesNotExist:
                # Fallback to domain name if App not found
                top_apps.append({
                    'domain': app_domain,
                    'name': app_domain.split('.')[-1].title(),
                    'icon_url': '',
                    'time': time_seconds,
                    'hours': round(time_seconds/3600, 1)
                })
        
        # Location data
        locations = c.location_history.order_by('-timestamp')[:20]
        location_count = c.location_history.count()
        
        # Get latest location and convert to address
        latest_location_text = "No location data"
        latest_location = c.location_history.order_by('-timestamp').first()
        if latest_location:
            try:
                from opencage.geocoder import OpenCageGeocode
                key = settings.OPENCAGE_API_KEY
                if not key:
                    raise ValueError("OPENCAGE_API_KEY not found in settings")
                geocoder = OpenCageGeocode(key)
                results = geocoder.reverse_geocode(latest_location.latitude, latest_location.longitude)
                if results and len(results) > 0:
                    # Extract compact address components
                    components = results[0].get('components', {})
                    
                    # Get city (try multiple possible keys)
                    city = (components.get('city') or 
                           components.get('town') or 
                           components.get('village') or 
                           components.get('municipality') or 
                           components.get('county') or '')
                    
                    # Get country
                    country = components.get('country', '')
                    
                    # Get postcode
                    postcode = components.get('postcode', '')
                    
                    # Get street address (limited to first 25 characters)
                    road = components.get('road', '')
                    house_number = components.get('house_number', '')
                    street = f"{house_number} {road}".strip() if house_number else road
                    street = street[:25] + '...' if len(street) > 25 else street
                    
                    # Format compact address
                    address_parts = []
                    if street:
                        address_parts.append(street)
                    if city:
                        address_parts.append(city)
                    if postcode:
                        address_parts.append(postcode)
                    if country:
                        address_parts.append(country)
                    
                    latest_location_text = ', '.join(address_parts) if address_parts else f"{latest_location.latitude:.4f}, {latest_location.longitude:.4f}"
                else:
                    latest_location_text = f"{latest_location.latitude:.4f}, {latest_location.longitude:.4f}"
            except Exception as e:
                print(f"Error geocoding location: {e}")
                latest_location_text = f"{latest_location.latitude:.4f}, {latest_location.longitude:.4f}"
        
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
        
        # Calculate child's age
        child_age = None
        if c.date_of_birth:
            today = timezone.now().date()
            age = today.year - c.date_of_birth.year
            # Adjust if birthday hasn't occurred yet this year
            if today.month < c.date_of_birth.month or (today.month == c.date_of_birth.month and today.day < c.date_of_birth.day):
                age -= 1
            child_age = age
        
        children_data[c] = {
            'child': c,
            'age': child_age,
            'stats': {
                'total_screen_time': total_time,
                'total_screen_time_hours': f"{total_hours:.1f}h",
                'avg_screen_time': avg_time,
                'avg_screen_time_formatted': f"{avg_hours:.1f}h",
                'recent_avg_formatted': f"{recent_avg/3600:.1f}h/day",
                'latest_location': latest_location_text,
                'site_access_count': site_count,
                'blocked_sites': blocked_count,
                'accessed_sites': accessed_count,
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
    from datetime import datetime, timedelta
    import json
    
    try:
        child = Child.objects.get(child_hash=child_hash, guardians=request.user)
        
        # Get date range from query parameters
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        # Build queryset with date filters if provided
        st_qs = ScreenTime.objects.filter(child=child)
        
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                st_qs = st_qs.filter(date__gte=start_date_obj)
            except ValueError:
                pass  # Invalid date format, ignore
        
        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                st_qs = st_qs.filter(date__lte=end_date_obj)
            except ValueError:
                pass  # Invalid date format, ignore
        
        # If no date filters provided, default to last 30 days
        if not start_date and not end_date:
            st_qs = st_qs.order_by('-date')[:30]
        else:
            st_qs = st_qs.order_by('-date')
        
        # Prepare data for line chart (screen time over days)
        dates = []
        screen_times = []
        for st in reversed(list(st_qs)):
            dates.append(st.date.strftime('%m/%d'))
            screen_times.append(round(st.total_screen_time / 3600, 2))  # Convert to hours
        
        # Prepare data for pie chart (app breakdown)
        app_breakdown = {}
        for st in st_qs:
            # Use the new helper method to get app breakdown
            breakdown = st.get_app_breakdown()
            for app_domain, time in breakdown.items():
                app_breakdown[app_domain] = app_breakdown.get(app_domain, 0) + time
        
        # Get all apps sorted by usage time
        sorted_apps_all = sorted(app_breakdown.items(), key=lambda x: x[1], reverse=True)
        
        # Get top 5 apps for bar chart
        sorted_apps_top5 = sorted_apps_all[:5] if len(sorted_apps_all) > 5 else sorted_apps_all
        
        # Fetch App objects to get names and icons
        from backend.models import App
        
        # Process TOP 5 apps for bar chart
        top5_labels = []
        top5_times = []
        top5_icons = []
        top5_domains = []
        
        if sorted_apps_top5:
            for app_domain, time_seconds in sorted_apps_top5:
                try:
                    app = App.objects.get(domain=app_domain)
                    top5_labels.append(app.app_name)
                    top5_icons.append(app.icon_url)
                except App.DoesNotExist:
                    # Fallback to domain name if App not found
                    top5_labels.append(app_domain.split('.')[-1].title())
                    top5_icons.append('')
                top5_domains.append(app_domain)
                top5_times.append(round(time_seconds / 3600, 2))  # Convert to hours
        else:
            top5_labels = ['No Data']
            top5_times = [0]
            top5_icons = ['']
            top5_domains = ['']
        
        # Process ALL apps for app list
        all_labels = []
        all_times = []
        all_icons = []
        all_domains = []
        
        if sorted_apps_all:
            for app_domain, time_seconds in sorted_apps_all:
                try:
                    app = App.objects.get(domain=app_domain)
                    all_labels.append(app.app_name)
                    all_icons.append(app.icon_url)
                except App.DoesNotExist:
                    # Fallback to domain name if App not found
                    all_labels.append(app_domain.split('.')[-1].title())
                    all_icons.append('')
                all_domains.append(app_domain)
                all_times.append(round(time_seconds / 3600, 2))  # Convert to hours
        else:
            all_labels = ['No Data']
            all_times = [0]
            all_icons = ['']
            all_domains = ['']
        
        return JsonResponse({
            'line_chart': {
                'labels': dates if dates else ['No Data'],
                'data': screen_times if screen_times else [0],
            },
            'bar_chart': {
                'labels': top5_labels,
                'data': top5_times,
                'icons': top5_icons,
                'domains': top5_domains,
            },
            'app_list': {
                'labels': all_labels,
                'data': all_times,
                'icons': all_icons,
                'domains': all_domains,
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


# API endpoint for stats data
@login_required
def child_stats_data(request, child_hash):
    from backend.models import Child, ScreenTime
    from datetime import datetime, timedelta
    
    try:
        child = Child.objects.get(child_hash=child_hash, guardians=request.user)
        
        # Get date range from query parameters
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        # Build queryset with date filters if provided
        st_qs = ScreenTime.objects.filter(child=child)
        
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                st_qs = st_qs.filter(date__gte=start_date_obj)
            except ValueError:
                pass
        
        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                st_qs = st_qs.filter(date__lte=end_date_obj)
            except ValueError:
                pass
        
        # If no date filters provided, default to last 30 days
        if not start_date and not end_date:
            st_qs = st_qs.order_by('-date')[:30]
        else:
            st_qs = st_qs.order_by('-date')
        
        # Calculate statistics
        total_time = sum([st.total_screen_time for st in st_qs])
        avg_time = total_time / len(st_qs) if st_qs else 0
        
        # Format time strings
        total_hours = total_time / 3600
        avg_hours = avg_time / 3600
        
        # Location data - filter by date range if provided
        locations_qs = child.location_history.all()
        if start_date:
            try:
                start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
                locations_qs = locations_qs.filter(timestamp__gte=start_datetime)
            except ValueError:
                pass
        if end_date:
            try:
                end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
                end_datetime = end_datetime.replace(hour=23, minute=59, second=59)
                locations_qs = locations_qs.filter(timestamp__lte=end_datetime)
            except ValueError:
                pass
        
        # Get latest location and convert to address
        latest_location_text = "No location data"
        latest_location = locations_qs.order_by('-timestamp').first()
        if latest_location:
            try:
                from opencage.geocoder import OpenCageGeocode
                key = settings.OPENCAGE_API_KEY
                if not key:
                    raise ValueError("OPENCAGE_API_KEY not found in settings")
                geocoder = OpenCageGeocode(key)
                results = geocoder.reverse_geocode(latest_location.latitude, latest_location.longitude)
                if results and len(results) > 0:
                    # Extract compact address components
                    components = results[0].get('components', {})
                    
                    # Get city (try multiple possible keys)
                    city = (components.get('city') or 
                           components.get('town') or 
                           components.get('village') or 
                           components.get('municipality') or 
                           components.get('county') or '')
                    
                    # Get country
                    country = components.get('country', '')
                    
                    # Get postcode
                    postcode = components.get('postcode', '')
                    
                    # Get street address (limited to first 25 characters)
                    road = components.get('road', '')
                    house_number = components.get('house_number', '')
                    street = f"{house_number} {road}".strip() if house_number else road
                    street = street[:25] + '...' if len(street) > 25 else street
                    
                    # Format compact address
                    address_parts = []
                    if street:
                        address_parts.append(street)
                    if city:
                        address_parts.append(city)
                    if postcode:
                        address_parts.append(postcode)
                    if country:
                        address_parts.append(country)
                    
                    latest_location_text = ', '.join(address_parts) if address_parts else f"{latest_location.latitude:.4f}, {latest_location.longitude:.4f}"
                else:
                    latest_location_text = f"{latest_location.latitude:.4f}, {latest_location.longitude:.4f}"
            except Exception as e:
                print(f"Error geocoding location: {e}")
                latest_location_text = f"{latest_location.latitude:.4f}, {latest_location.longitude:.4f}"
        
        # Site access logs - filter by date range if provided
        site_logs_qs = child.site_access_logs.all()
        if start_date:
            try:
                start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
                site_logs_qs = site_logs_qs.filter(timestamp__gte=start_datetime)
            except ValueError:
                pass
        if end_date:
            try:
                end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
                end_datetime = end_datetime.replace(hour=23, minute=59, second=59)
                site_logs_qs = site_logs_qs.filter(timestamp__lte=end_datetime)
            except ValueError:
                pass
        
        site_count = site_logs_qs.count()
        blocked_count = site_logs_qs.filter(accessed=False).count()
        accessed_count = site_logs_qs.filter(accessed=True).count()
        
        return JsonResponse({
            'stats': {
                'total_screen_time_hours': f"{total_hours:.1f}h",
                'avg_screen_time_formatted': f"{avg_hours:.1f}h",
                'latest_location': latest_location_text,
                'site_access_count': site_count,
                'blocked_sites': blocked_count,
                'accessed_sites': accessed_count,
            }
        })
    except Child.DoesNotExist:
        return JsonResponse({'error': 'Child not found'}, status=404)
    except Exception as e:
        import traceback
        print(f"Error in child_stats_data: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)


# API endpoint for locations data
@login_required
def child_locations_data(request, child_hash):
    from backend.models import Child
    from datetime import datetime
    
    try:
        child = Child.objects.get(child_hash=child_hash, guardians=request.user)
        
        # Get date range from query parameters
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        # Build queryset with date filters if provided
        locations_qs = child.location_history.all()
        
        if start_date:
            try:
                start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
                locations_qs = locations_qs.filter(timestamp__gte=start_datetime)
            except ValueError:
                pass
        
        if end_date:
            try:
                end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
                end_datetime = end_datetime.replace(hour=23, minute=59, second=59)
                locations_qs = locations_qs.filter(timestamp__lte=end_datetime)
            except ValueError:
                pass
        
        # If no date filters provided, default to last 20 entries
        if not start_date and not end_date:
            locations_qs = locations_qs.order_by('-timestamp')[:20]
        else:
            locations_qs = locations_qs.order_by('-timestamp')
        
        # Prepare location data for JSON response
        locations_list = []
        for loc in locations_qs:
            locations_list.append({
                'timestamp': loc.timestamp.strftime('%b %d, %Y %H:%M'),
                'latitude': loc.latitude,
                'longitude': loc.longitude
            })
        
        return JsonResponse({
            'locations': locations_list,
            'count': len(locations_list)
        })
    except Child.DoesNotExist:
        return JsonResponse({'error': 'Child not found'}, status=404)
    except Exception as e:
        import traceback
        print(f"Error in child_locations_data: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)


# API endpoint for site logs data
@login_required
def child_site_logs_data(request, child_hash):
    from backend.models import Child
    from datetime import datetime
    
    try:
        child = Child.objects.get(child_hash=child_hash, guardians=request.user)
        
        # Get date range from query parameters
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        # Build queryset with date filters if provided
        site_logs_qs = child.site_access_logs.all()
        
        if start_date:
            try:
                start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
                site_logs_qs = site_logs_qs.filter(timestamp__gte=start_datetime)
            except ValueError:
                pass
        
        if end_date:
            try:
                end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
                end_datetime = end_datetime.replace(hour=23, minute=59, second=59)
                site_logs_qs = site_logs_qs.filter(timestamp__lte=end_datetime)
            except ValueError:
                pass
        
        # If no date filters provided, default to last 30 entries
        if not start_date and not end_date:
            site_logs_qs = site_logs_qs.order_by('-timestamp')[:30]
        else:
            site_logs_qs = site_logs_qs.order_by('-timestamp')
        
        # Prepare site logs data for JSON response
        site_logs_list = []
        for log in site_logs_qs:
            site_logs_list.append({
                'timestamp': log.timestamp.strftime('%b %d, %Y %H:%M'),
                'url': log.url,
                'accessed': log.accessed
            })
        
        return JsonResponse({
            'site_logs': site_logs_list,
            'count': len(site_logs_list)
        })
    except Child.DoesNotExist:
        return JsonResponse({'error': 'Child not found'}, status=404)
    except Exception as e:
        import traceback
        print(f"Error in child_site_logs_data: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)


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
        "child_hash": "abc123",            # single child identifier for entire payload
        "screen_time_info": { ... },
        "location_info": { ... },
        "site_access_info": { "logs": [...] },
        // other data can be present
    }
    """
    if request.method != 'POST':
        print("api_ingest: non-POST request received")
        return JsonResponse({'error': 'POST required'}, status=405)

    # Log request meta and raw body
    try:
        raw_body = request.body.decode('utf-8')
    except Exception:
        raw_body = repr(request.body)
    print(f"api_ingest called. Method={request.method}, Path={getattr(request, 'path', '')}")
    print(f"Client: {request.META.get('REMOTE_ADDR')} User-Agent: {request.META.get('HTTP_USER_AGENT')}")
    print(f"Raw request body: {raw_body}")

    try:
        payload = json.loads(raw_body)
        try:
            # Pretty-print payload for easier reading in logs
            print("Parsed JSON payload:", json.dumps(payload, indent=2))
        except Exception:
            print("Parsed JSON payload (repr):", repr(payload))
    except Exception as e:
        print(f"api_ingest: Failed to parse JSON: {e}")
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    # Require a top-level child_hash for the entire payload
    child_hash = payload.get('child_hash')
    if not child_hash:
        print("api_ingest: missing top-level child_hash")
        return JsonResponse({'error': 'child_hash required at top level'}, status=400)

    from backend.models import ScreenTime, LocationHistory, SiteAccessLog

    # Extract and store screen time info if present
    screen_time_info = payload.get('screen_time_info')
    screen_time_result = None
    if screen_time_info:
        print(f"Received screen_time_info for child_hash={child_hash}: {screen_time_info}")
        try:
            # Ensure child_hash is present in the dict passed to the model helper
            if isinstance(screen_time_info, dict):
                if 'child_hash' not in screen_time_info:
                    screen_time_info['child_hash'] = child_hash
            try:
                obj, created = ScreenTime.store_from_dict(screen_time_info)
                screen_time_result = {'status': 'ok', 'created': created}
                try:
                    print(f"ScreenTime stored: id={getattr(obj, 'id', None)} created={created}")
                except Exception:
                    print("ScreenTime stored (object repr):", repr(obj))
            except TypeError:
                # If the helper signature differs, try passing child_hash explicitly
                obj, created = ScreenTime.store_from_dict(child_hash, screen_time_info)
                screen_time_result = {'status': 'ok', 'created': created}
                print(f"ScreenTime stored using alternate signature: id={getattr(obj, 'id', None)} created={created}")
        except ValueError as e:
            print(f"Error storing screen time: {e}")
            screen_time_result = {'error': str(e)}
        except Exception as e:
            import traceback
            print("Unexpected error storing screen time:", str(e))
            print(traceback.format_exc())
            screen_time_result = {'error': str(e)}

    # Extract and store location info if present
    location_info = payload.get('location_info')
    location_result = None
    if location_info:
        print(f"Received location_info for child_hash={child_hash}: {location_info}")
        try:
            if isinstance(location_info, dict) and 'child_hash' not in location_info:
                location_info['child_hash'] = child_hash
            try:
                obj = LocationHistory.store_from_dict(location_info)
                location_result = {'status': 'ok'}
                try:
                    print(f"LocationHistory stored: id={getattr(obj, 'id', None)}")
                except Exception:
                    print("LocationHistory stored (object repr):", repr(obj))
            except TypeError:
                # Alternate signature: (child_hash, data)
                obj = LocationHistory.store_from_dict(child_hash, location_info)
                location_result = {'status': 'ok'}
                print(f"LocationHistory stored using alternate signature: id={getattr(obj, 'id', None)}")
        except ValueError as e:
            print(f"Error storing location info: {e}")
            location_result = {'error': str(e)}
        except Exception as e:
            import traceback
            print("Unexpected error storing location info:", str(e))
            print(traceback.format_exc())
            location_result = {'error': str(e)}

    # Extract and store site access info if present
    site_access_info = payload.get('site_access_info')
    site_access_result = None
    if site_access_info:
        print(f"Received site_access_info for child_hash={child_hash}: {site_access_info}")
        # Expecting: {"logs": [ {timestamp, url, accessed}, ... ]}
        logs = None
        if isinstance(site_access_info, dict):
            logs = site_access_info.get('logs')
        else:
            # If site_access_info is directly a list of logs
            if isinstance(site_access_info, list):
                logs = site_access_info
        print(f"site_access_info child_hash={child_hash} logs_count={len(logs) if isinstance(logs, list) else 'N/A'}")
        try:
            objs = SiteAccessLog.store_from_list(child_hash, logs)
            site_access_result = {'status': 'ok', 'count': len(objs)}
            print(f"Stored {len(objs)} SiteAccessLog entries for child_hash={child_hash}")
        except ValueError as e:
            print(f"Error storing site access logs: {e}")
            site_access_result = {'error': str(e)}
        except Exception as e:
            import traceback
            print("Unexpected error storing site access logs:", str(e))
            print(traceback.format_exc())
            site_access_result = {'error': str(e)}

    return JsonResponse({
        'child_hash': child_hash,
        'screen_time': screen_time_result or 'not provided',
        'location': location_result or 'not provided',
        'site_access': site_access_result or 'not provided',
    })


# API endpoint to get restricted apps for a child
@csrf_exempt
def get_blocked_apps(request, child_hash):
    """
    GET endpoint to retrieve the list of restricted apps for a child.
    Returns: JSON with restricted_apps dict (app_domain: allowed_hours)
    """
    try:
        child = Child.objects.get(child_hash=child_hash)
        return JsonResponse({
            'child_hash': child_hash,
            'restricted_apps': child.restricted_apps or {},
            'status': 'success'
        })
    except Child.DoesNotExist:
        return JsonResponse({
            'error': 'Child not found',
            'status': 'error'
        }, status=404)
    except Exception as e:
        import traceback
        print(f"Error retrieving restricted apps: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'error': str(e),
            'status': 'error'
        }, status=500)


# API endpoint to update restricted apps for a child (for guardian dashboard)
@login_required
def update_blocked_apps(request, child_hash):
    """
    POST endpoint to update the list of restricted apps for a child.
    Only accessible by guardians who have this child.
    Expects JSON body: {"restricted_apps": {"com.example.app1": 2.5, "com.example.app2": 1.0}}
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        import json
        child = Child.objects.get(child_hash=child_hash, guardians=request.user)
        
        data = json.loads(request.body)
        restricted_apps = data.get('restricted_apps', {})
        
        # Validate that restricted_apps is a dict
        if not isinstance(restricted_apps, dict):
            return JsonResponse({
                'error': 'restricted_apps must be a dictionary',
                'status': 'error'
            }, status=400)
        
        # Validate that all values are numbers
        for app_domain, hours in restricted_apps.items():
            if not isinstance(hours, (int, float)) or hours < 0:
                return JsonResponse({
                    'error': f'Invalid hours value for {app_domain}. Must be a positive number.',
                    'status': 'error'
                }, status=400)
        
        # Update the restricted apps
        child.restricted_apps = restricted_apps
        child.save()
        
        return JsonResponse({
            'child_hash': child_hash,
            'restricted_apps': child.restricted_apps,
            'status': 'success',
            'message': 'Restricted apps updated successfully'
        })
    except Child.DoesNotExist:
        return JsonResponse({
            'error': 'Child not found or you do not have permission',
            'status': 'error'
        }, status=404)
    except json.JSONDecodeError:
        return JsonResponse({
            'error': 'Invalid JSON in request body',
            'status': 'error'
        }, status=400)
    except Exception as e:
        import traceback
        print(f"Error updating restricted apps: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'error': str(e),
            'status': 'error'
        }, status=500)


# API endpoint to search available apps
@login_required
def search_available_apps(request):
    """
    GET endpoint to search/list all available apps from the App model.
    Query parameter: q (search query, optional)
    Returns: JSON with list of apps (name, domain, icon)
    """
    try:
        from backend.models import App
        
        search_query = request.GET.get('q', '').strip()
        
        if search_query:
            # Search by app name or domain
            apps = App.objects.filter(
                app_name__icontains=search_query
            ) | App.objects.filter(
                domain__icontains=search_query
            )
        else:
            # Return all apps (limit to 100 for performance)
            apps = App.objects.all()[:100]
        
        # Format response
        apps_list = []
        for app in apps:
            apps_list.append({
                'name': app.app_name,
                'domain': app.domain,
                'icon': app.icon_url or ''
            })
        
        return JsonResponse({
            'apps': apps_list,
            'count': len(apps_list),
            'status': 'success'
        })
    except Exception as e:
        import traceback
        print(f"Error searching apps: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'error': str(e),
            'status': 'error'
        }, status=500)


# API endpoint to get child profile image
@csrf_exempt
def get_child_profile_image(request, child_hash):
    """
    GET endpoint to retrieve the profile image URL for a child.
    Returns: JSON with profile_image_url (or null if not set)
    """
    try:
        child = Child.objects.get(child_hash=child_hash)
        
        profile_image_url = None
        if child.profile_image:
            # Build absolute URL
            profile_image_url = request.build_absolute_uri(child.profile_image.url)
        
        return JsonResponse({
            'child_hash': child_hash,
            'profile_image_url': profile_image_url,
            'has_profile_image': bool(child.profile_image),
            'status': 'success'
        })
    except Child.DoesNotExist:
        return JsonResponse({
            'error': 'Child not found',
            'status': 'error'
        }, status=404)
    except Exception as e:
        import traceback
        print(f"Error retrieving profile image: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'error': str(e),
            'status': 'error'
        }, status=500)
