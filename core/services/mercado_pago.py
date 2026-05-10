import uuid
from decimal import Decimal

import requests
from django.conf import settings


MERCADO_PAGO_PAYMENT_URL = 'https://api.mercadopago.com/v1/payments'


def create_pix_payment(order):
    access_token = getattr(settings, 'MERCADO_PAGO_ACCESS_TOKEN', '')

    if not access_token:
        return {
            'configured': False,
            'status': 'gateway_not_configured',
            'error_message': 'Defina MERCADO_PAGO_ACCESS_TOKEN no .env para gerar Pix real.',
        }

    amount = order.total
    if isinstance(amount, Decimal):
        amount = float(amount)

    payload = {
        'transaction_amount': amount,
        'description': f'Remaz Pharm - Pedido #{order.id}',
        'payment_method_id': 'pix',
        'payer': {
            'email': order.customer_email or order.user.email or f'cliente-{order.user_id}@example.com',
            'first_name': order.customer_name,
        },
        'external_reference': str(order.id),
    }
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'X-Idempotency-Key': f'order-{order.id}-{uuid.uuid4()}',
    }

    try:
        response = requests.post(
            MERCADO_PAGO_PAYMENT_URL,
            json=payload,
            headers=headers,
            timeout=20,
        )
        data = response.json() if response.content else {}
    except requests.RequestException as exc:
        return {
            'configured': True,
            'status': 'error',
            'error_message': str(exc),
        }

    if response.status_code >= 400:
        return {
            'configured': True,
            'status': 'error',
            'raw_response': data,
            'error_message': data.get('message') or 'Erro ao criar pagamento Pix.',
        }

    point_of_interaction = data.get('point_of_interaction') or {}
    transaction_data = point_of_interaction.get('transaction_data') or {}

    return {
        'configured': True,
        'status': data.get('status') or 'pending',
        'external_id': str(data.get('id') or ''),
        'qr_code': transaction_data.get('qr_code') or '',
        'qr_code_base64': transaction_data.get('qr_code_base64') or '',
        'payment_url': transaction_data.get('ticket_url') or '',
        'raw_response': data,
        'error_message': '',
    }
