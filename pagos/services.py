# pagos/services.py
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from django.utils import timezone
from pagos.models import Pago, EstadoPago
from workflow.models import Tramite
from financiamiento.models import Financiamiento, FinanciamientoCommeta

class GeneradorCuotasService:
    @staticmethod
    def generar_cuotas_para_tramite(tramite_id, usuario):
        """Genera todas las cuotas para un trámite"""
        try:
            tramite = Tramite.objects.get(id=tramite_id)
            financiamiento = tramite.financiamiento
            
            # Verificar que no haya cuotas ya generadas
            if tramite.pagos.exists():
                return False, "Ya existen cuotas generadas para este trámite"
            
            # Obtener estado "pendiente"
            estado_pendiente = EstadoPago.objects.get(codigo='pendiente')
            
            # Determinar tipo de financiamiento y generar cuotas
            if financiamiento.es_commeta:
                return GeneradorCuotasService._generar_commeta(tramite, usuario, estado_pendiente)
            else:
                return GeneradorCuotasService._generar_normal(tramite, usuario, estado_pendiente)
                
        except Tramite.DoesNotExist:
            return False, "Trámite no encontrado"
        except Exception as e:
            return False, f"Error al generar cuotas: {str(e)}"
    
    @staticmethod
    def _generar_normal(tramite, usuario, estado_pendiente):
        """Genera cuotas para financiamiento normal"""
        financiamiento = tramite.financiamiento
        
        if not financiamiento.num_mensualidades or not financiamiento.monto_mensualidad:
            return False, "Faltan datos en el financiamiento (número de mensualidades o monto)"
        
        if not financiamiento.fecha_primer_pago:
            return False, "Falta fecha de primer pago en el financiamiento"
        
        cuotas = []
        fecha_actual = financiamiento.fecha_primer_pago
        
        # Generar cuotas mensuales
        for i in range(1, financiamiento.num_mensualidades + 1):
            monto = financiamiento.monto_mensualidad
            
            # Última cuota puede ser diferente (pago final)
            if i == financiamiento.num_mensualidades and financiamiento.monto_pago_final:
                monto = financiamiento.monto_pago_final
            
            cuota = Pago(
                tramite=tramite,
                numero_cuota=i,
                fecha_vencimiento=fecha_actual,
                monto=monto,
                monto_pagado=0,
                estado=estado_pendiente,
                creado_por=usuario
            )
            cuotas.append(cuota)
            
            # Avanzar un mes
            fecha_actual = fecha_actual + relativedelta(months=1)
        
        # Guardar todas las cuotas
        Pago.objects.bulk_create(cuotas)
        return True, f"Se generaron {len(cuotas)} cuotas correctamente"
    
    @staticmethod
    def _generar_commeta(tramite, usuario, estado_pendiente):
        """Genera cuotas para financiamiento Commeta"""
        try:
            financiamiento = tramite.financiamiento
            detalle_commeta = financiamiento.detalle_commeta
            
            if not detalle_commeta:
                return False, "No se encontró detalle Commeta para este financiamiento"
            
            if not financiamiento.fecha_primer_pago:
                return False, "Falta fecha de primer pago en el financiamiento"
            
            cuotas = []
            fecha_actual = financiamiento.fecha_primer_pago
            
            # Determinar tipo de esquema
            if detalle_commeta.tipo_esquema == 'mensualidades_fijas':
                cuotas = GeneradorCuotasService._generar_mensualidades_fijas(
                    tramite, usuario, estado_pendiente, financiamiento, detalle_commeta, fecha_actual
                )
            elif detalle_commeta.tipo_esquema == 'meses_fuertes':
                cuotas = GeneradorCuotasService._generar_meses_fuertes(
                    tramite, usuario, estado_pendiente, financiamiento, detalle_commeta, fecha_actual
                )
            else:
                return False, f"Tipo de esquema no soportado: {detalle_commeta.tipo_esquema}"
            
            # Guardar todas las cuotas
            Pago.objects.bulk_create(cuotas)
            return True, f"Se generaron {len(cuotas)} cuotas Commeta correctamente"
            
        except AttributeError as e:
            return False, f"Error en la estructura de datos Commeta: {str(e)}"
    
    @staticmethod
    def _generar_mensualidades_fijas(tramite, usuario, estado_pendiente, financiamiento, detalle_commeta, fecha_inicio):
        """Genera cuotas con mensualidades fijas"""
        cuotas = []
        fecha_actual = fecha_inicio
        
        for i in range(1, financiamiento.num_mensualidades + 1):
            monto = financiamiento.monto_mensualidad
            
            # Última cuota puede ser diferente
            if i == financiamiento.num_mensualidades and detalle_commeta.monto_pago_final:
                monto = detalle_commeta.monto_pago_final
            
            cuota = Pago(
                tramite=tramite,
                numero_cuota=i,
                fecha_vencimiento=fecha_actual,
                monto=monto,
                monto_pagado=0,
                estado=estado_pendiente,
                creado_por=usuario
            )
            cuotas.append(cuota)
            fecha_actual = fecha_actual + relativedelta(months=1)
        
        return cuotas
    
    @staticmethod
    def _generar_meses_fuertes(tramite, usuario, estado_pendiente, financiamiento, detalle_commeta, fecha_inicio):
        """Genera cuotas con meses fuertes"""
        cuotas = []
        fecha_actual = fecha_inicio
        
        for i in range(1, financiamiento.num_mensualidades + 1):
            # Determinar si es mes fuerte
            es_mes_fuerte = False
            
            if detalle_commeta.usar_meses_especificos:
                # Usar lista específica de meses fuertes
                if i in (detalle_commeta.meses_fuertes_calculados or []):
                    es_mes_fuerte = True
            else:
                # Calcular por frecuencia
                if (detalle_commeta.frecuencia_meses_fuertes and 
                    i % detalle_commeta.frecuencia_meses_fuertes == 0):
                    es_mes_fuerte = True
            
            # Determinar monto
            if es_mes_fuerte and detalle_commeta.monto_mes_fuerte:
                monto = detalle_commeta.monto_mes_fuerte
            elif detalle_commeta.monto_mensualidad_normal:
                monto = detalle_commeta.monto_mensualidad_normal
            else:
                monto = financiamiento.monto_mensualidad
            
            # Última cuota puede ser diferente
            if i == financiamiento.num_mensualidades and detalle_commeta.monto_pago_final:
                monto = detalle_commeta.monto_pago_final
            
            cuota = Pago(
                tramite=tramite,
                numero_cuota=i,
                fecha_vencimiento=fecha_actual,
                monto=monto,
                monto_pagado=0,
                estado=estado_pendiente,
                creado_por=usuario,
                observaciones="Mes fuerte" if es_mes_fuerte else ""
            )
            cuotas.append(cuota)
            fecha_actual = fecha_actual + relativedelta(months=1)
        
        return cuotas