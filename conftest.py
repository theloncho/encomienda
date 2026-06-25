# conftest.py (raiz del proyecto)
import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User


@pytest.fixture
def api_client():
    """Cliente de API sin autenticación"""
    return APIClient()


@pytest.fixture
def user(db):
    """Usuario de prueba"""
    return User.objects.create_user(
        username='test_empleado',
        email='empleado@encomiendas.pe',
        password='test1234',
    )


@pytest.fixture
def auth_client(api_client, user):
    """Cliente de API con JWT válido"""
    refresh = RefreshToken.for_user(user)
    api_client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}'
    )
    return api_client
