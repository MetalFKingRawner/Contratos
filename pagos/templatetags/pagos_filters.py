# pagos/templatetags/pagos_filters.py
from django import template
from django.utils import timezone

register = template.Library()

@register.filter
def estado_general(pagos):
    """
    Devuelve el estado general basado en los pagos de un trámite.
    Valores: 'atrasado', 'pendiente', 'pagado', 'sin_cuotas'
    
    IMPORTANTE: Verifica si hay pagos pendientes con fecha vencida (atrasados)
    """
    if not pagos or pagos.count() == 0:
        return 'sin_cuotas'
    
    # Convertir QuerySet a lista para mejor rendimiento
    pagos_lista = list(pagos)
    hoy = timezone.now().date()
    
    # PRIMERO: Verificar si hay algún pago pendiente con fecha vencida (atrasado)
    for pago in pagos_lista:
        if pago.estado.codigo == 'pendiente' and pago.fecha_vencimiento < hoy:
            return 'atrasado'
    
    # SEGUNDO: Verificar si hay pagos con estado explícito 'atrasado'
    for pago in pagos_lista:
        if pago.estado.codigo == 'atrasado':
            return 'atrasado'
    
    # TERCERO: Si no hay atrasados, verificar si hay pendientes
    for pago in pagos_lista:
        if pago.estado.codigo == 'pendiente':
            return 'pendiente'
    
    # CUARTO: Si llegamos aquí, todos los pagos están en estado 'pagado' u otro
    for pago in pagos_lista:
        if pago.estado.codigo == 'pagado':
            return 'pagado'
    
    return 'sin_cuotas'


@register.filter
def proximo_vencimiento(pagos):
    """
    Devuelve el próximo vencimiento de entre los pagos pendientes.
    """
    if not pagos:
        return None
    
    hoy = timezone.now().date()
    proximo = None
    
    for pago in pagos:
        if pago.estado.codigo == 'pendiente':
            if not proximo or pago.fecha_vencimiento < proximo.fecha_vencimiento:
                proximo = pago
    
    return proximo.fecha_vencimiento if proximo else None


@register.filter
def saldo_pendiente(pagos):
    """
    Calcula el saldo pendiente total.
    """
    if not pagos:
        return 0
    
    total_pagado = sum(pago.monto_pagado for pago in pagos)
    total_esperado = sum(pago.monto for pago in pagos)
    
    return total_esperado - total_pagado


@register.filter
def porcentaje_pagado(pagos):
    """
    Calcula el porcentaje pagado.
    """
    if not pagos:
        return 0
    
    try:
        total_pagado = sum(pago.monto_pagado for pago in pagos)
        total_esperado = sum(pago.monto for pago in pagos)
        
        if total_esperado == 0:
            return 0
        
        return (total_pagado / total_esperado) * 100
    except (AttributeError, TypeError):
        return 0


@register.filter
def monto_total(pagos):
    """
    Calcula el monto total de todos los pagos.
    """
    if not pagos:
        return 0
    
    return sum(pago.monto for pago in pagos)


@register.filter
def monto_pagado_total(pagos):
    """
    Calcula el monto total pagado.
    """
    if not pagos:
        return 0
    
    return sum(pago.monto_pagado for pago in pagos)


@register.filter
def tiene_pagos_atrasados(pagos):
    """
    Verifica si hay pagos atrasados.
    Considera tanto pagos con estado 'atrasado' como pagos pendientes con fecha vencida.
    """
    if not pagos:
        return False
    
    hoy = timezone.now().date()
    
    for pago in pagos:
        # Verificar si tiene estado atrasado explícito
        if pago.estado.codigo == 'atrasado':
            return True
        # Verificar si es un pago pendiente con fecha vencida
        if pago.estado.codigo == 'pendiente' and pago.fecha_vencimiento < hoy:
            return True
    
    return False


@register.filter
def pagos_pendientes_count(pagos):
    """
    Cuenta cuántos pagos están pendientes (no incluye atrasados).
    """
    if not pagos:
        return 0
    
    hoy = timezone.now().date()
    count = 0
    
    for pago in pagos:
        # Solo contar pendientes que NO estén vencidos
        if pago.estado.codigo == 'pendiente' and pago.fecha_vencimiento >= hoy:
            count += 1
    
    return count


@register.filter
def pagos_atrasados_count(pagos):
    """
    Cuenta cuántos pagos están atrasados.
    Incluye pagos con estado 'atrasado' Y pagos pendientes con fecha vencida.
    """
    if not pagos:
        return 0
    
    hoy = timezone.now().date()
    count = 0
    
    for pago in pagos:
        # Contar pagos con estado atrasado
        if pago.estado.codigo == 'atrasado':
            count += 1
        # Contar pagos pendientes con fecha vencida
        elif pago.estado.codigo == 'pendiente' and pago.fecha_vencimiento < hoy:
            count += 1
    
    return count

@register.filter
def contar_atrasados(tramites):
    """
    Cuenta el TOTAL de pagos atrasados en una lista de trámites.
    Incluye:
    - Pagos con estado 'atrasado' explícito
    - Pagos con estado 'pendiente' y fecha_vencimiento vencida
    """
    if not tramites:
        return 0
    
    from django.utils import timezone
    hoy = timezone.now().date()
    total_atrasados = 0
    
    for tramite in tramites:
        pagos = tramite.pagos.all()
        for pago in pagos:
            # Contar pagos con estado atrasado
            if pago.estado.codigo == 'atrasado':
                total_atrasados += 1
            # Contar pagos pendientes con fecha vencida
            elif pago.estado.codigo == 'pendiente' and pago.fecha_vencimiento < hoy:
                total_atrasados += 1
    
    return total_atrasados