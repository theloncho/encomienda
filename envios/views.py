from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q

from .models import Encomienda, Empleado, HistorialEstado
from config.choices import EstadoEnvio
from .forms import EncomiendaForm


@login_required
def dashboard(request):
    """Vista principal del sistema con estadísticas"""
    hoy = timezone.now().date()
    context = {
        'total_activas':    Encomienda.objects.activas().count(),
        'en_transito':      Encomienda.objects.en_transito().count(),
        'con_retraso':      Encomienda.objects.con_retraso().count(),
        'entregadas_hoy':   Encomienda.objects.filter(
                               estado=EstadoEnvio.ENTREGADO,
                               fecha_entrega_real=hoy).count(),
        'ultimas':          Encomienda.objects.con_relaciones()[:5],
    }
    return render(request, 'envios/dashboard.html', context)


@login_required
def encomienda_lista(request):
    qs = Encomienda.objects.con_relaciones()

    # Filtros opcionales
    estado = request.GET.get('estado', '')
    q      = request.GET.get('q', '')

    if estado:
        qs = qs.filter(estado=estado)
    if q:
        qs = qs.filter(
            Q(codigo__icontains=q) |
            Q(remitente__apellidos__icontains=q) |
            Q(destinatario__apellidos__icontains=q)
        )

    # Paginación
    paginator    = Paginator(qs, 15)            # 15 por página
    page_number  = request.GET.get('page', 1)  # página actual
    encomiendas  = paginator.get_page(page_number)  # objeto Page

    return render(request, 'envios/lista.html', {
        'encomiendas':    encomiendas,
        'estados':        EstadoEnvio.choices,
        'estado_activo':  estado,
        'q':              q,
    })


@login_required
def encomienda_detalle(request, pk):
    enc = get_object_or_404(Encomienda.objects.con_relaciones(), pk=pk)
    historial = enc.historial.select_related('empleado')
    return render(request, 'envios/detalle.html', {
        'encomienda': enc,
        'historial': historial
    })


@login_required
def encomienda_crear(request):
    """
    GET  -> muestra el formulario vacío
    POST -> valida, guarda y redirige al detalle
    """
    if request.method == 'POST':
        form = EncomiendaForm(request.POST)
        if form.is_valid():
            enc = form.save(commit=False)    # no guarda aún en BD
            # Obtenemos el empleado. El usuario debe estar asociado a un Empleado.
            # En Django admin se tendrá que haber enlazado el User con Empleado (por email)
            # o podemos fallar gracefulmente si no lo encuentra.
            try:
                empleado = Empleado.objects.get(email=request.user.email)
                enc.empleado_registro = empleado
                enc.save()                     # ahora sí guarda
                messages.success(
                    request,
                    f'Encomienda {enc.codigo} registrada correctamente.'
                )
                # Redirige para evitar reenvío del formulario al recargar
                return redirect('encomienda_detalle', pk=enc.pk)
            except Empleado.DoesNotExist:
                messages.error(request, 'Tu usuario no tiene un empleado asociado. Contacta al administrador.')
    else:
        form = EncomiendaForm() # GET: form vacío

    return render(request, 'envios/form.html', {
        'form': form,
        'titulo': 'Nueva Encomienda',
    })


@login_required
def encomienda_cambiar_estado(request, pk):
    enc = get_object_or_404(Encomienda, pk=pk)
    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado')
        observacion  = request.POST.get('observacion', '')
        try:
            empleado = Empleado.objects.get(email=request.user.email)
            enc.cambiar_estado(nuevo_estado, empleado, observacion)
            messages.success(request, f'Estado actualizado a: {enc.get_estado_display()}')
        except Empleado.DoesNotExist:
            messages.error(request, 'Tu usuario no tiene un empleado asociado.')
        except ValueError as e:
            messages.error(request, str(e))
    return redirect('encomienda_detalle', pk=pk)


def health_check(request):
    """
    Endpoint para verificar el estado de salud de la aplicación,
    incluyendo la conexión a la base de datos y a la capa de canales (Redis).
    """
    from django.http import JsonResponse
    from django.db import connections
    from django.db.utils import OperationalError
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    db_ok = True
    try:
        connections['default'].cursor()
    except OperationalError:
        db_ok = False

    redis_ok = True
    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)('health_check_test', {'type': 'test'})
        else:
            redis_ok = False
    except Exception:
        redis_ok = False

    status_code = 200 if db_ok and redis_ok else 503
    return JsonResponse({
        'status': 'ok' if status_code == 200 else 'error',
        'database': 'connected' if db_ok else 'disconnected',
        'redis_channels': 'connected' if redis_ok else 'disconnected',
        'timestamp': timezone.now().isoformat(),
    }, status=status_code)
