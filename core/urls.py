from django.urls import path
from .views import (
    dashboard_view,
    home,
    login_view,
    logout_view,
    register_view,
    password_recovery_view,
    profile_view,
)

urlpatterns = [
    path('', home, name='home'),
    path('login/', login_view, name='login'),
    path('registro/', register_view, name='registro'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('recuperar-senha/', password_recovery_view, name='recuperar_senha'),
    path('logout/', logout_view, name='logout'),
    path('perfil/', profile_view, name='perfil'),      
]