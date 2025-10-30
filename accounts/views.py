from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages

from .models import Guardian


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

