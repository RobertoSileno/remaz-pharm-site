import re
import uuid
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.utils import timezone
from .models import (
    Address,
    Medicine,
    Category,
    Cart,
    CartItem,
    Pharmacy,
    PharmacyInventory,
    Order,
    OrderItem,
    OrderStatusHistory,
    PaymentTransaction,
    UserProfile,
)
from .forms import (
    AddressForm,
    PharmacyMedicineCreateForm,
    PharmacyRegistrationForm,
    UserProfileForm,
    PaymentForm,
)
from .services.mercado_pago import create_pix_payment
from .services.supabase_storage import upload_image
from django.db.models import Count, Q
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme

GOVBR_SIGNATURE_URL = 'https://assinador.iti.br'
PRESCRIPTION_EXTENSIONS = {'pdf'}
PRESCRIPTION_MAX_SIZE = 10 * 1024 * 1024
PRODUCT_IMAGE_CONTENT_TYPES = {'image/png', 'image/jpeg', 'image/webp'}
PRODUCT_IMAGE_MAX_SIZE = 5 * 1024 * 1024

def normalize_digits(value):
    return re.sub(r'\D', '', (value or '').strip())


def get_display_name(user):
    username = user.username.strip()
    parts = username.split()

    if len(parts) >= 2:
        return f"{parts[0]} {parts[-1]}"

    return username

def get_cart_count(user):
    if not user.is_authenticated:
        return 0

    cart = Cart.objects.filter(user=user).first()
    if not cart:
        return 0

    return sum(item.quantity for item in cart.cartitem_set.all())

def get_cart_items_and_total(user):
    cart, created = Cart.objects.get_or_create(user=user)
    items = list(
        cart.cartitem_set
        .select_related('medicine', 'medicine__category', 'inventory', 'inventory__pharmacy')
        .all()
    )
    total = 0

    for item in items:
        item.unit_price = item.inventory.effective_price if item.inventory else item.medicine.price
        item.pharmacy = item.inventory.pharmacy if item.inventory else None
        item.stock_available = item.inventory.stock if item.inventory else None
        item.subtotal = item.unit_price * item.quantity
        total += item.subtotal

    return cart, items, total

def get_accessible_pharmacies(user):
    pharmacies = Pharmacy.objects.filter(is_active=True)

    if user.is_staff or user.is_superuser:
        return pharmacies

    return pharmacies.filter(owner=user)

def get_accessible_pharmacy_or_404(user, pharmacy_id):
    return get_object_or_404(get_accessible_pharmacies(user), id=pharmacy_id)

def cart_requires_prescription(items):
    return any(item.medicine.tarja == 'preta' for item in items)

def prescription_uploaded(request):
    return bool(request.session.get('prescription_uploaded'))

def clear_prescription_session(request):
    request.session.pop('prescription_uploaded', None)
    request.session.pop('prescription_file', None)

def validate_product_image(image_file):
    if image_file.content_type not in PRODUCT_IMAGE_CONTENT_TYPES:
        return 'Envie uma imagem PNG, JPG, JPEG ou WebP.'

    if image_file.size > PRODUCT_IMAGE_MAX_SIZE:
        return 'A imagem deve ter no maximo 5 MB.'

    return ''

def create_order_status_history(order, to_status, changed_by=None, from_status='', note=''):
    OrderStatusHistory.objects.create(
        order=order,
        from_status=from_status,
        to_status=to_status,
        changed_by=changed_by,
        note=note,
    )

def create_order_payment(order):
    if order.payment_method == 'pix':
        pix_data = create_pix_payment(order)
        return PaymentTransaction.objects.create(
            order=order,
            provider='mercado_pago',
            status=pix_data.get('status', 'pending'),
            payment_method=order.payment_method,
            amount=order.total,
            external_id=pix_data.get('external_id', ''),
            qr_code=pix_data.get('qr_code', ''),
            qr_code_base64=pix_data.get('qr_code_base64', ''),
            payment_url=pix_data.get('payment_url', ''),
            error_message=pix_data.get('error_message', ''),
            raw_response=pix_data.get('raw_response'),
        )

    return PaymentTransaction.objects.create(
        order=order,
        provider='manual',
        status='manual',
        payment_method=order.payment_method,
        amount=order.total,
    )

def home(request):
    return render(request, 'home.html')

def login_view(request):
    if request.method == 'POST':
        email_or_cpf = request.POST['username']  # campo do form
        password = request.POST['password']
        
        user = None
        
        # Verifica se é email (contém @)
        if '@' in email_or_cpf:
            user = User.objects.filter(email=email_or_cpf).first()
        else:
            # Trata como CPF (remove pontos e hífen)
            cpf_limpo = normalize_digits(email_or_cpf)
            try:
                from core.models import UserProfile
                profile = UserProfile.objects.get(cpf=cpf_limpo)
                user = profile.user
            except UserProfile.DoesNotExist:
                pass
        
        # Verifica se o usuário foi encontrado
        if user is None:
            messages.error(request, 'Email/CPF não encontrado')
        elif user.pharmacies.exists():
            messages.error(request, 'Esta conta é de farmácia. Use o login da farmácia.')
        else:
            # Tenta autenticar com a senha
            user_auth = authenticate(request, username=user.username, password=password)
            if user_auth is None:
                messages.error(request, 'Senha incorreta')
            else:
                login(request, user_auth)
                return redirect('dashboard')
    
    return render(request, 'login.html')


def pharmacy_auth_view(request):
    active_tab = request.GET.get('tab', 'login')
    form = PharmacyRegistrationForm()

    if request.method == 'POST':
        form_type = request.POST.get('form_type', 'login')

        if form_type == 'login':
            email_or_cnpj = request.POST.get('username', '').strip()
            password = request.POST.get('password', '')
            user = None

            if '@' in email_or_cnpj:
                user = User.objects.filter(email=email_or_cnpj).first()
            else:
                cnpj_limpo = normalize_digits(email_or_cnpj)
                pharmacy = Pharmacy.objects.filter(cnpj=cnpj_limpo).select_related('owner').first()
                if pharmacy and pharmacy.owner:
                    user = pharmacy.owner

            if user is None:
                messages.error(request, 'Email/CNPJ não encontrado para farmácia')
            elif not user.pharmacies.exists():
                messages.error(request, 'Esta conta não é de farmácia. Use o login de usuário normal.')
            else:
                user_auth = authenticate(request, username=user.username, password=password)
                if user_auth is None:
                    messages.error(request, 'Senha incorreta')
                else:
                    login(request, user_auth)
                    return redirect('pharmacy_dashboard')

        elif form_type == 'register':
            active_tab = 'register'
            username = request.POST.get('username', '').strip()
            email = request.POST.get('email', '').strip()
            password = request.POST.get('password', '')
            password_confirm = request.POST.get('password_confirm', '')
            cnpj = request.POST.get('cnpj', '').strip()
            cnpj_clean = normalize_digits(cnpj)

            post_data = request.POST.copy()
            post_data['name'] = username
            post_data['cnpj'] = cnpj
            form = PharmacyRegistrationForm(post_data, request.FILES)

            if password != password_confirm:
                messages.error(request, 'Senhas não coincidem')
            elif User.objects.filter(username=username).exists():
                messages.error(request, 'Nome de usuário já existe')
            elif User.objects.filter(email=email).exists():
                messages.error(request, 'Este email já está cadastrado. Não pode ser usado para farmácia.')
            elif cnpj_clean and Pharmacy.objects.filter(cnpj=cnpj_clean).exists():
                messages.error(request, 'Este CNPJ já está cadastrado')
            elif form.is_valid():
                user = User.objects.create_user(username=username, email=email, password=password)
                user.save()
                pharmacy = form.save(commit=False)
                pharmacy.owner = user
                pharmacy.is_active = True

                image_file = request.FILES.get('image_file')
                if image_file:
                    image_error = validate_product_image(image_file)
                    if image_error:
                        messages.error(request, image_error)
                        return render(request, 'pharmacy_auth.html', {
                            'active_tab': active_tab,
                            'form': form,
                        })
                    try:
                        pharmacy.logo = upload_image(image_file)
                    except Exception as exc:
                        print('Erro ao enviar logo para Supabase:', exc)
                        messages.error(request, 'Não foi possível enviar a logo. Tente novamente.')
                        return render(request, 'pharmacy_auth.html', {
                            'active_tab': active_tab,
                            'form': form,
                        })

                pharmacy.save()
                from core.models import UserProfile
                UserProfile.objects.create(user=user)
                messages.success(request, 'Cadastro de farmácia realizado com sucesso! Faça login com seu email ou CNPJ.')
                return redirect('pharmacy_auth')
            else:
                messages.error(request, 'Confira os dados da farmácia.')

    return render(request, 'pharmacy_auth.html', {
        'active_tab': active_tab,
        'form': form,
    })


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
        
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email já cadastrado')
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

    inventory_items = PharmacyInventory.objects.select_related(
        'medicine',
        'medicine__category',
        'pharmacy'
    ).filter(
        pharmacy__is_active=True,
        pharmacy__owner__isnull=False,
        is_available=True,
        stock__gt=0,
    )

    if search_query:
        inventory_items = inventory_items.filter(
            Q(medicine__name__icontains=search_query) |
            Q(medicine__description__icontains=search_query) |
            Q(pharmacy__name__icontains=search_query)
        )

    if selected_categories:
        inventory_items = inventory_items.filter(medicine__category_id__in=selected_categories)

    if selected_tarja:
        inventory_items = inventory_items.filter(medicine__tarja__in=selected_tarja)

    inventory_items = inventory_items.order_by('medicine__name', 'price')

    categories = Category.objects.all()

    return render(request, 'dashboard.html', {
        'display_name': display_name,
        'cart_count': get_cart_count(request.user),
        'inventory_items': inventory_items,
        'categories': categories,
        'search_query': search_query,
        'selected_categories': selected_categories,
        'selected_tarja': selected_tarja,
    })
@login_required(login_url='login')
@require_POST
def add_inventory_to_cart(request, inventory_id):
    inventory = get_object_or_404(
        PharmacyInventory,
        id=inventory_id,
        pharmacy__is_active=True,
        pharmacy__owner__isnull=False,
        is_available=True,
    )
    cart, created = Cart.objects.get_or_create(user=request.user)
    next_url = request.POST.get('next')

    if inventory.stock <= 0:
        messages.error(request, 'Produto sem estoque nesta farmácia.')
        return redirect(next_url or 'dashboard')

    item, created = CartItem.objects.get_or_create(
        cart=cart,
        inventory=inventory,
        defaults={'medicine': inventory.medicine}
    )

    if not created:
        if item.quantity >= inventory.stock:
            messages.error(request, 'Quantidade máxima disponível no estoque desta farmácia.')
            return redirect(next_url or 'cart')

        item.quantity += 1
        item.save()

    if inventory.medicine.tarja == 'preta':
        clear_prescription_session(request)

    messages.success(request, f'{inventory.medicine.name} foi adicionado ao carrinho.')

    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure()
    ):
        return redirect(next_url)

    return redirect('cart')


@login_required(login_url='login')
@require_POST
def add_to_cart(request, medicine_id):
    medicine = get_object_or_404(Medicine, id=medicine_id)
    inventory = PharmacyInventory.objects.filter(
        medicine=medicine,
        pharmacy__is_active=True,
        pharmacy__owner__isnull=False,
        is_available=True,
        stock__gt=0,
    ).order_by('price').first()

    if not inventory:
        messages.error(request, 'Produto sem estoque nas farmácias parceiras.')
        return redirect('dashboard')

    return add_inventory_to_cart(request, inventory.id)


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
@require_POST
def clear_cart(request):
    cart = get_object_or_404(Cart, user=request.user)
    cart.cartitem_set.all().delete()
    clear_prescription_session(request)
    messages.success(request, 'Carrinho limpo.')

    return redirect('cart')


@login_required(login_url='login')
def cart_view(request):
    cart, items, total = get_cart_items_and_total(request.user)
    requires_prescription = cart_requires_prescription(items)

    return render(request, 'cart.html', {
        'cart': cart,
        'items': items,
        'total': total,
        'display_name': get_display_name(request.user),
        'cart_count': get_cart_count(request.user),
        'requires_prescription': requires_prescription,
        'prescription_uploaded': prescription_uploaded(request),
    })

@login_required(login_url='login')
def checkout_view(request):
    cart, items, total = get_cart_items_and_total(request.user)
    requires_prescription = cart_requires_prescription(items)
    addresses = request.user.addresses.all()
    default_address = addresses.filter(is_default=True).first()

    if items and requires_prescription and not prescription_uploaded(request):
        messages.error(request, 'Envie a receita assinada pelo gov.br antes de concluir este pedido.')
        return redirect('prescription_upload')

    if request.method == 'POST':
        if not items:
            messages.error(request, 'Seu carrinho está vazio.')
        else:
            for item in items:
                if item.inventory and item.quantity > item.inventory.stock:
                    messages.error(
                        request,
                        f'Estoque insuficiente para {item.medicine.name} em {item.inventory.pharmacy.name}.'
                    )
                    return redirect('cart')

            selected_address = None
            address_id = request.POST.get('address_id')

            if address_id:
                selected_address = Address.objects.filter(user=request.user, id=address_id).first()

            if selected_address:
                recipient_name = selected_address.recipient_name
                phone = selected_address.phone
                zip_code = selected_address.cep
                state = selected_address.state
                city = selected_address.city
                district = selected_address.neighborhood
                street = selected_address.street
                number = selected_address.number
                complement = selected_address.complement or ''
            else:
                recipient_name = request.POST.get('recipient_name') or request.user.username
                phone = request.POST.get('phone') or ''
                zip_code = request.POST.get('zip_code') or ''
                state = request.POST.get('state') or ''
                city = request.POST.get('city') or ''
                district = request.POST.get('district') or ''
                street = request.POST.get('street') or ''
                number = request.POST.get('number') or ''
                complement = request.POST.get('complement') or ''
            delivery_method = request.POST.get('delivery_method') or 'delivery'
            payment_method = request.POST.get('payment_method') or 'pix'
            created_orders = []

            grouped_items = {}
            for item in items:
                grouped_items.setdefault(item.pharmacy, []).append(item)

            with transaction.atomic():
                if request.POST.get('save_address') == 'on' and not selected_address:
                    Address.objects.create(
                        user=request.user,
                        label=request.POST.get('address_label') or 'Principal',
                        recipient_name=recipient_name,
                        phone=phone,
                        cep=zip_code,
                        state=state,
                        city=city,
                        neighborhood=district,
                        street=street,
                        number=number,
                        complement=complement,
                        is_default=request.POST.get('address_default') == 'on',
                    )

                for pharmacy, pharmacy_items in grouped_items.items():
                    order_subtotal = sum(item.subtotal for item in pharmacy_items)
                    has_prescription_item = cart_requires_prescription(pharmacy_items)
                    status = 'waiting_prescription' if has_prescription_item else 'pending'

                    order = Order.objects.create(
                        user=request.user,
                        pharmacy=pharmacy,
                        status=status,
                        customer_name=recipient_name,
                        customer_email=request.user.email,
                        customer_phone=phone,
                        cep=zip_code,
                        state=state,
                        city=city,
                        neighborhood=district,
                        street=street,
                        number=number,
                        complement=complement,
                        notes='',
                        delivery_method=delivery_method,
                        payment_method=payment_method,
                        total=order_subtotal,
                        requires_prescription=has_prescription_item,
                        prescription_status='pending' if has_prescription_item else 'not_required',
                        prescription_file=request.session.get('prescription_file') if has_prescription_item else None,
                    )
                    created_orders.append(order)
                    create_order_status_history(
                        order,
                        status,
                        changed_by=request.user,
                        note='Pedido criado no checkout.',
                    )

                    for item in pharmacy_items:
                        OrderItem.objects.create(
                            order=order,
                            medicine=item.medicine,
                            medicine_name=item.medicine.name,
                            medicine_price=item.unit_price,
                            quantity=item.quantity,
                            tarja=item.medicine.tarja,
                        )

                        if item.inventory:
                            locked_inventory = PharmacyInventory.objects.select_for_update().get(id=item.inventory.id)
                            locked_inventory.stock -= item.quantity
                            locked_inventory.save(update_fields=['stock', 'updated_at'])

                cart.cartitem_set.all().delete()
                clear_prescription_session(request)

            messages.success(request, 'Pedido criado! A farmácia acompanhará a disponibilidade e a receita quando necessário.')
            for order in created_orders:
                payment = create_order_payment(order)
                if payment.payment_method == 'pix' and payment.payment_url:
                    messages.success(request, f'Pedido #{order.id} criado. Use o link Pix exibido em pedidos para pagar.')
                elif payment.status == 'gateway_not_configured':
                    messages.warning(request, f'Pedido #{order.id} criado, mas o gateway Pix ainda nao esta configurado.')

            return redirect('orders')

    return render(request, 'checkout.html', {
        'items': items,
        'total': total,
        'display_name': get_display_name(request.user),
        'cart_count': get_cart_count(request.user),
        'requires_prescription': requires_prescription,
        'prescription_file': request.session.get('prescription_file'),
        'addresses': addresses,
        'default_address': default_address,
    })

@login_required(login_url='login')
def prescription_upload_view(request):
    cart, items, total = get_cart_items_and_total(request.user)
    black_label_items = [item for item in items if item.medicine.tarja == 'preta']

    if not items:
        messages.error(request, 'Seu carrinho está vazio.')
        return redirect('cart')

    if not black_label_items:
        return redirect('checkout')

    if request.method == 'POST':
        prescription_file = request.FILES.get('prescription_file')

        if not prescription_file:
            messages.error(request, 'Selecione a receita digitalizada e assinada antes de continuar.')
        else:
            file_ext = prescription_file.name.rsplit('.', 1)[-1].lower()

            if file_ext not in PRESCRIPTION_EXTENSIONS:
                messages.error(request, 'Envie a receita em formato PDF.')
            elif prescription_file.size > PRESCRIPTION_MAX_SIZE:
                messages.error(request, 'A receita deve ter no máximo 10 MB.')
            else:
                storage = FileSystemStorage(location=str(settings.PRIVATE_MEDIA_ROOT / 'prescriptions'))
                file_name = f'user_{request.user.id}_{uuid.uuid4().hex}.{file_ext}'
                saved_name = storage.save(file_name, prescription_file)

                request.session['prescription_uploaded'] = True
                request.session['prescription_file'] = saved_name
                messages.success(request, 'Receita enviada. Ela será analisada pela farmácia antes da liberação.')

                return redirect('checkout')

    return render(request, 'prescription_upload.html', {
        'items': items,
        'black_label_items': black_label_items,
        'total': total,
        'display_name': get_display_name(request.user),
        'cart_count': get_cart_count(request.user),
        'govbr_signature_url': GOVBR_SIGNATURE_URL,
        'prescription_file': request.session.get('prescription_file'),
    })

@login_required(login_url='login')
def prescription_document_view(request, order_id):
    order = get_object_or_404(Order.objects.select_related('pharmacy'), id=order_id, requires_prescription=True)
    user_can_access = order.user_id == request.user.id

    if not user_can_access and order.pharmacy_id:
        user_can_access = get_accessible_pharmacies(request.user).filter(id=order.pharmacy_id).exists()

    if not user_can_access:
        raise Http404

    if not order.prescription_file:
        raise Http404

    file_name = Path(order.prescription_file).name
    file_path = (settings.PRIVATE_MEDIA_ROOT / 'prescriptions' / file_name).resolve()
    prescriptions_root = (settings.PRIVATE_MEDIA_ROOT / 'prescriptions').resolve()

    if not str(file_path).startswith(str(prescriptions_root)) or not file_path.exists():
        raise Http404

    return FileResponse(open(file_path, 'rb'), content_type='application/pdf')

@login_required(login_url='login')
def orders_view(request):
    orders = request.user.orders.select_related('pharmacy', 'payment_transaction').prefetch_related('items', 'status_history').all()

    return render(request, 'orders.html', {
        'orders': orders,
        'display_name': get_display_name(request.user),
        'cart_count': get_cart_count(request.user),
    })

@login_required(login_url='login')
def pharmacy_dashboard_view(request):
    if request.method == 'POST' and request.POST.get('action') == 'update_logo':
        pharmacy = get_accessible_pharmacy_or_404(request.user, request.POST.get('pharmacy_id'))
        image_file = request.FILES.get('image_file')

        if not image_file:
            messages.error(request, 'Selecione a imagem da farmácia para enviar.')
            return redirect('pharmacy_dashboard')

        image_error = validate_product_image(image_file)
        if image_error:
            messages.error(request, image_error)
            return redirect('pharmacy_dashboard')

        try:
            pharmacy.logo = upload_image(image_file)
            pharmacy.save(update_fields=['logo'])
            messages.success(request, 'Logo da farmácia atualizada com sucesso.')
        except Exception as exc:
            print('Erro ao enviar logo para Supabase:', exc)
            messages.error(request, 'Não foi possível enviar a imagem. Tente novamente.')

        return redirect('pharmacy_dashboard')

    pharmacies = get_accessible_pharmacies(request.user).annotate(
        total_products=Count('inventory_items', distinct=True),
        active_products=Count(
            'inventory_items',
            filter=Q(inventory_items__is_available=True, inventory_items__stock__gt=0),
            distinct=True
        ),
        blocked_products=Count(
            'inventory_items',
            filter=Q(inventory_items__is_available=False) | Q(inventory_items__stock=0),
            distinct=True
        ),
        active_promotions=Count(
            'inventory_items',
            filter=Q(
                inventory_items__promotion_active=True,
                inventory_items__promotional_price__isnull=False,
                inventory_items__stock__gt=0,
                inventory_items__is_available=True,
            ),
            distinct=True
        ),
        pending_orders=Count(
            'orders',
            filter=Q(orders__status__in=['pending', 'waiting_prescription', 'approved']),
            distinct=True
        ),
        pending_prescriptions=Count(
            'orders',
            filter=Q(orders__requires_prescription=True, orders__prescription_status='pending'),
            distinct=True
        ),
    )

    return render(request, 'pharmacy_dashboard.html', {
        'pharmacies': pharmacies,
        'display_name': get_display_name(request.user),
        'cart_count': get_cart_count(request.user),
    })

@login_required(login_url='login')
def pharmacy_register_view(request):
    if request.method == 'POST':
        form = PharmacyRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            pharmacy = form.save(commit=False)
            pharmacy.owner = request.user
            pharmacy.is_active = True

            image_file = request.FILES.get('image_file')
            if image_file:
                image_error = validate_product_image(image_file)
                if image_error:
                    messages.error(request, image_error)
                    return render(request, 'pharmacy_register.html', {
                        'form': form,
                        'display_name': get_display_name(request.user),
                        'cart_count': get_cart_count(request.user),
                    })
                try:
                    pharmacy.logo = upload_image(image_file)
                except Exception as exc:
                    print('Erro ao enviar logo para Supabase:', exc)
                    messages.error(request, 'Não foi possível enviar a imagem. Tente novamente.')
                    return render(request, 'pharmacy_register.html', {
                        'form': form,
                        'display_name': get_display_name(request.user),
                        'cart_count': get_cart_count(request.user),
                    })

            pharmacy.save()
            messages.success(request, 'Farmácia cadastrada. Agora você pode configurar o estoque.')
            return redirect('pharmacy_inventory', pharmacy_id=pharmacy.id)

        messages.error(request, 'Confira os dados da farmácia.')
    else:
        form = PharmacyRegistrationForm()

    return render(request, 'pharmacy_register.html', {
        'form': form,
        'display_name': get_display_name(request.user),
        'cart_count': get_cart_count(request.user),
    })

@login_required(login_url='login')
def pharmacy_inventory_view(request, pharmacy_id):
    pharmacy = get_accessible_pharmacy_or_404(request.user, pharmacy_id)
    new_medicine_form = PharmacyMedicineCreateForm()

    if request.method == 'POST':
        form_action = request.POST.get('form_action')

        if form_action == 'create_medicine':
            new_medicine_form = PharmacyMedicineCreateForm(request.POST, request.FILES)
            if new_medicine_form.is_valid():
                image_file = new_medicine_form.cleaned_data.get('image_file')
                image_url = ''

                if image_file:
                    try:
                        image_url = upload_image(image_file)
                    except Exception as exc:
                        print('Erro ao enviar imagem para Supabase:', exc)
                        messages.error(request, 'Nao foi possivel enviar a imagem para o Supabase. Tente novamente.')
                        return redirect('pharmacy_inventory', pharmacy_id=pharmacy.id)

                medicine, inventory_item = new_medicine_form.save_with_inventory(pharmacy, image_url=image_url)

                if inventory_item.stock == 0:
                    messages.warning(request, f'{medicine.name} foi cadastrado, mas o estoque zero bloqueou a venda.')
                else:
                    messages.success(request, f'{medicine.name} foi cadastrado e adicionado ao estoque.')

                return redirect('pharmacy_inventory', pharmacy_id=pharmacy.id)

            messages.error(request, 'Confira os dados do novo produto.')
        else:
            medicine = get_object_or_404(Medicine, id=request.POST.get('medicine'))
            image_file = request.FILES.get('image_file')
            if image_file:
                image_error = validate_product_image(image_file)
                if image_error:
                    messages.error(request, image_error)
                    return redirect('pharmacy_inventory', pharmacy_id=pharmacy.id)

                try:
                    medicine.image = upload_image(image_file)
                    medicine.save(update_fields=['image'])
                except Exception as exc:
                    print('Erro ao enviar imagem para Supabase:', exc)
                    messages.error(request, 'Nao foi possivel enviar a imagem para o Supabase. Tente novamente.')
                    return redirect('pharmacy_inventory', pharmacy_id=pharmacy.id)

            price = request.POST.get('price') or medicine.price
            stock = int(request.POST.get('stock') or 0)
            is_available = request.POST.get('is_available') == 'on' and stock > 0
            promotional_price = request.POST.get('promotional_price') or None
            promotion_active = request.POST.get('promotion_active') == 'on' and bool(promotional_price)

            inventory_item, created = PharmacyInventory.objects.update_or_create(
                pharmacy=pharmacy,
                medicine=medicine,
                defaults={
                    'price': price,
                    'stock': stock,
                    'is_available': is_available,
                    'promotion_active': promotion_active,
                    'promotion_title': request.POST.get('promotion_title', '').strip(),
                    'promotion_description': request.POST.get('promotion_description', '').strip(),
                    'promotional_price': promotional_price,
                }
            )

            if inventory_item.stock == 0:
                messages.warning(request, 'Estoque salvo em zero. O produto foi bloqueado automaticamente para venda.')
            else:
                messages.success(request, 'Estoque cadastrado.' if created else 'Estoque atualizado.')

            return redirect('pharmacy_inventory', pharmacy_id=pharmacy.id)

    inventory_items = pharmacy.inventory_items.select_related('medicine', 'medicine__category').order_by('medicine__name')
    medicines = Medicine.objects.order_by('name')

    return render(request, 'pharmacy_inventory.html', {
        'pharmacy': pharmacy,
        'inventory_items': inventory_items,
        'medicines': medicines,
        'new_medicine_form': new_medicine_form,
        'display_name': get_display_name(request.user),
        'cart_count': get_cart_count(request.user),
    })

@login_required(login_url='login')
@require_POST
def pharmacy_inventory_update(request, inventory_id):
    inventory_item = get_object_or_404(PharmacyInventory.objects.select_related('pharmacy'), id=inventory_id)
    pharmacy = get_accessible_pharmacy_or_404(request.user, inventory_item.pharmacy.id)
    image_file = request.FILES.get('image_file')

    if image_file:
        image_error = validate_product_image(image_file)
        if image_error:
            messages.error(request, image_error)
            return redirect('pharmacy_inventory', pharmacy_id=pharmacy.id)

        try:
            inventory_item.medicine.image = upload_image(image_file)
            inventory_item.medicine.save(update_fields=['image'])
        except Exception as exc:
            print('Erro ao enviar imagem para Supabase:', exc)
            messages.error(request, 'Nao foi possivel enviar a imagem para o Supabase. Tente novamente.')
            return redirect('pharmacy_inventory', pharmacy_id=pharmacy.id)

    inventory_item.price = request.POST.get('price') or inventory_item.price
    inventory_item.stock = int(request.POST.get('stock') or 0)
    inventory_item.is_available = request.POST.get('is_available') == 'on' and inventory_item.stock > 0
    inventory_item.promotional_price = request.POST.get('promotional_price') or None
    inventory_item.promotion_active = request.POST.get('promotion_active') == 'on' and bool(inventory_item.promotional_price)
    inventory_item.promotion_title = request.POST.get('promotion_title', '').strip()
    inventory_item.promotion_description = request.POST.get('promotion_description', '').strip()
    inventory_item.save()

    if inventory_item.stock == 0:
        messages.warning(request, 'Estoque zerado. O produto foi bloqueado automaticamente para venda.')
    else:
        messages.success(request, 'Estoque atualizado.')

    return redirect('pharmacy_inventory', pharmacy_id=pharmacy.id)

@login_required(login_url='login')
def pharmacy_orders_view(request, pharmacy_id):
    pharmacy = get_accessible_pharmacy_or_404(request.user, pharmacy_id)

    if request.method == 'POST':
        order = get_object_or_404(Order, id=request.POST.get('order_id'), pharmacy=pharmacy)
        status = request.POST.get('status')
        pharmacy_notes = request.POST.get('pharmacy_notes', '').strip()

        if status in dict(Order.STATUS_CHOICES):
            previous_status = order.status
            order.status = status
            order.pharmacy_notes = pharmacy_notes
            order.save(update_fields=['status', 'pharmacy_notes', 'updated_at'])
            if previous_status != status:
                create_order_status_history(
                    order,
                    status,
                    changed_by=request.user,
                    from_status=previous_status,
                    note=pharmacy_notes,
                )
            messages.success(request, f'Pedido #{order.id} atualizado.')

        return redirect('pharmacy_orders', pharmacy_id=pharmacy.id)

    orders = pharmacy.orders.select_related('user').prefetch_related('items').all()

    return render(request, 'pharmacy_orders.html', {
        'pharmacy': pharmacy,
        'orders': orders,
        'status_choices': Order.STATUS_CHOICES,
        'display_name': get_display_name(request.user),
        'cart_count': get_cart_count(request.user),
    })

@login_required(login_url='login')
def pharmacy_prescriptions_view(request, pharmacy_id):
    pharmacy = get_accessible_pharmacy_or_404(request.user, pharmacy_id)

    if request.method == 'POST':
        order = get_object_or_404(
            Order,
            id=request.POST.get('order_id'),
            pharmacy=pharmacy,
            requires_prescription=True,
        )
        action = request.POST.get('action')
        reason = request.POST.get('prescription_review_reason', '').strip()

        if action == 'reject' and not reason:
            messages.error(request, 'Informe o motivo da recusa da receita.')
            return redirect('pharmacy_prescriptions', pharmacy_id=pharmacy.id)

        previous_status = order.status

        if action == 'approve':
            order.prescription_status = 'approved'
            order.status = 'approved'
            order.prescription_review_reason = reason or 'Receita aprovada pela farmacia.'
            messages.success(request, f'Receita do pedido #{order.id} aprovada.')
        elif action == 'reject':
            order.prescription_status = 'rejected'
            order.status = 'rejected'
            order.prescription_review_reason = reason
            order.pharmacy_notes = reason
            messages.success(request, f'Receita do pedido #{order.id} recusada.')
        else:
            messages.error(request, 'Acao invalida para analise da receita.')
            return redirect('pharmacy_prescriptions', pharmacy_id=pharmacy.id)

        order.prescription_reviewed_at = timezone.now()
        order.prescription_reviewed_by = request.user
        order.save(update_fields=[
            'prescription_status',
            'status',
            'prescription_review_reason',
            'prescription_reviewed_at',
            'prescription_reviewed_by',
            'pharmacy_notes',
            'updated_at',
        ])
        if previous_status != order.status:
            create_order_status_history(
                order,
                order.status,
                changed_by=request.user,
                from_status=previous_status,
                note=order.prescription_review_reason,
            )

        return redirect('pharmacy_prescriptions', pharmacy_id=pharmacy.id)

    prescriptions = pharmacy.orders.filter(
        requires_prescription=True,
        prescription_file__isnull=False,
    ).select_related('user', 'prescription_reviewed_by').prefetch_related('items')

    return render(request, 'pharmacy_prescriptions.html', {
        'pharmacy': pharmacy,
        'prescriptions': prescriptions,
        'display_name': get_display_name(request.user),
        'cart_count': get_cart_count(request.user),
    })

@login_required(login_url='login')
def profile_view(request):
    username = request.user.username.strip()
    parts = username.split()

    if len(parts) >= 2:
        display_name = f"{parts[0]} {parts[-1]}"
    else:
        display_name = username

    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    profile_form = UserProfileForm(initial={
        'username': request.user.username,
        'email': request.user.email,
        'cpf': profile.cpf,
        'nickname': profile.nickname,
    })
    address_form = AddressForm(initial={
        'recipient_name': request.user.username,
    })

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'save_profile':
            profile_form = UserProfileForm(request.POST)
            if profile_form.is_valid():
                username_clean = profile_form.cleaned_data['username'].strip()
                email_clean = profile_form.cleaned_data['email'].strip()

                if User.objects.exclude(pk=request.user.pk).filter(username=username_clean).exists():
                    messages.error(request, 'Nome de usuário já está em uso.')
                elif User.objects.exclude(pk=request.user.pk).filter(email=email_clean).exists():
                    messages.error(request, 'Email já está em uso.')
                else:
                    request.user.username = username_clean
                    request.user.email = email_clean
                    request.user.save(update_fields=['username', 'email'])

                    profile.cpf = profile_form.cleaned_data['cpf']
                    profile.nickname = profile_form.cleaned_data['nickname']
                    profile.save(update_fields=['cpf', 'nickname'])
                    messages.success(request, 'Perfil atualizado com sucesso.')
                    return redirect('perfil')
            else:
                messages.error(request, 'Confira os dados do perfil.')

        elif action == 'add_address':
            address_form = AddressForm(request.POST)
            if address_form.is_valid():
                address = address_form.save(commit=False)
                address.user = request.user
                address.save()
                messages.success(request, 'Endereco salvo.')
                return redirect('perfil')

            messages.error(request, 'Confira os dados do endereco.')

        elif action == 'set_default_address':
            address = get_object_or_404(Address, id=request.POST.get('address_id'), user=request.user)
            address.is_default = True
            address.save(update_fields=['is_default', 'updated_at'])
            messages.success(request, 'Endereco principal atualizado.')
            return redirect('perfil')

        elif action == 'delete_address':
            address = get_object_or_404(Address, id=request.POST.get('address_id'), user=request.user)
            address.delete()
            messages.success(request, 'Endereco removido.')
            return redirect('perfil')

    return render(request, 'profile.html', {
        'display_name': display_name,
        'profile_form': profile_form,
        'address_form': address_form,
        'addresses': request.user.addresses.all(),
        'cart_count': get_cart_count(request.user),
        'user_email': request.user.email,
        'user_cpf': profile.cpf,
        'user_nickname': profile.nickname or '',
        'user_username': request.user.username,
    })

@login_required(login_url='login')
def payment_view(request):
    username = request.user.username.strip()
    parts = username.split()
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if len(parts) >= 2:
        display_name = f"{parts[0]} {parts[-1]}"
    else:
        display_name = username

    payment_form = PaymentForm(initial={
        'payment_method': profile.payment_method,
        'card_name': profile.payment_card_owner,
        'card_number': profile.payment_card_last4 and f'**** **** **** {profile.payment_card_last4}' or '',
        'card_expiry': profile.payment_card_expiry,
    })

    if request.method == 'POST' and request.POST.get('action') == 'save_payment':
        payment_form = PaymentForm(request.POST)
        if payment_form.is_valid():
            profile.payment_method = payment_form.cleaned_data['payment_method']
            profile.payment_card_owner = payment_form.cleaned_data['card_name']
            card_number = payment_form.cleaned_data.get('card_number') or ''
            cleaned_number = re.sub(r'\D', '', card_number)
            profile.payment_card_last4 = cleaned_number[-4:] if len(cleaned_number) >= 4 else None
            profile.payment_card_expiry = payment_form.cleaned_data['card_expiry']
            profile.save(update_fields=['payment_method', 'payment_card_owner', 'payment_card_last4', 'payment_card_expiry'])
            messages.success(request, 'Dados de pagamento salvos com sucesso.')
            return redirect('pagamento')
        messages.error(request, 'Confira os dados do pagamento.')

    return render(request, 'payment.html', {
        'display_name': display_name,
        'cart_count': get_cart_count(request.user),
        'payment_form': payment_form,
        'profile': profile,
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
        'display_name': display_name,
        'cart_count': get_cart_count(request.user),
    })
