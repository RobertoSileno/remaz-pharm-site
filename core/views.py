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
        email_or_cpf = request.POST['username']  # campo do form
        password = request.POST['password']
        
        user = None
        
        # Verifica se é email (contém @)
        if '@' in email_or_cpf:
            try:
                user = User.objects.get(email=email_or_cpf)
            except User.DoesNotExist:
                pass
        else:
            # Trata como CPF (remove pontos e hífen)
            cpf_limpo = email_or_cpf.replace('.', '').replace('-', '')
            try:
                from core.models import UserProfile
                profile = UserProfile.objects.get(cpf=cpf_limpo)
                user = profile.user
            except UserProfile.DoesNotExist:
                pass
        
        # Verifica se o usuário foi encontrado
        if user is None:
            messages.error(request, 'Email/CPF não encontrado')
        else:
            # Tenta autenticar com a senha
            user_auth = authenticate(request, username=user.username, password=password)
            if user_auth is None:
                messages.error(request, 'Senha incorreta')
            else:
                login(request, user_auth)
                return redirect('dashboard')
    
    return render(request, 'login.html')

def register_view(request):
    if request.method == 'POST':
        username = request.POST['username']  # Nome completo (ou altere para email se preferir)
        email = request.POST['email']
        password = request.POST['password']
        password_confirm = request.POST['password_confirm']
        cpf = request.POST.get('cpf', '').replace('.', '').replace('-', '')  # Limpa o CPF
        
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
        
        # Criar perfil do usuário com CPF (sem nickname)
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
    username = request.user.username.strip()
    parts = username.split()

    if len(parts) >= 2:
        display_name = f"{parts[0]} {parts[-1]}"
    else:
        display_name = username

    medicines = Medicine.objects.all()  # 👈 pega do banco

    return render(request, 'dashboard.html', {
        'display_name': display_name,
        'medicines': medicines  # 👈 envia pro HTML
    })