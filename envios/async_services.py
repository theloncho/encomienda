# envios/async_services.py
import asyncio
import httpx
from django.utils import timezone
from .models import Encomienda

async def verificar_estado_transportista(codigo: str) -> dict:
    """
    Corrutina que consulta la API del transportista.
    Puede pausarse mientras espera la respuesta HTTP.
    """
    url = f'https://api.transportista.pe/v1/track/{codigo}'
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=5.0)
            data = response.json()
            return {
                'codigo': codigo,
                'encontrado': True,
                'estado_ext': data.get('status'),
                'ubicacion': data.get('location'),
                'timestamp': timezone.now().isoformat(),
            }
    except httpx.TimeoutException:
        return {'codigo': codigo, 'encontrado': False, 'error': 'timeout'}
    except httpx.ConnectError:
        return {'codigo': codigo, 'encontrado': False, 'error': 'conexion'}
    except Exception as e:
        return {'codigo': codigo, 'encontrado': False, 'error': str(e)}


async def actualizar_estados_en_transito() -> list:
    """
    Actualiza el estado de todas las encomiendas en transito
    consultando la API del transportista en paralelo.
    """
    encomiendas = await Encomienda.objects.en_transito().alist()
    if not encomiendas:
        return []

    resultados = await asyncio.gather(
        *[verificar_estado_transportista(enc.codigo) for enc in encomiendas],
        return_exceptions=True
    )

    actualizadas = []
    for enc, resultado in zip(encomiendas, resultados):
        if isinstance(resultado, Exception):
            continue

        if resultado.get('encontrado') and resultado.get('estado_ext') == 'DELIVERED':
            enc.estado = 'EN'
            enc.fecha_entrega_real = timezone.now().date()
            await enc.asave()
            actualizadas.append(enc.codigo)

    return actualizadas


async def verificar_una(session: httpx.AsyncClient, codigo: str) -> dict:
    """Verifica UNA encomienda. Se ejecuta en paralelo con las demas."""
    try:
        r = await session.get(
            f'https://api.transportista.pe/track/{codigo}',
            timeout=5.0
        )
        return {'codigo': codigo, 'ok': True, 'data': r.json()}
    except httpx.TimeoutException:
        return {'codigo': codigo, 'ok': False, 'error': 'timeout'}
    except Exception as e:
        return {'codigo': codigo, 'ok': False, 'error': str(e)}


async def verificar_lote_completo() -> dict:
    """
    Verifica TODAS las encomiendas en transito en paralelo.
    """
    encomiendas = await Encomienda.objects.en_transito().alist()
    if not encomiendas:
        return {'verificadas': 0, 'resultados': []}

    async with httpx.AsyncClient() as session:
        tareas = [
            verificar_una(session, enc.codigo)
            for enc in encomiendas
        ]
        resultados = await asyncio.gather(*tareas, return_exceptions=True)

    exitosas = [r for r in resultados if isinstance(r, dict) and r.get('ok')]
    fallidas = [r for r in resultados if isinstance(r, dict) and not r.get('ok')]
    errores = [r for r in resultados if isinstance(r, Exception)]

    return {
        'verificadas': len(encomiendas),
        'exitosas': len(exitosas),
        'fallidas': len(fallidas),
        'errores': len(errores),
        'resultados': resultados,
    }


async def verificar_api_externa(codigo: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.get(f'https://api.transportista.pe/track/{codigo}', timeout=5.0)
        return r.json()


async def verificar_con_timeout(enc) -> dict:
    """
    Verifica una encomienda con timeout estricto de 3 segundos usando wait_for.
    """
    try:
        resultado = await asyncio.wait_for(
            verificar_api_externa(enc.codigo),
            timeout=3.0
        )
        return resultado
    except asyncio.TimeoutError:
        return {
            'codigo': enc.codigo,
            'estado': enc.get_estado_display(),
            'fuente': 'cache_local',
            'advertencia': 'API del transportista no disponible',
        }
    except Exception as e:
        return {'error': str(e), 'codigo': enc.codigo}


async def verificar_lote_con_timeout(codigos: list) -> list:
    encomiendas = await Encomienda.objects.filter(codigo__in=codigos).alist()
    resultados = await asyncio.gather(
        *[verificar_con_timeout(enc) for enc in encomiendas],
        return_exceptions=True
    )
    return [
        r if not isinstance(r, Exception) else {'error': str(r)}
        for r in resultados
    ]
