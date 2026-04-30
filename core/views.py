from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .models import Medicine, Category, Cart, CartItem
from django.db.models import Q
from django.views.decorators.http import require_POST

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

    search_query = request.GET.get('q', '').strip()
    selected_categories = request.GET.getlist('category')
    selected_tarja = request.GET.getlist('tarja')

    medicines = Medicine.objects.select_related('category').all()

    if search_query:
        medicines = medicines.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    if selected_categories:
        medicines = medicines.filter(category_id__in=selected_categories)

    if selected_tarja:
        medicines = medicines.filter(tarja__in=selected_tarja)

    categories = Category.objects.all()

    return render(request, 'dashboard.html', {
        'display_name': display_name,
        'medicines': medicines,
        'categories': categories,
        'search_query': search_query,
        'selected_categories': selected_categories,
        'selected_tarja': selected_tarja,
    })
@login_required(login_url='login')
@require_POST
def add_to_cart(request, medicine_id):
    medicine = get_object_or_404(Medicine, id=medicine_id)

    cart, created = Cart.objects.get_or_create(user=request.user)

    item, created = CartItem.objects.get_or_create(
        cart=cart,
        medicine=medicine
    )

    if not created:
        item.quantity += 1
        item.save()

    return redirect('dashboard')


@login_required(login_url='login')
@require_POST
def decrease_cart_item(request, item_id):
    item = get_object_or_404(
        CartItem,
        id=item_id,
        cart__user=request.user
    )

    if item.quantity > 1:
        item.quantity -= 1
        item.save()
    else:
        item.delete()

    return redirect('cart')


@login_required(login_url='login')
@require_POST
def remove_cart_item(request, item_id):
    item = get_object_or_404(
        CartItem,
        id=item_id,
        cart__user=request.user
    )

    item.delete()

    return redirect('cart')


@login_required(login_url='login')
def cart_view(request):
    cart, created = Cart.objects.get_or_create(user=request.user)

    items = cart.cartitem_set.select_related('medicine').all()

    total = sum(item.medicine.price * item.quantity for item in items)

    return render(request, 'cart.html', {
        'cart': cart,
        'items': items,
        'total': total,
    })

@login_required(login_url='login')
def profile_view(request):
    username = request.user.username.strip()
    parts = username.split()

    if len(parts) >= 2:
        display_name = f"{parts[0]} {parts[-1]}"
    else:
        display_name = username

    return render(request, 'profile.html', {
        'display_name': display_name
    })

@login_required(login_url='login')
def payment_view(request):
    username = request.user.username.strip()
    parts = username.split()

    if len(parts) >= 2:
        display_name = f"{parts[0]} {parts[-1]}"
    else:
        display_name = username

    return render(request, 'payment.html', {
        'display_name': display_name
    })

@login_required(login_url='login')
def help_view(request):
    username = request.user.username.strip()
    parts = username.split()

    if len(parts) >= 2:
        display_name = f"{parts[0]} {parts[-1]}"
    else:
        display_name = username

    return render(request, 'help.html', {
        'display_name': display_name
    })