from django.urls import path
from .views import home, login_view, register_view, password_recovery_view

urlpatterns = [
    path('', home, name='home'),
    path('login/', login_view, name='login'),
    path('registro/', register_view, name='registro'),
    path('recuperar-senha/', password_recovery_view, name='recuperar_senha'),
]