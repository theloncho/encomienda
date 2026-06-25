# envios/api_views.py
# Contiene: FBV con @api_view, CBV con APIView, Mixins y Generic Views
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status, mixins, generics
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema

from .models import Encomienda
from .serializers import (
    EncomiendaSerializer, EncomiendaDetailSerializer,
    ClienteSerializer, RutaSerializer,
)
from clientes.models import Cliente
from rutas.models import Ruta
from api.pagination import ClientePagination


# ══════════════════════════════════════════════════════════════════════
# 5.2.2 — FBV con @api_view
# ══════════════════════════════════════════════════════════════════════

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def encomienda_list(request):
    if request.method == 'GET':
        qs = Encomienda.objects.con_relaciones()
        serializer = EncomiendaSerializer(
            qs, many=True, context={'request': request}
        )
        return Response(serializer.data)
    elif request.method == 'POST':
        serializer = EncomiendaSerializer(
            data=request.data, context={'request': request}
        )
        if serializer.is_valid():
            serializer.save(empleado_registro=request.user.empleado)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def encomienda_detail(request, pk):
    enc = get_object_or_404(Encomienda, pk=pk)
    if request.method == 'GET':
        return Response(EncomiendaSerializer(enc).data)
    elif request.method in ['PUT', 'PATCH']:
        s = EncomiendaSerializer(
            enc, data=request.data, partial=(request.method == 'PATCH')
        )
        if s.is_valid():
            s.save()
            return Response(s.data)
        return Response(s.errors, status=400)
    elif request.method == 'DELETE':
        enc.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ══════════════════════════════════════════════════════════════════════
# 5.3 — CBV con APIView
# ══════════════════════════════════════════════════════════════════════

class EncomiendaListAPIView(APIView):
    """GET /api/v1/encomiendas/  POST /api/v1/encomiendas/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Encomienda.objects.con_relaciones()
        serializer = EncomiendaSerializer(
            qs, many=True, context={'request': request}
        )
        return Response(serializer.data)

    def post(self, request):
        serializer = EncomiendaSerializer(
            data=request.data, context={'request': request}
        )
        if serializer.is_valid():
            serializer.save(empleado_registro=request.user.empleado)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EncomiendaDetailAPIView(APIView):
    """GET/PUT/PATCH/DELETE /api/v1/encomiendas/{pk}/"""
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        return get_object_or_404(
            Encomienda.objects.con_relaciones(), pk=pk
        )

    def get(self, request, pk):
        enc = self.get_object(pk)
        return Response(EncomiendaDetailSerializer(enc).data)

    def put(self, request, pk):
        enc = self.get_object(pk)
        s = EncomiendaSerializer(
            enc, data=request.data, context={'request': request}
        )
        if s.is_valid():
            s.save()
            return Response(s.data)
        return Response(s.errors, status=400)

    def patch(self, request, pk):
        enc = self.get_object(pk)
        s = EncomiendaSerializer(
            enc, data=request.data, partial=True,
            context={'request': request}
        )
        if s.is_valid():
            s.save()
            return Response(s.data)
        return Response(s.errors, status=400)

    def delete(self, request, pk):
        enc = self.get_object(pk)
        enc.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ══════════════════════════════════════════════════════════════════════
# 5.4 — Mixins
# ══════════════════════════════════════════════════════════════════════

class EncomiendaListCreateView(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    generics.GenericAPIView
):
    queryset = Encomienda.objects.con_relaciones()
    serializer_class = EncomiendaSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(empleado_registro=self.request.user.empleado)


class EncomiendaDetailView(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    generics.GenericAPIView
):
    queryset = Encomienda.objects.con_relaciones()
    serializer_class = EncomiendaSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        return self.destroy(request, *args, **kwargs)


# ══════════════════════════════════════════════════════════════════════
# 5.5 — Generic Views (la forma recomendada)
# ══════════════════════════════════════════════════════════════════════

@extend_schema(
    summary='Listar clientes activos',
    description='Devuelve todos los clientes con estado Activo, paginados de 20 en 20.',
    tags=['Clientes'],
)
class ClienteListView(generics.ListAPIView):
    serializer_class = ClienteSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ClientePagination

    def get_queryset(self):
        return Cliente.objects.activos()


@extend_schema(
    summary='Listar rutas activas',
    description='Devuelve todas las rutas con estado Activo. Sin paginación.',
    tags=['Rutas'],
)
class RutaListView(generics.ListAPIView):
    serializer_class = RutaSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        return Ruta.objects.activas()
