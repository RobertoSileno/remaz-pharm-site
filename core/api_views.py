import hashlib
import json
import secrets
import uuid
from datetime import timedelta
from decimal import Decimal
from functools import wraps
from pathlib import Path

from django.conf import settings
from django.contrib.auth import authenticate, password_validation
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import (
    Address,
    Cart,
    CartItem,
    MobileAuthToken,
    Order,
    OrderItem,
    PaymentTransaction,
    PharmacyInventory,
    UserProfile,
)
from .views import create_order_payment, create_order_status_history
from .services.supabase_storage import upload_prescription


TOKEN_LIFETIME = timedelta(days=30)
LOGIN_ATTEMPT_LIMIT = 5
LOGIN_LOCK_SECONDS = 15 * 60
PRESCRIPTION_MAX_SIZE = 10 * 1024 * 1024
PRESCRIPTION_CONTENT_TYPES = {'application/pdf', 'application/octet-stream'}


def api_error(message, status=400, fields=None):
    payload = {'error': message}
    if fields:
        payload['fields'] = fields
    return JsonResponse(payload, status=status)


def parse_payload(request):
    if request.content_type and request.content_type.startswith('multipart/form-data'):
        return request.POST.dict()
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def clean_cpf(value):
    return ''.join(character for character in (value or '') if character.isdigit())


def valid_cpf(value):
    if len(value) != 11 or value == value[0] * 11:
        return False
    for length in (9, 10):
        total = sum(int(value[index]) * (length + 1 - index) for index in range(length))
        digit = (total * 10 % 11) % 10
        if digit != int(value[length]):
            return False
    return True


def issue_token(user):
    raw_token = secrets.token_urlsafe(40)
    MobileAuthToken.objects.create(
        user=user,
        key_hash=hashlib.sha256(raw_token.encode('utf-8')).hexdigest(),
        expires_at=timezone.now() + TOKEN_LIFETIME,
    )
    return raw_token


def login_attempt_key(request, identifier):
    remote_address = request.META.get('REMOTE_ADDR', '')
    digest = hashlib.sha256(f'{remote_address}:{identifier.lower()}'.encode('utf-8')).hexdigest()
    return f'mobile_login_attempts:{digest}'


def mobile_auth_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        header = request.headers.get('Authorization', '')
        prefix, separator, raw_token = header.partition(' ')
        if not separator or prefix.lower() != 'bearer' or not raw_token:
            return api_error('Autenticacao necessaria.', status=401)

        token = MobileAuthToken.objects.select_related('user').filter(
            key_hash=hashlib.sha256(raw_token.encode('utf-8')).hexdigest(),
            revoked_at__isnull=True,
            expires_at__gt=timezone.now(),
            user__is_active=True,
        ).first()
        if not token:
            return api_error('Sessao expirada ou invalida.', status=401)

        request.mobile_user = token.user
        request.mobile_token = token
        if not token.last_used_at or token.last_used_at < timezone.now() - timedelta(minutes=10):
            token.last_used_at = timezone.now()
            token.save(update_fields=['last_used_at'])
        return view(request, *args, **kwargs)

    return wrapped


def serialize_user(user):
    profile = getattr(user, 'profile', None)
    return {
        'id': user.id,
        'name': user.username,
        'email': user.email,
        'cpf': profile.cpf if profile else '',
        'nickname': profile.nickname if profile else '',
    }


def serialize_address(address):
    return {
        'id': address.id,
        'label': address.label,
        'recipient_name': address.recipient_name,
        'phone': address.phone,
        'cep': address.cep,
        'state': address.state,
        'city': address.city,
        'neighborhood': address.neighborhood,
        'street': address.street,
        'number': address.number,
        'complement': address.complement or '',
        'is_default': address.is_default,
        'summary': address.summary,
    }


def visible_inventories():
    return PharmacyInventory.objects.filter(
        pharmacy__is_active=True,
        pharmacy__owner__isnull=False,
        is_available=True,
        stock__gt=0,
    ).select_related('pharmacy', 'medicine', 'medicine__category')


def serialize_inventory(inventory):
    return {
        'id': inventory.id,
        'medicine_id': inventory.medicine_id,
        'name': inventory.medicine.name,
        'description': inventory.medicine.description,
        'image': inventory.medicine.image or '',
        'category': inventory.medicine.category.name,
        'tarja': inventory.medicine.tarja,
        'requires_prescription': inventory.medicine.tarja == 'preta',
        'pharmacy': {
            'id': inventory.pharmacy_id,
            'name': inventory.pharmacy.name,
            'logo': inventory.pharmacy.logo or '',
        },
        'stock': inventory.stock,
        'price': str(inventory.price),
        'effective_price': str(inventory.effective_price),
        'promotion': {
            'active': inventory.has_active_promotion,
            'title': inventory.promotion_title,
            'description': inventory.promotion_description,
        },
    }


def user_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    items = list(
        cart.cartitem_set.select_related(
            'inventory',
            'inventory__pharmacy',
            'medicine',
            'medicine__category',
        )
    )
    total = Decimal('0.00')
    result = []
    for item in items:
        if not item.inventory:
            continue
        price = item.inventory.effective_price
        subtotal = price * item.quantity
        total += subtotal
        result.append({
            'id': item.id,
            'quantity': item.quantity,
            'subtotal': str(subtotal),
            'inventory': serialize_inventory(item.inventory),
        })
    return cart, result, total


def cart_response(user):
    _, items, total = user_cart(user)
    return JsonResponse({
        'items': items,
        'total': str(total),
        'requires_prescription': any(item['inventory']['requires_prescription'] for item in items),
    })


def serialize_payment(payment):
    if not payment:
        return None
    return {
        'method': payment.payment_method,
        'status': payment.status,
        'amount': str(payment.amount),
        'qr_code': payment.qr_code,
        'qr_code_base64': payment.qr_code_base64,
        'payment_url': payment.payment_url,
        'error_message': payment.error_message,
    }


def serialize_order(order):
    payment = getattr(order, 'payment_transaction', None)
    return {
        'id': order.id,
        'pharmacy': order.pharmacy.name if order.pharmacy else '',
        'status': order.status,
        'status_label': order.get_status_display(),
        'total': str(order.total),
        'delivery_method': order.delivery_method,
        'payment_method': order.payment_method,
        'requires_prescription': order.requires_prescription,
        'prescription_status': order.prescription_status,
        'created_at': order.created_at.isoformat(),
        'items': [
            {
                'name': item.medicine_name,
                'quantity': item.quantity,
                'price': str(item.medicine_price),
                'subtotal': str(item.subtotal),
            }
            for item in order.items.all()
        ],
        'payment': serialize_payment(payment),
        'history': [
            {
                'status': history.to_status,
                'note': history.note,
                'created_at': history.created_at.isoformat(),
            }
            for history in order.status_history.all()
        ],
    }


def address_from_payload(user, payload):
    required_fields = (
        'recipient_name',
        'phone',
        'cep',
        'state',
        'city',
        'neighborhood',
        'street',
        'number',
    )
    missing = [field for field in required_fields if not str(payload.get(field, '')).strip()]
    if missing:
        return None, {'address': f'Preencha: {", ".join(missing)}.'}
    values = {
        'recipient_name': str(payload['recipient_name']).strip(),
        'phone': str(payload['phone']).strip(),
        'cep': str(payload['cep']).strip(),
        'state': str(payload['state']).strip().upper(),
        'city': str(payload['city']).strip(),
        'neighborhood': str(payload['neighborhood']).strip(),
        'street': str(payload['street']).strip(),
        'number': str(payload['number']).strip(),
        'complement': str(payload.get('complement', '')).strip(),
    }
    candidate = Address(
        user=user,
        label=str(payload.get('label', 'Principal')).strip() or 'Principal',
        **values,
    )
    try:
        candidate.full_clean()
    except ValidationError as exc:
        return None, {key: ' '.join(messages) for key, messages in exc.message_dict.items()}
    return values, None


@csrf_exempt
@require_http_methods(['GET'])
def api_health(request):
    try:
        User.objects.only('id').exists()
    except Exception:
        return api_error('Banco de dados indisponivel.', status=503)
    return JsonResponse({'status': 'ok', 'database': 'connected'})


@csrf_exempt
@require_http_methods(['POST'])
def api_register(request):
    payload = parse_payload(request)
    if payload is None:
        return api_error('JSON invalido.')

    name = str(payload.get('name', '')).strip()
    email = str(payload.get('email', '')).strip().lower()
    cpf = clean_cpf(payload.get('cpf'))
    password = str(payload.get('password', ''))
    if not name or not email or not password or not cpf:
        return api_error('Nome, CPF, e-mail e senha sao obrigatorios.')
    try:
        validate_email(email)
    except ValidationError:
        return api_error('E-mail invalido.', fields={'email': 'Informe um e-mail valido.'})
    if not valid_cpf(cpf):
        return api_error('CPF invalido.', fields={'cpf': 'Informe um CPF valido.'})
    if User.objects.filter(Q(email__iexact=email) | Q(username=name)).exists():
        return api_error('Nome ou e-mail ja cadastrado.', status=409)
    if UserProfile.objects.filter(cpf=cpf).exists():
        return api_error('CPF ja cadastrado.', status=409)

    user = User(username=name, email=email)
    try:
        password_validation.validate_password(password, user)
    except ValidationError as exc:
        return api_error('Senha nao atende aos requisitos de seguranca.', fields={'password': list(exc.messages)})

    try:
        with transaction.atomic():
            user.set_password(password)
            user.save()
            UserProfile.objects.create(user=user, cpf=cpf)
            token = issue_token(user)
    except IntegrityError:
        return api_error('Nao foi possivel concluir o cadastro com estes dados.', status=409)
    return JsonResponse({'token': token, 'user': serialize_user(user)}, status=201)


@csrf_exempt
@require_http_methods(['POST'])
def api_login(request):
    payload = parse_payload(request)
    if payload is None:
        return api_error('JSON invalido.')
    identifier = str(payload.get('identifier', '')).strip()
    password = str(payload.get('password', ''))
    attempt_key = login_attempt_key(request, identifier)
    attempts = cache.get(attempt_key, 0)
    if attempts >= LOGIN_ATTEMPT_LIMIT:
        return api_error('Muitas tentativas. Aguarde alguns minutos.', status=429)
    if '@' in identifier:
        user = User.objects.filter(email__iexact=identifier).first()
    else:
        profile = UserProfile.objects.select_related('user').filter(cpf=clean_cpf(identifier)).first()
        user = profile.user if profile else None
    authenticated = authenticate(username=user.username, password=password) if user else None
    if not authenticated:
        cache.set(attempt_key, attempts + 1, LOGIN_LOCK_SECONDS)
        return api_error('Credenciais invalidas.', status=401)
    cache.delete(attempt_key)
    return JsonResponse({'token': issue_token(authenticated), 'user': serialize_user(authenticated)})


@csrf_exempt
@require_http_methods(['POST'])
@mobile_auth_required
def api_logout(request):
    request.mobile_token.revoked_at = timezone.now()
    request.mobile_token.save(update_fields=['revoked_at'])
    return JsonResponse({'status': 'ok'})


@csrf_exempt
@require_http_methods(['GET'])
@mobile_auth_required
def api_me(request):
    return JsonResponse({'user': serialize_user(request.mobile_user)})


@csrf_exempt
@require_http_methods(['GET'])
@mobile_auth_required
def api_catalog(request):
    query = request.GET.get('q', '').strip()
    category_ids = [
        category_id for category_id in request.GET.getlist('category')
        if category_id.isdigit()
    ]
    tarjas = [
        tarja for tarja in request.GET.getlist('tarja')
        if tarja in {'sem', 'vermelha', 'preta'}
    ]
    inventory = visible_inventories()
    if query:
        inventory = inventory.filter(
            Q(medicine__name__icontains=query)
            | Q(medicine__description__icontains=query)
            | Q(medicine__category__name__icontains=query)
            | Q(pharmacy__name__icontains=query)
        )
    if category_ids:
        inventory = inventory.filter(medicine__category_id__in=category_ids)
    if tarjas:
        inventory = inventory.filter(medicine__tarja__in=tarjas)

    categories = visible_inventories().values(
        'medicine__category_id',
        'medicine__category__name',
    ).distinct().order_by('medicine__category__name')
    return JsonResponse({
        'results': [serialize_inventory(item) for item in inventory.order_by('medicine__name', 'price')],
        'categories': [
            {'id': item['medicine__category_id'], 'name': item['medicine__category__name']}
            for item in categories
        ],
    })


@csrf_exempt
@require_http_methods(['GET'])
@mobile_auth_required
def api_cart(request):
    return cart_response(request.mobile_user)


@csrf_exempt
@require_http_methods(['POST'])
@mobile_auth_required
def api_cart_add(request):
    payload = parse_payload(request)
    if payload is None:
        return api_error('JSON invalido.')
    try:
        inventory_id = int(payload.get('inventory_id'))
        amount = max(1, int(payload.get('quantity', 1)))
    except (TypeError, ValueError):
        return api_error('Produto invalido.')

    with transaction.atomic():
        inventory = visible_inventories().select_for_update().filter(id=inventory_id).first()
        if not inventory:
            return api_error('Produto indisponivel.', status=404)
        cart, _ = Cart.objects.get_or_create(user=request.mobile_user)
        item, created = CartItem.objects.get_or_create(
            cart=cart,
            inventory=inventory,
            defaults={'medicine': inventory.medicine, 'quantity': amount},
        )
        next_quantity = amount if created else item.quantity + amount
        if next_quantity > inventory.stock:
            if created:
                item.delete()
            return api_error('Quantidade maior que o estoque disponivel.')
        if not created:
            item.quantity = next_quantity
            item.save(update_fields=['quantity'])
    return cart_response(request.mobile_user)


@csrf_exempt
@require_http_methods(['PATCH', 'DELETE'])
@mobile_auth_required
def api_cart_item(request, item_id):
    item = CartItem.objects.filter(id=item_id, cart__user=request.mobile_user).select_related('inventory').first()
    if not item:
        return api_error('Item nao encontrado.', status=404)
    if request.method == 'DELETE':
        item.delete()
        return cart_response(request.mobile_user)
    payload = parse_payload(request)
    try:
        quantity = int(payload.get('quantity'))
    except (AttributeError, TypeError, ValueError):
        return api_error('Quantidade invalida.')
    if quantity <= 0:
        item.delete()
    elif not item.inventory or quantity > item.inventory.stock:
        return api_error('Quantidade maior que o estoque disponivel.')
    else:
        item.quantity = quantity
        item.save(update_fields=['quantity'])
    return cart_response(request.mobile_user)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
@mobile_auth_required
def api_addresses(request):
    if request.method == 'GET':
        return JsonResponse({'addresses': [serialize_address(item) for item in request.mobile_user.addresses.all()]})
    payload = parse_payload(request)
    values, errors = address_from_payload(request.mobile_user, payload or {})
    if errors:
        return api_error('Endereco incompleto.', fields=errors)
    address = Address.objects.create(
        user=request.mobile_user,
        label=str(payload.get('label', 'Principal')).strip() or 'Principal',
        is_default=bool(payload.get('is_default', False)),
        **values,
    )
    return JsonResponse({'address': serialize_address(address)}, status=201)


@csrf_exempt
@require_http_methods(['PATCH', 'DELETE'])
@mobile_auth_required
def api_address(request, address_id):
    address = Address.objects.filter(id=address_id, user=request.mobile_user).first()
    if not address:
        return api_error('Endereco nao encontrado.', status=404)
    if request.method == 'DELETE':
        address.delete()
        return JsonResponse({'status': 'ok'})
    payload = parse_payload(request) or {}
    if payload.get('is_default') is True:
        address.is_default = True
        address.save(update_fields=['is_default', 'updated_at'])
        return JsonResponse({'address': serialize_address(address)})
    return api_error('Atualizacao invalida.')


def validate_prescription(upload):
    if not upload:
        return 'Envie a receita assinada em PDF.'
    if Path(upload.name).suffix.lower() != '.pdf':
        return 'A receita deve estar em formato PDF.'
    if upload.size > PRESCRIPTION_MAX_SIZE:
        return 'A receita deve ter no maximo 10 MB.'
    if upload.content_type not in PRESCRIPTION_CONTENT_TYPES:
        return 'O arquivo enviado nao foi reconhecido como PDF.'
    signature = upload.read(5)
    upload.seek(0)
    if signature != b'%PDF-':
        return 'O arquivo enviado nao e um PDF valido.'
    return ''


@csrf_exempt
@require_http_methods(['POST'])
@mobile_auth_required
def api_checkout(request):
    payload = parse_payload(request)
    if payload is None:
        return api_error('Dados invalidos.')
    cart, items, _ = user_cart(request.mobile_user)
    if not items:
        return api_error('Seu carrinho esta vazio.')
    requires_prescription = any(item['inventory']['requires_prescription'] for item in items)
    prescription_upload = request.FILES.get('prescription_file')
    if requires_prescription:
        prescription_error = validate_prescription(prescription_upload)
        if prescription_error:
            return api_error(prescription_error, fields={'prescription_file': prescription_error})

    payment_method = payload.get('payment_method', 'pix')
    delivery_method = payload.get('delivery_method', 'delivery')
    if payment_method not in {'pix', 'cash'}:
        return api_error('Utilize Pix ou dinheiro ate a integracao segura de cartoes.')
    if delivery_method not in dict(Order.DELIVERY_CHOICES):
        return api_error('Metodo de entrega invalido.')

    selected_address = None
    if payload.get('address_id'):
        selected_address = Address.objects.filter(id=payload['address_id'], user=request.mobile_user).first()
        if not selected_address:
            return api_error('Endereco invalido.')
        delivery = {
            'recipient_name': selected_address.recipient_name,
            'phone': selected_address.phone,
            'cep': selected_address.cep,
            'state': selected_address.state,
            'city': selected_address.city,
            'neighborhood': selected_address.neighborhood,
            'street': selected_address.street,
            'number': selected_address.number,
            'complement': selected_address.complement or '',
        }
    else:
        delivery, errors = address_from_payload(request.mobile_user, payload)
        if errors:
            return api_error('Informe um endereco de entrega.', fields=errors)

    prescription_name = None
    if prescription_upload:
        try:
            prescription_name = upload_prescription(prescription_upload, request.mobile_user.id)
        except Exception as e:
            logger.exception(f'Falha ao fazer upload da receita para Supabase: {str(e)}')
            return api_error('Nao foi possivel enviar a receita. Tente novamente.')

    created_orders = []
    try:
        with transaction.atomic():
            if not selected_address and str(payload.get('save_address', '')).lower() in ('true', '1', 'on'):
                Address.objects.create(
                    user=request.mobile_user,
                    label=str(payload.get('label', 'Principal')).strip() or 'Principal',
                    is_default=str(payload.get('is_default', '')).lower() in ('true', '1', 'on'),
                    **delivery,
                )

            grouped = {}
            for item in cart.cartitem_set.select_related('inventory', 'medicine').all():
                if not item.inventory_id:
                    raise ValueError('Item sem farmacia vinculada.')
                locked = visible_inventories().select_for_update().filter(id=item.inventory_id).first()
                if not locked or item.quantity > locked.stock:
                    raise ValueError(f'Estoque indisponivel para {item.medicine.name}.')
                grouped.setdefault(locked.pharmacy, []).append((item, locked))

            for pharmacy, pharmacy_items in grouped.items():
                order_total = sum(inventory.effective_price * item.quantity for item, inventory in pharmacy_items)
                has_prescription = any(item.medicine.tarja == 'preta' for item, _ in pharmacy_items)
                status = 'waiting_prescription' if has_prescription else 'pending'
                order = Order.objects.create(
                    user=request.mobile_user,
                    pharmacy=pharmacy,
                    status=status,
                    payment_method=payment_method,
                    total=order_total,
                    requires_prescription=has_prescription,
                    customer_name=delivery['recipient_name'],
                    customer_email=request.mobile_user.email,
                    customer_phone=delivery['phone'],
                    cep=delivery['cep'],
                    state=delivery['state'],
                    city=delivery['city'],
                    neighborhood=delivery['neighborhood'],
                    street=delivery['street'],
                    number=delivery['number'],
                    complement=delivery['complement'],
                    delivery_method=delivery_method,
                    prescription_file=prescription_name if has_prescription else None,
                    prescription_status='pending' if has_prescription else 'not_required',
                )
                create_order_status_history(order, status, changed_by=request.mobile_user, note='Pedido criado pelo aplicativo.')
                for item, inventory in pharmacy_items:
                    OrderItem.objects.create(
                        order=order,
                        medicine=item.medicine,
                        medicine_name=item.medicine.name,
                        medicine_price=inventory.effective_price,
                        quantity=item.quantity,
                        tarja=item.medicine.tarja,
                    )
                    inventory.stock -= item.quantity
                    inventory.save(update_fields=['stock', 'updated_at'])
                created_orders.append(order)
            cart.cartitem_set.all().delete()
    except ValueError as exc:
        return api_error(str(exc), status=409)

    for order in created_orders:
        create_order_payment(order)
    orders = Order.objects.filter(id__in=[order.id for order in created_orders]).select_related(
        'pharmacy', 'payment_transaction'
    ).prefetch_related('items', 'status_history')
    return JsonResponse({'orders': [serialize_order(order) for order in orders]}, status=201)


@csrf_exempt
@require_http_methods(['GET'])
@mobile_auth_required
def api_orders(request):
    orders = request.mobile_user.orders.select_related('pharmacy', 'payment_transaction').prefetch_related(
        'items', 'status_history'
    )
    return JsonResponse({'orders': [serialize_order(order) for order in orders]})
