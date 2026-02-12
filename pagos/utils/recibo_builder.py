import os
import uuid
from datetime import date
from django.conf import settings
from docxtpl import InlineImage
from docx.shared import Mm
import base64
import tempfile
from workflow.utils import calcular_superficie, numero_a_letras

def build_recibo_pago_from_instance(pago, request=None, tpl=None, firma_data=None):
    """
    Builder específico para recibo de pago desde la instancia de Pago
    Siguiendo la misma estructura que build_solicitud_contrato_context
    """
    # Obtener objetos relacionados
    tramite = pago.tramite
    financiamiento = tramite.financiamiento
    lote = financiamiento.lote
    cliente = tramite.cliente
    proyecto = lote.proyecto
    
    # Fecha actual y formato
    hoy = date.today()
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
             "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    
    # Calcular superficie del lote
    try:
        superficie = calcular_superficie(lote.norte, lote.sur, lote.este, lote.oeste)
    except:
        superficie = "No disponible"
    
    # OBTENER DATOS DE DESGLOSE PARA ESTE PAGO
    # 1. Saldo a favor aplicado TOTAL (suma de todos los historiales)
    from pagos.models import HistorialPago, AplicacionSaldo
    
    # Opción A: Sumar todos los saldos aplicados del historial
    historiales = HistorialPago.objects.filter(pago=pago)
    saldo_a_favor_aplicado_total = sum(h.monto_saldo for h in historiales)
    
    # Opción B: También podemos sumar de AplicacionSaldo (para verificación)
    aplicaciones = AplicacionSaldo.objects.filter(pago=pago)
    saldo_aplicado_verificacion = sum(a.monto_aplicado for a in aplicaciones)
    
    # Usamos el mayor de los dos para estar seguros
    saldo_a_favor_aplicado = max(saldo_a_favor_aplicado_total, saldo_aplicado_verificacion)
    
    # 2. Efectivo total pagado (suma de todos los historiales)
    monto_pagado_efectivo_total = sum(h.monto_efectivo for h in historiales)
    
    # Verificar consistencia (monto_pagado del pago debe ser igual a la suma)
    # Ajustar si hay discrepancia
    total_calculado = monto_pagado_efectivo_total + saldo_a_favor_aplicado
    if pago.monto_pagado != total_calculado:
        # Ajustar basado en el pago.monto_pagado, priorizando el saldo a favor
        if saldo_a_favor_aplicado > pago.monto_pagado:
            saldo_a_favor_aplicado = pago.monto_pagado
            monto_pagado_efectivo_total = 0
        else:
            monto_pagado_efectivo_total = pago.monto_pagado - saldo_a_favor_aplicado
    
    # CALCULAR RESULT_1 y RESULT_2 según tu descripción
    # RESULT_1: El monto a pagar en la mensualidad - el saldo a favor
    result_1 = pago.monto - saldo_a_favor_aplicado
    
    # RESULT_2: El resultado de RESULT_1 menos el monto pagado
    result_2 = result_1 - monto_pagado_efectivo_total
    
    # Asegurar que no sean negativos
    result_1 = max(0, result_1)
    result_2 = max(0, result_2)
    
    # Convertir montos a letras
    def formatear_monto_letras(monto):
        try:
            return numero_a_letras(monto).upper()
        except:
            return "CERO PESOS 00/100 M.N."
    
    monto_total_letra = formatear_monto_letras(pago.monto)
    saldo_a_favor_letra = formatear_monto_letras(saldo_a_favor_aplicado)
    monto_pagado_letra = formatear_monto_letras(monto_pagado_efectivo_total)
    result_2_letra = formatear_monto_letras(result_2)
    
    # Obtener próxima cuota si existe
    proxima_cuota = pago.tramite.pagos.filter(
        numero_cuota__gt=pago.numero_cuota,
        estado__codigo__in=['pendiente', 'parcial']
    ).order_by('numero_cuota').first()
    
    # Construir contexto EXACTO según tus placeholders
    context = {
        # Recibo de pago
        'RECIBO_NUMERO': f"PAG-{tramite.id:03d}-{pago.numero_cuota:02d}-{pago.id:05d}",
        'FECHA_EMISION': f"{hoy.day} de {meses[hoy.month-1]} de {hoy.year}",
        
        # Datos del cliente
        'CLIENTE_NOMBRE': cliente.nombre_completo.upper(),
        'CLIENTE_TELEFONO': cliente.telefono or 'NO PROPORCIONADO',
        'CLIENTE_EMAIL': cliente.email.upper() or 'NO PROPORCIONADO',
        
        # Datos del proyecto
        'PROYECTO_NOMBRE': proyecto.nombre.upper(),
        'LOTE_IDENTIFICADOR': lote.identificador,
        'PROYECTO_UBICACION': proyecto.ubicacion.upper(),
        'LOTE_SUPERFICIE': superficie,
        'PROYECTO_REGIMEN': proyecto.tipo_contrato.upper(),
        
        # Resumen financiamiento
        'FINANCIAMIENTO_TIPO': financiamiento.tipo_pago.upper(),
        'FINANCIAMIENTO_PRECIO': f"{financiamiento.precio_lote:,.2f}",
        'FINANCIAMIENTO_ENGANCHE': f"{financiamiento.apartado:,.2f}",
        'FINANCIAMIENTO_MESES': financiamiento.num_mensualidades,
        'CUOTA_NUMERO': pago.numero_cuota,
        'CUOTA_FECHA_VENCI': pago.fecha_vencimiento.strftime("%d/%m/%Y") if pago.fecha_vencimiento else 'No especificada',
        'CUOTA_SALDO_PENDIENTE': f"{(pago.monto - pago.monto_pagado):,.2f}",
        'CUOTA_MONTO_PAGADO': f"{pago.monto_pagado:,.2f}",
        
        # Desglose del pago registrado (¡exactamente como en tu template!)
        'CUOTA_MONTO_TOTAL': f"{pago.monto:,.2f}",
        'CUOTA_MONTO_TOTAL_LETRA': monto_total_letra,
        'RESULT_1': f"{result_1:,.2f}",
        'SALDO_A_FAVOR': f"{saldo_a_favor_aplicado:,.2f}",
        'SALDO_A_FAVOR_LETRA': saldo_a_favor_letra,
        'RESULT_2': f"{result_2:,.2f}",
        'MONTO_PAGADO': f"{monto_pagado_efectivo_total:,.2f}",
        'MONTO_PAGADO_LETRA': monto_pagado_letra,
        'RESULT_2_LETRA': result_2_letra,
    }
    
    # Firma del cliente (imagen)
    data_url = firma_data or (request.session.get('firma_cliente_data') if request else None)
    print("FIRMA LEÍDA EN BUILDER:", bool(firma_data), (data_url[:100] + '...') if data_url else '')
    if request and tpl:
        # Tamaño consistente para TODAS las firmas
        FIRMA_ANCHO = 40  # 40mm de ancho
        FIRMA_ALTO = 15   # 15mm de alto
        
        # Función reutilizable para procesar firmas
        def crear_firma_unificada(data_url):
            if not data_url:
                return ''
            
            try:
                # Decodificar base64
                header, b64 = data_url.split(',', 1)
                img_data = base64.b64decode(b64)
                
                # Crear archivo temporal
                fd, temp_path = tempfile.mkstemp(suffix='.png')
                with os.fdopen(fd, 'wb') as f:
                    f.write(img_data)
                
                # ✅ MISMO TAMAÑO para todas las firmas
                return InlineImage(tpl, temp_path, width=Mm(FIRMA_ANCHO), height=Mm(FIRMA_ALTO))
                
            except Exception as e:
                print(f"Error al procesar firma: {e}")
                return ''
        
        # Procesar cada firma con el mismo tamaño
        context['FIRMA_CLIENTE'] = crear_firma_unificada(firma_data)
        
    else:
        # Valores por defecto si no hay template
        context['FIRMA_CLIENTE'] = ''
    
    return context