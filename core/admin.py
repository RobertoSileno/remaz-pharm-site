from django.contrib import admin
from .models import UserProfile, Medicine, Category, Cart, CartItem


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
    list_display = ('name', 'price', 'category', 'tarja')
    list_filter = ('category', 'tarja')
    search_fields = ('name',)
    ordering = ('name',)


# 🔹 CART ITEM (inline dentro do carrinho)
class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 1


# 🔹 CART
class CartAdmin(admin.ModelAdmin):
    list_display = ('user',)
    inlines = [CartItemInline]


# REGISTROS
admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(Medicine, MedicineAdmin)
admin.site.register(Cart, CartAdmin)