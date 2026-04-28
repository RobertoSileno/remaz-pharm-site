from django import forms
from .models import Medicine

class MedicineAdminForm(forms.ModelForm):
    image_file = forms.ImageField(required=False)  # 👈 nome diferente

    class Meta:
        model = Medicine
        fields = '__all__'