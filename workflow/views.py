from django.shortcuts import render

# Create your views here.
from django.views.generic import TemplateView, FormView
from django.urls import reverse_lazy
from .forms import SolicitudContratoForm, Paso1Form
from django.views.generic import FormView
from django.http import JsonResponse
from core.models import Vendedor, Propietario
from financiamiento.models import Financiamiento, FinanciamientoCommeta
from core.forms import ClienteForm, BeneficiarioForm
from core.models import Cliente, Beneficiario
from django.shortcuts import get_object_or_404, redirect
from .forms import VendorSelectForm
from django import forms
from workflow.docs import DOCUMENTOS
from .forms import SeleccionDocumentosForm
from requests import request
from .forms import SegundoClienteForm
import io
import zipfile
from django.http import HttpResponse
import os
from docxtpl import DocxTemplate
from django.views import View
from django.http import FileResponse, Http404
from django.utils import timezone
from .forms import SolicitudContratoForm, FirmaForm
#from .views import SolicitudContratoView  # si lo necesitas
from .models import ClausulasEspeciales, Tramite
from django.shortcuts import redirect
from datetime import date
from workflow.forms import ClausulasEspecialesForm
from django.conf import settings
from pdfs.utils import fill_word_template, convert_docx_to_pdf

from core.models import Lote
import time
from django.views.decorators.csrf import csrf_exempt

from pagos.services import GeneradorCuotasService

@csrf_exempt
def health_check(request):
    """Endpoint simple para health checks - mantener activa la app"""
    return JsonResponse({
        "status": "ok", 
        "timestamp": time.time(),
        "message": "Application is alive", 
        "app": "workflow"
    })

def ajax_lotes(request, proyecto_id):
    lotes = Lote.objects.filter(proyecto_id=proyecto_id, activo=True).order_by('identificador')
    data = [{'id': l.id, 'identificador': l.identificador} for l in lotes]
    return JsonResponse({'lotes': data})

class SeleccionDocumentoView(TemplateView):
    template_name = "inicio.html"
class AvancePruebaView(TemplateView):
    template_name = "workflow/prueba.html"

class SolicitudContratoView(FormView):
    template_name = "workflow/solicitud_form.html"
    form_class    = SolicitudContratoForm

    def form_valid(self, form):
        cd = form.cleaned_data
        # Convertimos todo a primitivos, incluyendo IDs
        datos_sesion = {
            'financiamiento_id':  cd['financiamiento'].id,
            'cliente_id':         cd['cliente_id'],   # asumiendo que agregaste este campo
            'vendedor_id':        cd['asesor_id'].id,
            'fecha_solicitud':    cd['fecha_solicitud'].isoformat(),
            'domicilio_cliente':  cd['domicilio_cliente'],
            'id_tipo':            cd['id_tipo'],
            'id_numero':          cd['id_numero'],
            'superficie':         float(cd['superficie']),
            'regimen':            cd['regimen'],
            'valor_venta':        float(cd['valor_venta']),
            'forma_pago':         cd['forma_pago'],
            'oferta_compra':      float(cd['oferta_compra']),
            'credito_hipo':       cd['credito_hipo'],
            'institucion':        cd.get('institucion',''),
            'apartado_monto':     float(cd['apartado_monto']),
            'apartado_letras':    cd['apartado_letras'],
            'apartado_destino':   cd['apartado_destino'],
            'vigencia_inicio':    cd['vigencia_inicio'].isoformat(),
            'vigencia_plazo':     cd['vigencia_plazo'],
            'cliente_telefono':   cd['cliente_telefono'],
            'cliente_email':      cd['cliente_email'],
            # Cualquier otro campo que necesites...
        }
        self.request.session['solicitud_contrato'] = datos_sesion
        return redirect('workflow:generar_carta')


def obtener_datos_financiamiento(request):
    id_fin = request.GET.get('id')
    if not id_fin:
        return JsonResponse({'error': 'No se proporcionó un ID'}, status=400)

    try:
        fin = Financiamiento.objects.select_related('lote__proyecto').get(id=id_fin)
        lote = fin.lote
        proyecto = lote.proyecto

        superficie = calcular_superficie(lote.norte, lote.sur, lote.este, lote.oeste)

        # Filtrar vendedores que manejan este proyecto
        vendedores = proyecto.vendedores.all()
        vendedores_data = [
            {'id': v.id, 'nombre': v.nombre_completo}
            for v in vendedores
        ]

        return JsonResponse({
            'direccion': f"{proyecto.ubicacion} - Lote {lote.identificador}",
            'superficie': superficie,
            'regimen': proyecto.tipo_contrato,
            'valor_venta': fin.precio_lote,
            'oferta_compra': fin.precio_lote,
            'apartado_monto': fin.apartado,
            'apartado_destino': vendedores_data,
            'vendedores': vendedores_data
        })
    except Financiamiento.DoesNotExist:
        return JsonResponse({'error': 'Financiamiento no encontrado'}, status=404)

def calcular_superficie(norte, sur, este, oeste):
    # Este es solo un ejemplo sencillo
    try:
        norte_val = float(norte.split()[0])
        sur_val   = float(sur.split()[0])
        este_val  = float(este.split()[0])
        oeste_val = float(oeste.split()[0])
        largo  = (norte_val + sur_val) / 2
        ancho  = (este_val + oeste_val) / 2
        return round(largo * ancho, 2)
    except:
        return 0.0
    
# Solo mostrando la clase que necesita cambios:

# Solo la clase que necesita actualizarse:

class GenerarCartaIntencionView(View):
    def get(self, request, *args, **kwargs):
        datos = request.session.get('solicitud_contrato')
        if not datos:
            return redirect('workflow:solicitud')

        # 1) Recuperar objetos
        fin    = get_object_or_404(Financiamiento, id=datos['financiamiento_id'])
        cli    = get_object_or_404(Cliente,       id=datos['cliente_id'])
        ven    = get_object_or_404(Vendedor,      id=datos['vendedor_id'])

        # 2) Fechas y formatos
        fecha = date.today()
        meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                 "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
        vig   = date.fromisoformat(datos['vigencia_inicio'])

        # 3) Construcción del contexto
        context = {
            'LUGAR': 'Oaxaca de Juárez, Oax',
            # Fecha de emisión
            'DIA_1': fecha.day,
            'MES_1': meses[fecha.month - 1].upper(),
            'ANIO_1': str(fecha.year)[-2:],
            # Datos del cliente
            'NOMBRE_CLIENTE':        cli.nombre_completo,
            'DIRECCION_CLIENTE':     cli.domicilio,
            'TIPO_ID':               cli.tipo_id,
            'NUMERO_ID':             cli.numero_id,
            #'LUGAR_ORIGEN':          cli.originario,
            #'ESTADO_CIVIL':          cli.estado_civil,
            #'TELEFONO_COMPRADOR':    datos['cliente_telefono'],
            #'OCUPACION_COMPRADOR':   cli.ocupacion,
            #'CORREO_COMPRADOR':      datos['cliente_email'],

            # Datos del lote
            #'NUMERO_LOTE':           fin.lote.identificador,
            #'LETRA_IDENTIFICADOR':   fin.lote.identificador,  # o formateo
            'DIRECCION_INMUEBLE':    fin.lote.proyecto.ubicacion,
            'NUMERO_LOTE':           fin.lote.identificador,
            'SUPERFICIE':            datos['superficie'],
            'REGIMEN':               datos['regimen'],

            # Datos del vendedor
            'NOMBRE_ASESOR':         ven.nombre_completo,
            #'ID_INE':                ven.ine,
            #'NUMERO_VENDEDOR':       ven.telefono,

            # Datos de pago/apartado
            'VALOR_VENTA':                   f"{fin.precio_lote:.2f}",
            'OFERTA_COMPRA':                 f"{fin.precio_lote:.2f}",
            'FORMA_PAGO':                    'Contado' if fin.tipo_pago == 'contado' else 'Financiado',
            'CREDITO_HIPOTECARIO':           'No',
            'INSTITUCION_FINANCIERA':        '',
            'MONTO_APARTADO':                f"{fin.apartado:.2f}",
            'MONTO_LETRAS':                  numero_a_letras(float(fin.apartado)),
            'DESTINATARIO_APARTADO':         ven.nombre_completo,
            #'LETRA_PRECIO_LOTE':             numero_a_letras(float(fin.precio_lote)),
            'TIPO_PAGO': 'efectivo',
            'VIGENCIA_DIA': fecha.day,
            'VIGENCIA_MES': meses[fecha.month - 1],
            'VIGENCIA_ANIO': str(fecha.year)[-2:],
            'TELEFONO_CLIENTE': cli.telefono,
            'EMAIL_CLIENTE': cli.email,
            'TELEFONO_ASESOR': ven.telefono,
            #'DESTINATARIO_APARTADO':         datos['apartado_destino'],
            #'DIA_ENGANCHE':                  vig.day,
            #'MES_ENGANCHE':                  meses[vig.month-1],
            #'ANIO_ENGANCHE':                 vig.year,
            #'CANTIDAD_ENGANCHE_FINANCIAMIENTO': f"{fin.enganche:.2f}",
            #'LETRA_ENGANCHE':                numero_a_letras(float(fin.enganche)),
            #'MENSUALIADES_FINANCIAMIENTO':   fin.num_mensualidades,
            # etc…
            # y demás campos públicos de ven…
        }
        print("Contexto para la carta:", context)
        # 4) Rutas de plantilla y salida
        tpl = os.path.join(settings.BASE_DIR, 'pdfs', 'templates', 'pdfs', 'carta_intencion_template.docx')
        out_dir = os.path.join(settings.MEDIA_ROOT, 'generated')
        os.makedirs(out_dir, exist_ok=True)

        base = f"carta_{fin.id}_{fecha.strftime('%Y%m%d')}"
        docx_out = os.path.join(out_dir, f"{base}.docx")
        pdf_out  = os.path.join(out_dir, f"{base}.pdf")

        # 5) Rellenar y convertir
        print("Contexto para la carta:", context)
        fill_word_template(tpl, context, docx_out)
        #success = convert_docx_to_pdf(docx_out, pdf_out)
        #final_path = pdf_out if success else docx_out
        #final_name = os.path.basename(final_path)

        # 6) Servir
        try:
            return FileResponse(open(docx_out,'rb'), as_attachment=True, filename=f"{base}.docx")
        except FileNotFoundError:
            raise Http404("No se encontró el archivo generado.")



def numero_a_letras(numero):
    """Convierte un número a su representación en letras en español"""
    unidades = ['', 'UN', 'DOS', 'TRES', 'CUATRO', 'CINCO', 'SEIS', 'SIETE', 'OCHO', 'NUEVE']
    decenas = ['', 'DIEZ', 'VEINTE', 'TREINTA', 'CUARENTA', 'CINCUENTA', 'SESENTA', 'SETENTA', 'OCHENTA', 'NOVENTA']
    especiales = {
        11: 'ONCE', 12: 'DOCE', 13: 'TRECE', 14: 'CATORCE', 15: 'QUINCE',
        16: 'DIECISÉIS', 17: 'DIECISIETE', 18: 'DIECIOCHO', 19: 'DIECINUEVE',
        20: 'VEINTE', 21: 'VEINTIUN', 22: 'VEINTIDÓS', 23: 'VEINTITRÉS',
        24: 'VEINTICUATRO', 25: 'VEINTICINCO', 26: 'VEINTISÉIS', 27: 'VEINTISIETE',
        28: 'VEINTIOCHO', 29: 'VEINTINUEVE'
    }
    
    # Manejar decimales (centavos)
    entero = int(numero)
    decimales = int(round((numero - entero) * 100))
    
    # Convertir parte entera
    if entero in especiales:
        resultado = especiales[entero]
    elif entero < 10:
        resultado = unidades[entero]
    elif entero < 100:
        decena = entero // 10
        unidad = entero % 10
        if unidad == 0:
            resultado = decenas[decena]
        else:
            resultado = f"{decenas[decena]} Y {unidades[unidad]}"
    elif entero < 1000:
        centena = entero // 100
        resto = entero % 100
        if resto == 0:
            resultado = f"{unidades[centena]}CIENTOS" if centena > 1 else "CIEN"
        else:
            resultado = f"{unidades[centena]}CIENTOS {numero_a_letras(resto)}"
    else:
        miles = entero // 1000
        resto = entero % 1000
        if resto == 0:
            resultado = f"{numero_a_letras(miles)} MIL"
        else:
            resultado = f"{numero_a_letras(miles)} MIL {numero_a_letras(resto)}"
    
    # Agregar decimales si existen
    if decimales > 0:
        resultado += f" CON {decimales:02d}/100"
    
    return resultado

class FinanciamientoSelectView(FormView):
    template_name = "workflow/paso1_financiamiento.html"
    form_class = Paso1Form# que veremos más abajo

    def form_valid(self, form):
        fin = form.cleaned_data['financiamiento']
        self.request.session['financiamiento_id'] = fin.id
        return redirect('workflow:paso2_cliente')

class ClienteDataView(FormView):
    template_name = "workflow/paso2_cliente.html"
    form_class = ClienteForm

    def dispatch(self, request, *args, **kwargs):
        if not request.session.get('financiamiento_id'):
            return redirect('workflow:paso1_financiamiento')
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        """
        Pre-llenamos el campo nombre_completo con el nombre
        que ya guardó la inmobiliaria en el plan.
        """
        initial = super().get_initial()
        fin_id = self.request.session['financiamiento_id']
        fin = get_object_or_404(Financiamiento, id=fin_id)
        initial['nombre_completo'] = fin.nombre_cliente
        return initial

    def get_context_data(self, **kwargs):
        """
        Añadimos el objeto financiamiento al contexto para mostrar
        sus datos en el template (por ejemplo, nombre de cliente
        y lote asociado).
        """
        ctx = super().get_context_data(**kwargs)
        fin_id = self.request.session['financiamiento_id']
        fin = get_object_or_404(Financiamiento, id=fin_id)
        ctx['financiamiento'] = fin

        # segundo_form con prefix (si ya existe en contexto, respetarlo)
        if 'segundo_form' not in ctx:
            ctx['segundo_form'] = SegundoClienteForm(prefix='second')
        
        # Agregar formulario de beneficiario al contexto
        if 'beneficiario_form' not in ctx:
            ctx['beneficiario_form'] = BeneficiarioForm(prefix='benef')

        return ctx

    #def form_valid(self, form):
    #    cd = form.cleaned_data
    #    cliente = form.save()
        # Guardamos ID en sesión para el siguiente paso
    #    self.request.session['cliente_id'] = cliente.id
    #    return redirect('workflow:paso_vendedor')
    def post(self, request, *args, **kwargs):
        """Manejamos ambos formularios: el principal y el segundo (opcional)."""
        main_form = self.get_form(self.get_form_class())  # ClienteForm
        segundo_form = SegundoClienteForm(request.POST or None, prefix='second')
        beneficiario_form = BeneficiarioForm(request.POST or None, prefix='benef')  # NUEVO FORMULARIO

        # detecta checkbox en la plantilla que active el segundo cliente
        add_second = request.POST.get('second_add') == 'on'
        add_testigos = request.POST.get('testigos_add') == 'on'
        add_beneficiarios = request.POST.get('beneficiarios_add') == 'on'

        if not main_form.is_valid():
            # forzamos render con errores (y pasamos segundo_form para que mantenga valores)
            return self.form_invalid(main_form, segundo_form)

        # main_form válido: guardar primer cliente a BD (igual que antes)
        cliente = main_form.save()
        self.request.session['cliente_id'] = cliente.id

        # ----------------------------------------------------------------
        # Campos extra (Edad y Vecino) — no pertenecen al modelo Cliente,
        # se guardan en sesión como un dict identificado por cliente.
        # ----------------------------------------------------------------
        extra_fields = {}

        edad_c1 = request.POST.get('edad_cliente_1', '').strip()
        if edad_c1:
            extra_fields['edad_cliente_1'] = edad_c1

        vecino_c1 = request.POST.get('vecino_cliente_1', '').strip()
        if vecino_c1:
            extra_fields['vecino_cliente_1'] = vecino_c1

        # Manejar segundo cliente (si solicitado)
        if add_second:
            if not segundo_form.is_valid():
                # segundo formulario inválido -> mostrar errores
                return self.form_invalid(main_form, segundo_form)

            # segundo válido -> guardamos sus datos en sesión (no lo persistimos aún)
            # guardamos solo campos primitivos (strings, números)
            cd2 = segundo_form.cleaned_data
            cliente2_data = {
                'nombre_completo': cd2.get('nombre_completo', ''),
                'sexo': cd2.get('sexo', ''),
                'rfc': cd2.get('rfc', ''),
                'domicilio': cd2.get('domicilio', ''),
                'telefono': cd2.get('telefono', ''),
                'email': cd2.get('email', ''),
                'ocupacion': cd2.get('ocupacion', ''),
                'estado_civil': cd2.get('estado_civil', ''),
                'nacionalidad': cd2.get('nacionalidad', ''),
                'originario': cd2.get('originario', ''),
                'tipo_id': cd2.get('tipo_id', ''),
                'numero_id': cd2.get('numero_id', ''),
            }
            self.request.session['cliente2_data'] = cliente2_data

            # Campos extra del segundo cliente
            edad_c2 = request.POST.get('edad_cliente_2', '').strip()
            if edad_c2:
                extra_fields['edad_cliente_2'] = edad_c2

            vecino_c2 = request.POST.get('vecino_cliente_2', '').strip()
            if vecino_c2:
                extra_fields['vecino_cliente_2'] = vecino_c2
                
        else:
            # si no lo seleccionó, nos aseguramos de limpiar la sesión
            self.request.session.pop('cliente2_data', None)

        # Guardar campos extra en sesión (vacío si no se proporcionaron)
        self.request.session['extra_fields'] = extra_fields

        # Manejar testigos (opcionales)
        testigos_data = {}
        if add_testigos:
            # Ahora ambos testigos son opcionales
            testigo1_nombre = request.POST.get('testigo1_nombre', '').strip()
            testigo2_nombre = request.POST.get('testigo2_nombre', '').strip()
            testigo1_idmex  = request.POST.get('testigo1_idmex', '').strip()
            testigo2_idmex  = request.POST.get('testigo2_idmex', '').strip()
            
            if testigo1_nombre:
                testigos_data['testigo1_nombre'] = testigo1_nombre
            if testigo2_nombre:
                testigos_data['testigo2_nombre'] = testigo2_nombre

            if testigo1_idmex:
                testigos_data['testigo1_idmex'] = testigo1_idmex
            if testigo2_idmex:
                testigos_data['testigo2_idmex'] = testigo2_idmex
        
        self.request.session['testigos_data'] = testigos_data

        # NUEVO: Manejar beneficiario (opcional)
        beneficiario_data = {}
        if add_beneficiarios:
            if not beneficiario_form.is_valid():
                return self.form_invalid(main_form, segundo_form, beneficiario_form)

            # beneficiario válido -> guardamos sus datos en sesión
            beneficiario_data = beneficiario_form.cleaned_data
        
        self.request.session['beneficiario_data'] = beneficiario_data
        
        # redirigir al siguiente paso
        return redirect('workflow:paso_vendedor')
    
    def form_invalid(self, main_form, segundo_form=None, beneficiario_form=None):
        ctx = self.get_context_data(form=main_form)
        ctx['segundo_form'] = segundo_form or SegundoClienteForm(prefix='second')
        ctx['beneficiario_form'] = beneficiario_form or BeneficiarioForm(prefix='benef')
        return self.render_to_response(ctx)
    
class SeleccionVendedorView(FormView):
    template_name = "workflow/paso_vendedor.html"
    form_class = VendorSelectForm

    def dispatch(self, request, *args, **kwargs):
        if not request.session.get('financiamiento_id'):
            return redirect('workflow:paso1_financiamiento')
        if not request.session.get('cliente_id'):
            return redirect('workflow:paso2_cliente')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        fin_id = self.request.session['financiamiento_id']
        fin = get_object_or_404(Financiamiento, id=fin_id)
        kwargs['financiamiento'] = fin
        return kwargs
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        fin = get_object_or_404(Financiamiento, id=self.request.session['financiamiento_id'])
        ctx['financiamiento'] = fin
        
        # Obtener vendedores y propietarios del proyecto
        proyecto_id = fin.lote.proyecto.id
        
        # Vendedores - filtrar según el tipo de usuario
        if self.request.user.is_staff:
            # Usuario staff: mostrar todos los vendedores del proyecto
            vendedores = Vendedor.objects.filter(proyectos__id=proyecto_id)
        else:
            # Usuario vendedor: mostrar solo el vendedor asociado al usuario actual
            try:
                vendedores = Vendedor.objects.filter(
                    usuario=self.request.user,
                    proyectos__id=proyecto_id
                )
            except Vendedor.DoesNotExist:
                # Si el usuario no tiene un vendedor asociado, no mostrar ningún vendedor
                vendedores = Vendedor.objects.none()
        
        # Propietarios (propietarios y apoderados)
        propietarios = Propietario.objects.all()
        
        # Agregar información de tipo a cada objeto
        for v in vendedores:
            v.tipo_modelo = 'vendedor'
        
        for p in propietarios:
            p.tipo_modelo = 'propietario'

        # Combinar ambas listas para mostrar en la plantilla
        personas = list(vendedores) + list(propietarios)
        
        ctx['personas'] = personas
        return ctx

    def form_valid(self, form):
        # Obtener el ID y tipo de la persona seleccionada
        persona_id = form.cleaned_data['persona']
        
        # El formato del valor es "tipo-id" (ej: "vendedor-1" o "propietario-3")
        tipo, id_val = persona_id.split('-')
        self.request.session['persona_tipo'] = tipo
        self.request.session['persona_id'] = int(id_val)
        
        return redirect('workflow:aviso_privacidad')

    def form_invalid(self, form):
        print("Errores del formulario:", form.errors)
        return super().form_invalid(form)

class ClausulasEspecialesView(FormView):
    template_name = "workflow/clausulas_especiales.html"
    form_class = ClausulasEspecialesForm

    def dispatch(self, request, *args, **kwargs):
        # Requiere haber aceptado el aviso
        if not request.session.get('privacy_accepted'):
            return redirect('workflow:aviso_privacidad')
        
        # Requiere haber seleccionado financiamiento, cliente y persona (vendedor o propietario)
        required_keys = ['financiamiento_id', 'cliente_id', 'persona_tipo', 'persona_id']
        for key in required_keys:
            if not request.session.get(key):
                return redirect('workflow:paso1_financiamiento')
                
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        # Guardar las cláusulas en la sesión
        # Obtener el trámite actual
        tramite_id = self.request.session.get('tramite_id')
        if not tramite_id:
            # Si no hay trámite, redirigir al inicio
            return redirect('workflow:paso1_financiamiento')
        
        tramite = get_object_or_404(Tramite, id=tramite_id)

        # Guardar las cláusulas en la base de datos
        ClausulasEspeciales.objects.update_or_create(
            tramite=tramite,
            defaults={
                'clausula_pago': form.cleaned_data['clausula_pago'],
                'clausula_deslinde': form.cleaned_data['clausula_deslinde'],
                'clausula_promesa': form.cleaned_data['clausula_promesa'],
            }
        )

        self.request.session['clausulas_especiales'] = {
            'pago': form.cleaned_data['clausula_pago'],
            'deslinde': form.cleaned_data['clausula_deslinde'],
            'promesa': form.cleaned_data['clausula_promesa'],
        }
        return redirect('workflow:paso3_documentos')

class SeleccionDocumentosView(FormView):
    template_name = "workflow/paso3_documentos.html"
    form_class = SeleccionDocumentosForm

    def dispatch(self, request, *args, **kwargs):
        # Requiere haber aceptado el aviso
        if not request.session.get('privacy_accepted'):
            return redirect('workflow:aviso_privacidad')
        # NUEVO: Requiere tener tramite_id en sesión (ya que ahora se crea en aviso)
        if not request.session.get('tramite_id'):
            print("⚠️ No hay tramite_id en sesión, redirigiendo a inicio")
            return redirect('workflow:paso1_financiamiento')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        tramite_id = self.request.session.get('tramite_id')
        if not tramite_id:
            raise Http404("No se encontró el trámite")
            
        tramite = get_object_or_404(Tramite, id=tramite_id)
        fin = tramite.financiamiento

        # 1) Empezamos con los documentos que siempre queremos mostrar
        slugs = ['aviso_privacidad']
        slugs += ['carta_intencion', 'solicitud_contrato']
    
        # 2) Solo agregar el documento de financiamiento si el tipo de pago es 'financiado'
        if fin.tipo_pago == 'financiado':
            slugs.append('financiamiento')

        # 2) Ahora, agregamos el contrato correspondiente según régimen y tipo de pago
        regime = fin.lote.proyecto.tipo_contrato.lower()
        pago   = fin.tipo_pago

        # Verificar si hay segundo cliente
        has_second_client = tramite and tramite.cliente_2 is not None

        if 'propiedad definitiva' in regime:
            if has_second_client:
                if pago == 'contado':
                    slugs.append('contrato_definitiva_contado_varios')
                else:
                    slugs.append('contrato_definitiva_pagos_varios')
            else:
                if pago == 'contado':
                    slugs.append('contrato_definitiva_contado')
                else:
                    slugs.append('contrato_definitiva_pagos')
        elif 'pequeña propiedad' in regime:
            # Contratos especiales para cuando hay 2 clientes
            if has_second_client:
                if pago == 'contado':
                    slugs.append('contrato_propiedad_contado_varios')
                else:
                    slugs.append('contrato_propiedad_pagos_varios')
            else:
                if pago == 'contado':
                    slugs.append('contrato_propiedad_contado')
                else:
                    slugs.append('contrato_propiedad_pagos')
        elif 'ejido' in regime:
            # ejidal o comunal
            if has_second_client:
                if pago == 'contado':
                    slugs.append('contrato_ejidal_contado_varios')
                else:
                    slugs.append('contrato_ejidal_pagos_varios')
            else:
                if pago == 'contado':
                    slugs.append('contrato_ejidal_contado')
                else:
                    slugs.append('contrato_ejidal_pagos')
        else:
            if fin.es_commeta:
                if has_second_client:
                    if pago == 'contado':
                        slugs.append('contrato_canario_contado_varios')
                    else:
                        slugs.append('contrato_commeta_pagos_varios')
                else:
                    if pago == 'contado':
                        slugs.append('contrato_canario_contado')
                    else:
                        slugs.append('contrato_commeta_pagos')
            else:
                if has_second_client:
                    if pago == 'contado':
                        slugs.append('contrato_canario_contado_varios')
                    else:
                        slugs.append('contrato_canario_pagos_varios')
                else:
                    if pago == 'contado':
                        slugs.append('contrato_canario_contado')
                    else:
                        slugs.append('contrato_canario_pagos')

        kwargs['available_slugs'] = slugs
        return kwargs
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Obtener trámite desde la sesión
        tramite_id = self.request.session.get('tramite_id')
        if not tramite_id:
            raise Http404("No se encontró el trámite")
            
        tramite = get_object_or_404(Tramite, id=tramite_id)
        # ✅ GENERAR LOS LINKS SI NO EXISTEN
        if not tramite.link_firma_cliente:  # Si no hay links generados
            print("⚠️ Links no generados - generando ahora...")
            tramite.generar_links_inteligentes()  # Usa el método mejorado
        ctx['tramite'] = tramite
        slugs = self.get_form_kwargs()['available_slugs']
        
        # Construimos la lista de docs con toda la info
        available_docs = []
        for slug in slugs:
            info = DOCUMENTOS[slug]
            available_docs.append({
                'slug':        slug,
                'titulo':      info['titulo'],
                'descripcion': info['descripcion'],
                'plantilla':   info['plantilla'],
                'builder':     info['builder'],
            })
        ctx['available_docs'] = available_docs

        # Pasar segundo cliente al contexto si existe
        if tramite.cliente_2:
            ctx['cliente2'] = tramite.cliente_2
        
        # NUEVO: Pasar información de Commeta al contexto si aplica
        if tramite.es_commeta:
            ctx['es_commeta'] = True
            ctx['detalle_commeta'] = tramite.obtener_detalle_commeta
            ctx['configuracion_commeta'] = tramite.obtener_configuracion_commeta
            print(f"✅ Trámite {tramite.id} es Commeta. Zona: {tramite.zona_commeta}")
        else:
            ctx['es_commeta'] = False
            print(f"✅ Trámite {tramite.id} es financiamiento normal")

        return ctx

    def form_valid(self, form):
        # 1) Carga el trámite
        tramite_id = self.request.session.get('tramite_id')
        if not tramite_id:
            raise Http404("No se encontró el trámite")
            
        tramite = get_object_or_404(Tramite, id=tramite_id)
        print(f"📄 Generando documentos para trámite {tramite.id}, tipo: {'Commeta' if tramite.es_commeta else 'Normal'}")

        fin = tramite.financiamiento
        cli = tramite.cliente
        
        # Obtener la persona correcta según el tipo
        if tramite.persona_tipo == 'vendedor':
            ven = tramite.vendedor
        else:
            ven = tramite.propietario
            
        cli2 = tramite.cliente_2
        
        # Obtener cláusulas especiales de la base de datos
        clausulas_adicionales = {}
        if hasattr(tramite, 'clausulas_especiales'):
            clausulas_db = tramite.clausulas_especiales
            clausulas_adicionales = {
                'pago': clausulas_db.clausula_pago,
                'deslinde': clausulas_db.clausula_deslinde,
                'promesa': clausulas_db.clausula_promesa,
            }
        else:
            # Fallback a la sesión por si acaso
            clausulas_adicionales = self.request.session.get('clausulas_especiales', {})

        selected = form.cleaned_data['documentos']
        print(f"📋 Documentos seleccionados: {selected}")

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as zf:
            for slug in selected:
                doc_info = DOCUMENTOS[slug]
                tpl_path = os.path.join(settings.BASE_DIR, doc_info['plantilla'])
                
                # 1) generar contexto
                tpl = DocxTemplate(tpl_path)
                
                # Manejo especial para el documento de financiamiento
                if slug == 'financiamiento':
                    # Para financiamiento, usar el builder unificado con parámetros Commeta si aplica
                    try:
                        if tramite.es_commeta:
                            # Obtener el detalle de Commeta
                            fin_commeta = tramite.obtener_detalle_commeta
                            print(f"📊 Usando builder unificado para Commeta, esquema: {fin_commeta.tipo_esquema}")
                            
                            # Llamar al builder unificado con parámetros Commeta
                            context = doc_info['builder'](
                                fin, cli, ven, 
                                request=self.request, 
                                tpl=tpl, 
                                firma_data=tramite.firma_cliente,
                                clausulas_adicionales=clausulas_adicionales,
                                cliente2=cli2,
                                tramite=tramite,
                                is_commeta=True,
                                fin_commeta=fin_commeta
                            )
                        else:
                            # Llamar al builder unificado para financiamiento normal
                            context = doc_info['builder'](
                                fin, cli, ven, 
                                request=self.request, 
                                tpl=tpl, 
                                firma_data=tramite.firma_cliente,
                                clausulas_adicionales=clausulas_adicionales,
                                cliente2=cli2,
                                tramite=tramite,
                                is_commeta=False,
                                fin_commeta=None
                            )
                    except Exception as e:
                        print(f"❌ Error en builder de financiamiento: {str(e)}")
                        # Fallback a la versión simple
                        context = doc_info['builder'](
                            fin, cli, ven, 
                            request=self.request, 
                            tpl=tpl, 
                            firma_data=tramite.firma_cliente
                        )
                else:
                    # Para los otros documentos, usar el método existente
                    try:
                        # Intenta pasar el segundo cliente si el builder lo soporta
                        context = doc_info['builder'](
                            fin, cli, ven, 
                            request=self.request, 
                            tpl=tpl, 
                            firma_data=tramite.firma_cliente, 
                            clausulas_adicionales=clausulas_adicionales,
                            cliente2=cli2,
                            tramite=tramite
                        )
                    except TypeError:
                        try:
                            # Versión sin cliente2
                            context = doc_info['builder'](
                                fin, cli, ven, 
                                request=self.request, 
                                tpl=tpl, 
                                firma_data=tramite.firma_cliente, 
                                clausulas_adicionales=clausulas_adicionales,
                                tramite=tramite
                            )
                        except TypeError:
                            try:
                                # Versión mínima con Trámite (Ej. Solicitud de contrato)
                                context = doc_info['builder'](
                                    fin, cli, ven,
                                    request=self.request, 
                                    tpl=tpl,
                                    firma_data=tramite.firma_cliente, 
                                    tramite=tramite
                                )
                            except TypeError:
                                #Versión sin Trámite
                                context = doc_info['builder'](
                                    fin, cli, ven,
                                    request=self.request, 
                                    tpl=tpl,
                                    firma_data=tramite.firma_cliente
                                )

                # 2) rellenar plantilla Word
                tmp_docx = os.path.join(settings.MEDIA_ROOT, 'temp', f"{slug}.docx")
                os.makedirs(os.path.dirname(tmp_docx), exist_ok=True)
                tpl.render(context)
                tpl.save(tmp_docx)

                # 3) convertir a PDF
                out_pdf = os.path.join(settings.MEDIA_ROOT, 'temp', f"{slug}.pdf")
                success = convert_docx_to_pdf(tmp_docx, out_pdf)
                final_file = out_pdf if success else tmp_docx

                # 4) añadir al zip
                arcname = os.path.basename(final_file)
                with open(final_file, 'rb') as f:
                    zf.writestr(arcname, f.read())

        buffer.seek(0)
        response = HttpResponse(buffer.getvalue(), content_type='application/zip')
        response['Content-Disposition'] = 'attachment; filename=documentos.zip'
        return response

class AvisoForm(forms.Form):
    FIRMAR_CHOICES = [
        ('sí', 'Sí, deseo firmar digitalmente'),
        ('no', 'No, prefiero firmar en papel'),
    ]

    firmar = forms.ChoiceField(
        label="¿Deseas firmar digitalmente?",
        choices=FIRMAR_CHOICES,
        widget=forms.RadioSelect,
        initial='sí',
    )
    aceptar = forms.BooleanField(label="He leído y acepto el Aviso de Privacidad")
    firma_data = forms.CharField(
        widget=forms.HiddenInput(attrs={'id': 'firmaData'}),  # ← AGREGAR ID
        required=False
    )
    def clean(self):
        """Validación condicional: solo requerir firma si eligió firmar digitalmente"""
        cleaned_data = super().clean()
        firmar = cleaned_data.get('firmar')
        firma_data = cleaned_data.get('firma_data')
        
        # ✅ VALIDACIÓN CONDICIONAL
        if firmar == 'sí':
            # Si eligió firma digital, debe proporcionar la firma
            if not firma_data or firma_data.strip() == '':
                raise forms.ValidationError(
                    'Debes proporcionar tu firma digital o seleccionar la opción de firma en papel'
                )
            
            # Validar que sea una imagen base64 válida
            if not firma_data.startswith('data:image/png;base64,'):
                raise forms.ValidationError(
                    'La firma digital no tiene un formato válido'
                )
        else:
            # Si eligió NO firmar digitalmente, limpiamos el campo
            cleaned_data['firma_data'] = None
        
        return cleaned_data

class AvisoPrivacidadView(FormView):
    template_name = "workflow/aviso_privacidad.html"
    form_class    = AvisoForm

    def form_valid(self, form):
        print("=== INICIANDO form_valid ===")  # Esto debería aparecer
        # 1) Guarda aceptación y firma en sesión
        self.request.session['privacy_accepted'] = True
        firmar_digitalmente = form.cleaned_data.get('firmar') == 'sí'
        firma = form.cleaned_data.get('firma_data')
        print(f"¿Firmará digitalmente?: {firmar_digitalmente}")
        print(f"Firma obtenida: {firma[:50] if firma else 'None'}...")  # Debug
        # Guardar en sesión según la elección
        if firmar_digitalmente and firma:
            self.request.session['firma_cliente_data'] = firma
            self.request.session['tipo_firma'] = 'digital'
            print("✅ Firma digital guardada en sesión")
        else:
            # Usuario prefiere firma física
            self.request.session['firma_cliente_data'] = None
            self.request.session['tipo_firma'] = 'fisica'
            print("✅ Usuario optó por firma física")
        
        # 2) Recupera IDs de pasos previos (deben existir en sesión)
        fin_id = self.request.session.get('financiamiento_id')
        cli_id = self.request.session.get('cliente_id')
        persona_tipo = self.request.session.get('persona_tipo')  # 'vendedor' o 'propietario'
        persona_id = self.request.session.get('persona_id')      # ID correspondiente
        cliente2_data = self.request.session.get('cliente2_data')
        testigos_data = self.request.session.get('testigos_data', {})
        beneficiario_data = self.request.session.get('beneficiario_data', {})  # CAMBIO: ahora es beneficiario_data (singular)

        # Campos extra (Edad y Vecino — no pertenecen al modelo Cliente)
        extra_fields = self.request.session.get('extra_fields', {})

        # NUEVO: Recuperar información de tipo de financiamiento y detalle Commeta
        tipo_financiamiento = self.request.session.get('tipo_financiamiento', 'normal')
        fin_commeta_id = self.request.session.get('financiamiento_commeta_id')

        print(f"Datos sesión - fin_id: {fin_id}, cli_id: {cli_id}, persona_tipo: {persona_tipo}")
        print(f"Tipo financiamiento: {tipo_financiamiento}, Fin Commeta ID: {fin_commeta_id}")  # NUEVO

        # Si falta alguno, aborta o redirige al inicio
        if not (fin_id and cli_id and persona_tipo and persona_id):
            return redirect('workflow:paso1_financiamiento')

        # 3) Obtén las instancias reales
        financiamiento = get_object_or_404(Financiamiento, id=fin_id)
        cliente = get_object_or_404(Cliente, id=cli_id)

        # En form_valid, recuperar la selección de lugar
        lugar_firma = self.request.POST.get('lugar_firma', '')
        es_tonameca = (lugar_firma == 'puerto_escondido')

        # NUEVO: Obtener instancia de FinanciamientoCommeta si existe
        financiamiento_commeta = None
        if tipo_financiamiento == 'commeta' and fin_commeta_id:
            financiamiento_commeta = get_object_or_404(
                FinanciamientoCommeta, 
                id=fin_commeta_id
            )
            # Verificar que corresponde al financiamiento base
            if financiamiento_commeta.financiamiento != financiamiento:
                raise ValueError("El financiamiento Commeta no corresponde al financiamiento base")
            print(f"✅ Financiamiento Commeta obtenido: {financiamiento_commeta.id}")

        # 3.1) Obtener la instancia correcta según el tipo
        vendedor = None
        propietario = None
        
        if persona_tipo == 'vendedor':
            vendedor = get_object_or_404(Vendedor, id=persona_id)
        else:
            propietario = get_object_or_404(Propietario, id=persona_id)

        # 3.2) Crear segundo cliente si existe
        cliente2 = None
        if cliente2_data:
            cliente2 = Cliente.objects.create(**cliente2_data)

        # 3.3) NUEVO: Crear beneficiario si existe
        beneficiario = None
        if beneficiario_data:
            beneficiario = Beneficiario.objects.create(**beneficiario_data)
            print(f"Beneficiario creado: {beneficiario.nombre_completo}")

        # 3.4) Parsear campos extra — convertir edad a int si está presente
        edad_cliente_1 = None
        edad_cliente_2 = None
        vecino_cliente_1 = None
        vecino_cliente_2 = None

        if extra_fields:
            try:
                edad_cliente_1 = int(extra_fields['edad_cliente_1']) if extra_fields.get('edad_cliente_1') else None
            except (ValueError, TypeError):
                edad_cliente_1 = None

            try:
                edad_cliente_2 = int(extra_fields['edad_cliente_2']) if extra_fields.get('edad_cliente_2') else None
            except (ValueError, TypeError):
                edad_cliente_2 = None

            vecino_cliente_1 = extra_fields.get('vecino_cliente_1') or None
            vecino_cliente_2 = extra_fields.get('vecino_cliente_2') or None

        # 4) Crea o actualiza el Tramite
        tramite_id = self.request.session.get('tramite_id')
        print(f"Tramite ID en sesión: {tramite_id}")

        if tramite_id:
            # Si ya existe, actualiza
            tramite = get_object_or_404(Tramite, id=tramite_id)
            print(f"Actualizando trámite existente: {tramite.id}")
            tramite.financiamiento = financiamiento
            # NUEVO: Actualizar financiamiento_commeta
            tramite.financiamiento_commeta = financiamiento_commeta
            tramite.cliente = cliente
            tramite.vendedor = vendedor
            tramite.propietario = propietario
            # ✅ CORRECCIÓN: Asignar firma solo si existe
            if firmar_digitalmente and firma:
                tramite.firma_vendedor = firma
                print("✅ Firma digital asignada a tramite.firma_vendedor")
            else:
                tramite.firma_vendedor = None  # O "" si el campo no acepta None
                print("⚠️ Trámite sin firma digital (se firmará en físico)")
            #tramite.firma_vendedor = firma or tramite.firma_cliente
            if cliente2:
                tramite.cliente_2 = cliente2

            # Asignar usuario creador si no está asignado (para trámites existentes)
            if not tramite.usuario_creador:
                tramite.usuario_creador = self.request.user

            # Actualizar testigos y beneficiarios si existen
            if testigos_data:
                # Ahora ambos testigos son opcionales
                tramite.testigo_1_nombre = testigos_data.get('testigo1_nombre', '')
                tramite.testigo_2_nombre = testigos_data.get('testigo2_nombre', '')
                tramite.testigo_1_idmex  = testigos_data.get('testigo1_idmex', '')   # ← añadir
                tramite.testigo_2_idmex  = testigos_data.get('testigo2_idmex', '')   # ← añadir
            
            # NUEVO: Actualizar beneficiario si existe
            if beneficiario:
                tramite.beneficiario_1 = beneficiario

            # Asignar campos extra (solo sobreescribe si hay valor; preserva lo anterior si es None)
            if edad_cliente_1 is not None:
                tramite.edad_cliente_1 = edad_cliente_1
            if edad_cliente_2 is not None:
                tramite.edad_cliente_2 = edad_cliente_2
            if vecino_cliente_1 is not None:
                tramite.vecino = vecino_cliente_1
            if vecino_cliente_2 is not None:
                tramite.vecino_2 = vecino_cliente_2

            tramite.es_tonameca = es_tonameca  # ← añadir antes del tramite.save()

            tramite.save()
            print(f"Trámite {tramite.id} actualizado correctamente")
        else:
            print("Creando nuevo trámite")
            # Nuevo trámite - asignar testigos y beneficiarios
            testigo_1_nombre = ""
            if vendedor:
                testigo_1_nombre = f"{vendedor.nombre_completo}"
            elif propietario:
                testigo_1_nombre = f"{propietario.nombre_completo}"

            # ✅ CORRECCIÓN: Asignar firma según la elección
            firma_para_guardar = firma if (firmar_digitalmente and firma) else ""

            tramite = Tramite.objects.create(
                financiamiento=financiamiento,
                # NUEVO: Asignar financiamiento_commeta (puede ser None)
                financiamiento_commeta=financiamiento_commeta,
                cliente=cliente,
                vendedor=vendedor,
                propietario=propietario,
                persona_tipo=persona_tipo,
                persona_id=persona_id,
                firma_vendedor=firma_para_guardar,  # CORRECCIÓN: usar firma_vendedor
                cliente_2=cliente2,
                usuario_creador=self.request.user,  # ← Aquí asignamos el usuario
                # Asignar testigos
                testigo_1_nombre=testigos_data.get('testigo1_nombre', ''),  # <-- Usa testigos_data
                testigo_2_nombre=testigos_data.get('testigo2_nombre', ''),
                testigo_1_idmex=testigos_data.get('testigo1_idmex', ''),   # ← añadir
                testigo_2_idmex=testigos_data.get('testigo2_idmex', ''),   # ← añadir
                # NUEVO: Asignar beneficiario (puede ser None)
                beneficiario_1=beneficiario,
                es_tonameca=es_tonameca,  # ← añadir esta línea
                # Campos extra Commeta Community
                edad_cliente_1=edad_cliente_1,
                edad_cliente_2=edad_cliente_2,
                vecino=vecino_cliente_1,
                vecino_2=vecino_cliente_2,
            )
            if tramite.financiamiento.tipo_pago == 'PAGOS':
                GeneradorCuotasService.generar_cuotas(tramite)
            
            self.request.session['tramite_id'] = tramite.id

        # 5) Generar los links de firma para todos los involucrados
        tramite.generar_links_firma()

        # Limpiar datos temporales de la sesión
        session_keys = ['cliente2_data', 'testigos_data', 'beneficiario_data', 'extra_fields']  # CAMBIO: beneficiarios_data -> beneficiario_data
        for key in session_keys:
            if key in self.request.session:
                del self.request.session[key]

        # 5) Vamos a la selección de documentos
        return redirect('workflow:clausulas_especiales')
    
    def form_invalid(self, form):
        """Mostrar errores de validación en consola"""
        print("❌ Formulario inválido")
        print(f"Errores: {form.errors}")
        return super().form_invalid(form)

class Paso1FinanciamientoView(TemplateView):
    template_name = "workflow/paso1_financiamiento.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        
        # Obtener financiamientos normales activos
        financiamientos_normales = Financiamiento.objects.select_related(
            'lote__proyecto'
        ).filter(
            activo=True,
            es_cotizacion=False,
            lote__proyecto__tipo_proyecto='normal'  # Solo proyectos normales
        )
        
        # Obtener financiamientos Commeta activos
        financiamientos_commeta = Financiamiento.objects.select_related(
            'lote__proyecto'
        ).filter(
            activo=True,
            es_cotizacion=False,
            lote__proyecto__tipo_proyecto='commeta'  # Solo proyectos Commeta
        ).prefetch_related('detalle_commeta')  # Incluir detalle Commeta
        
        ctx['financiamientos_normales'] = financiamientos_normales
        ctx['financiamientos_commeta'] = financiamientos_commeta
        
        return ctx

    def post(self, request, *args, **kwargs):
        plan_id = request.POST.get('financiamiento')
        if not plan_id:
            from django.contrib import messages
            messages.error(request, "Por favor selecciona un plan de financiamiento.")
            return self.get(request, *args, **kwargs)

        # Limpiar todos los datos de sesión relacionados con trámites anteriores
        session_keys_to_clear = [
            'financiamiento_id',  # aunque lo vamos a reemplazar, es bueno limpiarlo primero
            'financiamiento_commeta_id',  # NUEVO: para commeta
            'tipo_financiamiento',        # NUEVO: para identificar tipo
            'cliente_id',
            'vendedor_id',
            'tramite_id',
            'privacy_accepted',
            'firma_cliente_data',
            'cliente2_data',
            'clausulas_especiales'
        ]
        
        for key in session_keys_to_clear:
            if key in request.session:
                del request.session[key]

        # Guardar en sesión para los pasos siguientes
        request.session['financiamiento_id'] = int(plan_id)

        # Determinar si es Commeta o normal
        try:
            fin = Financiamiento.objects.select_related('lote__proyecto').get(id=plan_id)
            
            if fin.lote.proyecto.tipo_proyecto == 'commeta':
                # Es Commeta - guardar tipo y detalle
                request.session['tipo_financiamiento'] = 'commeta'
                # Guardar ID del FinanciamientoCommeta si existe
                if hasattr(fin, 'detalle_commeta'):
                    request.session['financiamiento_commeta_id'] = fin.detalle_commeta.id
                    print(f"✅ Financiamiento Commeta detectado. ID detalle: {fin.detalle_commeta.id}")
            else:
                # Es normal
                request.session['tipo_financiamiento'] = 'normal'
                
        except Financiamiento.DoesNotExist:
            from django.contrib import messages
            messages.error(request, "El financiamiento seleccionado no existe.")
            return self.get(request, *args, **kwargs)
        
        return redirect('workflow:paso2_cliente')

# Vista base para todas las firmas
class FirmaBaseView(FormView):
    template_name = None  # Cada vista hija debe definir su template
    form_class = FirmaForm  # Necesitamos crear este formulario
    
    def get_tramite_desde_token(self, token):
        """Encuentra el trámite a partir de cualquier token de firma"""
        # Buscar en todos los campos posibles
        campos_busqueda = [
            ('link_firma_cliente', 'cliente'),
            ('link_firma_cliente2', 'segundo_cliente'),
            ('link_firma_beneficiario1', 'beneficiario'),
            ('link_firma_testigo1', 'testigo1'),
            ('link_firma_testigo2', 'testigo2')
        ]
        
        for campo, tipo in campos_busqueda:
            try:
                tramite = Tramite.objects.get(**{campo: token})
                return tramite, tipo
            except Tramite.DoesNotExist:
                continue
        
        return None, None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        token = self.kwargs['token']
        tramite, tipo_firmante = self.get_tramite_desde_token(token)
        
        if not tramite:
            raise Http404("Token no válido o enlace expirado.")
        
        # Definir título y subtítulo según el tipo de firmante
        titulos = {
            'cliente': ('Firma - Cliente Principal', 'Proporciona tu firma para completar el contrato'),
            'segundo_cliente': ('Firma - Segundo Cliente', 'Proporciona tu firma como co-acreditado'),
            'beneficiario': ('Firma - Beneficiario', 'Completa tus datos y proporciona tu firma'),
            'testigo1': ('Firma - Testigo 1', 'Certifica la autenticidad del documento'),
            'testigo2': ('Firma - Testigo 2', 'Certifica la autenticidad del documento'),
        }
        
        titulo, subtitulo = titulos.get(tipo_firmante, ('Firma Digital', 'Complete el proceso de firma'))
        
        context.update({
            'tramite': tramite,
            'tipo_firmante': tipo_firmante,
            'titulo': titulo,
            'subtitulo': subtitulo,
        })
        
        return context

    def form_valid(self, form):
        token = self.kwargs['token']
        tramite, tipo_firmante = self.get_tramite_desde_token(token)
        firma_data = form.cleaned_data['firma_data']
        
        # Guardar la firma según el tipo de firmante
        if tipo_firmante == 'cliente':
            tramite.firma_cliente = firma_data
        elif tipo_firmante == 'segundo_cliente':
            tramite.firma_cliente2 = firma_data
        elif tipo_firmante == 'beneficiario':
            tramite.beneficiario_1_firma = firma_data
        elif tipo_firmante == 'testigo1':
            tramite.testigo_1_firma = firma_data
        elif tipo_firmante == 'testigo2':
            tramite.testigo_2_firma = firma_data
        
        tramite.save()
        
        # Redirigir a página de éxito
        return redirect('workflow:firma_exitosa')

# Vistas específicas para cada tipo de firmante
class FirmaClienteView(FirmaBaseView):
    template_name = 'workflow/firma_cliente.html'

class FirmaSegundoClienteView(FirmaBaseView):
    template_name = 'workflow/firma_segundo_cliente.html'

class FirmaBeneficiarioView(FirmaBaseView):
    template_name = 'workflow/firma_beneficiario.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Agregar formulario de datos del beneficiario si no están completos
        if context['tramite'].beneficiario_1:
            from core.forms import BeneficiarioForm
            context['beneficiario_form'] = BeneficiarioForm(
                instance=context['tramite'].beneficiario_1
            )
        return context
    
    def post(self, request, *args, **kwargs):
        # Manejar tanto los datos del beneficiario como la firma
        token = self.kwargs['token']
        tramite, tipo_firmante = self.get_tramite_desde_token(token)
        
        # Si el beneficiario existe, actualizar sus datos
        if tramite.beneficiario_1:
            from core.forms import BeneficiarioForm
            beneficiario_form = BeneficiarioForm(
                request.POST, 
                instance=tramite.beneficiario_1
            )
            if beneficiario_form.is_valid():
                beneficiario_form.save()
        
        # Luego manejar la firma normalmente
        return super().post(request, *args, **kwargs)

class FirmaTestigo1View(FirmaBaseView):
    template_name = 'workflow/firma_testigo.html'

    def form_valid(self, form):
        token = self.kwargs['token']
        tramite, _ = self.get_tramite_desde_token(token)
        idmex = self.request.POST.get('idmex_testigo', '').strip()
        if idmex:
            tramite.testigo_1_idmex = idmex
            tramite.save(update_fields=['testigo_1_idmex'])
        return super().form_valid(form)


class FirmaTestigo2View(FirmaBaseView):
    template_name = 'workflow/firma_testigo.html'

    def form_valid(self, form):
        token = self.kwargs['token']
        tramite, _ = self.get_tramite_desde_token(token)
        idmex = self.request.POST.get('idmex_testigo', '').strip()
        if idmex:
            tramite.testigo_2_idmex = idmex
            tramite.save(update_fields=['testigo_2_idmex'])
        return super().form_valid(form)
        
# Vista de éxito después de firmar
class FirmaExitosaView(TemplateView):
    template_name = 'workflow/firma_exitosa.html'







