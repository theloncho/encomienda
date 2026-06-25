# envios/views_async.py
import asyncio
import json
from django.http import JsonResponse
from django.utils import timezone
from .models import Encomienda

async def dashboard_stats_async(request):
    """
    Endpoint async que calcula las estadisticas del dashboard.
    ANTES (sincrono): 4 queries secuenciales = 4 * 10ms = 40ms
    AHORA (async): 4 queries en paralelo   = max(10ms) = 10ms
    """
    if not request.user.is_authenticated:
        from django.http import HttpResponse
        return HttpResponse(status=401)

    hoy = timezone.now().date()

    # Las 4 queries corren EN PARALELO
    activas, en_transito, con_retraso, entregadas_hoy = await asyncio.gather(
        Encomienda.objects.activas().acount(),
        Encomienda.objects.en_transito().acount(),
        Encomienda.objects.con_retraso().acount(),
        Encomienda.objects.filter(
            estado='EN', fecha_entrega_real=hoy
        ).acount(),
    )

    return JsonResponse({
        'activas':        activas,
        'en_transito':    en_transito,
        'con_retraso':    con_retraso,
        'entregadas_hoy': entregadas_hoy,
    })


async def enviar_notificacion_email(enc, nuevo_estado: str):
    """Envia un email de notificacion en background."""
    await asyncio.sleep(0.5)
    print(f'Email enviado: {enc.codigo} -> {nuevo_estado}')


async def registrar_en_log_externo(enc, estado: str):
    """Registra el cambio en un sistema de logs externo en background."""
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                'https://logs.empresa.pe/api/encomiendas',
                json={'codigo': enc.codigo, 'estado': estado},
                timeout=3.0
            )
    except Exception:
        pass


# Conjunto global para evitar que el Garbage Collector destruya tareas asíncronas pendientes
_tasks = set()

async def cambiar_estado_vista(request, pk: int):
    """
    Vista async que cambia el estado y lanza las notificaciones
    en background mediante create_task sin hacer esperar al cliente.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Metodo no permitido'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON invalido'}, status=400)

    try:
        enc = await Encomienda.objects.aget(pk=pk)
    except Encomienda.DoesNotExist:
        return JsonResponse({'error': 'Encomienda no encontrada'}, status=404)

    nuevo_estado = data.get('estado')
    if not nuevo_estado:
        return JsonResponse({'error': 'Estado es requerido'}, status=400)

    # Paso 1: cambiar el estado (CRITICO - el cliente espera esto)
    enc.estado = nuevo_estado
    await enc.asave()

    # Paso 2: lanzar notificaciones en BACKGROUND (no criticas)
    task1 = asyncio.create_task(enviar_notificacion_email(enc, nuevo_estado))
    task2 = asyncio.create_task(registrar_en_log_externo(enc, nuevo_estado))
    
    _tasks.add(task1)
    _tasks.add(task2)
    task1.add_done_callback(_tasks.discard)
    task2.add_done_callback(_tasks.discard)

    return JsonResponse({'ok': True, 'estado': nuevo_estado})
