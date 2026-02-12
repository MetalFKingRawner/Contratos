# pagos/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, FormView
from django.urls import reverse_lazy
from django.utils import timezone
from django.db.models import Sum, Q, Count
from django.http import JsonResponse, HttpResponse
from datetime import datetime, timedelta

from workflow.models import Tramite
from .models import AplicacionSaldo, Pago, EstadoPago, HistorialPago, SaldoAFavor
from .forms import AplicarSaldoFavorForm, RegistroPagoForm
from .services import GeneradorCuotasService
from django.db.models import Prefetch
from django.views.generic import View
from django.contrib import messages
from django.db import models

import os
from docxtpl import DocxTemplate
from django.conf import settings

class DashboardPagosView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    template_name = 'pagos/dashboard.html'
    context_object_name = 'tramites'
    permission_required = 'pagos.view_pago'
    
    def get_queryset(self):
        # Prefetch optimizado para evitar consultas N+1
        pagos_prefetch = Prefetch(
            'pagos',
            queryset=Pago.objects.select_related('estado').order_by('fecha_vencimiento')
        )
        
        queryset = Tramite.objects.filter(
            financiamiento__tipo_pago='financiado'
        ).prefetch_related(
            pagos_prefetch
        ).select_related(
            'cliente',
            'vendedor',
            'financiamiento',
            'financiamiento__lote',
            'financiamiento__lote__proyecto'
        ).order_by('-creado_en')  # ← CAMBIADO: de fecha_creacion a creado_en
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Calcular estadísticas generales
        tramites = context['tramites']
        total_pendientes = 0
        total_atrasados = 0
        total_saldo = 0
        
        for tramite in tramites:
            pagos_tramite = list(tramite.pagos.all())
            if pagos_tramite:
                total_pendientes += sum(1 for p in pagos_tramite if p.estado.codigo == 'pendiente')
                # CORRECCIÓN: Considerar que monto_pagado no debe exceder monto
                total_saldo += sum(max(0, p.monto - p.monto_pagado) for p in pagos_tramite)
        
        context.update({
            'total_pendientes': total_pendientes,
            'total_saldo': total_saldo,
        })
        
        return context

class DetalleTramiteView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Tramite
    template_name = 'pagos/detalle_tramite.html'
    context_object_name = 'tramite'
    permission_required = 'pagos.view_pago'
    
    def get_queryset(self):
        # Filtrar solo trámites con financiamiento financiado
        return Tramite.objects.filter(
            financiamiento__tipo_pago='financiado'
        ).select_related(
            'cliente',
            'vendedor',
            'financiamiento',
            'financiamiento__lote',
            'financiamiento__lote__proyecto'
        )
    
    def get_object(self):
        # Obtener el trámite con sus pagos precargados
        queryset = self.get_queryset()
        obj = get_object_or_404(
            queryset.prefetch_related('pagos__estado'),
            id=self.kwargs['pk']
        )
        return obj
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tramite = self.object
        
        # Obtener todos los pagos del trámite
        pagos = tramite.pagos.all().order_by('numero_cuota')
        
        # CORRECCIÓN: Calcular estadísticas considerando posibles excedentes
        monto_total = pagos.aggregate(total=Sum('monto'))['total'] or 0
        
        # Calcular monto_pagado real (sin exceder el monto de cada cuota)
        monto_pagado_real = sum(min(p.monto_pagado, p.monto) for p in pagos)
        
        # Calcular excedentes (pagos que superan el monto de la cuota)
        excedente_total = sum(max(0, p.monto_pagado - p.monto) for p in pagos)
        
        # Saldo pendiente correcto
        saldo_pendiente = max(0, monto_total - monto_pagado_real)

        # Obtener la fecha actual
        today = timezone.now().date()
        
        # Calcular días de atraso para cada pago pendiente
        pagos_con_info = []
        for pago in pagos:
            pago_info = {
                'pago': pago,
                'dias_atraso': 0
            }
            if pago.estado.codigo == 'pendiente' and pago.fecha_vencimiento < today:
                pago_info['dias_atraso'] = (today - pago.fecha_vencimiento).days
            pagos_con_info.append(pago_info)
        
        context.update({
            'pagos_info': pagos_con_info,
            'monto_total': monto_total,
            'monto_pagado': monto_pagado_real,  # Monto pagado real sin excedentes
            'saldo_pendiente': saldo_pendiente,  # Ahora refleja el valor correcto
            'excedente_total': excedente_total,  # Nuevo: para mostrar si hay excedentes
            'porcentaje_pagado': (monto_pagado_real / monto_total * 100) if monto_total > 0 else 0,
            'today': today,
            'pagos_count': pagos.count(),
        })
        
        return context

class RegistrarPagoView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Vista para registrar un pago a una cuota específica"""
    model = Pago
    form_class = RegistroPagoForm
    template_name = 'pagos/registrar_pago.html'
    permission_required = 'pagos.add_pago'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['pago'] = self.pago
        kwargs['saldo_disponible'] = self.saldo_disponible
        return kwargs
    
    def dispatch(self, request, *args, **kwargs):
        # Obtener el pago (cuota) a registrar
        self.pago = get_object_or_404(
            Pago.objects.select_related('tramite', 'estado'),
            id=kwargs['pago_id']
        
        )
        # Calcular saldo disponible
        self.saldo_disponible = self.pago.tramite.saldos_favor.filter(
            utilizado=False
        ).aggregate(total=models.Sum('monto'))['total'] or 0

        # Verificar que el pago no esté ya pagado completamente
        if self.pago.estado.codigo == 'pagado':
            messages.warning(request, "Esta cuota ya está completamente pagada.")
            return redirect('pagos:detalle_tramite', pk=self.pago.tramite.id)
            
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['pago'] = self.pago
        context['tramite'] = self.pago.tramite
        
        # Calcular monto pendiente para esta cuota
        context['monto_pendiente'] = self.pago.monto - self.pago.monto_pagado
        #context['saldo_disponible'] = self.saldo_disponible
        try:
            from pagos.models import SaldoAFavor
            saldo_disponible = SaldoAFavor.objects.filter(
                tramite=self.pago.tramite,
                utilizado=False
            ).aggregate(total=models.Sum('monto'))['total'] or 0
            context['saldo_disponible'] = saldo_disponible
        except Exception:
            context['saldo_disponible'] = 0
        context['proxima_cuota'] = self._obtener_proxima_cuota_pendiente()
        
        # Verificar si hay saldo a favor disponible
        #saldo_disponible = self.pago.tramite.saldos_favor.filter(utilizado=False).aggregate(
        #    total=models.Sum('monto')
        #)['total'] or 0
        #context['saldo_disponible'] = saldo_disponible
        
        return context
    
    def _obtener_proxima_cuota_pendiente(self):
        """Obtiene la próxima cuota pendiente después de la actual"""
        return self.pago.tramite.pagos.filter(
            numero_cuota__gt=self.pago.numero_cuota,
            estado__codigo__in=['pendiente', 'parcial']
        ).order_by('numero_cuota').first()
    
    def form_valid(self, form):
        # Obtener datos del formulario
        monto_pagado = form.cleaned_data['monto_pagado']
        usar_saldo = form.cleaned_data.get('usar_saldo_disponible', False)
        monto_saldo_usar = form.cleaned_data.get('monto_saldo_usar', 0)
        manejo_excedente = form.cleaned_data.get('manejo_excedente', 'saldo_favor')
        monto_aplicar_proxima = form.cleaned_data.get('monto_aplicar_proxima', 0)
        
        monto_cuota = self.pago.monto
        monto_ya_pagado = self.pago.monto_pagado  # Lo que ya se había pagado antes
        monto_pendiente = monto_cuota - monto_ya_pagado
        
        # PASO 1: Aplicar saldo a favor si se seleccionó
        saldo_usado = 0
        
        if usar_saldo and monto_saldo_usar > 0:
            # Determinar cuánto saldo podemos usar
            saldo_maximo = min(monto_saldo_usar, self.saldo_disponible, monto_pendiente)
            saldo_usado = self._aplicar_saldo_favor(saldo_maximo, self.pago)
        
        # PASO 2: Agregar el pago en efectivo al monto total pagado
        # NOTA: _aplicar_saldo_favor ya actualizó self.pago.monto_pagado con el saldo
        # Ahora agregamos el monto en efectivo
        self.pago.monto_pagado += monto_pagado
        
        # PASO 3: Calcular el total aplicado en esta operación
        monto_total_aplicado_ahora = monto_pagado + saldo_usado
        
        # PASO 4: Verificar si la cuota queda pagada completamente
        # Ahora self.pago.monto_pagado incluye tanto el saldo como el efectivo
        if self.pago.monto_pagado >= monto_cuota:
            # Pago completo
            self.pago.estado = EstadoPago.objects.get(codigo='pagado')
            
            # Calcular excedente (solo del efectivo, porque el saldo ya se aplicó hasta lo necesario)
            # El excedente sería: monto_pagado - (monto_pendiente - saldo_usado)
            excedente_efectivo = max(0, monto_pagado - (monto_pendiente - saldo_usado))
            
            if excedente_efectivo > 0:
                self._manejar_excedente(
                    excedente_efectivo, 
                    manejo_excedente, 
                    monto_aplicar_proxima,
                    self.pago.tramite,
                    self.pago.numero_cuota
                )
        else:
            # Pago parcial
            self.pago.estado = EstadoPago.objects.get(codigo='parcial')
        
        # Actualizar otros campos del pago
        self.pago.fecha_pago = form.cleaned_data['fecha_pago']
        self.pago.metodo_pago = form.cleaned_data['metodo_pago']
        self.pago.observaciones = form.cleaned_data['observaciones']
        self.pago.save()
        
        # Registrar en historial
        detalle_historial = (
            f"Pago registrado: ${monto_pagado:.2f} en efectivo "
            f"(+ ${saldo_usado:.2f} saldo) = ${monto_total_aplicado_ahora:.2f}. "
            f"Método: {self.pago.metodo_pago}"
        )
        
        HistorialPago.objects.create(
            pago=self.pago,
            accion='REGISTRO_PAGO',
            detalle=detalle_historial,
            usuario=self.request.user,
            # NUEVOS CAMPOS
            monto_efectivo=monto_pagado,
            monto_saldo=saldo_usado
        )
        
        # Mensajes de éxito
        if saldo_usado > 0:
            messages.info(self.request, f"Se aplicó ${saldo_usado:.2f} de saldo a favor.")
        
        messages.success(
            self.request, 
            f"Pago registrado exitosamente para la cuota #{self.pago.numero_cuota}. "
            f"Total pagado ahora: ${monto_total_aplicado_ahora:.2f}. "
            f"Total acumulado: ${self.pago.monto_pagado:.2f} de ${monto_cuota:.2f}"
        )
        
        return redirect('pagos:detalle_tramite', pk=self.pago.tramite.id)
    
    def _aplicar_saldo_favor(self, monto, pago_destino):
        """Aplica saldo a favor a un pago específico"""
        saldos = SaldoAFavor.objects.filter(
            tramite=pago_destino.tramite,
            utilizado=False,
            monto__gt=0
        ).order_by('fecha_creacion')
        
        monto_restante = monto
        
        for saldo in saldos:
            if monto_restante <= 0:
                break
            
            monto_a_usar = min(saldo.monto, monto_restante)
            
            # Actualizar el pago destino (en memoria, NO guardar aún)
            pago_destino.monto_pagado += monto_a_usar
            
            # Crear registro de aplicación
            AplicacionSaldo.objects.create(
                saldo=saldo,
                pago=pago_destino,
                monto_aplicado=monto_a_usar,
                usuario=self.request.user
            )
            
            # Actualizar saldo
            saldo.monto -= monto_a_usar
            if saldo.monto <= 0:
                saldo.utilizado = True
                saldo.fecha_utilizacion = timezone.now()
            saldo.save()
            
            monto_restante -= monto_a_usar
        
        # NO guardar el pago aquí, se guardará en form_valid
        return monto - monto_restante  # Retorna el monto realmente aplicado

    
    def _manejar_excedente(self, excedente, manejo_excedente, monto_aplicar_proxima, tramite, numero_cuota_actual):
        """Maneja el excedente según la opción seleccionada"""
        
        if manejo_excedente == 'saldo_favor':
            # Todo a saldo a favor
            SaldoAFavor.objects.create(
                tramite=tramite,
                monto=excedente,
                origen=self.pago,
                observaciones=f"Excedente de pago cuota #{numero_cuota_actual}"
            )
            messages.info(self.request, f"Se creó un saldo a favor de ${excedente:.2f}.")
            
        elif manejo_excedente == 'aplicar_proxima':
            # Aplicar a próxima cuota
            proxima_cuota = self._obtener_proxima_cuota_pendiente()
            if proxima_cuota:
                # Aplicar el excedente directamente (sin pasar por saldo a favor)
                monto_a_aplicar = min(excedente, proxima_cuota.monto - proxima_cuota.monto_pagado)
                
                proxima_cuota.monto_pagado += monto_a_aplicar
                if proxima_cuota.monto_pagado >= proxima_cuota.monto:
                    proxima_cuota.estado = EstadoPago.objects.get(codigo='pagado')
                else:
                    proxima_cuota.estado = EstadoPago.objects.get(codigo='parcial')
                proxima_cuota.save()
                
                # Registrar en historial
                HistorialPago.objects.create(
                    pago=proxima_cuota,
                    accion='APLICACION_EXCEDENTE',
                    detalle=f"Aplicado excedente de cuota #{numero_cuota_actual}: ${monto_a_aplicar:.2f}",
                    usuario=self.request.user
                )
                
                messages.info(self.request, 
                            f"Se aplicó ${monto_a_aplicar:.2f} a la cuota #{proxima_cuota.numero_cuota}.")
                
                # Si queda excedente, crear saldo a favor
                if excedente > monto_a_aplicar:
                    saldo_restante = excedente - monto_a_aplicar
                    SaldoAFavor.objects.create(
                        tramite=tramite,
                        monto=saldo_restante,
                        origen=self.pago,
                        observaciones=f"Excedente restante de pago cuota #{numero_cuota_actual}"
                    )
                    messages.info(self.request, 
                                f"Saldo restante (${saldo_restante:.2f}) convertido a saldo a favor.")
            else:
                # No hay próxima cuota, crear saldo a favor
                SaldoAFavor.objects.create(
                    tramite=tramite,
                    monto=excedente,
                    origen=self.pago,
                    observaciones=f"Excedente de pago cuota #{numero_cuota_actual} (no hay próxima cuota)"
                )
                messages.info(self.request, 
                            f"No hay cuotas pendientes. Se creó saldo a favor de ${excedente:.2f}.")
                
        elif manejo_excedente == 'dividir':
            # Dividir entre saldo a favor y próxima cuota
            monto_saldo_favor = excedente - monto_aplicar_proxima if monto_aplicar_proxima else excedente / 2
            monto_proxima = excedente - monto_saldo_favor
            
            # Crear saldo a favor
            if monto_saldo_favor > 0:
                SaldoAFavor.objects.create(
                    tramite=tramite,
                    monto=monto_saldo_favor,
                    origen=self.pago,
                    observaciones=f"Parte del excedente de pago cuota #{numero_cuota_actual}"
                )
            
            # Aplicar a próxima cuota si hay monto
            if monto_proxima > 0:
                proxima_cuota = self._obtener_proxima_cuota_pendiente()
                if proxima_cuota:
                    monto_a_aplicar = min(monto_proxima, proxima_cuota.monto - proxima_cuota.monto_pagado)
                    
                    proxima_cuota.monto_pagado += monto_a_aplicar
                    if proxima_cuota.monto_pagado >= proxima_cuota.monto:
                        proxima_cuota.estado = EstadoPago.objects.get(codigo='pagado')
                    else:
                        proxima_cuota.estado = EstadoPago.objects.get(codigo='parcial')
                    proxima_cuota.save()
                    
                    # Registrar en historial
                    HistorialPago.objects.create(
                        pago=proxima_cuota,
                        accion='APLICACION_EXCEDENTE',
                        detalle=f"Aplicado excedente dividido de cuota #{numero_cuota_actual}: ${monto_a_aplicar:.2f}",
                        usuario=self.request.user
                    )
                    
                    # Si queda excedente, agregar al saldo a favor
                    if monto_proxima > monto_a_aplicar:
                        monto_saldo_favor += (monto_proxima - monto_a_aplicar)
                
                messages.info(self.request, 
                            f"Excedente dividido: ${monto_saldo_favor:.2f} a saldo a favor, "
                            f"${monto_proxima:.2f} a próxima cuota.")

@login_required
@permission_required('pagos.view_pago', raise_exception=True)
def generar_recibo_pdf(request, pago_id):
    """Vista para generar el recibo PDF de un pago"""
    pago = get_object_or_404(Pago, id=pago_id)
    
    # Aquí implementarás la generación del PDF
    # Similar a como lo haces con los contratos
    
    # Por ahora, redireccionamos al detalle
    return redirect('pagos:detalle_tramite', tramite_id=pago.tramite.id)

class GenerarCuotasView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'pagos.add_pago'
    
    def post(self, request, tramite_id):
        try:
            success, mensaje = GeneradorCuotasService.generar_cuotas_para_tramite(
                tramite_id, request.user
            )
            
            if success:
                messages.success(request, mensaje)
            else:
                messages.error(request, mensaje)
                
        except Exception as e:
            messages.error(request, f"Error inesperado: {str(e)}")
        
        return redirect('pagos:detalle_tramite', pk=tramite_id)


class GenerarCuotasAjaxView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'pagos.add_pago'
    
    def post(self, request, tramite_id):
        try:
            success, mensaje = GeneradorCuotasService.generar_cuotas_para_tramite(
                tramite_id, request.user
            )
            
            return JsonResponse({
                'success': success,
                'message': mensaje
            })
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f"Error inesperado: {str(e)}"
            }, status=500)
        
# pagos/views.py - Agregar esta vista
class AplicarSaldoFavorView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    """Vista para aplicar saldo a favor manualmente a cuotas específicas"""
    form_class = AplicarSaldoFavorForm
    template_name = 'pagos/aplicar_saldo.html'
    permission_required = 'pagos.change_pago'
    
    def dispatch(self, request, *args, **kwargs):
        self.tramite = get_object_or_404(
            Tramite.objects.prefetch_related('pagos', 'saldos_favor'),
            id=kwargs['tramite_id']
        )
        return super().dispatch(request, *args, **kwargs)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['tramite'] = self.tramite
        
        # Calcular saldo disponible
        saldo_disponible = self.tramite.saldos_favor.filter(
            utilizado=False
        ).aggregate(total=models.Sum('monto'))['total'] or 0
        kwargs['saldo_disponible'] = saldo_disponible
        
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tramite'] = self.tramite
        
        # Calcular saldo disponible
        saldo_disponible = self.tramite.saldos_favor.filter(
            utilizado=False
        ).aggregate(total=models.Sum('monto'))['total'] or 0
        context['saldo_disponible'] = saldo_disponible
        
        # Obtener cuotas pendientes para mostrar
        context['pagos_pendientes'] = self.tramite.pagos.filter(
            estado__codigo__in=['pendiente', 'parcial']
        ).order_by('numero_cuota')
        
        return context
    
    def form_valid(self, form):
        saldo_disponible = self.tramite.saldos_favor.filter(
            utilizado=False
        ).aggregate(total=models.Sum('monto'))['total'] or 0
        
        # Aplicar saldo a cada cuota seleccionada
        total_aplicado = 0
        
        for field_name, monto_aplicar in form.cleaned_data.items():
            if field_name.startswith('pago_') and monto_aplicar and monto_aplicar > 0:
                pago_id = int(field_name.split('_')[1])
                
                try:
                    pago = Pago.objects.get(id=pago_id, tramite=self.tramite)
                    
                    # Verificar que el pago esté pendiente o parcial
                    if pago.estado.codigo not in ['pendiente', 'parcial']:
                        continue
                    
                    # CORRECCIÓN: Limitar el monto a aplicar al saldo pendiente de la cuota
                    saldo_pendiente_cuota = pago.monto - pago.monto_pagado
                    monto_a_aplicar_real = min(monto_aplicar, saldo_pendiente_cuota)
                    
                    if monto_a_aplicar_real > 0:
                        # Aplicar el saldo
                        self._aplicar_saldo_a_pago(pago, monto_a_aplicar_real)
                        total_aplicado += monto_a_aplicar_real
                    
                    # Si hay excedente, crear un nuevo saldo a favor
                    excedente = monto_aplicar - monto_a_aplicar_real
                    if excedente > 0:
                        SaldoAFavor.objects.create(
                            tramite=self.tramite,
                            monto=excedente,
                            origen='EXCEDENTE_APLICACION',
                            descripcion=f'Excedente al aplicar saldo a cuota #{pago.numero_cuota}',
                            utilizado=False
                        )
                        messages.info(
                            self.request,
                            f"Se creó un nuevo saldo a favor de ${excedente:.2f} por excedente."
                        )
                    
                except Pago.DoesNotExist:
                    continue
        
        if total_aplicado > 0:
            messages.success(
                self.request, 
                f"Se aplicó ${total_aplicado:.2f} de saldo a favor a las cuotas seleccionadas."
            )
        else:
            messages.info(self.request, "No se aplicó ningún monto de saldo a favor.")
        
        return redirect('pagos:detalle_tramite', pk=self.tramite.id)
    
    def _aplicar_saldo_a_pago(self, pago, monto_aplicar):
        """
        Aplica saldo a favor a un pago específico
        CORRECCIÓN: Asegurar que no se aplique más del saldo pendiente
        """
        # CORRECCIÓN: Calcular el saldo pendiente real de la cuota
        saldo_pendiente_cuota = pago.monto - pago.monto_pagado
        
        # CORRECCIÓN: Limitar el monto a aplicar
        monto_aplicar = min(monto_aplicar, saldo_pendiente_cuota)
        
        if monto_aplicar <= 0:
            return
        
        # Obtener saldos disponibles ordenados por antigüedad
        saldos = SaldoAFavor.objects.filter(
            tramite=self.tramite,
            utilizado=False,
            monto__gt=0
        ).order_by('fecha_creacion')
        
        monto_restante = monto_aplicar
        
        for saldo in saldos:
            if monto_restante <= 0:
                break
            
            monto_a_usar = min(saldo.monto, monto_restante)
            
            # Crear registro de aplicación
            AplicacionSaldo.objects.create(
                saldo=saldo,
                pago=pago,
                monto_aplicado=monto_a_usar,
                usuario=self.request.user
            )
            
            # Actualizar saldo
            saldo.monto -= monto_a_usar
            if saldo.monto <= 0:
                saldo.utilizado = True
                saldo.fecha_utilizacion = timezone.now()
            saldo.save()
            
            # Actualizar el pago
            pago.monto_pagado += monto_a_usar
            
            # CORRECCIÓN: Asegurar que monto_pagado no exceda monto
            pago.monto_pagado = min(pago.monto_pagado, pago.monto)
            
            if pago.monto_pagado >= pago.monto:
                pago.estado = EstadoPago.objects.get(codigo='pagado')
            else:
                pago.estado = EstadoPago.objects.get(codigo='parcial')
            
            monto_restante -= monto_a_usar
        
        pago.save()
        
        # Registrar en historial del pago
        HistorialPago.objects.create(
            pago=pago,
            accion='APLICACION_SALDO_MANUAL',
            detalle=f"Saldo a favor aplicado manualmente: ${monto_aplicar:.2f}",
            usuario=self.request.user
        )

def descargar_recibo_pago_pdf(request, pago_id):
    """
    Vista para descargar un recibo de pago en PDF
    Similar a descargar_carta_intencion_pdf de financiamiento
    """
    # Obtener el pago
    pago = get_object_or_404(Pago, pk=pago_id)
    
    # Ruta a la plantilla de recibo de pago
    tpl_path = os.path.join(settings.BASE_DIR, 'pdfs/templates/pdfs/recibo_template.docx')
    
    # Verificar que la plantilla existe
    if not os.path.exists(tpl_path):
        return HttpResponse("Plantilla no encontrada", status=500)
    
    try:
        # Cargar plantilla
        tpl = DocxTemplate(tpl_path)
        
        # Generar contexto usando nuestro builder
        from .utils.recibo_builder import build_recibo_pago_from_instance
        firma = pago.tramite.firma_cliente
        context = build_recibo_pago_from_instance(pago, request=request, tpl=tpl, firma_data=firma)
        
        # Renderizar plantilla
        tpl.render(context)
        
        # Crear directorio temporal si no existe
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        
        # Guardar DOCX temporal
        tmp_docx = os.path.join(temp_dir, f"recibo_pago_{pago.id}.docx")
        tpl.save(tmp_docx)
        
        # Convertir a PDF usando tu función existente
        from pdfs.utils import convert_docx_to_pdf
        
        # Nombre del archivo PDF
        pdf_filename = f"recibo_pago_{pago.tramite.cliente.nombre_completo.replace(' ', '_')}_{pago.id}.pdf"
        tmp_pdf = os.path.join(temp_dir, pdf_filename)
        
        success = convert_docx_to_pdf(tmp_docx, tmp_pdf)
        
        if success and os.path.exists(tmp_pdf):
            # Leer el PDF y enviarlo como respuesta
            with open(tmp_pdf, 'rb') as pdf_file:
                response = HttpResponse(pdf_file.read(), content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="{pdf_filename}"'
                
                # Limpiar archivos temporales
                try:
                    os.remove(tmp_docx)
                    os.remove(tmp_pdf)
                except:
                    pass
                
                return response
        else:
            # Si falla la conversión a PDF, enviar el DOCX
            with open(tmp_docx, 'rb') as docx_file:
                response = HttpResponse(
                    docx_file.read(), 
                    content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                )
                response['Content-Disposition'] = f'attachment; filename="recibo_pago_{pago.id}.docx"'
                
                try:
                    os.remove(tmp_docx)
                except:
                    pass
                
                return response
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        return HttpResponse(f"Error al generar el recibo: {str(e)}\n\nDetalles:\n{error_details}", status=500)