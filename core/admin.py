from django.contrib import admin
from .models import UserProfile

class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'cpf', 'created_at')
    search_fields = ('user__username', 'cpf')
    readonly_fields = ('created_at', 'updated_at')

admin.site.register(UserProfile, UserProfileAdmin)
