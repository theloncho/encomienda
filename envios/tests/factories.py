# envios/tests/factories.py
import factory
from decimal import Decimal
from factory.django import DjangoModelFactory
from django.contrib.auth.models import User
from clientes.models import Cliente
from rutas.models import Ruta
from envios.models import Empleado, Encomienda
from config.choices import EstadoGeneral, TipoDocumento


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f'user{n}')
    email = factory.LazyAttribute(lambda o: f'{o.username}@enc.pe')
    password = factory.PostGenerationMethodCall('set_password', 'test1234')


class ClienteFactory(DjangoModelFactory):
    class Meta:
        model = Cliente

    tipo_doc = TipoDocumento.DNI
    nro_doc = factory.Sequence(lambda n: f'{10000000 + n}')
    nombres = factory.Faker('first_name', locale='es')
    apellidos = factory.Faker('last_name', locale='es')
    estado = EstadoGeneral.ACTIVO


class RutaFactory(DjangoModelFactory):
    class Meta:
        model = Ruta

    codigo = factory.Sequence(lambda n: f'RUT-{n:03d}')
    origen = 'Lima'
    destino = factory.Sequence(lambda n: f'Ciudad-{n}')
    precio_base = Decimal('25.00')
    dias_entrega = 2
    estado = EstadoGeneral.ACTIVO


class EmpleadoFactory(DjangoModelFactory):
    class Meta:
        model = Empleado

    codigo = factory.Sequence(lambda n: f'EMP-{n:03d}')
    nombres = factory.Faker('first_name', locale='es')
    apellidos = factory.Faker('last_name', locale='es')
    cargo = 'Operador de Envios'
    email = factory.LazyAttribute(lambda o: f'{o.codigo.lower()}@enc.pe')
    fecha_ingreso = factory.Faker('date_this_decade')
    estado = EstadoGeneral.ACTIVO


class EncomiendaFactory(DjangoModelFactory):
    class Meta:
        model = Encomienda
        skip_postgeneration_save = True

    codigo = factory.Sequence(lambda n: f'ENC-2026-{n:04d}')
    descripcion = factory.Faker('sentence', locale='es')
    peso_kg = Decimal('3.50')
    remitente = factory.SubFactory(ClienteFactory)
    destinatario = factory.SubFactory(ClienteFactory)
    ruta = factory.SubFactory(RutaFactory)
    empleado_registro = factory.SubFactory(EmpleadoFactory)
    costo_envio = Decimal('25.00')
    estado = 'PE'

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Skip full_clean() to allow past dates and other test scenarios"""
        obj = model_class(*args, **kwargs)
        # Call Django's base Model.save() directly, skipping
        # Encomienda.save() which triggers full_clean()
        from django.db import models
        models.Model.save(obj)
        return obj

