import re

from django import forms
from .models import Address, Medicine, Pharmacy, PharmacyInventory

class MedicineAdminForm(forms.ModelForm):
    image_file = forms.ImageField(required=False)  # 👈 nome diferente

    class Meta:
        model = Medicine
        fields = '__all__'


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = (
            'label',
            'recipient_name',
            'phone',
            'cep',
            'state',
            'city',
            'neighborhood',
            'street',
            'number',
            'complement',
            'is_default',
        )
        widgets = {
            'label': forms.TextInput(attrs={'placeholder': 'Casa, trabalho...'}),
            'recipient_name': forms.TextInput(attrs={'placeholder': 'Nome de quem recebe'}),
            'phone': forms.TextInput(attrs={'placeholder': '(00) 00000-0000'}),
            'cep': forms.TextInput(attrs={'placeholder': '00000-000', 'data-cep-field': 'true'}),
            'state': forms.TextInput(attrs={'placeholder': 'UF', 'maxlength': '2', 'data-cep-state': 'true'}),
            'city': forms.TextInput(attrs={'placeholder': 'Cidade', 'data-cep-city': 'true'}),
            'neighborhood': forms.TextInput(attrs={'placeholder': 'Bairro', 'data-cep-neighborhood': 'true'}),
            'street': forms.TextInput(attrs={'placeholder': 'Rua', 'data-cep-street': 'true'}),
            'number': forms.TextInput(attrs={'placeholder': 'Numero'}),
            'complement': forms.TextInput(attrs={'placeholder': 'Apartamento, bloco, referencia'}),
        }


class UserProfileForm(forms.Form):
    username = forms.CharField(max_length=150, label='Nome completo', widget=forms.TextInput(attrs={'placeholder': 'Digite seu nome'}))
    email = forms.EmailField(label='Email', widget=forms.EmailInput(attrs={'placeholder': 'Digite seu e-mail'}))
    cpf = forms.CharField(max_length=14, required=False, label='CPF', widget=forms.TextInput(attrs={'placeholder': '000.000.000-00'}))
    nickname = forms.CharField(max_length=15, required=False, label='Apelido', widget=forms.TextInput(attrs={'placeholder': 'Como gostaria de ser chamado'}))


class PaymentForm(forms.Form):
    PAYMENT_METHOD_CHOICES = [
        ('debit', 'Cartão de Débito'),
        ('credit', 'Cartão de Crédito'),
    ]

    payment_method = forms.ChoiceField(
        choices=PAYMENT_METHOD_CHOICES,
        widget=forms.RadioSelect,
        required=False,
        label='Forma de pagamento'
    )
    card_name = forms.CharField(max_length=100, required=False, label='Nome no cartão', widget=forms.TextInput(attrs={'placeholder': 'Nome impresso no cartão'}))
    card_number = forms.CharField(max_length=19, required=False, label='Número do cartão', widget=forms.TextInput(attrs={'placeholder': '0000 0000 0000 0000'}))
    card_expiry = forms.CharField(max_length=5, required=False, label='Validade', widget=forms.TextInput(attrs={'placeholder': 'MM/AA'}))

    def clean_card_number(self):
        card_number = self.cleaned_data.get('card_number', '')
        if not card_number:
            return ''

        cleaned = re.sub(r'\D', '', card_number)
        if not cleaned.isdigit() or len(cleaned) < 13 or len(cleaned) > 19:
            raise forms.ValidationError('Informe um número de cartão válido.')

        return cleaned


class PharmacyRegistrationForm(forms.ModelForm):
    image_file = forms.ImageField(
        required=False,
        label='Logo da farmácia',
        widget=forms.ClearableFileInput(attrs={'accept': 'image/png,image/jpeg,image/webp'})
    )
    cep = forms.CharField(max_length=12, required=False, widget=forms.TextInput(attrs={
        'placeholder': '00000-000',
        'data-cep-field': 'true',
    }))

    class Meta:
        model = Pharmacy
        fields = (
            'name',
            'cnpj',
            'phone',
            'cep',
            'state',
            'city',
            'district',
            'street',
            'number',
            'complement',
        )
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Nome fantasia da farmacia'}),
            'cnpj': forms.TextInput(attrs={'placeholder': '00.000.000/0000-00'}),
            'phone': forms.TextInput(attrs={'placeholder': '(00) 00000-0000'}),
            'state': forms.TextInput(attrs={'placeholder': 'UF', 'maxlength': '2', 'data-cep-state': 'true'}),
            'city': forms.TextInput(attrs={'placeholder': 'Cidade', 'data-cep-city': 'true'}),
            'district': forms.TextInput(attrs={'placeholder': 'Bairro', 'data-cep-neighborhood': 'true'}),
            'street': forms.TextInput(attrs={'placeholder': 'Rua', 'data-cep-street': 'true'}),
            'number': forms.TextInput(attrs={'placeholder': 'Numero'}),
            'complement': forms.TextInput(attrs={'placeholder': 'Complemento'}),
        }


class PharmacyMedicineCreateForm(forms.ModelForm):
    image_file = forms.ImageField(
        label='Imagem do produto',
        required=False,
        widget=forms.ClearableFileInput(attrs={'accept': 'image/png,image/jpeg,image/webp'})
    )
    inventory_price = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0,
        label='Preco de venda',
        widget=forms.NumberInput(attrs={'min': '0', 'step': '0.01', 'placeholder': '0.00'})
    )
    stock = forms.IntegerField(
        min_value=0,
        label='Estoque',
        widget=forms.NumberInput(attrs={'min': '0', 'step': '1', 'placeholder': '0'})
    )
    is_available = forms.BooleanField(label='Disponivel para venda', required=False, initial=True)
    promotion_active = forms.BooleanField(label='Promocao ativa', required=False)
    promotion_title = forms.CharField(max_length=120, required=False, widget=forms.TextInput(attrs={
        'placeholder': 'Ex: Oferta da semana',
    }))
    promotion_description = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'placeholder': 'Ex: Valido enquanto durar o estoque',
    }))
    promotional_price = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0,
        required=False,
        widget=forms.NumberInput(attrs={'min': '0', 'step': '0.01', 'placeholder': 'Opcional'})
    )

    class Meta:
        model = Medicine
        fields = (
            'name',
            'description',
            'category',
            'tarja',
            'price',
        )
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Nome do medicamento'}),
            'description': forms.Textarea(attrs={'placeholder': 'Descricao do produto', 'rows': 3}),
            'price': forms.NumberInput(attrs={'min': '0', 'step': '0.01', 'placeholder': 'Preco base'}),
        }

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if Medicine.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError('Ja existe um medicamento com este nome. Use o formulario de estoque existente.')

        return name

    def clean(self):
        cleaned_data = super().clean()
        promotion_active = cleaned_data.get('promotion_active')
        promotional_price = cleaned_data.get('promotional_price')

        if promotion_active and not promotional_price:
            self.add_error('promotional_price', 'Informe o preco promocional para ativar promocao.')

        return cleaned_data

    def clean_image_file(self):
        image_file = self.cleaned_data.get('image_file')
        if not image_file:
            return image_file

        allowed_content_types = {'image/png', 'image/jpeg', 'image/webp'}
        if image_file.content_type not in allowed_content_types:
            raise forms.ValidationError('Envie uma imagem PNG, JPG, JPEG ou WebP.')

        max_size = 5 * 1024 * 1024
        if image_file.size > max_size:
            raise forms.ValidationError('A imagem deve ter no maximo 5 MB.')

        return image_file

    def save_with_inventory(self, pharmacy, image_url=''):
        medicine = self.save(commit=False)
        if image_url:
            medicine.image = image_url
        medicine.save()

        stock = self.cleaned_data['stock']
        promotional_price = self.cleaned_data.get('promotional_price')
        inventory = PharmacyInventory.objects.create(
            pharmacy=pharmacy,
            medicine=medicine,
            price=self.cleaned_data['inventory_price'],
            stock=stock,
            is_available=self.cleaned_data.get('is_available') and stock > 0,
            promotion_active=self.cleaned_data.get('promotion_active') and bool(promotional_price),
            promotion_title=self.cleaned_data.get('promotion_title', '').strip(),
            promotion_description=self.cleaned_data.get('promotion_description', '').strip(),
            promotional_price=promotional_price,
        )

        return medicine, inventory
