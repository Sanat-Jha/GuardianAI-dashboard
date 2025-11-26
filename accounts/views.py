from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from PIL import Image
import os
import io
from django.core.files.base import ContentFile

from .models import Guardian, Child


def landing_page(request):
	"""Serve the landing page"""
	return render(request, 'landing_page.html')


def signup_view(request):
	if request.method == 'POST':
		email = request.POST.get('email')
		password = request.POST.get('password')
		full_name = request.POST.get('full_name', '')
		if not email or not password:
			messages.error(request, 'Email and password are required.')
			return render(request, 'accounts/signup.html')

		guardian = Guardian.objects.create_user(email=email, password=password, full_name=full_name)
		# log the user in and redirect to dashboard (backend app)
		user = authenticate(request, email=email, password=password)
		if user:
			login(request, user)
			return redirect('backend:dashboard')

	return render(request, 'accounts/signup.html')


def login_view(request):
	if request.method == 'POST':
		email = request.POST.get('email')
		password = request.POST.get('password')
		user = authenticate(request, email=email, password=password)
		if user is not None:
			login(request, user)
			return redirect('backend:dashboard')
		messages.error(request, 'Invalid credentials')

	return render(request, 'accounts/login.html')


def logout_view(request):
	logout(request)
	return redirect('accounts:login')


def password_reset_info(request):
	# Simple page explaining password reset; for production use Django's password reset views
	return render(request, 'accounts/password_reset.html')


@login_required
@require_http_methods(["POST"])
def delete_child(request, child_hash):
	"""Delete a child and all related data.
	
	Validates that the guardian owns this child before deletion.
	All related data (ScreenTime, LocationHistory, SiteAccessLog, AppScreenTime) 
	will be automatically deleted due to CASCADE on_delete.
	"""
	try:
		# Get the child and verify guardian owns it
		child = get_object_or_404(Child, child_hash=child_hash)
		
		# Verify the logged-in guardian has this child
		if not request.user.children.filter(child_hash=child_hash).exists():
			return JsonResponse({
				'status': 'error',
				'message': 'You do not have permission to delete this child.'
			}, status=403)
		
		# Store child name for response message
		child_name = child.get_full_name()
		
		# Delete the child (all related data will cascade delete)
		child.delete()
		
		return JsonResponse({
			'status': 'success',
			'message': f'{child_name} has been deleted successfully.'
		})
		
	except Exception as e:
		return JsonResponse({
			'status': 'error',
			'message': f'An error occurred: {str(e)}'
		}, status=500)


@login_required
@require_http_methods(["POST"])
def upload_child_profile_image(request, child_hash):
	"""Handle profile image upload for a child.
	
	Validates:
	- File type (must be image: jpg, jpeg, png, gif, webp)
	- File size (max 5MB)
	- User permission (guardian must own this child)
	"""
	try:
		# Get the child and verify guardian owns it
		child = get_object_or_404(Child, child_hash=child_hash)
		
		# Verify the logged-in guardian has this child
		if not request.user.children.filter(child_hash=child_hash).exists():
			return JsonResponse({
				'status': 'error',
				'message': 'You do not have permission to edit this child.'
			}, status=403)
		
		# Check if file was uploaded
		if 'profile_image' not in request.FILES:
			return JsonResponse({
				'status': 'error',
				'message': 'No image file provided.'
			}, status=400)
		
		profile_image = request.FILES['profile_image']
		
		# Validate file size (5MB max)
		MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB in bytes
		if profile_image.size > MAX_FILE_SIZE:
			return JsonResponse({
				'status': 'error',
				'message': 'File size too large. Maximum size is 5MB.'
			}, status=400)
		
		# Validate file type
		ALLOWED_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp']
		file_ext = profile_image.name.split('.')[-1].lower()
		
		if file_ext not in ALLOWED_EXTENSIONS:
			return JsonResponse({
				'status': 'error',
				'message': f'Invalid file type. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}'
			}, status=400)
		
		# Validate that it's actually an image using PIL
		try:
			img = Image.open(profile_image)
			img.verify()  # Verify it's a valid image
			profile_image.seek(0)  # Reset file pointer after verify
		except Exception:
			return JsonResponse({
				'status': 'error',
				'message': 'Invalid image file.'
			}, status=400)
		
		# Delete old profile image if exists (best-effort)
		if child.profile_image:
			try:
				old_image_path = child.profile_image.path
				if os.path.exists(old_image_path):
					os.remove(old_image_path)
			except Exception:
				pass

		# Convert uploaded image to WEBP and save as <child_hash>.webp
		try:
			img = Image.open(profile_image)
			# Convert image mode appropriately for WEBP
			if img.mode in ("RGBA", "LA") or (img.mode == "P" and 'transparency' in img.info):
				converted = img.convert("RGBA")
			else:
				converted = img.convert("RGB")

			buf = io.BytesIO()
			# quality 85 is a reasonable default; method uses libwebp encoding when available
			converted.save(buf, format='WEBP', quality=85, method=6)
			buf.seek(0)

			filename = f"{child.child_hash}.webp"
			content_file = ContentFile(buf.read())
			# Use the ImageField's save method so Django storage handles file placement
			child.profile_image.save(filename, content_file, save=False)
			child.save()

			return JsonResponse({
				'status': 'success',
				'message': 'Profile image updated successfully.',
				'image_url': child.profile_image.url
			})
		except Exception as e:
			return JsonResponse({
				'status': 'error',
				'message': f'Image conversion failed: {str(e)}'
			}, status=500)
		
	except Exception as e:
		return JsonResponse({
			'status': 'error',
			'message': f'An error occurred: {str(e)}'
		}, status=500)

