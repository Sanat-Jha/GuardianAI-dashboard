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
        
        children_data[c] = {
            'child': c,
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
