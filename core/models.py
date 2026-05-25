from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('credit', 'Cartão de crédito'),
        ('debit', 'Cartão de débito'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    cpf = models.CharField(max_length=14, unique=True, blank=True, null=True)
    nickname = models.CharField(max_length=15, blank=True, null=True)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES, blank=True, null=True)
    payment_card_owner = models.CharField(max_length=100, blank=True, null=True)
    payment_card_last4 = models.CharField(max_length=4, blank=True, null=True)
    payment_card_expiry = models.CharField(max_length=5, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    def __str__(self):
        return f'{self.user.username} - {self.cpf}'

    class Meta:
        verbose_name = 'Perfil de Usuário'
        verbose_name_plural = 'Perfis de Usuários'


class MobileAuthToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mobile_auth_tokens')
    key_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    last_used_at = models.DateTimeField(blank=True, null=True)
    revoked_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f'Token mobile de {self.user_id}'

    class Meta:
        ordering = ('-created_at',)
        verbose_name = 'Token de autenticacao mobile'
        verbose_name_plural = 'Tokens de autenticacao mobile'


class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    label = models.CharField(max_length=60, default='Principal')
    recipient_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20)
    cep = models.CharField(max_length=12)
    state = models.CharField(max_length=2)
    city = models.CharField(max_length=100)
    neighborhood = models.CharField(max_length=100)
    street = models.CharField(max_length=150)
    number = models.CharField(max_length=20)
    complement = models.CharField(max_length=150, blank=True, null=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def summary(self):
        complement = f' - {self.complement}' if self.complement else ''
        return f'{self.street}, {self.number}{complement} - {self.neighborhood}, {self.city}/{self.state}'

    def save(self, *args, **kwargs):
        if self.is_default:
            Address.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        elif not self.pk and not Address.objects.filter(user=self.user).exists():
            self.is_default = True

        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.label} - {self.user}'

    class Meta:
        ordering = ('-is_default', '-updated_at')
        verbose_name = 'Endereco'
        verbose_name_plural = 'Enderecos'


class Category(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Medicine(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    # imagem do produto
    image = models.URLField(blank=True, null=True)

    # categorias (analgésico, antibiótico, etc)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)

    # tipo de tarja
    TARJA_CHOICES = [
        ('sem', 'Sem tarja'),
        ('vermelha', 'Tarja vermelha'),
        ('preta', 'Tarja preta'),
    ]
    tarja = models.CharField(max_length=10, choices=TARJA_CHOICES)

    def __str__(self):
        return self.name

class Pharmacy(models.Model):
    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='pharmacies',
        blank=True,
        null=True
    )
    name = models.CharField(max_length=200)
    cnpj = models.CharField(max_length=18, unique=True, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    cep = models.CharField(max_length=12, blank=True, null=True)
    state = models.CharField(max_length=2, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    district = models.CharField(max_length=100, blank=True, null=True)
    street = models.CharField(max_length=150, blank=True, null=True)
    number = models.CharField(max_length=20, blank=True, null=True)
    complement = models.CharField(max_length=150, blank=True, null=True)
    logo = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Farmacia'
        verbose_name_plural = 'Farmacias'

class PharmacyInventory(models.Model):
    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.CASCADE, related_name='inventory_items')
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE, related_name='pharmacy_inventory')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    is_available = models.BooleanField(default=True)
    promotion_active = models.BooleanField(default=False)
    promotion_title = models.CharField(max_length=120, blank=True, default='')
    promotion_description = models.TextField(blank=True, default='')
    promotional_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.pharmacy} - {self.medicine}'

    @property
    def has_active_promotion(self):
        return bool(self.promotion_active and self.promotional_price and self.stock > 0 and self.is_available)

    @property
    def effective_price(self):
        if self.has_active_promotion:
            return self.promotional_price

        return self.price

    def save(self, *args, **kwargs):
        if self.stock <= 0:
            self.stock = 0
            self.is_available = False

            update_fields = kwargs.get('update_fields')
            if update_fields is not None and 'stock' in update_fields:
                kwargs['update_fields'] = set(update_fields) | {'is_available'}

        if not self.promotional_price:
            self.promotion_active = False

        super().save(*args, **kwargs)

    class Meta:
        unique_together = ('pharmacy', 'medicine')
        verbose_name = 'Estoque da farmacia'
        verbose_name_plural = 'Estoques das farmacias'
    
class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE)
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE)
    inventory = models.ForeignKey(
        PharmacyInventory,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name='cart_items'
    )
    quantity = models.PositiveIntegerField(default=1)

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Aguardando confirmacao'),
        ('waiting_prescription', 'Aguardando analise da receita'),
        ('approved', 'Aprovado'),
        ('rejected', 'Recusado'),
        ('completed', 'Concluido'),
        ('cancelled', 'Cancelado'),
    ]

    DELIVERY_CHOICES = [
        ('delivery', 'Receber em casa'),
        ('pickup', 'Retirar na farmacia'),
    ]

    PRESCRIPTION_STATUS_CHOICES = [
        ('not_required', 'Nao exige receita'),
        ('pending', 'Aguardando analise'),
        ('approved', 'Receita aprovada'),
        ('rejected', 'Receita recusada'),
    ]

    PAYMENT_CHOICES = [
        ('pix', 'Pix'),
        ('credit_card', 'Cartao de credito'),
        ('debit_card', 'Cartao de debito'),
        ('cash', 'Dinheiro na entrega'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    pharmacy = models.ForeignKey(
        Pharmacy,
        on_delete=models.SET_NULL,
        related_name='orders',
        blank=True,
        null=True
    )
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    requires_prescription = models.BooleanField(default=False)
    customer_name = models.CharField(max_length=200)
    customer_email = models.EmailField(blank=True, null=True)
    customer_phone = models.CharField(max_length=20)
    cep = models.CharField(max_length=12)
    state = models.CharField(max_length=2)
    city = models.CharField(max_length=100)
    neighborhood = models.CharField(max_length=100)
    street = models.CharField(max_length=150)
    number = models.CharField(max_length=20)
    complement = models.CharField(max_length=150, blank=True, null=True)
    notes = models.TextField(blank=True, default='')
    delivery_method = models.CharField(max_length=20, choices=DELIVERY_CHOICES, default='delivery')
    prescription_file = models.CharField(max_length=255, blank=True, null=True)
    prescription_status = models.CharField(
        max_length=20,
        choices=PRESCRIPTION_STATUS_CHOICES,
        default='not_required'
    )
    prescription_review_reason = models.TextField(blank=True, default='')
    prescription_reviewed_at = models.DateTimeField(blank=True, null=True)
    prescription_reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='reviewed_prescriptions',
        blank=True,
        null=True
    )
    pharmacy_notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Pedido #{self.id} - {self.user}'

    class Meta:
        ordering = ('-created_at',)
        verbose_name = 'Pedido'
        verbose_name_plural = 'Pedidos'

class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history')
    from_status = models.CharField(max_length=30, blank=True, default='')
    to_status = models.CharField(max_length=30)
    note = models.TextField(blank=True, default='')
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='order_status_changes',
        blank=True,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Pedido #{self.order_id}: {self.from_status or "-"} -> {self.to_status}'

    class Meta:
        ordering = ('-created_at',)
        verbose_name = 'Historico de status'
        verbose_name_plural = 'Historicos de status'


class PaymentTransaction(models.Model):
    PROVIDER_CHOICES = [
        ('mercado_pago', 'Mercado Pago'),
        ('manual', 'Manual'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pendente'),
        ('in_process', 'Em processamento'),
        ('approved', 'Aprovado'),
        ('rejected', 'Recusado'),
        ('cancelled', 'Cancelado'),
        ('manual', 'Manual'),
        ('gateway_not_configured', 'Gateway nao configurado'),
        ('error', 'Erro'),
    ]

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='payment_transaction')
    provider = models.CharField(max_length=30, choices=PROVIDER_CHOICES, default='manual')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=20, choices=Order.PAYMENT_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    external_id = models.CharField(max_length=120, blank=True, default='')
    qr_code = models.TextField(blank=True, default='')
    qr_code_base64 = models.TextField(blank=True, default='')
    payment_url = models.URLField(blank=True, default='')
    error_message = models.TextField(blank=True, default='')
    raw_response = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Pagamento pedido #{self.order_id} - {self.get_status_display()}'

    class Meta:
        ordering = ('-created_at',)
        verbose_name = 'Transacao de pagamento'
        verbose_name_plural = 'Transacoes de pagamento'


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    medicine = models.ForeignKey(Medicine, on_delete=models.SET_NULL, blank=True, null=True)
    medicine_name = models.CharField(max_length=200)
    medicine_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    tarja = models.CharField(max_length=10, blank=True, null=True)

    @property
    def subtotal(self):
        return self.medicine_price * self.quantity

    def __str__(self):
        return f'{self.quantity}x {self.medicine_name}'
