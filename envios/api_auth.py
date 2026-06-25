# envios/api_auth.py
from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from drf_spectacular.utils import extend_schema


class LoginCookieRequestSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()


class MessageSerializer(serializers.Serializer):
    message = serializers.CharField()


class LoginCookieView(APIView):
    permission_classes = []

    @extend_schema(
        summary='Login con HttpOnly Cookie',
        description='Autentica al usuario y guarda el JWT en una cookie HttpOnly.',
        request=LoginCookieRequestSerializer,
        responses={200: MessageSerializer},
        tags=['Auth'],
    )
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(username=username, password=password)

        if not user:
            return Response(
                {'error': 'Credenciales inválidas.'},
                status=401
            )

        refresh = RefreshToken.for_user(user)
        response = Response({'message': 'Login exitoso.'})

        # Guardar el JWT en una HttpOnly Cookie
        response.set_cookie(
            key='access_token',
            value=str(refresh.access_token),
            httponly=True,
            secure=False,       # True en producción (HTTPS)
            samesite='Lax',
            max_age=3600,       # 1 hora
        )
        response.set_cookie(
            key='refresh_token',
            value=str(refresh),
            httponly=True,
            secure=False,
            samesite='Lax',
            max_age=604800,     # 7 días
        )
        return response


class LogoutCookieView(APIView):
    @extend_schema(
        summary='Logout con HttpOnly Cookie',
        description='Elimina las cookies de autenticación.',
        responses={200: MessageSerializer},
        tags=['Auth'],
    )
    def post(self, request):
        response = Response({'message': 'Logout exitoso.'})
        response.delete_cookie('access_token')
        response.delete_cookie('refresh_token')
        return response
