# api/views.py
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from api.throttles import LoginRateThrottle


class EncomiendaTokenSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Agregar datos del empleado al payload del JWT
        token['username'] = user.username
        token['email'] = user.email

        try:
            emp = user.empleado
            token['empleado_id'] = emp.id
            token['empleado_cod'] = emp.codigo
            token['cargo'] = emp.cargo
        except Exception:
            pass

        return token


class EncomiendaTokenView(TokenObtainPairView):
    serializer_class = EncomiendaTokenSerializer
    throttle_classes = [LoginRateThrottle]
