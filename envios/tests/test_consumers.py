import pytest
import json
from channels.testing import WebsocketCommunicator
from channels.layers import get_channel_layer
from channels.routing import URLRouter
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from envios.routing import websocket_urlpatterns

User = get_user_model()

@database_sync_to_async
def create_test_user():
    user, created = User.objects.get_or_create(
        username='testuser', 
        defaults={'email': 'test@test.com'}
    )
    if created:
        user.set_password('password123')
        user.save()
    return user


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestEncomiendaConsumer:

    async def test_conexion_sin_autenticacion(self):
        """Sin autenticar: el servidor debe rechazar con codigo 4001"""
        communicator = WebsocketCommunicator(
            URLRouter(websocket_urlpatterns),
            '/ws/encomiendas/'
        )
        communicator.scope['user'] = AnonymousUser()
        connected, code = await communicator.connect()
        assert not connected
        assert code == 4001
        await communicator.disconnect()

    async def test_conexion_autenticada(self):
        """Con usuario autenticado: el servidor acepta y envia stats"""
        user = await create_test_user()
        communicator = WebsocketCommunicator(
            URLRouter(websocket_urlpatterns),
            '/ws/encomiendas/'
        )
        communicator.scope['user'] = user

        connected, _ = await communicator.connect()
        assert connected

        # Recibir el mensaje de bienvenida
        response = await communicator.receive_json_from(timeout=3)
        assert response['tipo'] == 'conectado'
        assert 'stats' in response
        assert 'activas' in response['stats']

        await communicator.disconnect()

    async def test_ping_pong(self):
        """El consumer responde pong al recibir ping"""
        user = await create_test_user()
        communicator = WebsocketCommunicator(
            URLRouter(websocket_urlpatterns), 
            '/ws/encomiendas/'
        )
        communicator.scope['user'] = user

        await communicator.connect()
        await communicator.receive_json_from(timeout=2) # mensaje bienvenida

        # Enviar ping
        await communicator.send_json_to({'tipo': 'ping'})

        # Recibir pong
        response = await communicator.receive_json_from(timeout=2)
        assert response['tipo'] == 'pong'

        await communicator.disconnect()

    async def test_notificacion_via_channel_layer(self):
        """El consumer recibe y reenvía mensajes del channel layer"""
        user = await create_test_user()
        communicator = WebsocketCommunicator(
            URLRouter(websocket_urlpatterns), 
            '/ws/encomiendas/'
        )
        communicator.scope['user'] = user

        await communicator.connect()
        await communicator.receive_json_from(timeout=2) # bienvenida

        # Simular que el modelo envia una notificacion al channel layer
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            'encomiendas_global',
            {
                'type':          'encomienda_estado_cambio',
                'encomienda_id': 1,
                'codigo':        'ENC-2026-001',
                'estado_anterior': 'PE',
                'estado_nuevo':  'TR',
                'empleado':      'Mendoza Cruz, Luis',
                'timestamp':     '2026-05-14T10:00:00Z',
            }
        )

        # El consumer debe recibir y reenviar al cliente
        response = await communicator.receive_json_from(timeout=3)
        assert response['tipo']      == 'estado_cambio'
        assert response['codigo']    == 'ENC-2026-001'
        assert response['estado_nuevo'] == 'TR'

        await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_dashboard_consumer():
    """
    Prueba unitaria asincrona para validar la conexion
    y los mensajes iniciales emitidos por DashboardConsumer.
    """
    user = await create_test_user()
    communicator = WebsocketCommunicator(
        URLRouter(websocket_urlpatterns), 
        "/ws/dashboard/"
    )
    communicator.scope['user'] = user

    connected, subprotocol = await communicator.connect()
    assert connected

    response = await communicator.receive_json_from(timeout=3)
    assert response['tipo'] == 'stats_iniciales'
    assert 'stats' in response
    assert 'activas' in response['stats']

    await communicator.disconnect()
