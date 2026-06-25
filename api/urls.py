# api/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from . import views
from envios.viewsets import EncomiendaViewSet
from envios.api_views import ClienteListView, RutaListView
from envios.api_auth import LoginCookieView, LogoutCookieView

router = DefaultRouter()
router.register('encomiendas', EncomiendaViewSet, basename='encomienda')

urlpatterns = [
    # Endpoints de autenticación JWT
    path('auth/token/', views.EncomiendaTokenView.as_view(), name='token_obtain'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Autenticación con HttpOnly Cookies
    path('auth/cookie/login/', LoginCookieView.as_view(), name='cookie_login'),
    path('auth/cookie/logout/', LogoutCookieView.as_view(), name='cookie_logout'),

    # Documentación interactiva
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger'),

    # URLs del router (ViewSets) y vistas genéricas
    path('', include(router.urls)),
    path('clientes/', ClienteListView.as_view(), name='cliente-list'),
    path('rutas/', RutaListView.as_view(), name='ruta-list'),
]
