from django.shortcuts import render

# Create your views here.
from django.views.generic import TemplateView
from django.urls import reverse_lazy
from .forms import SolicitudContratoForm, Paso1Form
from django.views.generic import FormView
from django.http import JsonResponse
from core.models import Vendedor
from financiamiento.models import Financiamiento
from core.forms import ClienteForm
from core.models import Cliente
from django.shortcuts import get_object_or_404, redirect
from .forms import VendorSelectForm
from django import forms
from workflow.docs import DOCUMENTOS
from .forms import SeleccionDocumentosForm
from requests import request
import io
import zipfile
from django.http import HttpResponse
import os
from docxtpl import DocxTemplate
from django.views import View
from django.http import FileResponse, Http404
from django.utils import timezone
from .forms import SolicitudContratoForm
#from .views import SolicitudContratoView  # si lo necesitas
from .models import Tramite
from django.shortcuts import redirect
from datetime import date

from django.conf import settings
from pdfs.utils import fill_word_template, convert_docx_to_pdf

from django.http import JsonResponse
from core.models import Lote

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
        return ctx

    def form_valid(self, form):
        cd = form.cleaned_data
        cliente = form.save()
        # Guardamos ID en sesión para el siguiente paso
        self.request.session['cliente_id'] = cliente.id
        return redirect('workflow:paso_vendedor')
    
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
        
        # AQUÍ ESTÁ EL CAMBIO IMPORTANTE: Obtener los vendedores
        # Filtrar por el proyecto del financiamiento actual
        proyecto_id = fin.lote.proyecto.id
        vendedores = Vendedor.objects.filter(proyectos__id=proyecto_id)
        
        ctx['vendedores'] = vendedores
        return ctx

    def form_valid(self, form):
        vendedor = form.cleaned_data['vendedor']
        self.request.session['vendedor_id'] = vendedor.id
        return redirect('workflow:aviso_privacidad')

    def form_invalid(self, form):
        # Agrega esto para depurar
        print("Errores del formulario:", form.errors)
        return super().form_invalid(form)

class SeleccionDocumentosView(FormView):
    template_name = "workflow/paso3_documentos.html"
    form_class = SeleccionDocumentosForm

    def dispatch(self, request, *args, **kwargs):
        # Requiere haber aceptado el aviso
        if not request.session.get('privacy_accepted'):
            return redirect('workflow:aviso_privacidad')
        # Requiere haber seleccionado financiamiento, cliente y vendedor
        for key in ('financiamiento_id','cliente_id','vendedor_id'):
            if not request.session.get(key):
                return redirect('workflow:paso1_financiamiento')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        fin = get_object_or_404(Financiamiento, id=self.request.session['financiamiento_id'])

        # 1) Empezamos con los documentos que siempre queremos mostrar
        # 1) Aviso de privacidad siempre disponible
        slugs = ['aviso_privacidad']
        slugs += ['carta_intencion', 'solicitud_contrato']

        # 2) Ahora, agregamos el contrato correspondiente según régimen y tipo de pago
        regime = fin.lote.proyecto.tipo_contrato.lower()
        pago   = fin.tipo_pago

        if 'definitiva' in regime:
            if pago == 'contado':
                slugs.append('contrato_definitiva_contado')
            else:
                slugs.append('contrato_definitiva_pagos')
        else:
            # ejidal o comunal
            if pago == 'contado':
                slugs.append('contrato_ejidal_contado')
            else:
                slugs.append('contrato_ejidal_pagos')

        kwargs['available_slugs'] = slugs
        return kwargs
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        fin = get_object_or_404(Financiamiento, id=self.request.session['financiamiento_id'])
        cli = get_object_or_404(Cliente, id=self.request.session['cliente_id'])
        ven = get_object_or_404(Vendedor, id=self.request.session['vendedor_id'])
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
                'builder':     info['builder'],  # la función la seguiremos usando en form_valid
            })
        ctx['available_docs'] = available_docs
        return ctx

    def form_valid(self, form):
        # 1) Carga el trámite
        tramite = get_object_or_404(Tramite, id=self.request.session.get('tramite_id'))

        fin = tramite.financiamiento
        cli = tramite.cliente
        ven = tramite.vendedor

        selected = form.cleaned_data['documentos']

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as zf:
            for slug in selected:
                doc_info = DOCUMENTOS[slug]
                tpl_path = os.path.join(settings.BASE_DIR, doc_info['plantilla'])
                # 1) generar contexto
                # 1) Template object and context
                tpl = DocxTemplate(tpl_path)
                # Pasamos tpl y request siempre; el builder puede ignorarlos si no los necesita
                try:
                    context = doc_info['builder'](fin, cli, ven, request=self.request, tpl=tpl, firma_data=tramite.firma_cliente)
                except TypeError:
                    # Si el builder no espera request o tpl, lo llamamos sin esos args
                    context = doc_info['builder'](fin, cli, ven)

                # 2) rellenar plantilla Word
                tmp_docx = os.path.join(settings.MEDIA_ROOT, 'temp', f"{slug}.docx")
                os.makedirs(os.path.dirname(tmp_docx), exist_ok=True)
                tpl.render(context)
                tpl.save(tmp_docx)
                #fill_word_template(tpl_path, context, tmp_docx)

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
    firma_data = forms.CharField(widget=forms.HiddenInput(), required=False)

class AvisoPrivacidadView(FormView):
    template_name = "workflow/aviso_privacidad.html"
    form_class    = AvisoForm

    def form_valid(self, form):
        # 1) Guarda que aceptó el aviso
        self.request.session['privacy_accepted'] = True

        # 2) Comprueba si quiso firmar digitalmente
        firmar = form.cleaned_data.get('firmar')  # "sí" o "no"
        firma  = form.cleaned_data.get('firma_data')

        if firmar == 'sí' and firma:
            # solo guardamos la firma si eligió “sí”
            self.request.session['firma_cliente_data'] = firma
        else:
            # si no quiere firmar digitalmente, eliminamos cualquier firma previa
            self.request.session.pop('firma_cliente_data', None)

        # 2) Recupera IDs de pasos previos (deben existir en sesión)
        fin_id = self.request.session.get('financiamiento_id')
        cli_id = self.request.session.get('cliente_id')
        ven_id = self.request.session.get('vendedor_id')

        # Si falta alguno, aborta o redirige al inicio
        if not (fin_id and cli_id and ven_id):
            # puedes mostrar un mensaje de error aquí
            return redirect('workflow:paso1_financiamiento')

        # 3) Obtén las instancias reales
        financiamiento = get_object_or_404(Financiamiento, id=fin_id)
        cliente        = get_object_or_404(Cliente,       id=cli_id)
        vendedor       = get_object_or_404(Vendedor,      id=ven_id)

        # 4) Crea o actualiza el Tramite
        tramite_id = self.request.session.get('tramite_id')
        if tramite_id:
            # Si ya existe (por recarga), actualiza
            tramite = get_object_or_404(Tramite, id=tramite_id)
            tramite.financiamiento = financiamiento
            tramite.cliente        = cliente
            tramite.vendedor       = vendedor
            # Si firmó, actualiza; si no, conserva la previa (o vacía)
            if firmar == 'sí' and firma:
                tramite.firma_cliente = firma
            tramite.save()
        else:
            # Nuevo trámite
            tramite = Tramite.objects.create(
                financiamiento = financiamiento,
                cliente        = cliente,
                vendedor       = vendedor,
                firma_cliente  = firma if firmar == 'sí' and firma else ""
            )
            self.request.session['tramite_id'] = tramite.id

        # 5) Vamos a la selección de documentos
        return redirect('workflow:paso3_documentos')

class Paso1FinanciamientoView(TemplateView):
    template_name = "workflow/paso1_financiamiento.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Trae TODOS los planes de financiamiento (o filtra si lo necesitas)
        ctx['financiamientos'] = Financiamiento.objects.select_related('lote__proyecto').all()
        return ctx

    def post(self, request, *args, **kwargs):
        plan_id = request.POST.get('financiamiento')
        if not plan_id:
            # si no selecciona ninguno, vuelve con mensaje
            from django.contrib import messages
            messages.error(request, "Por favor selecciona un plan de financiamiento.")
            return self.get(request, *args, **kwargs)

        # guarda en sesión para los pasos siguientes
        request.session['financiamiento_id'] = int(plan_id)
        return redirect('workflow:paso2_cliente')
