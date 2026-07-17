import os
import django
from django.utils import timezone
from datetime import timedelta

# No necesitamos os.environ.setdefault ni django.setup() porque
# lo ejecutaremos dentro de "manage.py shell", que ya tiene el entorno cargado.

from clientes.models import Cliente
from rutas.models import Ruta
from envios.models import Empleado, Encomienda
from config.choices import TipoDocumento, EstadoEnvio, EstadoGeneral

def run_seed():
    print("Creando clientes...")
    c1, _ = Cliente.objects.get_or_create(
        nro_doc="12345678",
        defaults={
            "nombres": "Juan", "apellidos": "Perez",
            "tipo_doc": TipoDocumento.DNI, "telefono": "999888777",
            "email": "juan@example.com", "direccion": "Av. Lima 123"
        }
    )
    c2, _ = Cliente.objects.get_or_create(
        nro_doc="87654321",
        defaults={
            "nombres": "Maria", "apellidos": "Gomez",
            "tipo_doc": TipoDocumento.DNI, "telefono": "987654321",
            "email": "maria@example.com", "direccion": "Calle Cusco 456"
        }
    )
    c3, _ = Cliente.objects.get_or_create(
        nro_doc="11223344",
        defaults={
            "nombres": "Carlos", "apellidos": "Ruiz",
            "tipo_doc": TipoDocumento.DNI, "telefono": "911223344",
            "email": "carlos@example.com", "direccion": "Jr. Arequipa 789"
        }
    )

    print("Creando rutas...")
    r1, _ = Ruta.objects.get_or_create(
        codigo="LIM-CUS",
        defaults={
            "origen": "Lima", "destino": "Cusco",
            "descripcion": "Ruta directa de Lima a Cusco en bus",
            "precio_base": 25.00, "dias_entrega": 2
        }
    )
    r2, _ = Ruta.objects.get_or_create(
        codigo="LIM-TRU",
        defaults={
            "origen": "Lima", "destino": "Trujillo",
            "descripcion": "Ruta hacia el norte",
            "precio_base": 15.00, "dias_entrega": 1
        }
    )
    r3, _ = Ruta.objects.get_or_create(
        codigo="CUS-ARE",
        defaults={
            "origen": "Cusco", "destino": "Arequipa",
            "descripcion": "Ruta sur",
            "precio_base": 20.00, "dias_entrega": 1
        }
    )

    print("Creando empleado administrador...")
    emp, _ = Empleado.objects.get_or_create(
        email="admin@example.com",
        defaults={
            "codigo": "EMP-001", "nombres": "Admin", "apellidos": "Sistema",
            "cargo": "Gerente", "fecha_ingreso": timezone.now().date(),
            "telefono": "900000000"
        }
    )

    print("Creando encomiendas...")
    if Encomienda.objects.count() < 3:
        # Encomienda Pendiente
        Encomienda.crear_con_costo_calculado(
            remitente=c1, destinatario=c2, ruta=r1, empleado=emp,
            descripcion="Caja de chocolates", peso_kg=2.5
        )

        # Encomienda En Tránsito
        e2 = Encomienda.crear_con_costo_calculado(
            remitente=c2, destinatario=c3, ruta=r2, empleado=emp,
            descripcion="Documentos legales", peso_kg=0.5
        )
        e2.cambiar_estado(EstadoEnvio.EN_TRANSITO, emp, "Salió de agencia origen")

        # Encomienda Entregada (ayer)
        e3 = Encomienda.crear_con_costo_calculado(
            remitente=c3, destinatario=c1, ruta=r3, empleado=emp,
            descripcion="Ropa de invierno", peso_kg=8.0
        )
        e3.cambiar_estado(EstadoEnvio.EN_TRANSITO, emp, "Salió a destino")
        e3.cambiar_estado(EstadoEnvio.EN_DESTINO, emp, "Llegó a agencia destino")
        # e3.cambiar_estado(EstadoEnvio.ENTREGADO, emp, "Entregado a cliente")

        print("Base de datos poblada exitosamente.")
    else:
        print("Ya existen encomiendas en la base de datos.")

run_seed()
