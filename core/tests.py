import hashlib
import json
import tempfile
from pathlib import Path

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from .models import Category, MobileAuthToken, Order, Pharmacy, PharmacyInventory, Medicine, UserProfile
from .views import validate_prescription_file


class MobileApiTests(TestCase):
    def setUp(self):
        self.private_media = tempfile.TemporaryDirectory()
        self.private_media_settings = self.settings(PRIVATE_MEDIA_ROOT=Path(self.private_media.name))
        self.private_media_settings.enable()
        self.client = Client()
        self.owner = User.objects.create_user(
            'Farmacia Responsavel',
            email='responsavel@farmacia.test',
            password='Owner-password-2026!',
        )
        self.category = Category.objects.create(name='Medicamentos')
        self.pharmacy = Pharmacy.objects.create(
            owner=self.owner,
            name='Remaz Centro',
            logo='https://storage.example/remacenter.png',
            is_active=True,
        )
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

    def test_registration_rejects_invalid_cpf(self):
        response = self.client.post(
            '/api/auth/register/',
            data=json.dumps({
                'name': 'Mario Cliente',
                'cpf': '032.765.452-08',
                'email': 'mario@example.com',
                'password': 'Compra-Segura-2026!',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'CPF invalido.')
        self.assertFalse(User.objects.filter(email='mario@example.com').exists())

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

    def test_mobile_login_allows_pharmacy_owner_as_customer(self):
        response = self.client.post(
            '/api/auth/login/',
            data=json.dumps({
                'identifier': 'responsavel@farmacia.test',
                'password': 'Owner-password-2026!',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        token = response.json()['token']
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}
        self.assertTrue(MobileAuthToken.objects.filter(user=self.owner).exists())
        self.assertEqual(self.client.get('/api/catalog/', **headers).status_code, 200)

    def test_pharmacy_registration_normalizes_cnpj_used_for_login(self):
        register_response = self.client.post('/farmacia/auth/', data={
            'form_type': 'register',
            'username': 'Farmacia Nova',
            'email': 'nova@farmacia.test',
            'password': 'Cadastro-Seguro-2026!',
            'password_confirm': 'Cadastro-Seguro-2026!',
            'cnpj': '11.222.333/0001-81',
        })

        self.assertRedirects(register_response, '/farmacia/auth/', fetch_redirect_response=False)
        self.assertTrue(Pharmacy.objects.filter(cnpj='11222333000181').exists())

        login_response = self.client.post('/farmacia/auth/', data={
            'form_type': 'login',
            'username': '11.222.333/0001-81',
            'password': 'Cadastro-Seguro-2026!',
        })

        self.assertRedirects(login_response, '/farmacia/', fetch_redirect_response=False)

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

        response = self.client.get('/api/catalog/?tarja=sem', **headers)

        self.assertEqual(response.status_code, 200)
        result = response.json()
        names = [item['name'] for item in result['results']]
        self.assertIn('Dipirona', names)
        self.assertNotIn('Controlado', names)
        self.assertNotIn('Produto Fantasma', names)
        self.assertEqual(result['results'][0]['pharmacy']['logo'], 'https://storage.example/remacenter.png')
        self.assertEqual(result['categories'], [{'id': self.category.id, 'name': 'Medicamentos'}])

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

    def test_mobile_checkout_rejects_card_payment_until_gateway_is_tokenized(self):
        headers, _ = self.register_customer()
        self.add_to_cart(headers, self.common_inventory)
        payload = self.checkout_payload()
        payload['payment_method'] = 'credit_card'

        response = self.client.post(
            '/api/checkout/',
            data=json.dumps(payload),
            content_type='application/json',
            **headers,
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Order.objects.exists())

    def test_web_checkout_rejects_card_payment_until_gateway_is_tokenized(self):
        headers, _ = self.register_customer()
        self.add_to_cart(headers, self.common_inventory)
        self.client.force_login(User.objects.get(email='maria@example.com'))
        payload = self.checkout_payload()
        payload['payment_method'] = 'credit_card'

        response = self.client.post('/concluir-pedido/', data=payload)

        self.assertRedirects(response, '/concluir-pedido/', fetch_redirect_response=False)
        self.assertFalse(Order.objects.exists())

    def test_payment_page_does_not_store_raw_card_submission(self):
        self.register_customer()
        user = User.objects.get(email='maria@example.com')
        self.client.force_login(user)

        response = self.client.post('/pagamento/', data={
            'action': 'save_payment',
            'payment_method': 'credit',
            'card_name': 'Maria Cliente',
            'card_number': '4111111111111111',
            'card_expiry': '12/30',
            'card_cvv': '123',
        })

        self.assertRedirects(response, '/pagamento/', fetch_redirect_response=False)
        profile = UserProfile.objects.get(user=user)
        self.assertIsNone(profile.payment_card_last4)

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
