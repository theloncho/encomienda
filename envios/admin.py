# envios/admin.py
from django.contrib import admin
from .models import Encomienda

@admin.register(Encomienda)
class EncomiendaAdmin(admin.ModelAdmin):
    list_display  = ('codigo', 'descripcion', 'peso_kg', 'estado', 'fecha_envio')
    list_filter   = ('estado',)
    search_fields = ('codigo', 'descripcion')
