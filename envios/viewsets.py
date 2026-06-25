# envios/viewsets.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.core.cache import cache
from django.utils import timezone

from drf_spectacular.utils import (
    extend_schema, extend_schema_view,
    OpenApiParameter, OpenApiResponse, OpenApiExample,
)
from drf_spectacular.types import OpenApiTypes

from api.filters import EncomiendaFilter
from api.pagination import EncomiendaPagination, HistorialPagination
from api.permissions import EsEmpleadoActivo, EsPropietarioOAdmin
from api.throttles import EmpleadoRateThrottle, CambioEstadoThrottle
from api.exceptions import EstadoInvalidoError, EncomiendaYaEntregadaError

from .models import Encomienda, Empleado
from .serializers import (
    EncomiendaSerializer,
    EncomiendaListSerializer,
    EncomiendaDetailSerializer,
    EncomiendaV2Serializer,
    HistorialEstadoSerializer,
)


@extend_schema_view(
    list=extend_schema(
        summary='Listar encomiendas',
        description='Devuelve la lista paginada de encomiendas. Soporta filtros por estado, búsqueda y ordenamiento.',
        tags=['Encomiendas'],
    ),
    create=extend_schema(
        summary='Crear encomienda',
        description='Registra una nueva encomienda en el sistema.',
        tags=['Encomiendas'],
    ),
    retrieve=extend_schema(
        summary='Detalle de encomienda',
        description='Devuelve los datos completos de una encomienda con remitente, destinatario, ruta e historial de estados.',
        tags=['Encomiendas'],
    ),
    update=extend_schema(summary='Actualizar encomienda', tags=['Encomiendas']),
    partial_update=extend_schema(summary='Actualizar parcial', tags=['Encomiendas']),
    destroy=extend_schema(summary='Eliminar encomienda', tags=['Encomiendas']),
)
class EncomiendaViewSet(viewsets.ModelViewSet):
    """
    ModelViewSet genera automáticamente:
    list()           → GET    /encomiendas/
    create()         → POST   /encomiendas/
    retrieve()       → GET    /encomiendas/{pk}/
    update()         → PUT    /encomiendas/{pk}/
    partial_update() → PATCH  /encomiendas/{pk}/
    destroy()        → DELETE /encomiendas/{pk}/
    """
    queryset = Encomienda.objects.con_relaciones()
    serializer_class = EncomiendaSerializer
    permission_classes = [EsEmpleadoActivo]
    pagination_class = EncomiendaPagination
    throttle_classes = [EmpleadoRateThrottle]

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = EncomiendaFilter
    search_fields = [
        'codigo',
        'remitente__apellidos',
        'destinatario__apellidos',
        'descripcion',
    ]
    ordering_fields = ['fecha_registro', 'peso_kg', 'costo_envio']
    ordering = ['-fecha_registro']

    def get_permissions(self):
        """Permisos distintos según la acción"""
        if self.action in ['update', 'partial_update', 'destroy']:
            return [EsEmpleadoActivo(), EsPropietarioOAdmin()]
        return [EsEmpleadoActivo()]

    def get_throttles(self):
        """Throttle diferente para la acción cambiar_estado"""
        if self.action == 'cambiar_estado':
            return [CambioEstadoThrottle()]
        return super().get_throttles()

    def get_serializer_class(self):
        """
        Elegir el serializer según la versión Y la acción.
        v2 → EncomiendaV2Serializer
        v1 list → EncomiendaListSerializer (ligero)
        v1 retrieve → EncomiendaDetailSerializer (con anidados)
        v1 write → EncomiendaSerializer (estándar)
        """
        version = getattr(self.request, 'version', 'v1')

        if version == 'v2':
            return EncomiendaV2Serializer

        if self.action == 'list':
            return EncomiendaListSerializer
        if self.action == 'retrieve':
            return EncomiendaDetailSerializer
        return EncomiendaSerializer

    def get_queryset(self):
        qs = Encomienda.objects.con_relaciones()
        return qs

    def perform_create(self, serializer):
        empleado = Empleado.objects.get(email=self.request.user.email)
        serializer.save(empleado_registro=empleado)

    def perform_update(self, serializer):
        """Invalidar caché cuando se actualiza una encomienda"""
        super().perform_update(serializer)
        cache_key = f'estadisticas_empleado_{self.request.user.id}'
        cache.delete(cache_key)

    def list(self, request, *args, **kwargs):
        """Agregar cabecera X-API-Version en la respuesta"""
        response = super().list(request, *args, **kwargs)
        response['X-API-Version'] = getattr(request, 'version', 'v1')
        return response

    def retrieve(self, request, *args, **kwargs):
        """Agregar cabecera X-API-Version en el detalle"""
        response = super().retrieve(request, *args, **kwargs)
        response['X-API-Version'] = getattr(request, 'version', 'v1')
        return response

    # ── Acción: cambiar_estado ────────────────────────────────────
    @extend_schema(
        summary='Cambiar estado de encomienda',
        description='''
        Cambia el estado de una encomienda y registra el cambio
        automáticamente en el historial de estados.
        Estados: PE (Pendiente), TR (En tránsito), DE (En destino),
        EN (Entregado), DV (Devuelto)
        ''',
        request=OpenApiTypes.OBJECT,
        responses={
            200: EncomiendaSerializer,
            400: OpenApiResponse(description='Estado inválido o ya en ese estado'),
        },
        examples=[
            OpenApiExample(
                'Pasar a En tránsito',
                value={'estado': 'TR', 'observacion': 'Recogido en agencia Lima'},
                request_only=True,
            ),
            OpenApiExample(
                'Marcar como Entregado',
                value={'estado': 'EN', 'observacion': 'Entregado al destinatario'},
                request_only=True,
            ),
        ],
        tags=['Encomiendas'],
    )
    @action(detail=True, methods=['post'], url_path='cambiar_estado')
    def cambiar_estado(self, request, pk=None, **kwargs):
        enc = self.get_object()
        nuevo_estado = request.data.get('estado')
        observacion = request.data.get('observacion', '')

        if not nuevo_estado:
            return Response(
                {'error': 'El campo estado es requerido.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if enc.esta_entregada:
            raise EncomiendaYaEntregadaError()

        try:
            empleado = Empleado.objects.get(email=request.user.email)
            enc.cambiar_estado(nuevo_estado, empleado, observacion)
            # Invalidar caché de estadísticas
            cache.delete_many([
                f'estadisticas_empleado_{request.user.id}',
                f'encomienda_detalle_{pk}',
            ])
            return Response(EncomiendaSerializer(enc).data)
        except ValueError as e:
            raise EstadoInvalidoError(detail=str(e))

    # ── Acción: con_retraso ──────────────────────────────────────
    @extend_schema(
        summary='Encomiendas con retraso',
        description='Lista todas las encomiendas activas cuya fecha estimada de entrega ya pasó.',
        tags=['Encomiendas'],
        responses={200: EncomiendaSerializer(many=True)},
    )
    @action(detail=False, methods=['get'], url_path='con_retraso')
    def con_retraso(self, request, **kwargs):
        qs = Encomienda.objects.con_retraso().con_relaciones()
        return Response(self.get_serializer(qs, many=True).data)

    # ── Acción: pendientes ───────────────────────────────────────
    @extend_schema(
        summary='Encomiendas pendientes',
        description='Lista todas las encomiendas en estado Pendiente.',
        tags=['Encomiendas'],
    )
    @action(detail=False, methods=['get'])
    def pendientes(self, request, **kwargs):
        qs = Encomienda.objects.pendientes().con_relaciones()
        return Response(self.get_serializer(qs, many=True).data)

    # ── Acción: historial ────────────────────────────────────────
    @extend_schema(
        summary='Historial de estados',
        description='Devuelve el historial de cambios de estado de una encomienda, paginado con limit/offset.',
        parameters=[
            OpenApiParameter('limit', type=int, description='Número de resultados', default=10),
            OpenApiParameter('offset', type=int, description='Posición de inicio', default=0),
        ],
        tags=['Encomiendas'],
    )
    @action(detail=True, methods=['get'], url_path='historial')
    def historial(self, request, pk=None, **kwargs):
        enc = self.get_object()
        qs = enc.historial.select_related('empleado').order_by('-fecha_cambio')

        paginator = HistorialPagination()
        page = paginator.paginate_queryset(qs, request)
        if page is not None:
            serializer = HistorialEstadoSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = HistorialEstadoSerializer(qs, many=True)
        return Response(serializer.data)

    # ── Acción: estadísticas (con caché Redis) ───────────────────
    @extend_schema(
        summary='Estadísticas globales',
        description='Contadores del sistema: activas, en tránsito, con retraso y entregadas hoy. Cacheado 15 minutos.',
        tags=['Encomiendas'],
        responses={200: OpenApiResponse(description='Objeto con contadores')},
    )
    @action(detail=False, methods=['get'])
    def estadisticas(self, request, **kwargs):
        cache_key = f'estadisticas_empleado_{request.user.id}'
        data = cache.get(cache_key)

        if data is None:
            hoy = timezone.now().date()
            data = {
                'total_activas': Encomienda.objects.activas().count(),
                'en_transito': Encomienda.objects.en_transito().count(),
                'con_retraso': Encomienda.objects.con_retraso().count(),
                'entregadas_hoy': Encomienda.objects.filter(
                    estado='EN', fecha_entrega_real=hoy
                ).count(),
            }
            cache.set(cache_key, data, 60 * 15)  # 15 min

        return Response(data)

    # ── Acción: bulk_create ──────────────────────────────────────
    @extend_schema(
        summary='Crear múltiples encomiendas',
        description='Crea varias encomiendas en una sola petición. Body: lista de objetos.',
        tags=['Encomiendas'],
    )
    @action(detail=False, methods=['post'], url_path='bulk_create')
    def bulk_create(self, request, **kwargs):
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        import time

        serializer = self.get_serializer(data=request.data, many=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        empleado = Empleado.objects.get(email=request.user.email)
        
        channel_layer = get_channel_layer()
        validated_data = serializer.validated_data
        total = len(validated_data)
        encomiendas = []
        
        for i, item_data in enumerate(validated_data, 1):
            item_data['empleado_registro'] = empleado
            enc = serializer.child.create(item_data)
            encomiendas.append(enc)
            
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    'encomiendas_global',
                    {
                        'type': 'encomienda_progreso',
                        'actual': i,
                        'total': total,
                        'codigo': enc.codigo
                    }
                )
            time.sleep(0.1) # Pequeño retardo para observar la barra de progreso

        return Response(
            self.get_serializer(encomiendas, many=True).data,
            status=status.HTTP_201_CREATED
        )

    # ── Acción: bulk_estado ──────────────────────────────────────
    @extend_schema(
        summary='Cambiar estado a múltiples encomiendas',
        description='Cambia el estado de varias encomiendas. Reporta cuáles tuvieron errores.',
        tags=['Encomiendas'],
    )
    @action(detail=False, methods=['patch'], url_path='bulk_estado')
    def bulk_estado(self, request, **kwargs):
        ids = request.data.get('ids', [])
        nuevo_estado = request.data.get('estado')
        observacion = request.data.get('observacion', '')

        if not ids:
            return Response(
                {'error': 'El campo ids es requerido y no puede estar vacío.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not nuevo_estado:
            return Response(
                {'error': 'El campo estado es requerido.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            empleado = Empleado.objects.get(email=request.user.email)
        except Empleado.DoesNotExist:
            return Response(
                {'error': 'El usuario no tiene un empleado asociado.'},
                status=status.HTTP_403_FORBIDDEN
            )

        encomiendas = Encomienda.objects.filter(id__in=ids)
        actualizadas = []
        errores = []

        for enc in encomiendas:
            try:
                enc.cambiar_estado(nuevo_estado, empleado, observacion)
                actualizadas.append(enc.id)
            except ValueError as e:
                errores.append({'id': enc.id, 'error': str(e)})

        ids_procesados = list(encomiendas.values_list('id', flat=True))
        no_encontrados = [i for i in ids if i not in ids_procesados]

        return Response({
            'actualizadas': actualizadas,
            'errores': errores,
            'no_encontrados': no_encontrados,
            'total': len(actualizadas),
        })
