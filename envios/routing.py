# envios/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Consumer general: todos los empleados conectados
    re_path(
        r'^ws/encomiendas/$',
        consumers.EncomiendaConsumer.as_asgi(),
        name='ws-encomiendas'
    ),

    # Consumer de detalle: una encomienda especifica
    re_path(
        r'^ws/encomiendas/(?P<pk>\d+)/$',
        consumers.EncomiendaDetalleConsumer.as_asgi(),
        name='ws-encomienda-detalle'
    ),

    # Consumer del dashboard: estadisticas en tiempo real
    re_path(
        r'^ws/dashboard/$',
        consumers.DashboardConsumer.as_asgi(),
        name='ws-dashboard'
    ),
]
