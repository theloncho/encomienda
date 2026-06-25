import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

logger = logging.getLogger(__name__)

class EncomiendaConsumer(AsyncWebsocketConsumer):
    """
    Consumer del canal global de encomiendas.
    Cada empleado conectado tiene una instancia de este consumer.
    """

    async def connect(self):
        user = self.scope['user']
        
        # 1. Verificar autenticacion
        if not user.is_authenticated:
            await self.close(code=4001)
            return

        # 2. Definir a que grupo pertenece este consumer
        self.group_name = 'encomiendas_global'

        # 3. Unirse al grupo en el channel layer
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        # 4. Aceptar la conexion
        await self.accept()

        # 5. Enviar mensaje inicial al cliente
        stats = await self.get_estadisticas()
        await self.send(text_data=json.dumps({
            'tipo': 'conectado',
            'usuario': user.username,
            'stats': stats,
        }))

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return

        try:
            data = json.loads(text_data)
            await self.procesar_mensaje(data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'tipo': 'error',
                'codigo': 'JSON_INVALIDO',
                'mensaje': 'El mensaje no es JSON valido',
            }))
        except Exception as e:
            logger.error(f'Error en consumer: {e}', exc_info=True)
            await self.send(text_data=json.dumps({
                'tipo': 'error',
                'codigo': 'ERROR_INTERNO',
                'mensaje': 'Error interno del servidor',
            }))

    async def procesar_mensaje(self, data):
        tipo = data.get('tipo')

        if tipo == 'ping':
            await self.send(text_data=json.dumps({'tipo': 'pong'}))
        elif tipo == 'solicitar_stats':
            stats = await self.get_estadisticas()
            await self.send(text_data=json.dumps({
                'tipo': 'stats', 'stats': stats
            }))
        elif tipo == 'suscribir_encomienda':
            enc_id = data.get('encomienda_id')
            if enc_id:
                await self.channel_layer.group_add(
                    f'encomienda_{enc_id}',
                    self.channel_name
                )
                await self.send(text_data=json.dumps({
                    'tipo': 'suscrito', 'encomienda_id': enc_id
                }))
        else:
            await self.send(text_data=json.dumps({
                'tipo': 'error', 'mensaje': f'Tipo desconocido: {tipo}'
            }))

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    async def encomienda_estado_cambio(self, event):
        await self.send(text_data=json.dumps({
            'tipo':          'estado_cambio',
            'encomienda_id': event['encomienda_id'],
            'codigo':        event['codigo'],
            'estado_anterior': event['estado_anterior'],
            'estado_nuevo':  event['estado_nuevo'],
            'empleado':      event['empleado'],
            'timestamp':     event['timestamp'],
        }))

    async def encomienda_progreso(self, event):
        await self.send(text_data=json.dumps({
            'tipo': 'progreso',
            'actual': event['actual'],
            'total': event['total'],
            'codigo': event.get('codigo', ''),
        }))

    @database_sync_to_async
    def get_estadisticas(self):
        from .models import Encomienda
        return {
            'activas':   Encomienda.objects.activas().count(),
            'en_transito': Encomienda.objects.en_transito().count(),
            'con_retraso': Encomienda.objects.con_retraso().count(),
        }


class EncomiendaDetalleConsumer(AsyncWebsocketConsumer):
    """
    Consumer para suscripción dinámica a los eventos de una sola encomienda.
    """

    async def connect(self):
        user = self.scope['user']
        if not user.is_authenticated:
            await self.close(code=4001)
            return

        self.enc_pk = self.scope['url_route']['kwargs']['pk']
        self.group_name = f'encomienda_{self.enc_pk}'

        existe = await self.enc_existe(self.enc_pk)
        if not existe:
            await self.close(code=4004)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        enc_data = await self.get_encomienda(self.enc_pk)
        await self.send(text_data=json.dumps({
            'tipo': 'estado_actual',
            'encomienda': enc_data,
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        pass  # Solo recibe notificaciones del channel layer

    async def encomienda_estado_cambio(self, event):
        await self.send(text_data=json.dumps({
            'tipo':          'estado_cambio',
            'estado_anterior': event['estado_anterior'],
            'estado_nuevo':  event['estado_nuevo'],
            'empleado':      event['empleado'],
            'timestamp':     event['timestamp'],
        }))

    @database_sync_to_async
    def enc_existe(self, pk):
        from .models import Encomienda
        return Encomienda.objects.filter(pk=pk).exists()

    @database_sync_to_async
    def get_encomienda(self, pk):
        from .models import Encomienda
        from .serializers import EncomiendaDetailSerializer
        try:
            enc = Encomienda.objects.con_relaciones().get(pk=pk)
            return dict(EncomiendaDetailSerializer(enc).data)
        except Encomienda.DoesNotExist:
            return None


class DashboardConsumer(AsyncWebsocketConsumer):
    """
    Consumer dedicado a la emisión en tiempo real de estadísticas globales.
    """

    async def connect(self):
        user = self.scope['user']
        if not user.is_authenticated:
            await self.close(code=4001)
            return

        self.group_name = 'dashboard'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        stats = await self.get_estadisticas()
        await self.send(text_data=json.dumps({
            'tipo': 'stats_iniciales',
            'stats': stats,
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def dashboard_actualizar(self, event):
        await self.send(text_data=json.dumps({
            'tipo': 'stats_actualizado',
            'stats': event['stats'],
        }))

    @database_sync_to_async
    def get_estadisticas(self):
        from .models import Encomienda
        return {
            'activas':   Encomienda.objects.activas().count(),
            'en_transito': Encomienda.objects.en_transito().count(),
            'con_retraso': Encomienda.objects.con_retraso().count(),
        }
