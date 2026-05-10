from django.contrib import admin
from django.utils.html import format_html
from httpx import request

from .models import (
    UserProfile,
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
)
from .services.supabase_storage import upload_image
from .forms import MedicineAdminForm


# 🔹 USER PROFILE
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'cpf', 'nickname', 'created_at')
    search_fields = ('user__username', 'cpf', 'nickname')
    readonly_fields = ('created_at', 'updated_at')


class AddressAdmin(admin.ModelAdmin):
    list_display = ('label', 'user', 'city', 'state', 'is_default', 'updated_at')
    list_filter = ('state', 'city', 'is_default')
    search_fields = ('label', 'user__username', 'cep', 'street', 'city')
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
class PharmacyInventoryInline(admin.TabularInline):
    model = PharmacyInventory
    extra = 1
    autocomplete_fields = ('medicine',)


class PharmacyAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'city', 'state', 'is_active')
    list_filter = ('is_active', 'state', 'city')
    search_fields = ('name', 'cnpj', 'cep', 'owner__username')
    inlines = [PharmacyInventoryInline]


class PharmacyInventoryAdmin(admin.ModelAdmin):
    list_display = ('pharmacy', 'medicine', 'price', 'promotional_price', 'stock', 'is_available', 'promotion_active')
    list_filter = ('pharmacy', 'is_available', 'promotion_active', 'medicine__tarja')
    search_fields = ('pharmacy__name', 'medicine__name')
    autocomplete_fields = ('pharmacy', 'medicine')


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('medicine', 'medicine_name', 'quantity', 'medicine_price', 'tarja')
    can_delete = False


class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'pharmacy', 'status', 'prescription_status', 'total', 'created_at')
    list_filter = ('status', 'prescription_status', 'pharmacy', 'payment_method', 'delivery_method')
    search_fields = ('id', 'user__username', 'pharmacy__name', 'customer_name')
    readonly_fields = ('created_at', 'updated_at', 'prescription_reviewed_at')
    inlines = [OrderItemInline]


class OrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ('order', 'from_status', 'to_status', 'changed_by', 'created_at')
    list_filter = ('to_status', 'created_at')
    search_fields = ('order__id', 'changed_by__username', 'note')
    readonly_fields = ('created_at',)


class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ('order', 'provider', 'payment_method', 'status', 'amount', 'external_id', 'updated_at')
    list_filter = ('provider', 'payment_method', 'status')
    search_fields = ('order__id', 'external_id', 'error_message')
    readonly_fields = ('created_at', 'updated_at')


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 1


# 🔹 CART
class CartAdmin(admin.ModelAdmin):
    list_display = ('user',)
    inlines = [CartItemInline]


# 🔹 REGISTROS
admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(Address, AddressAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(Medicine, MedicineAdmin)
admin.site.register(Cart, CartAdmin)
admin.site.register(Pharmacy, PharmacyAdmin)
admin.site.register(PharmacyInventory, PharmacyInventoryAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(OrderStatusHistory, OrderStatusHistoryAdmin)
admin.site.register(PaymentTransaction, PaymentTransactionAdmin)
