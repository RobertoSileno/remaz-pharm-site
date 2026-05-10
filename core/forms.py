from django import forms
from .models import Address, Medicine, Pharmacy

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


class PharmacyRegistrationForm(forms.ModelForm):
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
