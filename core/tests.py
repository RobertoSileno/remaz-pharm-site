import hashlib
import json
import tempfile
from pathlib import Path

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from .models import Category, MobileAuthToken, Order, Pharmacy, PharmacyInventory, Medicine
from .views import validate_prescription_file


class MobileApiTests(TestCase):
    def setUp(self):
        self.private_media = tempfile.TemporaryDirectory()
        self.private_media_settings = self.settings(PRIVATE_MEDIA_ROOT=Path(self.private_media.name))
        self.private_media_settings.enable()
        self.client = Client()
        self.owner = User.objects.create_user('Farmacia Responsavel', password='Owner-password-2026!')
        self.category = Category.objects.create(name='Medicamentos')
        self.pharmacy = Pharmacy.objects.create(owner=self.owner, name='Remaz Centro', is_active=True)
        self.common = Medicine.objects.create(
            name='Dipirona',
            description='Alivio de dor',
            price='12.50',
            category=self.category,
            tarja='sem',
        )
        self.controlled = Medicine.objects.create(
            name='Controlado',
            description='Medicamento controlado',
            price='40.00',
            category=self.category,
            tarja='preta',
        )
        self.common_inventory = PharmacyInventory.objects.create(
            pharmacy=self.pharmacy,
            medicine=self.common,
            price='11.50',
            stock=5,
        )
        self.controlled_inventory = PharmacyInventory.objects.create(
            pharmacy=self.pharmacy,
            medicine=self.controlled,
            price='39.00',
            stock=2,
        )

    def tearDown(self):
        self.private_media_settings.disable()
        self.private_media.cleanup()

    def register_customer(self):
        response = self.client.post(
            '/api/auth/register/',
            data=json.dumps({
                'name': 'Maria Cliente',
                'cpf': '529.982.247-25',
                'email': 'maria@example.com',
                'password': 'Compra-Segura-2026!',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201, response.content)
        token = response.json()['token']
        return {'HTTP_AUTHORIZATION': f'Bearer {token}'}, token

    def add_to_cart(self, headers, inventory):
        response = self.client.post(
            '/api/cart/items/',
            data=json.dumps({'inventory_id': inventory.id}),
            content_type='application/json',
            **headers,
        )
        self.assertEqual(response.status_code, 200, response.content)
        return response

    def checkout_payload(self):
        return {
            'recipient_name': 'Maria Cliente',
            'phone': '(92) 99999-9999',
            'cep': '69000-000',
            'state': 'AM',
            'city': 'Manaus',
            'neighborhood': 'Centro',
            'street': 'Rua Principal',
            'number': '100',
            'delivery_method': 'delivery',
            'payment_method': 'cash',
        }

    def test_register_issues_hashed_revocable_token(self):
        headers, token = self.register_customer()

        saved_token = MobileAuthToken.objects.get()
        self.assertNotEqual(saved_token.key_hash, token)
        self.assertEqual(saved_token.key_hash, hashlib.sha256(token.encode('utf-8')).hexdigest())
        self.assertEqual(self.client.get('/api/me/', **headers).status_code, 200)

        logout = self.client.post('/api/auth/logout/', **headers)
        self.assertEqual(logout.status_code, 200)
        self.assertEqual(self.client.get('/api/me/', **headers).status_code, 401)

    def test_registration_rejects_invalid_email(self):
        response = self.client.post(
            '/api/auth/register/',
            data=json.dumps({
                'name': 'Maria Cliente',
                'cpf': '529.982.247-25',
                'email': 'email-invalido',
                'password': 'Compra-Segura-2026!',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(User.objects.filter(username='Maria Cliente').count(), 0)

    def test_address_api_validates_model_field_lengths(self):
        headers, _ = self.register_customer()
        payload = self.checkout_payload()
        payload['label'] = 'Casa'
        payload['street'] = 'R' * 151

        response = self.client.post(
            '/api/addresses/',
            data=json.dumps(payload),
            content_type='application/json',
            **headers,
        )

        self.assertEqual(response.status_code, 400)

    def test_login_is_temporarily_limited_after_repeated_failures(self):
        self.register_customer()
        for _ in range(5):
            response = self.client.post(
                '/api/auth/login/',
                data=json.dumps({'identifier': 'maria@example.com', 'password': 'errada'}),
                content_type='application/json',
            )
            self.assertEqual(response.status_code, 401)

        blocked = self.client.post(
            '/api/auth/login/',
            data=json.dumps({'identifier': 'maria@example.com', 'password': 'Compra-Segura-2026!'}),
            content_type='application/json',
        )
        self.assertEqual(blocked.status_code, 429)

    def test_catalog_only_exposes_sellable_owned_pharmacy_inventory(self):
        ownerless = Pharmacy.objects.create(name='Farmacia Legada', is_active=True)
        hidden_medicine = Medicine.objects.create(
            name='Produto Fantasma',
            description='Nao deve aparecer',
            price='9.00',
            category=self.category,
            tarja='sem',
        )
        PharmacyInventory.objects.create(pharmacy=ownerless, medicine=hidden_medicine, price='9.00', stock=20)
        headers, _ = self.register_customer()

        response = self.client.get('/api/catalog/', **headers)

        self.assertEqual(response.status_code, 200)
        names = [item['name'] for item in response.json()['results']]
        self.assertIn('Dipirona', names)
        self.assertNotIn('Produto Fantasma', names)

    def test_customer_can_checkout_and_stock_is_reduced_atomically(self):
        headers, _ = self.register_customer()
        self.add_to_cart(headers, self.common_inventory)

        response = self.client.post(
            '/api/checkout/',
            data=json.dumps(self.checkout_payload()),
            content_type='application/json',
            **headers,
        )

        self.assertEqual(response.status_code, 201, response.content)
        self.common_inventory.refresh_from_db()
        self.assertEqual(self.common_inventory.stock, 4)
        order = Order.objects.get()
        self.assertFalse(order.requires_prescription)
        self.assertEqual(order.payment_transaction.status, 'manual')

    def test_controlled_medicine_requires_valid_pdf_prescription(self):
        headers, _ = self.register_customer()
        self.add_to_cart(headers, self.controlled_inventory)

        missing_file = self.client.post(
            '/api/checkout/',
            data=self.checkout_payload(),
            **headers,
        )
        self.assertEqual(missing_file.status_code, 400)

        payload = self.checkout_payload()
        payload['prescription_file'] = SimpleUploadedFile(
            'receita.pdf',
            b'%PDF-1.4\n% signed prescription document',
            content_type='application/pdf',
        )
        response = self.client.post('/api/checkout/', data=payload, **headers)

        self.assertEqual(response.status_code, 201, response.content)
        order = Order.objects.get()
        self.assertTrue(order.requires_prescription)
        self.assertEqual(order.status, 'waiting_prescription')
        self.assertTrue(order.prescription_file.endswith('.pdf'))


class PrescriptionValidationTests(TestCase):
    def test_fake_pdf_is_rejected_even_with_pdf_extension(self):
        fake_pdf = SimpleUploadedFile('receita.pdf', b'not actually pdf', content_type='application/pdf')

        self.assertEqual(validate_prescription_file(fake_pdf), 'O arquivo enviado nao e um PDF valido.')
