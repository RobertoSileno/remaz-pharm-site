from django.contrib import admin
from django.utils.html import format_html
from httpx import request

from .models import UserProfile, Medicine, Category, Cart, CartItem
from .services.supabase_storage import upload_image
from .forms import MedicineAdminForm


# 🔹 USER PROFILE
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'cpf', 'nickname', 'created_at')
    search_fields = ('user__username', 'cpf', 'nickname')
    readonly_fields = ('created_at', 'updated_at')


# 🔹 CATEGORY
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


# 🔹 MEDICINE
class MedicineAdmin(admin.ModelAdmin):
    form = MedicineAdminForm

    list_display = ('name', 'price', 'category', 'tarja', 'preview_image')
    list_filter = ('category', 'tarja')
    search_fields = ('name',)
    ordering = ('name',)
    actions = ['delete_selected']
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['image_file'].widget.attrs.update({'accept': 'image/*'})
        return form
    # 🔥 preview da imagem
    def preview_image(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" />', obj.image)
        return "Sem imagem"

    preview_image.short_description = "Imagem"

    # 🔥 upload para Supabase
    def save_model(self, request, obj, form, change):
        image_file = request.FILES.get('image_file')  # 👈 nome novo

        if image_file:
            image_url = upload_image(image_file)
            obj.image = image_url

        super().save_model(request, obj, form, change)


# 🔹 CART ITEM
class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 1


# 🔹 CART
class CartAdmin(admin.ModelAdmin):
    list_display = ('user',)
    inlines = [CartItemInline]


# 🔹 REGISTROS
admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(Medicine, MedicineAdmin)
admin.site.register(Cart, CartAdmin)