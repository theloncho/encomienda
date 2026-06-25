"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

# Customizing the Django admin texts
admin.site.site_header = 'Sistema de Gestión de Encomiendas'
admin.site.site_title = 'Encomiendas Admin'
admin.site.index_title = 'Panel de Administración'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', RedirectView.as_view(url='/login/', permanent=True)),

    # Vistas web del sistema
    path('', include('envios.urls')),

    # API REST con versionado dinámico
    path('api/<version>/', include('api.urls')),

    # Documentación de la API (fuera de /api/ para evitar conflictos con versionado)
    # Apunta directamente al esquema de la versión 1
    path('docs/', SpectacularSwaggerView.as_view(url='/api/v1/schema/'), name='swagger'),
    path('redoc/', SpectacularRedocView.as_view(url='/api/v1/schema/'), name='redoc'),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    # Panel de silk (solo en desarrollo)
    try:
        from silk import urls as silk_urls
        urlpatterns += [
            path('silk/', include('silk.urls', namespace='silk')),
        ]
    except ImportError:
        pass
