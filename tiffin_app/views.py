from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout # For later login/logout
from .forms import CustomUserCreationForm # Import your form

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user) # Log the user in after registration
            return redirect('home') # Redirect to a home page (create this later)
    else:
        form = CustomUserCreationForm()
    return render(request, 'tiffin_app/register.html', {'form': form})

def home(request):
    return render(request, 'tiffin_app/home.html') # A placeholder home page
