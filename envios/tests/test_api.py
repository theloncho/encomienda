# envios/tests/test_api.py
import pytest
from decimal import Decimal
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from envios.models import Encomienda
from config.choices import EstadoEnvio
from .factories import (
    UserFactory, ClienteFactory, RutaFactory,
    EmpleadoFactory, EncomiendaFactory,
)


# ══════════════════════════════════════════════════════════════════════
# Tests de Autenticación
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestAutenticacion:
    def test_sin_token_devuelve_401(self, api_client):
        response = api_client.get('/api/v1/encomiendas/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_token_invalido_devuelve_401(self, api_client):
        api_client.credentials(HTTP_AUTHORIZATION='Bearer tokeninvalido')
        response = api_client.get('/api/v1/encomiendas/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_con_token_valido_devuelve_200(self):
        user = UserFactory()
        EmpleadoFactory(email=user.email)
        client = APIClient()
        refresh = RefreshToken.for_user(user)
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}'
        )
        response = client.get('/api/v1/encomiendas/')
        assert response.status_code == status.HTTP_200_OK


# ══════════════════════════════════════════════════════════════════════
# Tests de Listado
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestListadoEncomiendas:
    def setup_method(self):
        self.user = UserFactory()
        self.empleado = EmpleadoFactory(email=self.user.email)
        self.ruta = RutaFactory()
        self.cliente1 = ClienteFactory()
        self.cliente2 = ClienteFactory()
        self.client = APIClient()
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}'
        )

    def test_lista_respuesta_paginada(self):
        EncomiendaFactory(
            remitente=self.cliente1, destinatario=self.cliente2,
            ruta=self.ruta, empleado_registro=self.empleado
        )
        response = self.client.get('/api/v1/encomiendas/')
        assert response.status_code == status.HTTP_200_OK
        for campo in ['count', 'next', 'previous', 'results']:
            assert campo in response.data
        assert response.data['count'] == 1

    def test_filtro_por_estado(self):
        enc_pe = EncomiendaFactory(
            estado='PE', ruta=self.ruta,
            remitente=self.cliente1, destinatario=self.cliente2,
            empleado_registro=self.empleado
        )
        enc_tr = EncomiendaFactory(
            estado='TR', ruta=self.ruta,
            remitente=self.cliente1, destinatario=self.cliente2,
            empleado_registro=self.empleado
        )
        response = self.client.get('/api/v1/encomiendas/?estado=PE')
        codigos = [r['codigo'] for r in response.data['results']]
        assert enc_pe.codigo in codigos
        assert enc_tr.codigo not in codigos

    def test_busqueda_por_codigo(self):
        EncomiendaFactory(
            codigo='ENC-2026-BUSCAR', ruta=self.ruta,
            remitente=self.cliente1, destinatario=self.cliente2,
            empleado_registro=self.empleado
        )
        response = self.client.get('/api/v1/encomiendas/?search=BUSCAR')
        assert response.data['count'] == 1
        assert response.data['results'][0]['codigo'] == 'ENC-2026-BUSCAR'


# ══════════════════════════════════════════════════════════════════════
# Tests de Creación
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestCrearEncomienda:
    def setup_method(self):
        self.user = UserFactory()
        self.empleado = EmpleadoFactory(email=self.user.email)
        self.cliente1 = ClienteFactory()
        self.cliente2 = ClienteFactory()
        self.ruta = RutaFactory(precio_base=Decimal('25.00'))
        self.client = APIClient()
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}'
        )
        self.data_valida = {
            'codigo': 'ENC-2026-TEST',
            'descripcion': 'Paquete de prueba',
            'peso_kg': '3.50',
            'remitente': self.cliente1.pk,
            'destinatario': self.cliente2.pk,
            'ruta': self.ruta.pk,
            'costo_envio': '25.00',
        }

    def test_crear_exitoso_devuelve_201(self):
        response = self.client.post(
            '/api/v1/encomiendas/', self.data_valida, format='json'
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['codigo'] == 'ENC-2026-TEST'
        assert response.data['estado'] == 'PE'
        assert Encomienda.objects.filter(codigo='ENC-2026-TEST').exists()

    def test_remitente_igual_destinatario_devuelve_400(self):
        data = {**self.data_valida, 'destinatario': self.cliente1.pk}
        response = self.client.post(
            '/api/v1/encomiendas/', data, format='json'
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_peso_negativo_devuelve_400_con_campo(self):
        data = {**self.data_valida, 'peso_kg': '-1.00'}
        response = self.client.post(
            '/api/v1/encomiendas/', data, format='json'
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_codigo_sin_prefijo_devuelve_400(self):
        data = {**self.data_valida, 'codigo': 'PKG-2026-001'}
        response = self.client.post(
            '/api/v1/encomiendas/', data, format='json'
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_sin_auth_no_crea_y_devuelve_401(self, api_client):
        response = api_client.post(
            '/api/v1/encomiendas/', self.data_valida, format='json'
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert not Encomienda.objects.filter(codigo='ENC-2026-TEST').exists()


# ══════════════════════════════════════════════════════════════════════
# Tests de Cambiar Estado
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestCambiarEstado:
    """Tests del endpoint POST /api/v1/encomiendas/{pk}/cambiar_estado/"""

    def setup_method(self):
        self.user = UserFactory()
        self.empleado = EmpleadoFactory(email=self.user.email)
        self.enc = EncomiendaFactory(
            empleado_registro=self.empleado, estado='PE'
        )
        self.client = APIClient()
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}'
        )

    def test_cambiar_estado_exitoso_actualiza_bd_y_crea_historial(self):
        url = f'/api/v1/encomiendas/{self.enc.pk}/cambiar_estado/'
        data = {'estado': 'TR', 'observacion': 'Recogido en agencia Lima'}
        response = self.client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        self.enc.refresh_from_db()
        assert self.enc.estado == EstadoEnvio.EN_TRANSITO
        assert self.enc.historial.count() == 1
        h = self.enc.historial.first()
        assert h.estado_anterior == 'PE'
        assert h.estado_nuevo == 'TR'
        assert h.observacion == 'Recogido en agencia Lima'

    def test_cambiar_al_mismo_estado_devuelve_400(self):
        url = f'/api/v1/encomiendas/{self.enc.pk}/cambiar_estado/'
        response = self.client.post(url, {'estado': 'PE'}, format='json')
        # 400 or 422 are both acceptable
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ]
        self.enc.refresh_from_db()
        assert self.enc.historial.count() == 0

    def test_sin_campo_estado_devuelve_400(self):
        url = f'/api/v1/encomiendas/{self.enc.pk}/cambiar_estado/'
        response = self.client.post(url, {}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_encomienda_inexistente_devuelve_404(self):
        url = '/api/v1/encomiendas/99999/cambiar_estado/'
        response = self.client.post(url, {'estado': 'TR'}, format='json')
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ══════════════════════════════════════════════════════════════════════
# Tests de Acciones Personalizadas
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestAccionesPersonalizadas:
    """Tests de con_retraso, pendientes y estadisticas"""

    def setup_method(self):
        from django.utils import timezone
        from datetime import timedelta

        self.user = UserFactory()
        self.empleado = EmpleadoFactory(email=self.user.email)
        self.client = APIClient()
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}'
        )

        ayer = timezone.now().date() - timedelta(days=1)
        self.enc_retraso = EncomiendaFactory(
            estado='TR', fecha_entrega_est=ayer,
            empleado_registro=self.empleado
        )
        self.enc_normal = EncomiendaFactory(
            estado='PE', empleado_registro=self.empleado
        )

    def test_con_retraso_solo_devuelve_retrasadas(self):
        response = self.client.get('/api/v1/encomiendas/con_retraso/')
        assert response.status_code == status.HTTP_200_OK
        codigos = [r['codigo'] for r in response.data]
        assert self.enc_retraso.codigo in codigos
        assert self.enc_normal.codigo not in codigos

    def test_pendientes_solo_devuelve_pendientes(self):
        response = self.client.get('/api/v1/encomiendas/pendientes/')
        assert response.status_code == status.HTTP_200_OK
        codigos = [r['codigo'] for r in response.data]
        assert self.enc_normal.codigo in codigos
        assert self.enc_retraso.codigo not in codigos

    def test_estadisticas_devuelve_todos_los_contadores(self):
        response = self.client.get('/api/v1/encomiendas/estadisticas/')
        assert response.status_code == status.HTTP_200_OK
        for campo in ['total_activas', 'en_transito', 'con_retraso', 'entregadas_hoy']:
            assert campo in response.data
        assert response.data['con_retraso'] == 1


# ══════════════════════════════════════════════════════════════════════
# Tests de Versionado
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
class TestVersionado:
    """Tests de versionado v1 vs v2"""

    def setup_method(self):
        self.user = UserFactory()
        EmpleadoFactory(email=self.user.email)
        EncomiendaFactory()
        self.client = APIClient()
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}'
        )

    def test_v1_responde_200_con_cabecera(self):
        response = self.client.get('/api/v1/encomiendas/')
        assert response.status_code == status.HTTP_200_OK
        assert response['X-API-Version'] == 'v1'

    def test_v2_responde_200_con_cabecera(self):
        response = self.client.get('/api/v2/encomiendas/')
        assert response.status_code == status.HTTP_200_OK
        assert response['X-API-Version'] == 'v2'

    def test_v2_incluye_campo_meta(self):
        response = self.client.get('/api/v2/encomiendas/')
        primer = response.data['results'][0]
        assert 'meta' in primer
        assert primer['meta']['version'] == 'v2'

    def test_v3_no_permitida_devuelve_404(self):
        response = self.client.get('/api/v3/encomiendas/')
        assert response.status_code == status.HTTP_404_NOT_FOUND
