# envios/models.py
from django.db import models

class Encomienda(models.Model):
    class EstadoChoices(models.TextChoices):
        PENDIENTE   = 'PE', 'Pendiente'
        EN_TRANSITO = 'TR', 'En tránsito'
        ENTREGADO   = 'EN', 'Entregado'
        DEVUELTO    = 'DE', 'Devuelto'

    codigo        = models.CharField(max_length=20, unique=True)
    descripcion   = models.TextField()
    peso_kg       = models.DecimalField(max_digits=8, decimal_places=2)
    estado        = models.CharField(
        max_length=2, choices=EstadoChoices.choices,
        default=EstadoChoices.PENDIENTE)
    fecha_envio   = models.DateTimeField(auto_now_add=True)
    fecha_entrega = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.codigo} - {self.get_estado_display()}"

    class Meta:
        verbose_name        = 'Encomienda'
        verbose_name_plural = 'Encomiendas'
        ordering            = ['-fecha_envio']
