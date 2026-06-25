from django.urls import path
from . import views
from . import views_auth
from . import views_async

urlpatterns = [
    # Auth
    path('login/', views_auth.login_view, name='login'),
    path('logout/', views_auth.logout_view, name='logout'),
    path('perfil/', views_auth.perfil_view, name='perfil'),

    # Encomiendas views
    path('', views.dashboard, name='dashboard'),
    path('encomiendas/', views.encomienda_lista, name='encomienda_lista'),
    path('encomiendas/nueva/', views.encomienda_crear, name='encomienda_crear'),
    path('encomiendas/<int:pk>/', views.encomienda_detalle, name='encomienda_detalle'),
    path('encomiendas/<int:pk>/estado/', views.encomienda_cambiar_estado, name='encomienda_cambiar_estado'),
    
    # Async views
    path('dashboard/stats/async/', views_async.dashboard_stats_async, name='dashboard_stats_async'),
    path('encomiendas/<int:pk>/estado/async/', views_async.cambiar_estado_vista, name='cambiar_estado_vista'),

    path('health_check/', views.health_check, name='health_check'),
]
