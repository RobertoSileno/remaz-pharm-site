from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .models import Medicine

def home(request):
    return render(request, 'home.html')

def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'Usuário ou senha inválidos')

    return render(request, 'login.html')

def register_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        password_confirm = request.POST['password_confirm']
        cpf = request.POST.get('cpf', '')
        
        if password != password_confirm:
            messages.error(request, 'Senhas não coincidem')
            return render(request, 'register.html')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Usuário já existe')
            return render(request, 'register.html')
        
        if cpf and User.objects.filter(profile__cpf=cpf).exists():
            messages.error(request, 'CPF já cadastrado')
            return render(request, 'register.html')
        
        user = User.objects.create_user(username=username, email=email, password=password)
        user.save()
        
        # Criar perfil do usuário com CPF
        from core.models import UserProfile
        UserProfile.objects.create(user=user, cpf=cpf)
        
        messages.success(request, 'Registro realizado! Faça login.')
        return redirect('login')
   
    return render(request, 'register.html')

def logout_view(request):
    logout(request)
    return redirect('home')

def password_recovery_view(request):
    return render(request, 'password.recovery.html')

@login_required(login_url='login')
def dashboard_view(request):
    return render(request, 'dashboard.html')    

def list_medicines(request):
    medicines = Medicine.objects.all()
    return render(request, 'medicines.html', {'medicines': medicines})