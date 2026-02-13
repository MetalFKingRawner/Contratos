# financiamiento/utils.py
# financiamiento/utils.py

def calcular_meses_fuertes(total_meses, cantidad_meses_fuertes, frecuencia=None):
    """
    Calcula la distribución de meses fuertes
    
    Args:
        total_meses: Número total de meses del financiamiento
        cantidad_meses_fuertes: Cuántos meses serán fuertes
        frecuencia: Cada cuántos meses se repite un mes fuerte (opcional)
    
    Returns:
        list: Lista de números de meses que son fuertes (1-based)
    """
    if cantidad_meses_fuertes > total_meses:
        raise ValueError("Los meses fuertes no pueden exceder el total de meses")
    
    if frecuencia:
        # Distribución con frecuencia fija
        meses_fuertes = []
        mes_actual = frecuencia
        while len(meses_fuertes) < cantidad_meses_fuertes and mes_actual <= total_meses:
            meses_fuertes.append(mes_actual)
            mes_actual += frecuencia
        return meses_fuertes
    else:
        # Distribución automática (equidistante)
        if cantidad_meses_fuertes == 1:
            return [total_meses]  # Último mes
        
        # Calcular espaciado aproximado
        espaciado = total_meses // cantidad_meses_fuertes
        meses_fuertes = []
        
        for i in range(cantidad_meses_fuertes):
            mes = min((i + 1) * espaciado, total_meses)
            if i == cantidad_meses_fuertes - 1:  # Último mes fuerte siempre el último
                mes = total_meses
            meses_fuertes.append(mes)
        
        return meses_fuertes

def calcular_meses_fuertes_inicio(total_meses, cantidad_meses_fuertes, frecuencia=None):
    """
    Calcula meses fuertes comenzando desde el inicio con frecuencia fija
    Ejemplo: 10 meses, 3 meses fuertes, cada 2 meses → [2, 4, 6]
    """
    # ✅ CORRECCIÓN: Validar que los parámetros no sean None
    if total_meses is None or cantidad_meses_fuertes is None:
        return []
    
    # ✅ CORRECCIÓN: Convertir a enteros por si acaso
    try:
        total_meses = int(total_meses)
        cantidad_meses_fuertes = int(cantidad_meses_fuertes)
    except (TypeError, ValueError):
        return []
    
    if cantidad_meses_fuertes >= total_meses:
        return list(range(1, total_meses + 1))
    
    if frecuencia:
        # ✅ CORRECCIÓN: Validar frecuencia
        try:
            frecuencia = int(frecuencia) if frecuencia is not None else None
        except (TypeError, ValueError):
            frecuencia = None
            
        if frecuencia:
            # Distribución con frecuencia fija
            meses_fuertes = []
            mes_actual = frecuencia
            while len(meses_fuertes) < cantidad_meses_fuertes and mes_actual <= total_meses:
                meses_fuertes.append(mes_actual)
                mes_actual += frecuencia
            return meses_fuertes
    
    # Distribución automática (sin frecuencia o frecuencia inválida)
    if cantidad_meses_fuertes == 0:
        return []
    
    # Calcular espaciado aproximado
    espaciado = max(1, total_meses // cantidad_meses_fuertes)
    
    meses_fuertes = []
    for i in range(cantidad_meses_fuertes):
        # Comenzar desde el primer mes y distribuir
        mes = min((i * espaciado) + 1, total_meses)
        meses_fuertes.append(mes)
    
    # Asegurarnos de no exceder el total y de que no hay duplicados
    meses_fuertes = sorted(set(meses_fuertes))
    meses_fuertes = [mes for mes in meses_fuertes if mes <= total_meses]
    
    # Si nos faltan meses fuertes, agregar al final
    while len(meses_fuertes) < cantidad_meses_fuertes and meses_fuertes[-1] < total_meses:
        nuevo_mes = min(meses_fuertes[-1] + 1, total_meses)
        if nuevo_mes not in meses_fuertes:
            meses_fuertes.append(nuevo_mes)
    
    return sorted(meses_fuertes[:cantidad_meses_fuertes])

def validar_estructura_pagos(total_meses, meses_fuertes, monto_normal, monto_fuerte, total_a_financiar):
    """
    Valida que los montos cuadren con el total a financiar
    """
    meses_normales = total_meses - len(meses_fuertes)
    total_calculado = (meses_normales * monto_normal) + (len(meses_fuertes) * monto_fuerte)
    
    return abs(total_calculado - total_a_financiar) < 0.01  # Tolerancia para decimales

def validar_meses_fuertes_limitados(total_meses, cantidad_meses_fuertes, frecuencia, 
                                   monto_normal, monto_fuerte, monto_final, total_a_financiar):
    """
    Valida estructura de pagos con meses fuertes limitados
    
    Retorna: (es_valido, mensaje_error, meses_fuertes_calculados)
    """
    try:
        # Validaciones básicas
        if cantidad_meses_fuertes > total_meses:
            return False, "Los meses fuertes no pueden exceder el total de meses", []
        
        if frecuencia and frecuencia >= total_meses:
            return False, "La frecuencia debe ser menor al total de meses", []
        
        # Calcular meses fuertes
        meses_fuertes = calcular_meses_fuertes_inicio(total_meses, cantidad_meses_fuertes, frecuencia)
        
        if len(meses_fuertes) != cantidad_meses_fuertes:
            return False, f"No se pudieron calcular {cantidad_meses_fuertes} meses fuertes en {total_meses} meses", []
        
        # Validar estructura financiera
        meses_normales = total_meses - cantidad_meses_fuertes
        
        # El último mes puede ser diferente (monto_final)
        if meses_fuertes and total_meses in meses_fuertes:
            # Si el último mes es fuerte, usar monto_fuerte para ese mes
            total_calculado = (meses_normales * monto_normal) + (cantidad_meses_fuertes * monto_fuerte)
        else:
            # Si el último mes es normal, usar monto_final para ese mes
            total_calculado = ((meses_normales - 1) * monto_normal) + (cantidad_meses_fuertes * monto_fuerte) + monto_final
        
        # Verificar que el total calculado sea razonable (con un margen del 1%)
        if abs(total_calculado - total_a_financiar) / total_a_financiar > 0.01:
            return False, f"La estructura de pagos no coincide con el total a financiar. Esperado: {total_a_financiar}, Calculado: {total_calculado}", []
        
        return True, "", meses_fuertes
        
    except Exception as e:
        return False, f"Error en validación: {str(e)}", []

def obtener_configuracion_commeta(lote):
    """
    Obtiene la configuración Commeta para un lote
    """
    from core.models import ConfiguracionCommeta
    try:
        return ConfiguracionCommeta.objects.get(lote=lote)
    except ConfiguracionCommeta.DoesNotExist:
        return None

def validar_estructura_completa_commeta(financiamiento_data, detalle_commeta_data):
    """
    Valida que toda la estructura de pagos de Commeta sea correcta
    
    Returns: (es_valido, mensaje_error, desglose_pagos)
    """
    try:
        precio_lote = float(financiamiento_data.get('precio_lote', 0))
        apartado = float(financiamiento_data.get('apartado', 0))
        enganche = float(financiamiento_data.get('enganche', 0))
        total_meses = int(financiamiento_data.get('num_mensualidades', 0))
        monto_pago_final = float(financiamiento_data.get('monto_pago_final', 0))
        
        tipo_esquema = detalle_commeta_data.get('tipo_esquema')
        
        total_a_financiar = precio_lote - apartado - enganche
        
        if total_a_financiar <= 0:
            return False, "El total a financiar debe ser mayor a cero", {}
        
        if total_meses <= 0:
            return False, "El número de mensualidades debe ser mayor a cero", {}
        
        desglose = {
            'total_a_financiar': total_a_financiar,
            'total_meses': total_meses,
            'pagos': []
        }
        
        if tipo_esquema == 'mensualidades_fijas':
            monto_mensualidad = float(financiamiento_data.get('monto_mensualidad', 0))
            
            if monto_mensualidad <= 0:
                return False, "El monto de mensualidad debe ser mayor a cero", {}
            
            # Crear desglose de pagos
            for mes in range(1, total_meses + 1):
                if mes == total_meses and monto_pago_final > 0:
                    desglose['pagos'].append({
                        'mes': mes,
                        'tipo': 'final',
                        'monto': monto_pago_final
                    })
                else:
                    desglose['pagos'].append({
                        'mes': mes,
                        'tipo': 'fija',
                        'monto': monto_mensualidad
                    })
            
            # Calcular total
            if monto_pago_final > 0:
                total_calculado = (monto_mensualidad * (total_meses - 1)) + monto_pago_final
            else:
                total_calculado = monto_mensualidad * total_meses
            
        elif tipo_esquema == 'meses_fuertes':
            cantidad_meses_fuertes = int(detalle_commeta_data.get('cantidad_meses_fuertes', 0))
            frecuencia = detalle_commeta_data.get('frecuencia_meses_fuertes')
            monto_normal = float(detalle_commeta_data.get('monto_mensualidad_normal', 0))
            monto_fuerte = float(detalle_commeta_data.get('monto_mes_fuerte', 0))
            
            if cantidad_meses_fuertes <= 0:
                return False, "La cantidad de meses fuertes debe ser mayor a cero", {}
            
            if monto_normal <= 0 or monto_fuerte <= 0:
                return False, "Los montos de mensualidad normal y fuerte deben ser mayores a cero", {}
            
            # Calcular meses fuertes
            meses_fuertes = calcular_meses_fuertes_inicio(
                total_meses, 
                cantidad_meses_fuertes,
                int(frecuencia) if frecuencia else None
            )
            
            desglose['meses_fuertes'] = meses_fuertes
            
            # Crear desglose de pagos
            for mes in range(1, total_meses + 1):
                if mes == total_meses and monto_pago_final > 0:
                    desglose['pagos'].append({
                        'mes': mes,
                        'tipo': 'final',
                        'monto': monto_pago_final,
                        'es_fuerte': mes in meses_fuertes
                    })
                elif mes in meses_fuertes:
                    desglose['pagos'].append({
                        'mes': mes,
                        'tipo': 'fuerte',
                        'monto': monto_fuerte,
                        'es_fuerte': True
                    })
                else:
                    desglose['pagos'].append({
                        'mes': mes,
                        'tipo': 'normal',
                        'monto': monto_normal,
                        'es_fuerte': False
                    })
            
            # Calcular total
            meses_normales = total_meses - len(meses_fuertes)
            
            if total_meses in meses_fuertes and monto_pago_final > 0:
                # Último mes es fuerte pero tiene monto_pago_final diferente
                total_calculado = (meses_normales * monto_normal) + ((len(meses_fuertes) - 1) * monto_fuerte) + monto_pago_final
            elif total_meses in meses_fuertes:
                # Último mes es fuerte y usa monto_fuerte normal
                total_calculado = (meses_normales * monto_normal) + (len(meses_fuertes) * monto_fuerte)
            elif monto_pago_final > 0:
                # Último mes es normal pero tiene monto_pago_final diferente
                total_calculado = ((meses_normales - 1) * monto_normal) + (len(meses_fuertes) * monto_fuerte) + monto_pago_final
            else:
                # Último mes es normal y usa monto_normal
                total_calculado = (meses_normales * monto_normal) + (len(meses_fuertes) * monto_fuerte)
        
        else:
            return False, f"Tipo de esquema '{tipo_esquema}' no reconocido", {}
        
        desglose['total_calculado'] = total_calculado
        desglose['diferencia'] = total_calculado - total_a_financiar
        desglose['porcentaje_diferencia'] = abs(desglose['diferencia'] / total_a_financiar * 100) if total_a_financiar > 0 else 0
        
        # Validar que la diferencia sea mínima (menos del 1%)
        if desglose['porcentaje_diferencia'] > 1.0:
            return False, f"La estructura de pagos no coincide. Esperado: ${total_a_financiar:,.2f}, Calculado: ${total_calculado:,.2f}, Diferencia: ${desglose['diferencia']:,.2f} ({desglose['porcentaje_diferencia']:.2f}%)", desglose
        
        return True, "✅ Estructura de pagos válida", desglose
        
    except Exception as e:
        return False, f"Error en validación: {str(e)}", {}