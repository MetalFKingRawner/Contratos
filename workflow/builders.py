# workflow/builders.py
import os, base64, tempfile
from docxtpl import DocxTemplate,InlineImage
from docx.shared import Mm
from datetime import date
from django.conf import settings
from workflow.utils import numero_a_letras, calcular_superficie
from requests import request
from django.db.models import Count

def obtener_letra_identificador(lote):
    """
    Devuelve 'ÚNICO' si el proyecto tiene solo un lote, 
    de lo contrario convierte el identificador a letras.
    Versión optimizada con consulta directa.
    """
    # Consulta optimizada: contar lotes directamente por ID de proyecto
    from core.models import Lote  # Asegúrate de importar tu modelo Lote
    
    cantidad_lotes = Lote.objects.filter(proyecto_id=lote.proyecto_id).count()
    
    if cantidad_lotes == 1 and lote.identificador == '1':
        return 'ÚNICO'
    else:
        return numero_a_letras(float(lote.identificador), apocopado=False)


def _parse_coord(text):
    """
    Dado un campo como "52.26 MTS | CON LOTE #2 (DOS)"
    devuelve (52.26, "CON LOTE #2 (DOS)")
    Formatea el número a 2 decimales siempre.
    """
    try:
        metros_part, col_part = text.split('|', 1)
        metros = float(metros_part.strip().split()[0])
        colindancia = col_part.strip()
    except Exception:
        # fallback
        try:
            metros = float(text.strip().split()[0])
        except:
            metros = 0.0
        colindancia = ''
    
    # Formatear a 2 decimales
    metros_str = format(metros, '.2f')
    return metros_str, colindancia


def build_aviso_privacidad_context(fin, cli, ven, request=None, tpl=None,firma_data=None):
    """
    Context para el Aviso de Privacidad: fecha, nombre y firma.
    """
    # 1) Fecha actual en formato "DD de MES de YYYY"
    hoy   = date.today()
    meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
    fecha_str = f"{hoy.day} de {meses[hoy.month-1]} de {hoy.year}"

    # 2) Construir contexto base
    context = {
        'FECHA_ACTUAL': fecha_str,
        'NOMBRE_CLIENTE': cli.nombre_completo,
    }

    # 3) Firma opcional
    if request and tpl:
        data_url = firma_data or (request.session.get('firma_cliente_data') if request else None)
        if data_url:
            header, b64 = data_url.split(',', 1)
            img_data = base64.b64decode(b64)
            fd, tmp = tempfile.mkstemp(suffix='.png')
            with os.fdopen(fd, 'wb') as f:
                f.write(img_data)
            # Inserta la imagen de firma
            context['FIRMA_CLIENTE'] = InlineImage(tpl, tmp, width=Mm(70))
        else:
            context['FIRMA_CLIENTE'] = ''
    else:
        context['FIRMA_CLIENTE'] = ''

    return context

def build_carta_intencion_context(fin, cli, ven,request=None, tpl=None, firma_data=None):
    # Aquí generaremos el dict con todos los placeholders de la carta
    # Ejemplo mínimo:
    print("BUILDER recibe request:", type(request), hasattr(request, 'session'))
    fecha = date.today()
    meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                 "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
    lote = fin.lote
    superficie = calcular_superficie(lote.norte, lote.sur, lote.este, lote.oeste)
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
            'SUPERFICIE':            superficie,
            'REGIMEN':               fin.lote.proyecto.tipo_contrato,

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
    }
    # Firma del cliente (imagen)
    data_url = firma_data or (request.session.get('firma_cliente_data') if request else None)
    print("FIRMA LEÍDA EN BUILDER:", bool(data_url), (data_url[:50] + '...') if data_url else '')
    if data_url and tpl:
        # Decodifica y guarda en un temp file
        header, encoded = data_url.split(',', 1)
        data = base64.b64decode(encoded)
        fd, tmp_path = tempfile.mkstemp(suffix='.png')
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
        # Crea InlineImage de docxtpl
        # Ajusta ancho en mm según tu diseño
        context['FIRMA_CLIENTE'] = InlineImage(
            tpl,  # placeholder, luego se ignora
            tmp_path,
            width=Mm(70)
        )
    else:
        context['FIRMA_CLIENTE'] = ''

    return context

def build_solicitud_contrato_context(fin, cli, ven, request=None, tpl=None, firma_data=None):
    """
    Context para Solicitud de Contratos.
    Campos comunes + ramificación contado/financiado.
    """
    # 1) Fecha actual y desgloses
    hoy   = date.today()
    meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
    DIA   = hoy.day
    MES   = meses[hoy.month-1].upper()
    ANIO  = hoy.year
    email = (cli.email or '')        # convierte None -> ''
    email = email.strip()            # quita espacios en blanco
    rfc = (cli.rfc or '')
    if email:
        correo_comprador = email.upper()
    else:
        correo_comprador = 'NO PROPORCIONADO'

    if rfc:
        rfc_comprador = rfc.upper()
    else:
        rfc_comprador = 'NO PROPORCIONADO'



    # 2) Datos básicos del cliente
    context = {
        'DIA':                DIA,
        'MES':                MES,
        'ANIO':               ANIO,
        'NOMBRE_CLIENTE':     cli.nombre_completo.upper(),
        'TELEFONO_CLIENTE':   cli.telefono,
        'CORREO_CLIENTE':     correo_comprador,
        'OCUPACION_CLIENTE':  cli.ocupacion.upper(),
        'ESTADO_CIVIL':       cli.estado_civil.upper(),
        'ORIGINARIO_CLIENTE': cli.originario.upper(),
        'NACIONALIDAD':       cli.nacionalidad,
        'DIRECCION_CLIENTE':  cli.domicilio,
        'RFC_CLIENTE':        rfc_comprador,  # asume tienes campo rfc en Cliente
        # Lote y financiamiento
        'NOMBRE_LOTE':        str(fin.lote.proyecto.nombre).upper(),
        'NUMERO_LOTE':        fin.lote.identificador,
        'PRECIO_LOTE':        f"{fin.precio_lote:.2f}",
        # Vendedor
        'NOMBRE_VENDEDOR':    ven.nombre_completo.upper(),
    }

    # 3) Campos según tipo_pago
    if fin.tipo_pago == 'contado':
        context.update({
            'CANTIDAD_APARTADO':      f"{fin.apartado:.2f}",
            'FECHA_PAGO_COMPLETO':    fin.fecha_pago_completo.strftime("%d/%m/%Y"),
            # los demás vacíos
            'CANTIDAD_ENGANCHE':      '',
            'FECHA_ENGANCHE':         '',
            'NUM_MENSUALIDAD':        '',
            'DIA_PAGO':               '',
        })
    else:
        # financiado
        context.update({
            'CANTIDAD_APARTADO':      f"{fin.apartado:.2f}",
            'FECHA_PAGO_COMPLETO':    '',
            'CANTIDAD_ENGANCHE':      f"{fin.enganche:.2f}",
            'FECHA_ENGANCHE':         fin.fecha_enganche.strftime("%d/%m/%Y") if fin.fecha_enganche else '',
            'NUM_MENSUALIDAD':        fin.num_mensualidades,
            'DIA_PAGO':               fin.fecha_primer_pago.day if fin.fecha_primer_pago else '',
        })

    # 4) Firma del cliente
    if request and tpl:
        data_url = firma_data or (request.session.get('firma_cliente_data') if request else None)
        if data_url:
            header, b64 = data_url.split(',', 1)
            img_data = base64.b64decode(b64)
            fd, tmp = tempfile.mkstemp(suffix='.png')
            with os.fdopen(fd, 'wb') as f:
                f.write(img_data)
            # Inserta la imagen de firma
            context['FIRMA_CLIENTE'] = InlineImage(tpl, tmp, width=Mm(40))
        else:
            context['FIRMA_CLIENTE'] = ''
    else:
        context['FIRMA_CLIENTE'] = ''

    return context

def build_contrato_definitiva_pagos_context(fin, cli, ven, request=None, tpl=None, firma_data=None):
    """
    Context para el Contrato Propiedad Definitiva y Pequeña Propiedad a Pagos.
    fin: Financiamiento
    cli: Cliente
    ven: Vendedor
    request: HttpRequest para firma
    tpl: DocxTemplate para InlineImage
    """

    # 1) Pronombres
    def art(sex, masculino, femenino):
        return masculino if sex == 'M' else femenino
    prop = fin.lote.proyecto.propietario

    # SEXO_1: EL/LA VENDEDOR
    SEXO_1 = art(ven.sexo, 'EL', 'LA')
    # SEXO_2: VENDEDOR/VENDEDORA
    SEXO_2 = art(ven.sexo, 'VENDEDOR', 'VENDEDORA')
    # SEXO_3: EL/LA COMPRADOR
    SEXO_3 = art(cli.sexo, 'EL', 'LA')
    # SEXO_4: COMPRADOR/COMPRADORA
    SEXO_4 = art(cli.sexo, 'COMPRADOR', 'COMPRADORA')
    # SEXO_5: A/O
    SEXO_5 = art(cli.sexo, 'O', 'A')
    # SEXO_6: EL/LA PROPIETARIO/A
    prop = fin.lote.proyecto.propietario
    SEXO_6 = art(prop.sexo, 'EL', 'LA')
    # SEXO_7: A LA / AL
    SEXO_7 = art(cli.sexo, 'A LA', 'AL')
    # SEXO_8: DEL / DE LA
    SEXO_8 = art(ven.sexo, 'DEL', 'DE LA')

    # 2) Fecha actual
    hoy   = date.today()
    meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
    DIA, MES = hoy.day, meses[hoy.month-1].upper()

    coords = {}
    for lado in ('norte','sur','este','oeste'):
        raw = getattr(fin.lote, lado, '')
        m, c = _parse_coord(raw)
        coords[f'NUMERO_METROS_{lado.upper()}'] = m
        coords[f'COLINDANCIA_LOTE_{lado.upper()}'] = c

    # 3) Miembro B dinámico según relación:
    # — Si ven es propietario:
    if ven.ine == prop.ine and prop.tipo == 'propietario':
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, "
            f"QUE ACREDITA CON LA CESIÓN DE DERECHOS DE FECHA {hoy.day} DE "
            f"{meses[hoy.month-1].upper()} DE DOS MIL VEINTICINCO, EXPEDIDA POR LOS INTEGRANTES "
            f"DEL COMISARIADO DE BIENES EJIDALES Y CONSEJO DE VIGILANCIA."
        )
    # — Si ven es apoderado:
    elif ven.ine == prop.ine and prop.tipo == 'apoderado':
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, AL IGUAL QUE, CON LAS "
            f"FACULTADES Y AUTORIZACIÓN SUFICIENTE PARA OBLIGARSE EN LOS TÉRMINOS DE ESTE, TAL COMO SE ACREDITA CON EL INSTRUMENTO PÚBLICO "
            f"{fin.instrumento_publico} OTORGADO ANTE LA FE DEL NOTARIO PÚBLICO "
            f"{fin.notario_publico} DE OAXACA, EL LICENCIADO {fin.nombre_notario.upper()}."
            f"C. ESTAR LEGITIMADO PARA REALIZAR TODOS AQUELLOS ACTOS SOBRE LA PROPIEDAD, CONFORME AL PODER DESCRITO EN LA DECLARACIÓN ANTERIOR."
        )
    # — Si es vendedor autorizado:
    else:
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, AL IGUAL QUE CON LAS FACULTADES Y AUTORIZACIÓN SUFICIENTE PARA OBLIGARSE EN LOS TÉRMINOS DE ESTE, "
            f"TAL COMO SE ACREDITA EN EL CONTRATO DE EXCLUSIVIDAD, PROMOCIÓN Y COMISIÓN POR LA VENTA DEL BIEN INMUEBLE DE FECHA {hoy.day} DE "
            f"{meses[hoy.month-1].upper()} DE DOS MIL VEINTICINCO, OTORGADO POR {SEXO_6} C. "
            f"{prop.nombre_completo.upper()}."
        )

    # 4) Enganche y mensualidades
    eng_dia = fin.fecha_enganche.day if fin.fecha_enganche else ''
    eng_mes = meses[fin.fecha_enganche.month-1].upper() if fin.fecha_enganche else ''
    eng_anio= fin.fecha_enganche.year if fin.fecha_enganche else ''
    cant_eng  = fin.enganche or 0
    letra_eng = numero_a_letras(float(cant_eng))
    num_men   = fin.num_mensualidades
    fija      = fin.monto_mensualidad or 0
    letra_fija= numero_a_letras(float(fija))
    final     = fin.monto_pago_final or 0
    letra_fin = numero_a_letras(float(final))

    # 5) Context base
    context = {
        # Pronombres
        'SEXO_1': SEXO_1, 'SEXO_2': SEXO_2, 'SEXO_3': SEXO_3,
        'SEXO_4': SEXO_4, 'SEXO_5': SEXO_5, 'SEXO_6': SEXO_6,
        'SEXO_7': SEXO_7, 'SEXO_8': SEXO_8,

        # Fecha
        'DIA': DIA, 'MES': MES,

        # Vendedor
        'NOMBRE_VENDEDOR': ven.nombre_completo.upper(),
        'ID_INE':          ven.ine,
        'NUMERO_VENDEDOR': ven.telefono,

        # Notario/Propietario
        'INSTRUMENTO_PUBLICO': prop.instrumento_publico or '',
        'NOTARIO':             prop.notario_publico or '',
        'NOMBRE_NOTARIO':      prop.nombre_notario or '',
        'NOMBRE_PROPIETARIO':  prop.nombre_completo.upper(),

        # Comprador
        'NOMBRE_COMPRADOR':    cli.nombre_completo.upper(),
        'DIRECCION_COMPRADOR': cli.domicilio.upper(),
        'ID_INE_COMPRADOR':    cli.numero_id,
        'LUGAR_ORIGEN':        cli.originario.upper(),
        'ESTADO_CIVIL':        cli.estado_civil.upper(),
        'TELEFONO_COMPRADOR':  cli.telefono.upper(),
        'OCUPACION_COMPRADOR': cli.ocupacion.upper(),
        'CORREO_COMPRADOR':    cli.email.upper(),

        # Lote
        'IDENTIFICADOR_LOTE':      fin.lote.identificador,
        'LETRA_IDENTIFICADOR':     fin.lote.identificador,
        'DIRECCION_PROYECTO_LOTE': fin.lote.proyecto.ubicacion.upper(),

        # Coordenadas
        **coords,

        # Financiamiento
        'PRECIO_LOTE_FINANCIAMIENTO': f"{fin.precio_lote:.2f}",
        'LETRA_PRECIO_LOTE':          numero_a_letras(float(fin.precio_lote)),
        'APARTADO_FINANCIAMIENTO':    f"{fin.apartado:.2f}",
        'LETRA_APARTADO':             numero_a_letras(float(fin.apartado)),

        # Enganche y mensualidades
        'DIA_ENGANCHE':                   eng_dia,
        'MES_ENGANCHE':                   eng_mes,
        'ANIO_ENGANCHE':                  eng_anio,
        'CANTIDAD_ENGANCHE_FINANCIAMIENTO': f"{cant_eng:.2f}",
        'LETRA_ENGANCHE':                   letra_eng,

        'MENSUALIADES_FINANCIAMIENTO':     num_men,
        'MENSUALIDADES': num_men-1,
        'MENSUALIDADES_FIJAS':             f"{fija:.2f}",
        'CANTIDAD_MENSUALIDAD_FIJA':       f"{fija:.2f}",
        'LETRA_MENSUALIDAD_FIJA':          letra_fija,

        'CANTIDAD_MENSUALIDAD_FINAL':      f"{final:.2f}",
        'LETRA_MENSUALIDAD_FINAL':         letra_fin,
        # Y la cláusula B variable:
        'CLAUSULA_B': claus_b,
    }

    # 6) Firma del cliente
    if request and tpl:
        data_url = firma_data or (request.session.get('firma_cliente_data') if request else None)
        if data_url:
            header, b64 = data_url.split(',', 1)
            img_data = base64.b64decode(b64)
            fd, tmp = tempfile.mkstemp(suffix='.png')
            with os.fdopen(fd, 'wb') as f:
                f.write(img_data)
            # Inserta la imagen de firma
            context['FIRMA_CLIENTE'] = InlineImage(tpl, tmp, width=Mm(40))
        else:
            context['FIRMA_CLIENTE'] = ''
    else:
        context['FIRMA_CLIENTE'] = ''

    return context

def build_contrato_definitiva_contado_context(fin, cli, ven, request=None, tpl=None, firma_data=None):
    """
    Construye el context para el Contrato Propiedad Definitiva (Contado).
    fin: Financiamiento
    cli: Cliente
    ven: Vendedor
    request: HttpRequest para extraer firma
    tpl: DocxTemplate para InlineImage
    """
    # 1) Pronombres y formas según sexo
    def art(sex, masculino, femenino):
        return masculino if sex == 'M' else femenino

    # SEXO_1: EL/LA VENDEDOR
    SEXO_1 = art(ven.sexo, 'EL', 'LA')
    # SEXO_2: VENDEDOR/VENDEDORA
    SEXO_2 = art(ven.sexo, 'VENDEDOR', 'VENDEDORA')
    # SEXO_3: EL/LA COMPRADOR
    SEXO_3 = art(cli.sexo, 'EL', 'LA')
    # SEXO_4: COMPRADOR/COMPRADORA
    SEXO_4 = art(cli.sexo, 'COMPRADOR', 'COMPRADORA')
    # SEXO_5: A/O
    SEXO_5 = art(cli.sexo, 'O', 'A')
    # SEXO_6: EL/LA PROPIETARIO/A
    prop = fin.lote.proyecto.propietario
    SEXO_6 = art(prop.sexo, 'EL', 'LA')
    # SEXO_7: A LA / AL
    SEXO_7 = art(cli.sexo, 'A LA', 'AL')
    # SEXO_8: DEL / DE LA
    SEXO_8 = art(ven.sexo, 'DEL', 'DE LA')

    # 2) Fecha de pago completo (hoy)
    pago = date.today()
    meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

    # 3) Coordenadas por cada lado
    dir_fields = {}
    for dir_name in ('norte','sur','este','oeste'):
        raw = getattr(fin.lote, dir_name, '')
        metros, col = _parse_coord(raw)
        key_m = f'NUMERO_METROS_{dir_name.upper()}'
        key_c = f'COLINDANCIA_LOTE_{dir_name.upper()}'
        dir_fields[key_m] = metros
        dir_fields[key_c] = col

    # 4) Cálculo pago restante
    restante = float(fin.precio_lote) - float(fin.apartado)
    restante_letra = numero_a_letras(restante)

# 3) Miembro B dinámico según relación:
    # — Si ven es propietario:
    if ven.ine == prop.ine and prop.tipo == 'propietario':
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, "
            f"QUE ACREDITA CON LA CESIÓN DE DERECHOS DE FECHA {pago.day} DE "
            f"{meses[pago.month-1].upper()} DE DOS MIL VEINTICINCO, EXPEDIDA POR LOS INTEGRANTES "
            f"DEL COMISARIADO DE BIENES EJIDALES Y CONSEJO DE VIGILANCIA."
        )
    # — Si ven es apoderado:
    elif ven.ine == prop.ine and prop.tipo == 'apoderado':
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, AL IGUAL QUE, CON LAS "
            f"FACULTADES Y AUTORIZACIÓN SUFICIENTE PARA OBLIGARSE EN LOS TÉRMINOS DE ESTE, TAL COMO SE ACREDITA CON EL INSTRUMENTO PÚBLICO "
            f"{fin.instrumento_publico} OTORGADO ANTE LA FE DEL NOTARIO PÚBLICO "
            f"{fin.notario_publico} DE OAXACA, EL LICENCIADO {fin.nombre_notario.upper()}."
            f"C. ESTAR LEGITIMADO PARA REALIZAR TODOS AQUELLOS ACTOS SOBRE LA PROPIEDAD, CONFORME AL PODER DESCRITO EN LA DECLARACIÓN ANTERIOR."
        )
    # — Si es vendedor autorizado:
    else:
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, AL IGUAL QUE CON LAS FACULTADES Y AUTORIZACIÓN SUFICIENTE PARA OBLIGARSE EN LOS TÉRMINOS DE ESTE, "
            f"TAL COMO SE ACREDITA EN EL CONTRATO DE EXCLUSIVIDAD, PROMOCIÓN Y COMISIÓN POR LA VENTA DEL BIEN INMUEBLE DE FECHA {pago.day} DE "
            f"{meses[pago.month-1].upper()} DE DOS MIL VEINTICINCO, OTORGADO POR {SEXO_6} C. "
            f"{prop.nombre_completo.upper()}."
        )

    # 5) Construcción del context
    context = {
        # Pronombres
        'SEXO_1': SEXO_1,
        'SEXO_2': SEXO_2,
        'SEXO_3': SEXO_3,
        'SEXO_4': SEXO_4,
        'SEXO_5': SEXO_5,
        'SEXO_6': SEXO_6,
        'SEXO_7': SEXO_7,
        'SEXO_8': SEXO_8,

        # Fecha de generación
        'DIA': pago.day,
        'MES': meses[pago.month - 1].upper(),

        # Vendedor
        'NOMBRE_VENDEDOR': ven.nombre_completo.upper(),
        'ID_INE':          ven.ine,
        'NUMERO_VENDEDOR': ven.telefono,

        # Notario e instrumento (del propietario)
        'INSTRUMENTO_PUBLICO': prop.instrumento_publico or '',
        'NOTARIO':             prop.notario_publico or '',
        'NOMBRE_NOTARIO':      prop.nombre_notario or '',

        # Propietario
        'NOMBRE_PROPIETARIO': prop.nombre_completo.upper(),

        # Cliente/Comprador
        'NOMBRE_COMPRADOR':   cli.nombre_completo.upper(),
        'DIRECCION_COMPRADOR':cli.domicilio.upper(),
        'ID_INE_COMPRADOR':    cli.numero_id,
        'LUGAR_ORIGEN':        cli.originario.upper(),
        'ESTADO_CIVIL':        cli.estado_civil.upper(),
        'TELEFONO_COMPRADOR':  cli.telefono.upper(),
        'OCUPACION_COMPRADOR': cli.ocupacion.upper(),
        'CORREO_COMPRADOR':    cli.email.upper(),

        # Lote
        'IDENTIFICADOR_LOTE':    fin.lote.identificador,
        'LETRA_IDENTIFICADOR':   fin.lote.identificador,
        'DIRECCION_PROYECTO_LOTE': fin.lote.proyecto.ubicacion.upper(),

        # Coordenadas dinámicas
        **dir_fields,

        # Financiamiento y pagos
        'PRECIO_LOTE_FINANCIAMIENTO': f"{fin.precio_lote:.2f}",
        'LETRA_PRECIO_LOTE':          numero_a_letras(float(fin.precio_lote)),
        'APARTADO_FINANCIAMIENTO':    f"{fin.apartado:.2f}",
        'LETRA_APARTADO':             numero_a_letras(float(fin.apartado)),

        'DIA_PAGO':  pago.day,
        'MES_PAGO':  meses[pago.month - 1].upper(),
        'ANIO_PAGO': pago.year,

        'CANTIDAD_PAGO_COMPLETO':  f"{restante:.2f}",
        'CANTIDAD_LETRA_PAGO':     restante_letra,

        # Y la cláusula B variable:
        'CLAUSULA_B': claus_b,
    }

    # 6) Firma del cliente (igual al otro builder)
    if request and tpl:
        data_url = firma_data or (request.session.get('firma_cliente_data') if request else None)
        if data_url:
            header, b64 = data_url.split(',', 1)
            img_data = base64.b64decode(b64)
            fd, tmp = tempfile.mkstemp(suffix='.png')
            with os.fdopen(fd, 'wb') as f:
                f.write(img_data)
            # Inserta la imagen de firma
            context['FIRMA_CLIENTE'] = InlineImage(tpl, tmp, width=Mm(40))
        else:
            context['FIRMA_CLIENTE'] = ''
    else:
        context['FIRMA_CLIENTE'] = ''

    return context


from decimal import Decimal, InvalidOperation
# Helper para formatear dinero con separador de miles y 2 decimales
def fmt_money(val):
    """
    Devuelve una cadena como '500,000.00' para entradas numéricas o cadenas numéricas.
    Si no se puede parsear, devuelve str(val) sin modificación.
    """
    try:
        d = Decimal(str(val))
    except (InvalidOperation, TypeError, ValueError):
        try:
            d = Decimal(float(val))
        except Exception:
            return str(val)
    # El formato con ',' funciona con Decimal en Python 3.6+
    return f"{d:,.2f}"

def build_contrato_propiedad_contado_context(fin, cli, ven, request=None, tpl=None, firma_data=None, clausulas_adicionales=None):

    print("Entré al build de pequeña propiedad a contado de un comprador")

    if clausulas_adicionales is None:
        clausulas_adicionales = {}

    # 1) Pronombres y formas según sexo
    def art(sex, masculino, femenino):
        return masculino if sex == 'M' else femenino

    # SEXO_1: EL/LA VENDEDOR
    SEXO_1 = art(ven.sexo, 'EL', 'LA')
    # SEXO_2: VENDEDOR/VENDEDORA
    SEXO_2 = art(ven.sexo, 'VENDEDOR', 'VENDEDORA')
    # SEXO_3: EL/LA COMPRADOR
    SEXO_3 = art(cli.sexo, 'EL', 'LA')
    # SEXO_4: COMPRADOR/COMPRADORA
    SEXO_4 = art(cli.sexo, 'COMPRADOR', 'COMPRADORA')
    # SEXO_5: A/O 
    SEXO_5 = art(cli.sexo, 'O', 'A')
    # SEXO_6: EL/LA PROPIETARIO/A
    prop = fin.lote.proyecto.propietario.first()
    SEXO_6 = art(prop.sexo, 'EL', 'LA')
    # SEXO_7: A LA / AL
    SEXO_7 = art(ven.sexo, 'AL "', 'A "LA ')
    # SEXO_8: DEL / DE LA
    SEXO_8 = art(ven.sexo, 'DEL "', 'DE "LA ')
    SEXO_9 = art(ven.sexo, 'O', 'A')

    SEXO_16 = art(ven.sexo, 'ÉSTE', 'ÉSTA')
    SEXO_17 = art(cli.sexo, 'ÉSTE', 'ÉSTA')
    SEXO_18 = art(cli.sexo, 'DEL "', 'DE "LA ')
    SEXO_19 = art(cli.sexo, 'AL "', 'A "LA ')
    SEXO_20 = art(prop.sexo, 'EL', 'LA')
    #SEXO_10 = art(cli.sexo, 'COMPRADORES','COMPRADORAS')
    #SEXO_11 = art(cli.sexo, 'O', 'A')
    #SEXO_12 = art(cli.sexo, 'A LOS', 'A LAS')
    #SEXO_13 = art(cli.sexo, 'DE LOS', 'DE LAS')

    # 2) Fecha de pago completo (hoy)
    pago = fin.fecha_pago_completo
    meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

    # 3) Coordenadas por cada lado
    dir_fields = {}
    for dir_name in ('norte','sur','este','oeste'):
        raw = getattr(fin.lote, dir_name, '')
        metros, col = _parse_coord(raw)
        key_m = f'NUMERO_METROS_{dir_name.upper()}'
        key_c = f'COLINDANCIA_LOTE_{dir_name.upper()}'
        dir_fields[key_m] = metros  # Ahora metros ya está formateado como string
        dir_fields[key_c] = col

    # 4) Cálculo pago restante
    restante = float(fin.precio_lote) - float(fin.apartado)
    restante_letra = numero_a_letras(restante)

    fecha_posesion = fin.lote.proyecto.fecha_emision_documento
    fecha_contrato = fin.lote.proyecto.fecha_emision_contrato
    autoridad = fin.lote.proyecto.autoridad
    dia_actual = date.today()
    email = (cli.email or '')        # convierte None -> ''
    email = email.strip()            # quita espacios en blanco
    if email:
        correo_comprador = email.upper()
    else:
        correo_comprador = 'NO PROPORCIONADO'

# 3) Miembro B dinámico según relación:
    # — Si ven es propietario:
    if ven.ine == prop.ine and prop.tipo == 'propietario':
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, "
            f"QUE ACREDITA CON EL CONTRATO PRIVADO DE COMPRAVENTA Y CONSTANCIA DE POSESIÓN DE FECHA {fecha_posesion} "
            f"EXPEDIDA POR LOS INTEGRANTES {autoridad}"
        )
    # — Si ven es apoderado:
    elif ven.ine == prop.ine and prop.tipo == 'apoderado':
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, AL IGUAL QUE, CON LAS "
            f"FACULTADES Y AUTORIZACIÓN SUFICIENTE PARA OBLIGARSE EN LOS TÉRMINOS DE ESTE, TAL COMO SE ACREDITA CON EL INSTRUMENTO PÚBLICO "
            f"{fin.instrumento_publico} OTORGADO ANTE LA FE DEL NOTARIO PÚBLICO "
            f"{fin.notario_publico} DE OAXACA, EL LICENCIADO {fin.nombre_notario.upper()}."
            f"C. ESTAR LEGITIMADO PARA REALIZAR TODOS AQUELLOS ACTOS SOBRE LA PROPIEDAD, CONFORME AL PODER DESCRITO EN LA DECLARACIÓN ANTERIOR."
        )
    # — Si es vendedor autorizado:
    else:
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, AL IGUAL QUE CON LAS FACULTADES Y AUTORIZACIÓN SUFICIENTE PARA OBLIGARSE EN LOS TÉRMINOS DE ESTE, "
            f"TAL COMO SE ACREDITA EN EL CONTRATO DE EXCLUSIVIDAD, PROMOCIÓN Y COMISIÓN POR LA VENTA DEL BIEN INMUEBLE DE FECHA {fecha_contrato} "
            f"OTORGADO POR {SEXO_20}  C. {prop.nombre_completo.upper()}"
        )

    # 5) Construcción del context
    context = {
        # Pronombres
        'SEXO_1': SEXO_1,
        'SEXO_2': SEXO_2,
        'SEXO_3': SEXO_3,
        'SEXO_4': SEXO_4,
        'SEXO_5': SEXO_5,
        'SEXO_6': SEXO_6,
        'SEXO_7': SEXO_7,
        'SEXO_8': SEXO_8,
        'SEXO_9': SEXO_9,
        'SEXO_16': SEXO_16,
        'SEXO_17': SEXO_17,
        'SEXO_18': SEXO_18,
        'SEXO_19': SEXO_19,
        #'SEXO_9': SEXO_9,
        #'SEXO_10': SEXO_10,
        #'SEXO_11': SEXO_11,
        #'SEXO_12': SEXO_12,
        #'SEXO_13': SEXO_13,

        # Fecha de generación
        'DIA': numero_a_letras(float(dia_actual.day),apocopado=False),
        'MES': meses[dia_actual.month - 1].upper(),

        # Vendedor
        'NOMBRE_VENDEDOR': ven.nombre_completo.upper(),
        'ID_INE':          ven.ine,
        'NUMERO_VENDEDOR': ven.telefono,

        # Notario e instrumento (del propietario)
        'INSTRUMENTO_PUBLICO': prop.instrumento_publico or '',
        'NOTARIO':             prop.notario_publico or '',
        'NOMBRE_NOTARIO':      prop.nombre_notario or '',

        # Propietario
        'NOMBRE_PROPIETARIO': prop.nombre_completo.upper(),

        # Cliente/Comprador
        'NOMBRE_COMPRADOR':   cli.nombre_completo.upper(),
        'DIRECCION_COMPRADOR':cli.domicilio.upper(),
        'ID_INE_COMPRADOR':    cli.numero_id.upper(),
        'LUGAR_ORIGEN':        cli.originario.upper(),
        'ESTADO_CIVIL':        cli.estado_civil.upper(),
        'TELEFONO_COMPRADOR':  cli.telefono.upper(),
        'OCUPACION_COMPRADOR': cli.ocupacion.upper(),
        'CORREO_COMPRADOR': correo_comprador,

        # Lote
        'IDENTIFICADOR_LOTE':    fin.lote.identificador,
        'LETRA_IDENTIFICADOR': obtener_letra_identificador(fin.lote),  # Cambio aquí
        'DIRECCION_PROYECTO_LOTE': fin.lote.proyecto.ubicacion.upper(),

        # Coordenadas dinámicas
        **dir_fields,

        # Financiamiento y pagos
        'PRECIO_LOTE_FINANCIAMIENTO': fmt_money(fin.precio_lote),
        'LETRA_PRECIO_LOTE':          numero_a_letras(float(fin.precio_lote)),
        'APARTADO_FINANCIAMIENTO':    fmt_money(fin.apartado),
        'LETRA_APARTADO':             numero_a_letras(float(fin.apartado)),

        'DIA_PAGO':  pago.day,
        'MES_PAGO':  meses[pago.month - 1].upper(),
        'ANIO_PAGO': pago.year,

        'CANTIDAD_PAGO_COMPLETO':  fmt_money(restante),
        'CANTIDAD_LETRA_PAGO':     restante_letra,

        # Y la cláusula B variable:
        'CLAUSULA_B': claus_b,
    }

    # 6) Firma del cliente (igual al otro builder)
    if request and tpl:
        data_url = firma_data or (request.session.get('firma_cliente_data') if request else None)
        if data_url:
            header, b64 = data_url.split(',', 1)
            img_data = base64.b64decode(b64)
            fd, tmp = tempfile.mkstemp(suffix='.png')
            with os.fdopen(fd, 'wb') as f:
                f.write(img_data)
            # Inserta la imagen de firma
            context['FIRMA_CLIENTE'] = InlineImage(tpl, tmp, width=Mm(40))
        else:
            context['FIRMA_CLIENTE'] = ''
    else:
        context['FIRMA_CLIENTE'] = ''

    # Determinar qué cláusulas adicionales existen
    tiene_pago = clausulas_adicionales and 'pago' in clausulas_adicionales and bool(clausulas_adicionales['pago'])
    tiene_deslinde = clausulas_adicionales and 'deslinde' in clausulas_adicionales and bool(clausulas_adicionales['deslinde'])
    tiene_promesa = clausulas_adicionales and 'promesa' in clausulas_adicionales and bool(clausulas_adicionales['promesa'])
    
    # Formatear cláusulas adicionales
    clausula_pago = clausulas_adicionales['pago'] if tiene_pago else ''
    clausula_deslinde = clausulas_adicionales['deslinde'] if tiene_deslinde else ''
    clausula_promesa = clausulas_adicionales['promesa'] if tiene_promesa else ''
    
    # Agregar al contexto
    context.update({
        'CLAUSULA_PAGO': clausula_pago.upper(),
        'CLAUSULA_DESLINDE': clausula_deslinde.upper(),
        'CLAUSULA_PROMESA': clausula_promesa.upper(),
    })

    return context

def build_contrato_propiedad_contado_varios_context(fin, cli, ven, cliente2=None, request=None, tpl=None, firma_data=None, clausulas_adicionales=None):

    print("Entré al build de pequeña propiedad para DOS COMPRADORES")

    if clausulas_adicionales is None:
        clausulas_adicionales = {}

    # 1) Pronombres y formas según sexo para SINGULARES (igual que antes)
    def art(sex, masculino, femenino):
        return masculino if sex == 'M' else femenino

    SEXO_1 = art(ven.sexo, 'EL', 'LA')
    SEXO_2 = art(ven.sexo, 'VENDEDOR', 'VENDEDORA')
    SEXO_3 = art(cli.sexo, 'EL', 'LA')
    SEXO_4 = art(cli.sexo, 'COMPRADOR', 'COMPRADORA')
    SEXO_5 = art(cli.sexo, 'O', 'A')
    prop = fin.lote.proyecto.propietario.first()
    SEXO_6 = art(prop.sexo, 'EL', 'LA')
    SEXO_7 = art(ven.sexo, 'AL "', 'A "LA ')
    SEXO_8 = art(ven.sexo, 'DEL "', 'DE "LA ')
    SEXO_14 = art(ven.sexo, 'O', 'A')
    SEXO_15 = art(ven.sexo, 'DEL "', 'DE "LA ')
    SEXO_16 = art(ven.sexo, 'ÉSTE', 'ÉSTA')
    SEXO_20 = art(prop.sexo, 'EL', 'LA')

    # 2) Pronombres PLURALES para DOS COMPRADORES
    # Determinar género predominante para plurales
    if cliente2:
        if cli.sexo == 'M' or cliente2.sexo == 'M':
            # Si al menos uno es masculino -> masculino plural
            SEXO_9 = 'LOS'
            SEXO_10 = 'COMPRADORES'
            SEXO_11 = 'O'
            SEXO_12 = 'A "LOS '
            SEXO_13 = 'DE "LOS '
            SEXO_17 = 'ÉSTOS'
        else:
            # Ambos femeninos -> femenino plural
            SEXO_9 = 'LAS'
            SEXO_10 = 'COMPRADORAS'
            SEXO_11 = 'A'
            SEXO_12 = 'A "LAS '
            SEXO_13 = 'DE "LAS '
            SEXO_17 = 'ÉSTAS'
    else:
        # Por si acaso (aunque esta función es para varios)
        SEXO_9 = 'LOS'
        SEXO_10 = 'COMPRADORES'
        SEXO_11 = 'O'
        SEXO_12 = 'A LOS'
        SEXO_13 = 'DE LOS'
        SEXO_17 = 'ÉSTOS'

    # 3) Fecha de pago completo (hoy)
    pago = date.today()
    meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

    # 4) Coordenadas por cada lado (igual que antes)
    dir_fields = {}
    # En ambas funciones, cambia este bucle:
    for dir_name in ('norte','sur','este','oeste'):
        raw = getattr(fin.lote, dir_name, '')
        metros, col = _parse_coord(raw)
        key_m = f'NUMERO_METROS_{dir_name.upper()}'
        key_c = f'COLINDANCIA_LOTE_{dir_name.upper()}'
        dir_fields[key_m] = metros  # Ahora metros ya está formateado como string
        dir_fields[key_c] = col

    # 5) Cálculo pago restante (igual que antes)
    restante = float(fin.precio_lote) - float(fin.apartado)
    restante_letra = numero_a_letras(restante)

    fecha_posesion = fin.lote.proyecto.fecha_emision_documento
    fecha_contrato = fin.lote.proyecto.fecha_emision_contrato
    autoridad = fin.lote.proyecto.autoridad

    email1 = (cli.email or '')        # convierte None -> ''
    email1 = email1.strip()            # quita espacios en blanco
    if email1:
        correo_comprador1 = email1.upper()
    else:
        correo_comprador1 = 'NO PROPORCIONADO'

    email2 = (cliente2.email or '')        # convierte None -> ''
    email2 = email2.strip()            # quita espacios en blanco
    if email2:
        correo_comprador2 = email2.upper()
    else:
        correo_comprador2 = 'NO PROPORCIONADO'

    # 6) Miembro B dinámico según relación (igual que antes)
    if ven.ine == prop.ine and prop.tipo == 'propietario':
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, "
            f"QUE ACREDITA CON EL CONTRATO PRIVADO DE COMPRAVENTA Y CONSTANCIA DE POSESIÓN DE FECHA {fecha_posesion} "
            f"EXPEDIDA POR LOS INTEGRANTES {autoridad}"
        )
    elif ven.ine == prop.ine and prop.tipo == 'apoderado':
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, AL IGUAL QUE, CON LAS "
            f"FACULTADES Y AUTORIZACIÓN SUFICIENTE PARA OBLIGARSE EN LOS TÉRMINOS DE ESTE, TAL COMO SE ACREDITA CON EL INSTRUMENTO PÚBLICO "
            f"{fin.instrumento_publico} OTORGADO ANTE LA FE DEL NOTARIO PÚBLICO "
            f"{fin.notario_publico} DE OAXACA, EL LICENCIADO {fin.nombre_notario.upper()}."
            f"C. ESTAR LEGITIMADO PARA REALIZAR TODOS AQUELLOS ACTOS SOBRE LA PROPIEDAD, CONFORME AL PODER DESCRITO EN LA DECLARACIÓN ANTERIOR."
        )
    else:
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, AL IGUAL QUE CON LAS FACULTADES Y AUTORIZACIÓN SUFICIENTE PARA OBLIGARSE EN LOS TÉRMINOS DE ESTE, "
            f"TAL COMO SE ACREDITA EN EL CONTRATO DE EXCLUSIVIDAD, PROMOCIÓN Y COMISIÓN POR LA VENTA DEL BIEN INMUEBLE DE FECHA {fecha_contrato} "
            f"OTORGADO POR {SEXO_20}  C. {prop.nombre_completo.upper()}"
        )
    fecha_pago = fin.fecha_pago_completo
    # 7) Construcción del context - con datos de AMBOS clientes
    context = {
        # Pronombres SINGULARES
        'SEXO_1': SEXO_1,
        'SEXO_2': SEXO_2,
        'SEXO_3': SEXO_3,
        'SEXO_4': SEXO_4,
        'SEXO_5': SEXO_5,
        'SEXO_6': SEXO_6,
        'SEXO_7': SEXO_7,
        'SEXO_8': SEXO_8,
        # Pronombres PLURALES
        'SEXO_9': SEXO_9,
        'SEXO_10': SEXO_10,
        'SEXO_11': SEXO_11,
        'SEXO_12': SEXO_12,
        'SEXO_13': SEXO_13,
        'SEXO_14': SEXO_14,
        'SEXO_15': SEXO_15,
        'SEXO_16': SEXO_16,
        'SEXO_17': SEXO_17,

        # Fecha de generación
        'DIA': numero_a_letras(float(pago.day),apocopado=False),
        'MES': meses[pago.month - 1].upper(),

        # Vendedor
        'NOMBRE_VENDEDOR': ven.nombre_completo.upper(),
        'ID_INE':          ven.ine,
        'NUMERO_VENDEDOR': ven.telefono,

        # Notario e instrumento (del propietario)
        'INSTRUMENTO_PUBLICO': prop.instrumento_publico or '',
        'NOTARIO':             prop.notario_publico or '',
        'NOMBRE_NOTARIO':      prop.nombre_notario or '',

        # Propietario
        'NOMBRE_PROPIETARIO': prop.nombre_completo.upper(),

        # Primer Cliente/Comprador
        'NOMBRE_COMPRADOR':   cli.nombre_completo.upper(),
        'DIRECCION_COMPRADOR':cli.domicilio.upper(),
        'ID_INE_COMPRADOR':    cli.numero_id,
        'LUGAR_ORIGEN':        cli.originario.upper(),
        'ESTADO_CIVIL':        cli.estado_civil.upper(),
        'TELEFONO_COMPRADOR':  cli.telefono.upper(),
        'OCUPACION_COMPRADOR': cli.ocupacion.upper(),
        'CORREO_COMPRADOR':    correo_comprador1,

        # Segundo Cliente/Comprador
        'NOMBRE_COMPRADOR_2':   cliente2.nombre_completo.upper() if cliente2 else '',
        'DIRECCION_COMPRADOR_2':cliente2.domicilio.upper() if cliente2 else '',
        'ID_INE_COMPRADOR_2':   cliente2.numero_id.upper() if cliente2 else '',
        'LUGAR_ORIGEN_2':       cliente2.originario.upper() if cliente2 else '',
        'ESTADO_CIVIL_2':       cliente2.estado_civil.upper() if cliente2 else '',
        'TELEFONO_COMPRADOR_2': cliente2.telefono.upper() if cliente2 else '',
        'OCUPACION_COMPRADOR_2':cliente2.ocupacion.upper() if cliente2 else '',
        'CORREO_COMPRADOR_2':   correo_comprador2 if cliente2 else '',

        # Lote
        'IDENTIFICADOR_LOTE':    fin.lote.identificador,
        'LETRA_IDENTIFICADOR':   obtener_letra_identificador(fin.lote),  # Cambio aquí
        'DIRECCION_PROYECTO_LOTE': fin.lote.proyecto.ubicacion.upper(),

        # Coordenadas dinámicas
        **dir_fields,

        # Financiamiento y pagos
        'PRECIO_LOTE_FINANCIAMIENTO': fmt_money(fin.precio_lote),
        'LETRA_PRECIO_LOTE':          numero_a_letras(float(fin.precio_lote)),
        'APARTADO_FINANCIAMIENTO':    fmt_money(fin.apartado),
        'LETRA_APARTADO':             numero_a_letras(float(fin.apartado)),

        'DIA_PAGO':  fecha_pago.day,
        'MES_PAGO':  meses[fecha_pago.month - 1].upper(),
        'ANIO_PAGO': fecha_pago.year,

        'CANTIDAD_PAGO_COMPLETO':  fmt_money(restante),
        'CANTIDAD_LETRA_PAGO':     restante_letra,

        # Cláusula B variable
        'CLAUSULA_B': claus_b,
    }

    # 8) Firma del cliente (para DOS clientes, usar la misma firma o implementar lógica para dos firmas)
    # (Manteniendo la misma lógica por ahora)
    if request and tpl:
        data_url = firma_data or (request.session.get('firma_cliente_data') if request else None)
        if data_url:
            header, b64 = data_url.split(',', 1)
            img_data = base64.b64decode(b64)
            fd, tmp = tempfile.mkstemp(suffix='.png')
            with os.fdopen(fd, 'wb') as f:
                f.write(img_data)
            context['FIRMA_CLIENTE'] = InlineImage(tpl, tmp, width=Mm(40))
        else:
            context['FIRMA_CLIENTE'] = ''
    else:
        context['FIRMA_CLIENTE'] = ''

    # Determinar qué cláusulas adicionales existen
    tiene_pago = clausulas_adicionales and 'pago' in clausulas_adicionales and bool(clausulas_adicionales['pago'])
    tiene_deslinde = clausulas_adicionales and 'deslinde' in clausulas_adicionales and bool(clausulas_adicionales['deslinde'])
    tiene_promesa = clausulas_adicionales and 'promesa' in clausulas_adicionales and bool(clausulas_adicionales['promesa'])
    
    # Formatear cláusulas adicionales
    clausula_pago = clausulas_adicionales['pago'] if tiene_pago else ''
    clausula_deslinde = clausulas_adicionales['deslinde'] if tiene_deslinde else ''
    clausula_promesa = clausulas_adicionales['promesa'] if tiene_promesa else ''
    
    # Agregar al contexto
    context.update({
        'CLAUSULA_PAGO': clausula_pago.upper(),
        'CLAUSULA_DESLINDE': clausula_deslinde.upper(),
        'CLAUSULA_PROMESA': clausula_promesa.upper(),
    })

    return context

def build_contrato_propiedad_pagos_context(fin, cli, ven, request=None, tpl=None, firma_data=None, clausulas_adicionales=None):

    print("Entré al build de pequeña propiedad a pagos")

    if clausulas_adicionales is None:
        clausulas_adicionales = {}

    # 1) Pronombres
    def art(sex, masculino, femenino):
        return masculino if sex == 'M' else femenino
    #prop = fin.lote.proyecto.propietario

    # SEXO_1: EL/LA VENDEDOR
    SEXO_1 = art(ven.sexo, 'EL', 'LA')
    # SEXO_2: VENDEDOR/VENDEDORA
    SEXO_2 = art(ven.sexo, 'VENDEDOR', 'VENDEDORA')
    # SEXO_3: EL/LA COMPRADOR
    SEXO_3 = art(cli.sexo, 'EL', 'LA')
    # SEXO_4: COMPRADOR/COMPRADORA
    SEXO_4 = art(cli.sexo, 'COMPRADOR', 'COMPRADORA')
    # SEXO_5: A/O 
    SEXO_5 = art(cli.sexo, 'O', 'A')
    # SEXO_6: EL/LA PROPIETARIO/A
    prop = fin.lote.proyecto.propietario.first()
    SEXO_6 = art(prop.sexo, 'EL', 'LA')
    # SEXO_7: A LA / AL
    SEXO_7 = art(ven.sexo, 'AL "', 'A "LA ')
    # SEXO_8: DEL / DE LA
    SEXO_8 = art(ven.sexo, 'DEL "', 'DE "LA ')
    SEXO_9 = art(ven.sexo, 'O', 'A')

    SEXO_16 = art(ven.sexo, 'ÉSTE', 'ÉSTA')
    SEXO_17 = art(cli.sexo, 'ÉSTE', 'ÉSTA')
    SEXO_18 = art(cli.sexo, 'DEL "', 'DE "LA ')
    SEXO_19 = art(cli.sexo, 'AL "', 'A "LA ')
    SEXO_20 = art(prop.sexo, 'EL', 'LA')

    # 2) Fecha actual
    hoy   = date.today()
    meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
    DIA, MES = numero_a_letras(float(hoy.day),apocopado=False), meses[hoy.month-1].upper()

    coords = {}
    for lado in ('norte','sur','este','oeste'):
        raw = getattr(fin.lote, lado, '')
        m, c = _parse_coord(raw)
        coords[f'NUMERO_METROS_{lado.upper()}'] = m
        coords[f'COLINDANCIA_LOTE_{lado.upper()}'] = c

    fecha_posesion = fin.lote.proyecto.fecha_emision_documento
    fecha_contrato = fin.lote.proyecto.fecha_emision_contrato
    autoridad = fin.lote.proyecto.autoridad

    email1 = (cli.email or '')        # convierte None -> ''
    email1 = email1.strip()            # quita espacios en blanco
    if email1:
        correo_comprador1 = email1.upper()
    else:
        correo_comprador1 = 'NO PROPORCIONADO'

    # 3) Miembro B dinámico según relación:
    # — Si ven es propietario:
    if ven.ine == prop.ine and prop.tipo == 'propietario':
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, "
            f"QUE ACREDITA CON EL CONTRATO PRIVADO DE COMPRAVENTA Y CONSTANCIA DE POSESIÓN DE FECHA {fecha_posesion} "
            f"EXPEDIDA POR LOS INTEGRANTES {autoridad}"
        )
    # — Si ven es apoderado:
    elif ven.ine == prop.ine and prop.tipo == 'apoderado':
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, AL IGUAL QUE, CON LAS "
            f"FACULTADES Y AUTORIZACIÓN SUFICIENTE PARA OBLIGARSE EN LOS TÉRMINOS DE ESTE, TAL COMO SE ACREDITA CON EL INSTRUMENTO PÚBLICO "
            f"{fin.instrumento_publico} OTORGADO ANTE LA FE DEL NOTARIO PÚBLICO "
            f"{fin.notario_publico} DE OAXACA, EL LICENCIADO {fin.nombre_notario.upper()}."
            f"C. ESTAR LEGITIMADO PARA REALIZAR TODOS AQUELLOS ACTOS SOBRE LA PROPIEDAD, CONFORME AL PODER DESCRITO EN LA DECLARACIÓN ANTERIOR."
        )
    # — Si es vendedor autorizado:
    else:
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, AL IGUAL QUE CON LAS FACULTADES Y AUTORIZACIÓN SUFICIENTE PARA OBLIGARSE EN LOS TÉRMINOS DE ESTE, "
            f"TAL COMO SE ACREDITA EN EL CONTRATO DE EXCLUSIVIDAD, PROMOCIÓN Y COMISIÓN POR LA VENTA DEL BIEN INMUEBLE DE FECHA {fecha_contrato}"
            f"OTORGADO POR {SEXO_20}  C. {prop.nombre_completo.upper()}"
        )

    # 4) Enganche y mensualidades
    eng_dia = fin.fecha_enganche.day if fin.fecha_enganche else ''
    eng_mes = meses[fin.fecha_enganche.month-1].upper() if fin.fecha_enganche else ''
    eng_anio= fin.fecha_enganche.year if fin.fecha_enganche else ''
    cant_eng  = fin.enganche or 0
    letra_eng = numero_a_letras(float(cant_eng))
    num_men   = fin.num_mensualidades
    fija      = fin.monto_mensualidad or 0
    letra_fija= numero_a_letras(float(fija))
    final     = fin.monto_pago_final or 0
    letra_fin = numero_a_letras(float(final))

    # 5) Context base
    context = {
        # Pronombres
        'SEXO_1': SEXO_1, 'SEXO_2': SEXO_2, 'SEXO_3': SEXO_3,
        'SEXO_4': SEXO_4, 'SEXO_5': SEXO_5, 'SEXO_6': SEXO_6,
        'SEXO_7': SEXO_7, 'SEXO_8': SEXO_8, 'SEXO_9': SEXO_9,
        'SEXO_16': SEXO_16,'SEXO_17': SEXO_17, 'SEXO_18': SEXO_18, 'SEXO_19': SEXO_19,

        # Fecha
        'DIA': DIA, 'MES': MES,

        # Vendedor
        'NOMBRE_VENDEDOR': ven.nombre_completo.upper(),
        'ID_INE':          ven.ine,
        'NUMERO_VENDEDOR': ven.telefono,

        # Notario/Propietario
        'INSTRUMENTO_PUBLICO': prop.instrumento_publico or '',
        'NOTARIO':             prop.notario_publico or '',
        'NOMBRE_NOTARIO':      prop.nombre_notario or '',
        'NOMBRE_PROPIETARIO':  prop.nombre_completo.upper(),

        # Comprador
        'NOMBRE_COMPRADOR':    cli.nombre_completo.upper(),
        'DIRECCION_COMPRADOR': cli.domicilio.upper(),
        'ID_INE_COMPRADOR':    cli.numero_id.upper(),
        'LUGAR_ORIGEN':        cli.originario.upper(),
        'ESTADO_CIVIL':        cli.estado_civil.upper(),
        'TELEFONO_COMPRADOR':  cli.telefono.upper(),
        'OCUPACION_COMPRADOR': cli.ocupacion.upper(),
        'CORREO_COMPRADOR':    correo_comprador1,

        # Lote
        'IDENTIFICADOR_LOTE':      fin.lote.identificador,
        'LETRA_IDENTIFICADOR':     obtener_letra_identificador(fin.lote),  # Cambio aquí
        'DIRECCION_PROYECTO_LOTE': fin.lote.proyecto.ubicacion.upper(),

        # Coordenadas
        **coords,

        # Financiamiento
        'PRECIO_LOTE_FINANCIAMIENTO': fmt_money(fin.precio_lote),
        'LETRA_PRECIO_LOTE':          numero_a_letras(float(fin.precio_lote)),
        'APARTADO_FINANCIAMIENTO':    fmt_money(fin.apartado),
        'LETRA_APARTADO':             numero_a_letras(float(fin.apartado)),

        # Enganche y mensualidades
        'DIA_ENGANCHE':                   eng_dia,
        'MES_ENGANCHE':                   eng_mes,
        'ANIO_ENGANCHE':                  eng_anio,
        'CANTIDAD_ENGANCHE_FINANCIAMIENTO': fmt_money(cant_eng),
        'LETRA_ENGANCHE':                   letra_eng,

        'MENSUALIADES_FINANCIAMIENTO':     num_men,
        'MENSUALIDADES': num_men-1,
        'MENSUALIDADES_FIJAS':             num_men-1,
        'CANTIDAD_MENSUALIDAD_FIJA':       fmt_money(fija),
        'LETRA_MENSUALIDAD_FIJA':          letra_fija,

        'CANTIDAD_MENSUALIDAD_FINAL':      fmt_money(final),
        'LETRA_MENSUALIDAD_FINAL':         letra_fin,
        # Y la cláusula B variable:
        'CLAUSULA_B': claus_b,
    }

    # 6) Firma del cliente
    if request and tpl:
        data_url = firma_data or (request.session.get('firma_cliente_data') if request else None)
        if data_url:
            header, b64 = data_url.split(',', 1)
            img_data = base64.b64decode(b64)
            fd, tmp = tempfile.mkstemp(suffix='.png')
            with os.fdopen(fd, 'wb') as f:
                f.write(img_data)
            # Inserta la imagen de firma
            context['FIRMA_CLIENTE'] = InlineImage(tpl, tmp, width=Mm(40))
        else:
            context['FIRMA_CLIENTE'] = ''
    else:
        context['FIRMA_CLIENTE'] = ''

    # Determinar qué cláusulas adicionales existen
    tiene_pago = clausulas_adicionales and 'pago' in clausulas_adicionales and bool(clausulas_adicionales['pago'])
    tiene_deslinde = clausulas_adicionales and 'deslinde' in clausulas_adicionales and bool(clausulas_adicionales['deslinde'])
    tiene_promesa = clausulas_adicionales and 'promesa' in clausulas_adicionales and bool(clausulas_adicionales['promesa'])
    
    # Formatear cláusulas adicionales
    clausula_pago = clausulas_adicionales['pago'] if tiene_pago else ''
    clausula_deslinde = clausulas_adicionales['deslinde'] if tiene_deslinde else ''
    clausula_promesa = clausulas_adicionales['promesa'] if tiene_promesa else ''
    
    # Agregar al contexto
    context.update({
        'CLAUSULA_PAGO': clausula_pago.upper(),
        'CLAUSULA_DESLINDE': clausula_deslinde.upper(),
        'CLAUSULA_PROMESA': clausula_promesa.upper(),
    })

    return context

def build_contrato_propiedad_pagos_varios_context(fin, cli, ven, cliente2=None, request=None, tpl=None, firma_data=None, clausulas_adicionales=None):

    print("Entré al build de pequeña propiedad para DOS COMPRADORES a pagos")

    if clausulas_adicionales is None:
        clausulas_adicionales = {}

    # 1) Pronombres y formas según sexo para SINGULARES (igual que antes)
    def art(sex, masculino, femenino):
        return masculino if sex == 'M' else femenino

    SEXO_1 = art(ven.sexo, 'EL', 'LA')
    SEXO_2 = art(ven.sexo, 'VENDEDOR', 'VENDEDORA')
    SEXO_3 = art(cli.sexo, 'EL', 'LA')
    SEXO_4 = art(cli.sexo, 'COMPRADOR', 'COMPRADORA')
    SEXO_5 = art(cli.sexo, 'O', 'A')
    prop = fin.lote.proyecto.propietario.first()
    SEXO_6 = art(prop.sexo, 'EL', 'LA')
    SEXO_7 = art(ven.sexo, 'AL "', 'A "LA ')
    SEXO_8 = art(ven.sexo, 'DEL "', 'DE "LA ')
    SEXO_14 = art(ven.sexo, 'O', 'A')
    SEXO_15 = art(ven.sexo, 'DEL "', 'DE "LA ')
    SEXO_16 = art(ven.sexo, 'ÉSTE', 'ÉSTA')
    SEXO_20 = art(prop.sexo, 'EL', 'LA')

    # 2) Pronombres PLURALES para DOS COMPRADORES
    # Determinar género predominante para plurales
    if cliente2:
        if cli.sexo == 'M' or cliente2.sexo == 'M':
            # Si al menos uno es masculino -> masculino plural
            SEXO_9 = 'LOS'
            SEXO_10 = 'COMPRADORES'
            SEXO_11 = 'O'
            SEXO_12 = 'A "LOS '
            SEXO_13 = 'DE "LOS '
            SEXO_17 = 'ÉSTOS'
        else:
            # Ambos femeninos -> femenino plural
            SEXO_9 = 'LAS'
            SEXO_10 = 'COMPRADORAS'
            SEXO_11 = 'A'
            SEXO_12 = 'A "LAS '
            SEXO_13 = 'DE "LAS '
            SEXO_17 = 'ÉSTAS'
    else:
        # Por si acaso (aunque esta función es para varios)
        SEXO_9 = 'LOS'
        SEXO_10 = 'COMPRADORES'
        SEXO_11 = 'O'
        SEXO_12 = 'A "LOS '
        SEXO_13 = 'DE "LOS '
        SEXO_17 = 'ÉSTOS'


    # 2) Fecha actual
    hoy   = date.today()
    meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
    DIA, MES = numero_a_letras(float(hoy.day),apocopado=False), meses[hoy.month-1].upper()

    email1 = (cli.email or '')        # convierte None -> ''
    email1 = email1.strip()            # quita espacios en blanco
    if email1:
        correo_comprador1 = email1.upper()
    else:
        correo_comprador1 = 'NO PROPORCIONADO'

    email2 = (cliente2.email or '')        # convierte None -> ''
    email2 = email2.strip()            # quita espacios en blanco
    if email2:
        correo_comprador2 = email2.upper()
    else:
        correo_comprador2 = 'NO PROPORCIONADO'

    # 4) Coordenadas por cada lado (igual que antes)
    dir_fields = {}
    for dir_name in ('norte','sur','este','oeste'):
        raw = getattr(fin.lote, dir_name, '')
        metros, col = _parse_coord(raw)
        key_m = f'NUMERO_METROS_{dir_name.upper()}'
        key_c = f'COLINDANCIA_LOTE_{dir_name.upper()}'
        dir_fields[key_m] = metros
        dir_fields[key_c] = col

    # 5) Cálculo pago restante (igual que antes)
    restante = float(fin.precio_lote) - float(fin.apartado)
    restante_letra = numero_a_letras(restante)

    fecha_posesion = fin.lote.proyecto.fecha_emision_documento
    fecha_contrato = fin.lote.proyecto.fecha_emision_contrato
    autoridad = fin.lote.proyecto.autoridad

    # 6) Miembro B dinámico según relación (igual que antes)
    if ven.ine == prop.ine and prop.tipo == 'propietario':
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, "
            f"QUE ACREDITA CON EL CONTRATO PRIVADO DE COMPRAVENTA Y CONSTANCIA DE POSESIÓN DE FECHA {fecha_posesion} "
            f"EXPEDIDA POR LOS INTEGRANTES {autoridad}"
        )
    elif ven.ine == prop.ine and prop.tipo == 'apoderado':
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, AL IGUAL QUE, CON LAS "
            f"FACULTADES Y AUTORIZACIÓN SUFICIENTE PARA OBLIGARSE EN LOS TÉRMINOS DE ESTE, TAL COMO SE ACREDITA CON EL INSTRUMENTO PÚBLICO "
            f"{fin.instrumento_publico} OTORGADO ANTE LA FE DEL NOTARIO PÚBLICO "
            f"{fin.notario_publico} DE OAXACA, EL LICENCIADO {fin.nombre_notario.upper()}."
            f"C. ESTAR LEGITIMADO PARA REALIZAR TODOS AQUELLOS ACTOS SOBRE LA PROPIEDAD, CONFORME AL PODER DESCRITO EN LA DECLARACIÓN ANTERIOR."
        )
    else:
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, AL IGUAL QUE CON LAS FACULTADES Y AUTORIZACIÓN SUFICIENTE PARA OBLIGARSE EN LOS TÉRMINOS DE ESTE, "
            f"TAL COMO SE ACREDITA EN EL CONTRATO DE EXCLUSIVIDAD, PROMOCIÓN Y COMISIÓN POR LA VENTA DEL BIEN INMUEBLE DE FECHA {fecha_contrato} "
            f"OTORGADO POR {SEXO_20}  C. {prop.nombre_completo.upper()}"
        )

    # 4) Enganche y mensualidades
    eng_dia = fin.fecha_enganche.day if fin.fecha_enganche else ''
    eng_mes = meses[fin.fecha_enganche.month-1].upper() if fin.fecha_enganche else ''
    eng_anio= fin.fecha_enganche.year if fin.fecha_enganche else ''
    cant_eng  = fin.enganche or 0
    letra_eng = numero_a_letras(float(cant_eng))
    num_men   = fin.num_mensualidades
    fija      = fin.monto_mensualidad or 0
    letra_fija= numero_a_letras(float(fija))
    final     = fin.monto_pago_final or 0
    letra_fin = numero_a_letras(float(final))

    # 7) Construcción del context - con datos de AMBOS clientes
    context = {
        # Pronombres SINGULARES
        'SEXO_1': SEXO_1,
        'SEXO_2': SEXO_2,
        'SEXO_3': SEXO_3,
        'SEXO_4': SEXO_4,
        'SEXO_5': SEXO_5,
        'SEXO_6': SEXO_6,
        'SEXO_7': SEXO_7,
        'SEXO_8': SEXO_8,
        # Pronombres PLURALES
        'SEXO_9': SEXO_9,
        'SEXO_10': SEXO_10,
        'SEXO_11': SEXO_11,
        'SEXO_12': SEXO_12,
        'SEXO_13': SEXO_13,
        'SEXO_14': SEXO_14,
        'SEXO_15': SEXO_15,
        'SEXO_16': SEXO_16,
        'SEXO_17': SEXO_17,

        # Fecha
        'DIA': DIA, 'MES': MES,

        # Vendedor
        'NOMBRE_VENDEDOR': ven.nombre_completo.upper(),
        'ID_INE':          ven.ine,
        'NUMERO_VENDEDOR': ven.telefono,

        # Notario e instrumento (del propietario)
        'INSTRUMENTO_PUBLICO': prop.instrumento_publico or '',
        'NOTARIO':             prop.notario_publico or '',
        'NOMBRE_NOTARIO':      prop.nombre_notario or '',

        # Propietario
        'NOMBRE_PROPIETARIO': prop.nombre_completo.upper(),

        # Primer Cliente/Comprador
        'NOMBRE_COMPRADOR':   cli.nombre_completo.upper(),
        'DIRECCION_COMPRADOR':cli.domicilio.upper(),
        'ID_INE_COMPRADOR':    cli.numero_id,
        'LUGAR_ORIGEN':        cli.originario.upper(),
        'ESTADO_CIVIL':        cli.estado_civil.upper(),
        'TELEFONO_COMPRADOR':  cli.telefono.upper(),
        'OCUPACION_COMPRADOR': cli.ocupacion.upper(),
        'CORREO_COMPRADOR':    correo_comprador1,

        # Segundo Cliente/Comprador
        'NOMBRE_COMPRADOR_2':   cliente2.nombre_completo.upper() if cliente2 else '',
        'DIRECCION_COMPRADOR_2':cliente2.domicilio.upper() if cliente2 else '',
        'ID_INE_COMPRADOR_2':   cliente2.numero_id if cliente2 else '',
        'LUGAR_ORIGEN_2':       cliente2.originario.upper() if cliente2 else '',
        'ESTADO_CIVIL_2':       cliente2.estado_civil.upper() if cliente2 else '',
        'TELEFONO_COMPRADOR_2': cliente2.telefono.upper() if cliente2 else '',
        'OCUPACION_COMPRADOR_2':cliente2.ocupacion.upper() if cliente2 else '',
        'CORREO_COMPRADOR_2':   correo_comprador2 if cliente2 else '',

        # Lote
        'IDENTIFICADOR_LOTE':    fin.lote.identificador,
        'LETRA_IDENTIFICADOR':   obtener_letra_identificador(fin.lote),  # Cambio aquí
        'DIRECCION_PROYECTO_LOTE': fin.lote.proyecto.ubicacion.upper(),

        # Coordenadas dinámicas
        **dir_fields,

       # Financiamiento
        'PRECIO_LOTE_FINANCIAMIENTO': fmt_money(fin.precio_lote),
        'LETRA_PRECIO_LOTE':          numero_a_letras(float(fin.precio_lote)),
        'APARTADO_FINANCIAMIENTO':    fmt_money(fin.apartado),
        'LETRA_APARTADO':             numero_a_letras(float(fin.apartado)),

        # Enganche y mensualidades
        'DIA_ENGANCHE':                   eng_dia,
        'MES_ENGANCHE':                   eng_mes,
        'ANIO_ENGANCHE':                  eng_anio,
        'CANTIDAD_ENGANCHE_FINANCIAMIENTO': fmt_money(cant_eng),
        'LETRA_ENGANCHE':                   letra_eng,

        'MENSUALIADES_FINANCIAMIENTO':     num_men,
        'MENSUALIDADES': num_men-1,
        'MENSUALIDADES_FIJAS':             f"{fija:.2f}",
        'CANTIDAD_MENSUALIDAD_FIJA':       fmt_money(fija),
        'LETRA_MENSUALIDAD_FIJA':          letra_fija,

        'CANTIDAD_MENSUALIDAD_FINAL':      fmt_money(final),
        'LETRA_MENSUALIDAD_FINAL':         letra_fin,
        # Y la cláusula B variable:
        'CLAUSULA_B': claus_b,
    }

    # 8) Firma del cliente (para DOS clientes, usar la misma firma o implementar lógica para dos firmas)
    # (Manteniendo la misma lógica por ahora)
    if request and tpl:
        data_url = firma_data or (request.session.get('firma_cliente_data') if request else None)
        if data_url:
            header, b64 = data_url.split(',', 1)
            img_data = base64.b64decode(b64)
            fd, tmp = tempfile.mkstemp(suffix='.png')
            with os.fdopen(fd, 'wb') as f:
                f.write(img_data)
            context['FIRMA_CLIENTE'] = InlineImage(tpl, tmp, width=Mm(40))
        else:
            context['FIRMA_CLIENTE'] = ''
    else:
        context['FIRMA_CLIENTE'] = ''

    # Determinar qué cláusulas adicionales existen
    tiene_pago = clausulas_adicionales and 'pago' in clausulas_adicionales and bool(clausulas_adicionales['pago'])
    tiene_deslinde = clausulas_adicionales and 'deslinde' in clausulas_adicionales and bool(clausulas_adicionales['deslinde'])
    tiene_promesa = clausulas_adicionales and 'promesa' in clausulas_adicionales and bool(clausulas_adicionales['promesa'])
    
    # Formatear cláusulas adicionales
    clausula_pago = clausulas_adicionales['pago'] if tiene_pago else ''
    clausula_deslinde = clausulas_adicionales['deslinde'] if tiene_deslinde else ''
    clausula_promesa = clausulas_adicionales['promesa'] if tiene_promesa else ''
    
    # Agregar al contexto
    context.update({
        'CLAUSULA_PAGO': clausula_pago.upper(),
        'CLAUSULA_DESLINDE': clausula_deslinde.upper(),
        'CLAUSULA_PROMESA': clausula_promesa.upper(),
    })

    return context

def build_contrato_ejidal_contado_context(fin, cli, ven, request=None, tpl=None, firma_data=None, clausulas_adicionales=None):

    print("Entré al build de ejido a contado de un comprador")

    if clausulas_adicionales is None:
        clausulas_adicionales = {}

    # 1) Pronombres según sexo (necesitarás un campo sexo en Cliente y Vendedor)
    # Asumimos cli.sexo y ven.sexo son 'M' o 'F'
    def art(sex, masculino, femenino):
        return masculino if sex == 'M' else femenino

    SEXO_1 = art(ven.sexo, 'EL', 'LA')               # cedente (vendedor)
    SEXO_2 = art(cli.sexo, 'EL', 'LA')               # cedatario (comprador)
    SEXO_3 = art(cli.sexo, 'CEDATARIO', 'CEDATARIA') # palabra completa
    SEXO_4 = art(ven.sexo, 'O', 'A')                 # letra
    # El “propietario” del lote:
    prop = fin.lote.proyecto.propietario.first()  # instancia Propietario
    SEXO_5 = art(prop.sexo, 'EL', 'LA')
    SEXO_6 = art(cli.sexo, 'DEL "', 'DE "LA ')
    SEXO_7 = art(ven.sexo, 'AL "', 'A "LA ')
    SEXO_8 = art(ven.sexo, 'DEL "', 'DE "LA ')
    SEXO_9 = art(cli.sexo, 'AL "', 'A "LA ')
    SEXO_10 = art(cli.sexo, 'O', 'A')

    # 2) Fechas
    cesion = date.today()  # o toma de fin.fecha_enganche si aplica
    pago = fin.fecha_pago_completo
    meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

    email1 = (cli.email or '')        # convierte None -> ''
    email1 = email1.strip()            # quita espacios en blanco
    if email1:
        correo_comprador1 = email1.upper()
    else:
        correo_comprador1 = 'NO PROPORCIONADO'

    # 3) Parse coordenadas
    dir_fields = {}
    for dir_name in ('norte','sur','este','oeste'):
        raw = getattr(fin.lote, dir_name, '')
        metros, col = _parse_coord(raw)
        key_m = f'NUMERO_METROS_{dir_name.upper()}'
        key_c = f'COLINDANCIA_LOTE_{dir_name.upper()}'
        dir_fields[key_m] = metros  # Ahora metros ya está formateado como string
        dir_fields[key_c] = col

    # 4) Cálculo pago restante
    restante = float(fin.precio_lote) - float(fin.apartado)
    restante_letra = numero_a_letras(restante)

    fecha_posesion = fin.lote.proyecto.fecha_emision_documento
    fecha_contrato = fin.lote.proyecto.fecha_emision_contrato
    autoridad = fin.lote.proyecto.autoridad

    # 3) Miembro B dinámico según relación:
    # — Si ven es propietario:
    if ven.ine == prop.ine and prop.tipo == 'propietario':
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, "
            f"QUE ACREDITA CON LA CESIÓN DE DERECHOS DE FECHA {fecha_posesion}"
            f", EXPEDIDA POR LOS INTEGRANTES {autoridad}"
        )
    # — Si ven es apoderado:
    elif ven.ine == prop.ine and prop.tipo == 'apoderado':
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, AL IGUAL QUE, CON LAS "
            f"FACULTADES Y AUTORIZACIÓN SUFICIENTE PARA OBLIGARSE EN LOS TÉRMINOS DE ESTE, TAL COMO SE ACREDITA CON EL INSTRUMENTO PÚBLICO "
            f"{fin.instrumento_publico} OTORGADO ANTE LA FE DEL NOTARIO PÚBLICO "
            f"{fin.notario_publico} DE OAXACA, EL LICENCIADO {fin.nombre_notario.upper()}."
            f"C. ESTAR LEGITIMADO PARA REALIZAR TODOS AQUELLOS ACTOS SOBRE LA PROPIEDAD, CONFORME AL PODER DESCRITO EN LA DECLARACIÓN ANTERIOR."
        )
    # — Si es vendedor autorizado:
    else:
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, AL IGUAL QUE CON LAS FACULTADES Y AUTORIZACIÓN SUFICIENTE PARA OBLIGARSE EN LOS TÉRMINOS DE ESTE, "
            f"TAL COMO SE ACREDITA EN EL CONTRATO DE EXCLUSIVIDAD, PROMOCIÓN Y COMISIÓN POR LA VENTA DEL BIEN INMUEBLE DE FECHA {fecha_contrato}"
            f", OTORGADO POR {SEXO_5} C. {prop.nombre_completo.upper()}."
        )

    # 4) Construcción del context completo
    context = {
        'SEXO_1': SEXO_1,
        'SEXO_2': SEXO_2,
        'SEXO_3': SEXO_3,
        'SEXO_4': SEXO_4,
        'SEXO_5': SEXO_5,
        'SEXO_6': SEXO_6,
        'SEXO_7': SEXO_7,
        'SEXO_8': SEXO_8,
        'SEXO_9': SEXO_9,
        'SEXO_10': SEXO_10,

        'NOMBRE_VENDEDOR':    ven.nombre_completo.upper(),
        'NOMBRE_COMPRADOR':   cli.nombre_completo.upper(),

        'DIRECCION_LOTE':     fin.lote.proyecto.ubicacion.upper(),
        'IDENTIFICADOR_LOTE': fin.lote.identificador.upper(),
        'LETRA_IDENTIFICADOR': obtener_letra_identificador(fin.lote),  # Cambio aquí

        'NOMBRE_CESION': autoridad,
        'FECHA_DOCUMENTO': fecha_posesion,
        'DIA_CESION': numero_a_letras(float(cesion.day),apocopado=False),
        'MES_CESION': meses[cesion.month-1].upper(),

        'ID_INE':            ven.ine,
        'INSTRUMENTO_PUBLICO': prop.instrumento_publico or '',
        'NOTARIO':           prop.notario_publico or '',
        'NOMBRE_NOTARIO':    prop.nombre_notario or '',

        'DIRECCION_COMPRADOR': cli.domicilio.upper(),
        'ID_INE_COMPRADOR':    cli.numero_id,
        'LUGAR_ORIGEN':        cli.originario.upper(),
        'ESTADO_CIVIL':        cli.estado_civil.upper(),
        'TELEFONO_COMPRADOR':  cli.telefono.upper(),
        'OCUPACION_COMPRADOR': cli.ocupacion.upper(),
        'CORREO_COMPRADOR':    correo_comprador1,

        # incluir los pares metros/colindancia:
        **dir_fields,

        'PRECIO_LOTE_FINANCIAMIENTO': fmt_money(fin.precio_lote),
        'LETRA_PRECIO_LOTE':          numero_a_letras(float(fin.precio_lote)),
        'APARTADO_FINANCIAMIENTO':    fmt_money(fin.apartado),
        'LETRA_APARTADO':             numero_a_letras(float(fin.apartado)),

        'DIA_PAGO':  pago.day,
        'MES_PAGO':  meses[pago.month - 1].upper(),
        'ANIO_PAGO': pago.year,

        'CANTIDAD_PAGO_COMPLETO':  fmt_money(restante),
        'CANTIDAD_LETRA_PAGO':     restante_letra,

        # Y la cláusula B variable:
        'CLAUSULA_B': claus_b,
    }

    # 5) Firma del cliente (igual que en carta)
    if request and tpl:
        data_url = firma_data or (request.session.get('firma_cliente_data') if request else None)
        if data_url:
            header, b64 = data_url.split(',', 1)
            img_data = base64.b64decode(b64)
            fd, tmp = tempfile.mkstemp(suffix='.png')
            with os.fdopen(fd, 'wb') as f:
                f.write(img_data)
            # Inserta la imagen de firma
            context['FIRMA_CLIENTE'] = InlineImage(tpl, tmp, width=Mm(40))
        else:
            context['FIRMA_CLIENTE'] = ''
    else:
        context['FIRMA_CLIENTE'] = ''
    

    # Determinar qué cláusulas adicionales existen
    tiene_pago = clausulas_adicionales and 'pago' in clausulas_adicionales and bool(clausulas_adicionales['pago'])
    tiene_deslinde = clausulas_adicionales and 'deslinde' in clausulas_adicionales and bool(clausulas_adicionales['deslinde'])
    tiene_promesa = clausulas_adicionales and 'promesa' in clausulas_adicionales and bool(clausulas_adicionales['promesa'])
    
    # Formatear cláusulas adicionales
    clausula_pago = clausulas_adicionales['pago'] if tiene_pago else ''
    clausula_deslinde = clausulas_adicionales['deslinde'] if tiene_deslinde else ''
    clausula_promesa = clausulas_adicionales['promesa'] if tiene_promesa else ''
    
    # Agregar al contexto
    context.update({
        'CLAUSULA_PAGO': clausula_pago.upper(),
        'CLAUSULA_DESLINDE': clausula_deslinde.upper(),
        'CLAUSULA_PROMESA': clausula_promesa.upper(),
    })

    return context

def build_contrato_ejidal_contado_varios_context(fin, cli, ven, cliente2=None, request=None, tpl=None, firma_data=None, clausulas_adicionales=None):
    
    print("Entré al build de ejido a contado de varios compradores")

    if clausulas_adicionales is None:
        clausulas_adicionales = {}

    # 1) Pronombres según sexo (necesitarás un campo sexo en Cliente y Vendedor)
    # Asumimos cli.sexo y ven.sexo son 'M' o 'F'
    def art(sex, masculino, femenino):
        return masculino if sex == 'M' else femenino

    SEXO_1 = art(ven.sexo, 'EL', 'LA')               # cedente (vendedor)
    SEXO_4 = art(ven.sexo, 'O', 'A')                 # letra
    # El “propietario” del lote:
    prop = fin.lote.proyecto.propietario.first()  # instancia Propietario
    SEXO_5 = art(prop.sexo, 'EL', 'LA')
    SEXO_7 = art(ven.sexo, 'AL "', 'A "LA ')
    SEXO_8 = art(ven.sexo, 'DEL "', 'DE "LA ')

    if cliente2:
        if cli.sexo == 'M' or cliente2.sexo == 'M':
            # Si al menos uno es masculino -> masculino plural
            
            SEXO_2 = 'LOS'               # cedatario (comprador)
            SEXO_3 = 'CEDATARIOS' # palabra completa
            SEXO_6 = 'DE "LOS '
            SEXO_9 = 'A "LOS '
            SEXO_10 = 'O'
        else:
            # Ambos femeninos -> femenino plural
            SEXO_2 = 'LAS'               # cedatario (comprador)
            SEXO_3 = 'CEDATARIAS' # palabra completa
            SEXO_6 = 'DE "LAS '
            SEXO_9 = 'A "LAS '
            SEXO_10 = 'A'
    else:
        # Por si acaso (aunque esta función es para varios)
        SEXO_2 = 'LOS'               # cedatario (comprador)
        SEXO_3 = 'CEDATARIOS' # palabra completa
        SEXO_6 = 'DE "LOS '
        SEXO_9 = 'A "LOS '
        SEXO_10 = 'O'

    # 2) Fechas
    cesion = date.today()  # o toma de fin.fecha_enganche si aplica
    pago = fin.fecha_pago_completo
    meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

    email1 = (cli.email or '')        # convierte None -> ''
    email1 = email1.strip()            # quita espacios en blanco
    if email1:
        correo_comprador1 = email1.upper()
    else:
        correo_comprador1 = 'NO PROPORCIONADO'

    email2 = (cliente2.email or '')        # convierte None -> ''
    email2 = email2.strip()            # quita espacios en blanco
    if email2:
        correo_comprador2 = email2.upper()
    else:
        correo_comprador2 = 'NO PROPORCIONADO'

    # 3) Parse coordenadas
    dir_fields = {}
    for dir_name in ('norte','sur','este','oeste'):
        raw = getattr(fin.lote, dir_name, '')
        metros, col = _parse_coord(raw)
        key_m = f'NUMERO_METROS_{dir_name.upper()}'
        key_c = f'COLINDANCIA_LOTE_{dir_name.upper()}'
        dir_fields[key_m] = metros
        dir_fields[key_c] = col

    # 4) Cálculo pago restante
    restante = float(fin.precio_lote) - float(fin.apartado)
    restante_letra = numero_a_letras(restante)

    fecha_posesion = fin.lote.proyecto.fecha_emision_documento
    fecha_contrato = fin.lote.proyecto.fecha_emision_contrato
    autoridad = fin.lote.proyecto.autoridad

    # 3) Miembro B dinámico según relación:
    # — Si ven es propietario:
    if ven.ine == prop.ine and prop.tipo == 'propietario':
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, "
            f"QUE ACREDITA CON LA CESIÓN DE DERECHOS DE FECHA {fecha_posesion}"
            f", EXPEDIDA POR LOS INTEGRANTES {autoridad}"
        )
    # — Si ven es apoderado:
    elif ven.ine == prop.ine and prop.tipo == 'apoderado':
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, AL IGUAL QUE, CON LAS "
            f"FACULTADES Y AUTORIZACIÓN SUFICIENTE PARA OBLIGARSE EN LOS TÉRMINOS DE ESTE, TAL COMO SE ACREDITA CON EL INSTRUMENTO PÚBLICO "
            f"{fin.instrumento_publico} OTORGADO ANTE LA FE DEL NOTARIO PÚBLICO "
            f"{fin.notario_publico} DE OAXACA, EL LICENCIADO {fin.nombre_notario.upper()}."
            f"C. ESTAR LEGITIMADO PARA REALIZAR TODOS AQUELLOS ACTOS SOBRE LA PROPIEDAD, CONFORME AL PODER DESCRITO EN LA DECLARACIÓN ANTERIOR."
        )
    # — Si es vendedor autorizado:
    else:
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, AL IGUAL QUE CON LAS FACULTADES Y AUTORIZACIÓN SUFICIENTE PARA OBLIGARSE EN LOS TÉRMINOS DE ESTE, "
            f"TAL COMO SE ACREDITA EN EL CONTRATO DE EXCLUSIVIDAD, PROMOCIÓN Y COMISIÓN POR LA VENTA DEL BIEN INMUEBLE DE FECHA {fecha_contrato}"
            f", OTORGADO POR {SEXO_5} C. {prop.nombre_completo.upper()}."
        )

    # 4) Construcción del context completo
    context = {
        'SEXO_1': SEXO_1,
        'SEXO_2': SEXO_2,
        'SEXO_3': SEXO_3,
        'SEXO_4': SEXO_4,
        'SEXO_5': SEXO_5,
        'SEXO_6': SEXO_6,
        'SEXO_7': SEXO_7,
        'SEXO_8': SEXO_8,
        'SEXO_9': SEXO_9,
        'SEXO_10': SEXO_10,

        'NOMBRE_VENDEDOR':    ven.nombre_completo.upper(),
        'NOMBRE_COMPRADOR':   cli.nombre_completo.upper(),

        'DIRECCION_LOTE':     fin.lote.proyecto.ubicacion.upper(),
        'IDENTIFICADOR_LOTE': fin.lote.identificador.upper(),
        'LETRA_IDENTIFICADOR': obtener_letra_identificador(fin.lote),  # Cambio aquí

        'NOMBRE_CESION': autoridad,
        'FECHA_DOCUMENTO': fecha_posesion,
        'DIA_CESION': numero_a_letras(float(cesion.day),apocopado=False),
        'MES_CESION': meses[cesion.month-1].upper(),

        'ID_INE':            ven.ine,
        'INSTRUMENTO_PUBLICO': prop.instrumento_publico or '',
        'NOTARIO':           prop.notario_publico or '',
        'NOMBRE_NOTARIO':    prop.nombre_notario or '',

        'DIRECCION_COMPRADOR': cli.domicilio.upper(),
        'ID_INE_COMPRADOR':    cli.numero_id,
        'LUGAR_ORIGEN':        cli.originario.upper(),
        'ESTADO_CIVIL':        cli.estado_civil.upper(),
        'TELEFONO_COMPRADOR':  cli.telefono.upper(),
        'OCUPACION_COMPRADOR': cli.ocupacion.upper(),
        'CORREO_COMPRADOR':    correo_comprador1,

        # Segundo Cliente/Comprador
        'NOMBRE_COMPRADOR_2':   cliente2.nombre_completo.upper() if cliente2 else '',
        'DIRECCION_COMPRADOR_2':cliente2.domicilio.upper() if cliente2 else '',
        'ID_INE_COMPRADOR_2':   cliente2.numero_id.upper() if cliente2 else '',
        'LUGAR_ORIGEN_2':       cliente2.originario.upper() if cliente2 else '',
        'ESTADO_CIVIL_2':       cliente2.estado_civil.upper() if cliente2 else '',
        'TELEFONO_COMPRADOR_2': cliente2.telefono.upper() if cliente2 else '',
        'OCUPACION_COMPRADOR_2':cliente2.ocupacion.upper() if cliente2 else '',
        'CORREO_COMPRADOR_2':   correo_comprador2 if cliente2 else '',

        # incluir los pares metros/colindancia:
        **dir_fields,

        'PRECIO_LOTE_FINANCIAMIENTO': fmt_money(fin.precio_lote),
        'LETRA_PRECIO_LOTE':          numero_a_letras(float(fin.precio_lote)),
        'APARTADO_FINANCIAMIENTO':    fmt_money(fin.apartado),
        'LETRA_APARTADO':             numero_a_letras(float(fin.apartado)),

        'DIA_PAGO':  pago.day,
        'MES_PAGO':  meses[pago.month - 1].upper(),
        'ANIO_PAGO': pago.year,

        'CANTIDAD_PAGO_COMPLETO':  f"{restante:.2f}",
        'CANTIDAD_LETRA_PAGO':     restante_letra,

        # Y la cláusula B variable:
        'CLAUSULA_B': claus_b,
    }

    # 5) Firma del cliente (igual que en carta)
    if request and tpl:
        data_url = firma_data or (request.session.get('firma_cliente_data') if request else None)
        if data_url:
            header, b64 = data_url.split(',', 1)
            img_data = base64.b64decode(b64)
            fd, tmp = tempfile.mkstemp(suffix='.png')
            with os.fdopen(fd, 'wb') as f:
                f.write(img_data)
            # Inserta la imagen de firma
            context['FIRMA_CLIENTE'] = InlineImage(tpl, tmp, width=Mm(40))
        else:
            context['FIRMA_CLIENTE'] = ''
    else:
        context['FIRMA_CLIENTE'] = ''
    

    # Determinar qué cláusulas adicionales existen
    tiene_pago = clausulas_adicionales and 'pago' in clausulas_adicionales and bool(clausulas_adicionales['pago'])
    tiene_deslinde = clausulas_adicionales and 'deslinde' in clausulas_adicionales and bool(clausulas_adicionales['deslinde'])
    tiene_promesa = clausulas_adicionales and 'promesa' in clausulas_adicionales and bool(clausulas_adicionales['promesa'])
    
    # Formatear cláusulas adicionales
    clausula_pago = clausulas_adicionales['pago'] if tiene_pago else ''
    clausula_deslinde = clausulas_adicionales['deslinde'] if tiene_deslinde else ''
    clausula_promesa = clausulas_adicionales['promesa'] if tiene_promesa else ''
    
    # Agregar al contexto
    context.update({
        'CLAUSULA_PAGO': clausula_pago.upper(),
        'CLAUSULA_DESLINDE': clausula_deslinde.upper(),
        'CLAUSULA_PROMESA': clausula_promesa.upper(),
    })

    return context

def build_contrato_ejidal_pagos_context(fin, cli, ven, request=None, tpl=None, firma_data=None, clausulas_adicionales=None):

    print("Entré al build de ejido a pagos de un comprador")

    if clausulas_adicionales is None:
        clausulas_adicionales = {}


    # 1) Pronombres según sexo (necesitarás un campo sexo en Cliente y Vendedor)
    # Asumimos cli.sexo y ven.sexo son 'M' o 'F'
    def art(sex, masculino, femenino):
        return masculino if sex == 'M' else femenino

    SEXO_1 = art(ven.sexo, 'EL', 'LA')               # cedente (vendedor)
    SEXO_2 = art(cli.sexo, 'EL', 'LA')               # cedatario (comprador)
    SEXO_3 = art(cli.sexo, 'CEDATARIO', 'CEDATARIA') # palabra completa
    SEXO_4 = art(ven.sexo, 'O', 'A')                 # letra
    # El “propietario” del lote:
    prop = fin.lote.proyecto.propietario.first()  # instancia Propietario
    SEXO_5 = art(prop.sexo, 'EL', 'LA')
    SEXO_6 = art(cli.sexo, 'DEL "', 'DE "LA ')
    SEXO_7 = art(ven.sexo, 'AL "', 'A "LA ')
    SEXO_8 = art(ven.sexo, 'DEL "', 'DE "LA ')
    SEXO_9 = art(cli.sexo, 'AL "', 'A "LA ')
    SEXO_10 = art(cli.sexo, 'O', 'A')

    # 2) Fecha de cesión (hoy, o fin.fecha_enganche)
    cesion = date.today()
    meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
    DIA_CESION = numero_a_letras(float(cesion.day),apocopado=False)
    MES_CESION = meses[cesion.month-1].upper()

    # 3) Coordenadas (igual)
    def _parse_coord(text):
        try:
            medios, cola = text.split('|',1)
            m = float(medios.strip().split()[0])
            c = cola.strip()
        except:
            try: m = float(text.split()[0])
            except: m=0.0
            c=''
        return m, c

    coords = {}
    for lado in ('norte','sur','este','oeste'):
        raw = getattr(fin.lote, lado, '')
        m, c = _parse_coord(raw)
        coords[f'NUMERO_METROS_{lado.upper()}'] = m
        coords[f'COLINDANCIA_LOTE_{lado.upper()}'] = c

    # 4) Esquema de pagos
    eng_dia = fin.fecha_enganche.day if fin.fecha_enganche else ''
    eng_mes = meses[fin.fecha_enganche.month-1].upper() if fin.fecha_enganche else ''
    eng_anio= fin.fecha_enganche.year if fin.fecha_enganche else ''
    cant_eng = fin.enganche
    letra_eng = numero_a_letras(float(cant_eng)) if cant_eng else ''

    num_men = fin.num_mensualidades
    monto_fija = fin.monto_mensualidad or 0
    letra_fija = numero_a_letras(float(monto_fija))
    monto_final = fin.monto_pago_final or 0
    letra_final = numero_a_letras(float(monto_final))

    fecha_posesion = fin.lote.proyecto.fecha_emision_documento
    fecha_contrato = fin.lote.proyecto.fecha_emision_contrato
    autoridad = fin.lote.proyecto.autoridad

    email1 = (cli.email or '')        # convierte None -> ''
    email1 = email1.strip()            # quita espacios en blanco
    if email1:
        correo_comprador1 = email1.upper()
    else:
        correo_comprador1 = 'NO PROPORCIONADO'

    # 3) Miembro B dinámico según relación:
    # — Si ven es propietario:
    if ven.ine == prop.ine and prop.tipo == 'propietario':
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, "
            f"QUE ACREDITA CON LA CESIÓN DE DERECHOS DE FECHA {fecha_posesion}"
            f", EXPEDIDA POR LOS INTEGRANTES {autoridad}"
        )
    # — Si ven es apoderado:
    elif ven.ine == prop.ine and prop.tipo == 'apoderado':
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, AL IGUAL QUE, CON LAS "
            f"FACULTADES Y AUTORIZACIÓN SUFICIENTE PARA OBLIGARSE EN LOS TÉRMINOS DE ESTE, TAL COMO SE ACREDITA CON EL INSTRUMENTO PÚBLICO "
            f"{fin.instrumento_publico} OTORGADO ANTE LA FE DEL NOTARIO PÚBLICO "
            f"{fin.notario_publico} DE OAXACA, EL LICENCIADO {fin.nombre_notario.upper()}."
            f"C. ESTAR LEGITIMADO PARA REALIZAR TODOS AQUELLOS ACTOS SOBRE LA PROPIEDAD, CONFORME AL PODER DESCRITO EN LA DECLARACIÓN ANTERIOR."
        )
    # — Si es vendedor autorizado:
    else:
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, AL IGUAL QUE CON LAS FACULTADES Y AUTORIZACIÓN SUFICIENTE PARA OBLIGARSE EN LOS TÉRMINOS DE ESTE, "
            f"TAL COMO SE ACREDITA EN EL CONTRATO DE EXCLUSIVIDAD, PROMOCIÓN Y COMISIÓN POR LA VENTA DEL BIEN INMUEBLE DE FECHA {fecha_contrato}"
            f", OTORGADO POR {SEXO_5} C. {prop.nombre_completo.upper()}."
        )

    # 5) Construcción del context
    context = {
        'DIA' : DIA_CESION,
        'MES' : MES_CESION,
        'SEXO_1': SEXO_1,
        'SEXO_2': SEXO_2,
        'SEXO_3': SEXO_3,
        'SEXO_4': SEXO_4,
        'SEXO_5': SEXO_5,
        'SEXO_6': SEXO_6,
        'SEXO_7': SEXO_7,
        'SEXO_8': SEXO_8,
        'SEXO_9': SEXO_9,
        'SEXO_10': SEXO_10,

        'NOMBRE_VENDEDOR':    ven.nombre_completo.upper(),
        'NOMBRE_COMPRADOR':   cli.nombre_completo.upper(),

        'DIRECCION_LOTE':     fin.lote.proyecto.ubicacion.upper(),
        'IDENTIFICADOR_LOTE': fin.lote.identificador,
        'LETRA_IDENTIFICADOR': obtener_letra_identificador(fin.lote),  # Cambio aquí

        'DIA_CESION':  DIA_CESION,
        'MES_CESION':  MES_CESION,

        'ID_INE':             prop.ine,
        'INSTRUMENTO_PUBLICO':prop.instrumento_publico or '',
        'NOTARIO':            prop.notario_publico or '',
        'NOMBRE_NOTARIO':     prop.nombre_notario or '',

        'DIRECCION_COMPRADOR':cli.domicilio.upper(),
        'ID_INE_COMPRADOR':   cli.numero_id,
        'LUGAR_ORIGEN':       cli.originario.upper(),
        'ESTADO_CIVIL':       cli.estado_civil.upper(),
        'TELEFONO_COMPRADOR': cli.telefono,
        'OCUPACION_COMPRADOR':cli.ocupacion.upper(),
        'CORREO_COMPRADOR':   correo_comprador1,

        **coords,

        'PRECIO_LOTE_FINANCIAMIENTO': fmt_money(fin.precio_lote),
        'LETRA_PRECIO_LOTE':          numero_a_letras(float(fin.precio_lote)),
        'APARTADO_FINANCIAMIENTO':    fmt_money(fin.apartado),
        'LETRA_APARTADO':             numero_a_letras(float(fin.apartado)),

        'DIA_ENGANCHE':               eng_dia,
        'MES_ENGANCHE':               eng_mes,
        'ANIO_ENGANCHE':              eng_anio,
        'CANTIDAD_ENGANCHE_FINANCIAMIENTO': fmt_money(cant_eng),
        'LETRA_ENGANCHE':                  letra_eng,

        'MENSUALIADES_FINANCIAMIENTO':     num_men,
        'MENSUALIDADES': num_men-1,
        'MENSUALIDADES_FIJAS':             num_men-1,
        'CANTIDAD_MENSUALIDAD_FIJA':       fmt_money(monto_fija),
        'LETRA_MENSUALIDAD_FIJA':          letra_fija,

        'CANTIDAD_MENSUALIDAD_FINAL':      fmt_money(monto_final),
        'LETRA_MENSUALIDAD_FINAL':         letra_final,

        'CLAUSULA_B': claus_b,
    }

    # 6) Firma
    if request and tpl:
        data_url = firma_data or (request.session.get('firma_cliente_data') if request else None)
        if data_url:
            header, b64 = data_url.split(',', 1)
            img_data = base64.b64decode(b64)
            fd, tmp = tempfile.mkstemp(suffix='.png')
            with os.fdopen(fd, 'wb') as f:
                f.write(img_data)
            # Inserta la imagen de firma
            context['FIRMA_CLIENTE'] = InlineImage(tpl, tmp, width=Mm(40))
        else:
            context['FIRMA_CLIENTE'] = ''
    else:
        context['FIRMA_CLIENTE'] = ''

    # Determinar qué cláusulas adicionales existen
    tiene_pago = clausulas_adicionales and 'pago' in clausulas_adicionales and bool(clausulas_adicionales['pago'])
    tiene_deslinde = clausulas_adicionales and 'deslinde' in clausulas_adicionales and bool(clausulas_adicionales['deslinde'])
    tiene_promesa = clausulas_adicionales and 'promesa' in clausulas_adicionales and bool(clausulas_adicionales['promesa'])
    
    # Formatear cláusulas adicionales
    clausula_pago = clausulas_adicionales['pago'] if tiene_pago else ''
    clausula_deslinde = clausulas_adicionales['deslinde'] if tiene_deslinde else ''
    clausula_promesa = clausulas_adicionales['promesa'] if tiene_promesa else ''
    
    # Agregar al contexto
    context.update({
        'CLAUSULA_PAGO': clausula_pago.upper(),
        'CLAUSULA_DESLINDE': clausula_deslinde.upper(),
        'CLAUSULA_PROMESA': clausula_promesa.upper(),
    })

    return context

def build_contrato_ejidal_pagos_varios_context(fin, cli, ven, cliente2=None,request=None, tpl=None, firma_data=None, clausulas_adicionales=None):

    print("Entré al build de ejido a pagos de varios compradores")

    if clausulas_adicionales is None:
        clausulas_adicionales = {}


    # 1) Pronombres según sexo (necesitarás un campo sexo en Cliente y Vendedor)
    # Asumimos cli.sexo y ven.sexo son 'M' o 'F'
    def art(sex, masculino, femenino):
        return masculino if sex == 'M' else femenino

    SEXO_1 = art(ven.sexo, 'EL', 'LA')               # cedente (vendedor)
    SEXO_4 = art(ven.sexo, 'O', 'A')                 # letra
    # El “propietario” del lote:
    prop = fin.lote.proyecto.propietario.first()  # instancia Propietario
    SEXO_5 = art(prop.sexo, 'EL', 'LA')
    SEXO_7 = art(ven.sexo, 'AL', 'A LA')
    SEXO_8 = art(ven.sexo, 'DEL', 'DE LA')

    # 2) Fecha de cesión (hoy, o fin.fecha_enganche)
    cesion = date.today()
    meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
    DIA_CESION = numero_a_letras(float(cesion.day))
    MES_CESION = meses[cesion.month-1].upper()

    # 2) Pronombres PLURALES para DOS COMPRADORES
    # Determinar género predominante para plurales
    if cliente2:
        if cli.sexo == 'M' or cliente2.sexo == 'M':
            # Si al menos uno es masculino -> masculino plural
            
            SEXO_2 = 'LOS'               # cedatario (comprador)
            SEXO_3 = 'CEDATARIOS' # palabra completa
            SEXO_6 = 'DE "LOS '
            SEXO_9 = 'A "LOS '
            SEXO_10 = 'O'
        else:
            # Ambos femeninos -> femenino plural
            SEXO_2 = 'LAS'               # cedatario (comprador)
            SEXO_3 = 'CEDATARIAS' # palabra completa
            SEXO_6 = 'DE "LAS '
            SEXO_9 = 'A "LAS '
            SEXO_10 = 'A'
    else:
        # Por si acaso (aunque esta función es para varios)
        SEXO_2 = 'LOS'               # cedatario (comprador)
        SEXO_3 = 'CEDATARIOS' # palabra completa
        SEXO_6 = 'DE "LOS '
        SEXO_9 = 'A "LOS '
        SEXO_10 = 'O'

    # 3) Coordenadas (igual)
    def _parse_coord(text):
        try:
            medios, cola = text.split('|',1)
            m = float(medios.strip().split()[0])
            c = cola.strip()
        except:
            try: m = float(text.split()[0])
            except: m=0.0
            c=''
        return m, c

    coords = {}
    for lado in ('norte','sur','este','oeste'):
        raw = getattr(fin.lote, lado, '')
        m, c = _parse_coord(raw)
        coords[f'NUMERO_METROS_{lado.upper()}'] = m
        coords[f'COLINDANCIA_LOTE_{lado.upper()}'] = c

    # 4) Esquema de pagos
    eng_dia = fin.fecha_enganche.day if fin.fecha_enganche else ''
    eng_mes = meses[fin.fecha_enganche.month-1].upper() if fin.fecha_enganche else ''
    eng_anio= fin.fecha_enganche.year if fin.fecha_enganche else ''
    cant_eng = fin.enganche
    letra_eng = numero_a_letras(float(cant_eng)) if cant_eng else ''

    num_men = fin.num_mensualidades
    monto_fija = fin.monto_mensualidad or 0
    letra_fija = numero_a_letras(float(monto_fija))
    monto_final = fin.monto_pago_final or 0
    letra_final = numero_a_letras(float(monto_final))

    fecha_posesion = fin.lote.proyecto.fecha_emision_documento
    fecha_contrato = fin.lote.proyecto.fecha_emision_contrato
    autoridad = fin.lote.proyecto.autoridad

    email1 = (cli.email or '')        # convierte None -> ''
    email1 = email1.strip()            # quita espacios en blanco
    if email1:
        correo_comprador1 = email1.upper()
    else:
        correo_comprador1 = 'NO PROPORCIONADO'

    email2 = (cliente2.email or '')        # convierte None -> ''
    email2 = email2.strip()            # quita espacios en blanco
    if email2:
        correo_comprador2 = email2.upper()
    else:
        correo_comprador2 = 'NO PROPORCIONADO'

    # 3) Miembro B dinámico según relación:
    # — Si ven es propietario:
    if ven.ine == prop.ine and prop.tipo == 'propietario':
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, "
            f"QUE ACREDITA CON LA CESIÓN DE DERECHOS DE FECHA {fecha_posesion}"
            f", EXPEDIDA POR LOS INTEGRANTES {autoridad}"
        )
    # — Si ven es apoderado:
    elif ven.ine == prop.ine and prop.tipo == 'apoderado':
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, AL IGUAL QUE, CON LAS "
            f"FACULTADES Y AUTORIZACIÓN SUFICIENTE PARA OBLIGARSE EN LOS TÉRMINOS DE ESTE, TAL COMO SE ACREDITA CON EL INSTRUMENTO PÚBLICO "
            f"{fin.instrumento_publico} OTORGADO ANTE LA FE DEL NOTARIO PÚBLICO "
            f"{fin.notario_publico} DE OAXACA, EL LICENCIADO {fin.nombre_notario.upper()}."
            f"C. ESTAR LEGITIMADO PARA REALIZAR TODOS AQUELLOS ACTOS SOBRE LA PROPIEDAD, CONFORME AL PODER DESCRITO EN LA DECLARACIÓN ANTERIOR."
        )
    # — Si es vendedor autorizado:
    else:
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, AL IGUAL QUE CON LAS FACULTADES Y AUTORIZACIÓN SUFICIENTE PARA OBLIGARSE EN LOS TÉRMINOS DE ESTE, "
            f"TAL COMO SE ACREDITA EN EL CONTRATO DE EXCLUSIVIDAD, PROMOCIÓN Y COMISIÓN POR LA VENTA DEL BIEN INMUEBLE DE FECHA {fecha_contrato}"
            f", OTORGADO POR {SEXO_5} C. {prop.nombre_completo.upper()}."
        )

    # 5) Construcción del context
    context = {
        'DIA' : DIA_CESION,
        'MES' : MES_CESION,
        'SEXO_1': SEXO_1,
        'SEXO_2': SEXO_2,
        'SEXO_3': SEXO_3,
        'SEXO_4': SEXO_4,
        'SEXO_5': SEXO_5,
        'SEXO_6': SEXO_6,
        'SEXO_7': SEXO_7,
        'SEXO_8': SEXO_8,
        'SEXO_9': SEXO_9,
        'SEXO_10': SEXO_10,

        'NOMBRE_VENDEDOR':    ven.nombre_completo.upper(),
        'NOMBRE_COMPRADOR':   cli.nombre_completo.upper(),

        'DIRECCION_LOTE':     fin.lote.proyecto.ubicacion.upper(),
        'IDENTIFICADOR_LOTE': fin.lote.identificador,
        'LETRA_IDENTIFICADOR': obtener_letra_identificador(fin.lote),  # Cambio aquí

        'DIA_CESION':  DIA_CESION,
        'MES_CESION':  MES_CESION,

        'ID_INE':             prop.ine,
        'INSTRUMENTO_PUBLICO':prop.instrumento_publico or '',
        'NOTARIO':            prop.notario_publico or '',
        'NOMBRE_NOTARIO':     prop.nombre_notario or '',

        'DIRECCION_COMPRADOR':cli.domicilio.upper(),
        'ID_INE_COMPRADOR':   cli.numero_id,
        'LUGAR_ORIGEN':       cli.originario.upper(),
        'ESTADO_CIVIL':       cli.estado_civil.upper(),
        'TELEFONO_COMPRADOR': cli.telefono,
        'OCUPACION_COMPRADOR':cli.ocupacion.upper(),
        'CORREO_COMPRADOR':   correo_comprador1,

        # Segundo Cliente/Comprador
        'NOMBRE_COMPRADOR_2':   cliente2.nombre_completo.upper() if cliente2 else '',
        'DIRECCION_COMPRADOR_2':cliente2.domicilio.upper() if cliente2 else '',
        'ID_INE_COMPRADOR_2':   cliente2.numero_id.upper() if cliente2 else '',
        'LUGAR_ORIGEN_2':       cliente2.originario.upper() if cliente2 else '',
        'ESTADO_CIVIL_2':       cliente2.estado_civil.upper() if cliente2 else '',
        'TELEFONO_COMPRADOR_2': cliente2.telefono.upper() if cliente2 else '',
        'OCUPACION_COMPRADOR_2':cliente2.ocupacion.upper() if cliente2 else '',
        'CORREO_COMPRADOR_2':   correo_comprador2 if cliente2 else '',


        **coords,

        'PRECIO_LOTE_FINANCIAMIENTO': fmt_money(fin.precio_lote),
        'LETRA_PRECIO_LOTE':          numero_a_letras(float(fin.precio_lote)),
        'APARTADO_FINANCIAMIENTO':    fmt_money(fin.apartado),
        'LETRA_APARTADO':             numero_a_letras(float(fin.apartado)),

        'DIA_ENGANCHE':               eng_dia,
        'MES_ENGANCHE':               eng_mes,
        'ANIO_ENGANCHE':              eng_anio,
        'CANTIDAD_ENGANCHE_FINANCIAMIENTO': fmt_money(cant_eng),
        'LETRA_ENGANCHE':                  letra_eng,

        'MENSUALIADES_FINANCIAMIENTO':     num_men,
        'MENSUALIDADES': num_men-1,
        'MENSUALIDADES_FIJAS':             num_men-1,
        'CANTIDAD_MENSUALIDAD_FIJA':       fmt_money(monto_fija),
        'LETRA_MENSUALIDAD_FIJA':          letra_fija,

        'CANTIDAD_MENSUALIDAD_FINAL':      fmt_money(monto_final),
        'LETRA_MENSUALIDAD_FINAL':         letra_final,

        'CLAUSULA_B': claus_b,
    }

    # 6) Firma
    if request and tpl:
        data_url = firma_data or (request.session.get('firma_cliente_data') if request else None)
        if data_url:
            header, b64 = data_url.split(',', 1)
            img_data = base64.b64decode(b64)
            fd, tmp = tempfile.mkstemp(suffix='.png')
            with os.fdopen(fd, 'wb') as f:
                f.write(img_data)
            # Inserta la imagen de firma
            context['FIRMA_CLIENTE'] = InlineImage(tpl, tmp, width=Mm(40))
        else:
            context['FIRMA_CLIENTE'] = ''
    else:
        context['FIRMA_CLIENTE'] = ''

    # Determinar qué cláusulas adicionales existen
    tiene_pago = clausulas_adicionales and 'pago' in clausulas_adicionales and bool(clausulas_adicionales['pago'])
    tiene_deslinde = clausulas_adicionales and 'deslinde' in clausulas_adicionales and bool(clausulas_adicionales['deslinde'])
    tiene_promesa = clausulas_adicionales and 'promesa' in clausulas_adicionales and bool(clausulas_adicionales['promesa'])
    
    # Formatear cláusulas adicionales
    clausula_pago = clausulas_adicionales['pago'] if tiene_pago else ''
    clausula_deslinde = clausulas_adicionales['deslinde'] if tiene_deslinde else ''
    clausula_promesa = clausulas_adicionales['promesa'] if tiene_promesa else ''
    
    # Agregar al contexto
    context.update({
        'CLAUSULA_PAGO': clausula_pago.upper(),
        'CLAUSULA_DESLINDE': clausula_deslinde.upper(),
        'CLAUSULA_PROMESA': clausula_promesa.upper(),
    })
    
    return context

def build_contrato_canario_contado_context(fin, cli, ven, request=None, tpl=None, firma_data=None, clausulas_adicionales=None):

    print("Entré al build de casa canario a contado de un comprador")

    if clausulas_adicionales is None:
        clausulas_adicionales = {}

    # 1) Pronombres y formas según sexo
    def art(sex, masculino, femenino):
        return masculino if sex == 'M' else femenino

    # SEXO_1: EL/LA VENDEDOR
    SEXO_1 = art(ven.sexo, 'EL', 'LA')
    # SEXO_2: VENDEDOR/VENDEDORA
    SEXO_2 = art(ven.sexo, 'VENDEDOR', 'VENDEDORA')
    # SEXO_3: EL/LA COMPRADOR
    SEXO_3 = art(cli.sexo, 'EL', 'LA')
    # SEXO_4: COMPRADOR/COMPRADORA
    SEXO_4 = art(cli.sexo, 'COMPRADOR', 'COMPRADORA')
    # SEXO_5: A/O 
    SEXO_5 = art(cli.sexo, 'O', 'A')
    # SEXO_6: EL/LA PROPIETARIO/A
    prop = fin.lote.proyecto.propietario.first()
    SEXO_6 = art(prop.sexo, 'EL', 'LA')
    # SEXO_7: A LA / AL (con espacio)
    SEXO_7 = art(ven.sexo, 'AL "', 'A "LA ')
    # SEXO_8: DEL / DE LA (con espacio)
    SEXO_8 = art(ven.sexo, 'DEL "', 'DE "LA ')
    SEXO_9 = art(ven.sexo, 'O', 'A')

    SEXO_16 = art(ven.sexo, 'ÉSTE', 'ÉSTA')
    SEXO_17 = art(cli.sexo, 'ÉSTE', 'ÉSTA')
    # SEXO_18: DEL / DE LA (con espacio) para comprador
    SEXO_18 = art(cli.sexo, 'DEL "', 'DE "LA ')
    # SEXO_19: AL / A LA (con espacio) para comprador
    SEXO_19 = art(cli.sexo, 'AL "', 'A "LA ')

    # 2) Fecha de pago completo (hoy)
    pago = fin.fecha_pago_completo
    meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

    # 3) Coordenadas por cada lado (aunque no se usen en contado, se calculan por si acaso)
    dir_fields = {}
    for dir_name in ('norte','sur','este','oeste'):
        raw = getattr(fin.lote, dir_name, '')
        metros, col = _parse_coord(raw)
        key_m = f'NUMERO_METROS_{dir_name.upper()}'
        key_c = f'COLINDANCIA_LOTE_{dir_name.upper()}'
        dir_fields[key_m] = metros  # Ahora metros ya está formateado como string
        dir_fields[key_c] = col

    # 4) Cálculo pago restante
    restante = float(fin.precio_lote) - float(fin.apartado)
    restante_letra = numero_a_letras(restante)
    dia_actual = date.today()
    email = (cli.email or '')        # convierte None -> ''
    email = email.strip()            # quita espacios en blanco
    if email:
        correo_comprador = email.upper()
    else:
        correo_comprador = 'NO PROPORCIONADO'

    # 3) Miembro B dinámico según relación:
    # — Si ven es propietario:
    if ven.ine == prop.ine and prop.tipo == 'propietario':
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, "
            f"QUE ACREDITA CON EL CONTRATO PRIVADO DE COMPRAVENTA Y CONSTANCIA DE POSESIÓN DE FECHA VEINTITRÉS DE OCTUBRE DE DOS MIL VEINTICUATRO "
            f"EXPEDIDA POR LOS INTEGRANTES DEL ALCALDE ÚNICO CONSTITUCIONAL DE SAN ANTONIO DE LA CAL, OAXACA"
        )
    # — Si es vendedor autorizado:
    else:
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, AL IGUAL QUE CON LAS FACULTADES Y AUTORIZACIÓN SUFICIENTE PARA OBLIGARSE EN LOS TÉRMINOS DE ESTE, "
            f"TAL COMO SE ACREDITA EN EL CONTRATO DE EXCLUSIVIDAD, PROMOCIÓN Y COMISIÓN POR LA VENTA DEL BIEN INMUEBLE DE FECHA SEIS DE ENERO DE DOS MIL VEINTICINCO "
            f"OTORGADO POR EL C. JORGE EMILIO ALAVEZ AGUILAR."
        )

    # 5) Construcción del context
    context = {
        # Pronombres
        'SEXO_1': SEXO_1,
        'SEXO_2': SEXO_2,
        'SEXO_3': SEXO_3,
        'SEXO_4': SEXO_4,
        'SEXO_5': SEXO_5,
        'SEXO_6': SEXO_6,
        'SEXO_7': SEXO_7,
        'SEXO_8': SEXO_8,
        'SEXO_9': SEXO_9,
        'SEXO_16': SEXO_16,
        'SEXO_17': SEXO_17,
        'SEXO_18': SEXO_18,
        'SEXO_19': SEXO_19,

        # Fecha de generación
        'DIA': numero_a_letras(float(dia_actual.day),apocopado=False),
        'MES': meses[dia_actual.month - 1].upper(),

        # Vendedor
        'NOMBRE_VENDEDOR': ven.nombre_completo.upper(),
        'ID_INE':          ven.ine,
        'NUMERO_VENDEDOR': ven.telefono,

        # Notario e instrumento (del propietario)
        'INSTRUMENTO_PUBLICO': prop.instrumento_publico or '',
        'NOTARIO':             prop.notario_publico or '',
        'NOMBRE_NOTARIO':      prop.nombre_notario or '',

        # Propietario
        'NOMBRE_PROPIETARIO': prop.nombre_completo.upper(),

        # Cliente/Comprador
        'NOMBRE_COMPRADOR':   cli.nombre_completo.upper(),
        'DIRECCION_COMPRADOR':cli.domicilio.upper(),
        'ID_INE_COMPRADOR':    cli.numero_id.upper(),
        'LUGAR_ORIGEN':        cli.originario.upper(),
        'ESTADO_CIVIL':        cli.estado_civil.upper(),
        'TELEFONO_COMPRADOR':  cli.telefono.upper(),
        'OCUPACION_COMPRADOR': cli.ocupacion.upper(),
        'CORREO_COMPRADOR': correo_comprador,

        # Coordenadas dinámicas (aunque no se usen en contado)
        **dir_fields,

        # Financiamiento y pagos
        'PRECIO_LOTE_FINANCIAMIENTO': fmt_money(fin.precio_lote),
        'LETRA_PRECIO_LOTE':          numero_a_letras(float(fin.precio_lote)),
        'APARTADO_FINANCIAMIENTO':    fmt_money(fin.apartado),
        'LETRA_APARTADO':             numero_a_letras(float(fin.apartado)),

        'DIA_PAGO':  pago.day,
        'MES_PAGO':  meses[pago.month - 1].upper(),
        'ANIO_PAGO': pago.year,

        'CANTIDAD_PAGO_COMPLETO':  fmt_money(restante),
        'CANTIDAD_LETRA_PAGO':     restante_letra,

        # Y la cláusula B variable:
        'CLAUSULA_B': claus_b,
    }

    # 6) Firma del cliente
    if request and tpl:
        data_url = firma_data or (request.session.get('firma_cliente_data') if request else None)
        if data_url:
            header, b64 = data_url.split(',', 1)
            img_data = base64.b64decode(b64)
            fd, tmp = tempfile.mkstemp(suffix='.png')
            with os.fdopen(fd, 'wb') as f:
                f.write(img_data)
            # Inserta la imagen de firma
            context['FIRMA_CLIENTE'] = InlineImage(tpl, tmp, width=Mm(40))
        else:
            context['FIRMA_CLIENTE'] = ''
    else:
        context['FIRMA_CLIENTE'] = ''

    # Determinar qué cláusulas adicionales existen
    tiene_pago = clausulas_adicionales and 'pago' in clausulas_adicionales and bool(clausulas_adicionales['pago'])
    tiene_deslinde = clausulas_adicionales and 'deslinde' in clausulas_adicionales and bool(clausulas_adicionales['deslinde'])
    tiene_promesa = clausulas_adicionales and 'promesa' in clausulas_adicionales and bool(clausulas_adicionales['promesa'])
    
    # Formatear cláusulas adicionales
    clausula_pago = clausulas_adicionales['pago'] if tiene_pago else ''
    clausula_deslinde = clausulas_adicionales['deslinde'] if tiene_deslinde else ''
    clausula_promesa = clausulas_adicionales['promesa'] if tiene_promesa else ''
    
    # Agregar al contexto
    context.update({
        'CLAUSULA_PAGO': clausula_pago.upper(),
        'CLAUSULA_DESLINDE': clausula_deslinde.upper(),
        'CLAUSULA_PROMESA': clausula_promesa.upper(),
    })

    return context

def build_contrato_canario_contado_varios_context(fin, cli, ven, cliente2=None, request=None, tpl=None, firma_data=None, clausulas_adicionales=None):
    
    print("Entré al build de casa canario para DOS COMPRADORES")

    if clausulas_adicionales is None:
        clausulas_adicionales = {}

    # 1) Pronombres y formas según sexo para SINGULARES (igual que antes)
    def art(sex, masculino, femenino):
        return masculino if sex == 'M' else femenino

    SEXO_1 = art(ven.sexo, 'EL', 'LA')
    SEXO_2 = art(ven.sexo, 'VENDEDOR', 'VENDEDORA')
    SEXO_4 = art(cli.sexo, 'COMPRADOR', 'COMPRADORA')
    SEXO_15 = art(ven.sexo, 'DEL "', 'DE "LA ')
    
    # 2) Pronombres PLURALES para DOS COMPRADORES
    # Determinar género predominante para plurales
    if cliente2:
        if cli.sexo == 'M' or cliente2.sexo == 'M':
            # Si al menos uno es masculino -> masculino plural
            SEXO_9 = 'LOS'
            SEXO_10 = 'COMPRADORES'
            SEXO_11 = 'O'  # Para originario(s)
            SEXO_12 = 'A "LOS '
            SEXO_13 = 'DE "LOS '
        else:
            # Ambos femeninos -> femenino plural
            SEXO_9 = 'LAS'
            SEXO_10 = 'COMPRADORAS'
            SEXO_11 = 'A'  # Para originaria(s)
            SEXO_12 = 'A "LAS '
            SEXO_13 = 'DE "LAS '
    else:
        # Por si acaso (aunque esta función es para varios)
        SEXO_9 = 'LOS'
        SEXO_10 = 'COMPRADORES'
        SEXO_11 = 'O'
        SEXO_12 = 'A "LOS '
        SEXO_13 = 'DE "LOS '

    # Para el vendedor (singular)
    SEXO_7 = art(ven.sexo, 'AL "', 'A "LA ')  # Con espacio al final
    SEXO_8 = art(ven.sexo, 'DEL "', 'DE "LA ')  # Con espacio al final
    SEXO_14 = art(ven.sexo, 'O', 'A')

    prop = fin.lote.proyecto.propietario.first()

    # 3) Fecha de pago completo (hoy)
    pago = date.today()
    meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

    # 4) Coordenadas por cada lado (igual que antes)
    dir_fields = {}
    for dir_name in ('norte','sur','este','oeste'):
        raw = getattr(fin.lote, dir_name, '')
        metros, col = _parse_coord(raw)
        key_m = f'NUMERO_METROS_{dir_name.upper()}'
        key_c = f'COLINDANCIA_LOTE_{dir_name.upper()}'
        dir_fields[key_m] = metros  # Ahora metros ya está formateado como string
        dir_fields[key_c] = col

    # 5) Cálculo pago restante (igual que antes)
    restante = float(fin.precio_lote) - float(fin.apartado)
    restante_letra = numero_a_letras(restante)

    email1 = (cli.email or '')        # convierte None -> ''
    email1 = email1.strip()            # quita espacios en blanco
    if email1:
        correo_comprador1 = email1.upper()
    else:
        correo_comprador1 = 'NO PROPORCIONADO'

    email2 = (cliente2.email or '') if cliente2 else ''        # convierte None -> ''
    email2 = email2.strip()            # quita espacios en blanco
    if email2:
        correo_comprador2 = email2.upper()
    else:
        correo_comprador2 = 'NO PROPORCIONADO' if cliente2 else ''

    # 6) Miembro B dinámico según relación (igual que antes)
    if ven.ine == prop.ine and prop.tipo == 'propietario':
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, "
            f"QUE ACREDITA CON EL CONTRATO PRIVADO DE COMPRAVENTA Y CONSTANCIA DE POSESIÓN DE FECHA VEINTITRÉS DE OCTUBRE DE DOS MIL VEINTICUATRO "
            f"EXPEDIDA POR LOS INTEGRANTES DEL ALCALDE ÚNICO CONSTITUCIONAL DE SAN ANTONIO DE LA CAL, OAXACA"
        )
    # — Si es vendedor autorizado:
    else:
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, AL IGUAL QUE CON LAS FACULTADES Y AUTORIZACIÓN SUFICIENTE PARA OBLIGARSE EN LOS TÉRMINOS DE ESTE, "
            f"TAL COMO SE ACREDITA EN EL CONTRATO DE EXCLUSIVIDAD, PROMOCIÓN Y COMISIÓN POR LA VENTA DEL BIEN INMUEBLE DE FECHA SEIS DE ENERO DE DOS MIL VEINTICINCO "
            f"OTORGADO POR EL C. JORGE EMILIO ALAVEZ AGUILAR."
        )
    
    fecha_pago = fin.fecha_pago_completo
    
    # 7) Construcción del context - con datos de AMBOS clientes
    context = {
        # Pronombres SINGULARES para vendedor
        'SEXO_1': SEXO_1,
        'SEXO_2': SEXO_2,
        'SEXO_4': SEXO_4,
        'SEXO_9': SEXO_9,  # Para vendedor en declaración
        
        # Pronombres PLURALES para compradores
        'SEXO_10': SEXO_10,
        'SEXO_11': SEXO_11,
        'SEXO_12': SEXO_12,
        'SEXO_13': SEXO_13,
        'SEXO_14': SEXO_14,
        
        # Pronombres para referencias al vendedor
        'SEXO_7': SEXO_7,
        'SEXO_8': SEXO_8,
        'SEXO_15': SEXO_15,

        # Fecha de generación
        'DIA': numero_a_letras(float(pago.day), apocopado=False),
        'MES': meses[pago.month - 1].upper(),

        # Vendedor
        'NOMBRE_VENDEDOR': ven.nombre_completo.upper(),
        'ID_INE': ven.ine,
        'NUMERO_VENDEDOR': ven.telefono,

        # Primer Cliente/Comprador
        'NOMBRE_COMPRADOR': cli.nombre_completo.upper(),
        'DIRECCION_COMPRADOR': cli.domicilio.upper(),
        'ID_INE_COMPRADOR': cli.numero_id,
        'LUGAR_ORIGEN': cli.originario.upper(),
        'ESTADO_CIVIL': cli.estado_civil.upper(),
        'TELEFONO_COMPRADOR': cli.telefono.upper(),
        'OCUPACION_COMPRADOR': cli.ocupacion.upper(),
        'CORREO_COMPRADOR': correo_comprador1,

        # Segundo Cliente/Comprador
        'NOMBRE_COMPRADOR_2': cliente2.nombre_completo.upper() if cliente2 else '',
        'DIRECCION_COMPRADOR_2': cliente2.domicilio.upper() if cliente2 else '',
        'ID_INE_COMPRADOR_2': cliente2.numero_id if cliente2 else '',
        'LUGAR_ORIGEN_2': cliente2.originario.upper() if cliente2 else '',
        'ESTADO_CIVIL_2': cliente2.estado_civil.upper() if cliente2 else '',
        'TELEFONO_COMPRADOR_2': cliente2.telefono.upper() if cliente2 else '',
        'OCUPACION_COMPRADOR_2': cliente2.ocupacion.upper() if cliente2 else '',
        'CORREO_COMPRADOR_2': correo_comprador2,

        # Financiamiento y pagos
        'PRECIO_LOTE_FINANCIAMIENTO': fmt_money(fin.precio_lote),
        'LETRA_PRECIO_LOTE': numero_a_letras(float(fin.precio_lote)),
        'APARTADO_FINANCIAMIENTO': fmt_money(fin.apartado),
        'LETRA_APARTADO': numero_a_letras(float(fin.apartado)),

        'DIA_PAGO': fecha_pago.day,
        'MES_PAGO': meses[fecha_pago.month - 1].upper(),
        'ANIO_PAGO': fecha_pago.year,

        'CANTIDAD_PAGO_COMPLETO': fmt_money(restante),
        'CANTIDAD_LETRA_PAGO': restante_letra,

        # Cláusula B variable
        'CLAUSULA_B': claus_b,
    }

    # 8) Firma del cliente
    if request and tpl:
        data_url = firma_data or (request.session.get('firma_cliente_data') if request else None)
        if data_url:
            header, b64 = data_url.split(',', 1)
            img_data = base64.b64decode(b64)
            fd, tmp = tempfile.mkstemp(suffix='.png')
            with os.fdopen(fd, 'wb') as f:
                f.write(img_data)
            context['FIRMA_CLIENTE'] = InlineImage(tpl, tmp, width=Mm(40))
        else:
            context['FIRMA_CLIENTE'] = ''
    else:
        context['FIRMA_CLIENTE'] = ''

    # 9) Cláusulas adicionales
    # Determinar qué cláusulas adicionales existen
    tiene_pago = clausulas_adicionales and 'pago' in clausulas_adicionales and bool(clausulas_adicionales['pago'])
    tiene_deslinde = clausulas_adicionales and 'deslinde' in clausulas_adicionales and bool(clausulas_adicionales['deslinde'])
    tiene_promesa = clausulas_adicionales and 'promesa' in clausulas_adicionales and bool(clausulas_adicionales['promesa'])
    
    # Formatear cláusulas adicionales
    clausula_pago = clausulas_adicionales['pago'] if tiene_pago else ''
    clausula_deslinde = clausulas_adicionales['deslinde'] if tiene_deslinde else ''
    clausula_promesa = clausulas_adicionales['promesa'] if tiene_promesa else ''
    
    # Agregar al contexto
    context.update({
        'CLAUSULA_PAGO': clausula_pago.upper(),
        'CLAUSULA_DESLINDE': clausula_deslinde.upper(),
        'CLAUSULA_PROMESA': clausula_promesa.upper(),
    })

    return context

def build_contrato_canario_pagos_context(fin, cli, ven, request=None, tpl=None, firma_data=None, clausulas_adicionales=None):

    print("Entré al build de casa canario a pagos")

    if clausulas_adicionales is None:
        clausulas_adicionales = {}

    # 1) Pronombres
    def art(sex, masculino, femenino):
        return masculino if sex == 'M' else femenino
    #prop = fin.lote.proyecto.propietario

    # SEXO_1: EL/LA VENDEDOR
    SEXO_1 = art(ven.sexo, 'EL', 'LA')
    # SEXO_2: VENDEDOR/VENDEDORA
    SEXO_2 = art(ven.sexo, 'VENDEDOR', 'VENDEDORA')
    # SEXO_3: EL/LA COMPRADOR
    SEXO_3 = art(cli.sexo, 'EL', 'LA')
    # SEXO_4: COMPRADOR/COMPRADORA
    SEXO_4 = art(cli.sexo, 'COMPRADOR', 'COMPRADORA')
    # SEXO_5: A/O 
    SEXO_5 = art(cli.sexo, 'O', 'A')
    # SEXO_6: EL/LA PROPIETARIO/A
    prop = fin.lote.proyecto.propietario.first()
    SEXO_6 = art(prop.sexo, 'EL', 'LA')
    # SEXO_7: A LA / AL
    SEXO_7 = art(ven.sexo, 'AL "', 'A "LA ')
    # SEXO_8: DEL / DE LA
    SEXO_8 = art(ven.sexo, 'DEL "', 'DE "LA ')
    SEXO_9 = art(ven.sexo, 'O', 'A')

    SEXO_16 = art(ven.sexo, 'ÉSTE', 'ÉSTA')
    SEXO_17 = art(cli.sexo, 'ÉSTE', 'ÉSTA')
    SEXO_18 = art(cli.sexo, 'DEL "', 'DE "LA ')
    SEXO_19 = art(cli.sexo, 'AL "', 'A "LA ')

    # 2) Fecha actual
    hoy   = date.today()
    meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
    DIA, MES = numero_a_letras(float(hoy.day),apocopado=False), meses[hoy.month-1].upper()

    coords = {}
    for lado in ('norte','sur','este','oeste'):
        raw = getattr(fin.lote, lado, '')
        m, c = _parse_coord(raw)
        coords[f'NUMERO_METROS_{lado.upper()}'] = m
        coords[f'COLINDANCIA_LOTE_{lado.upper()}'] = c

    email1 = (cli.email or '')        # convierte None -> ''
    email1 = email1.strip()            # quita espacios en blanco
    if email1:
        correo_comprador1 = email1.upper()
    else:
        correo_comprador1 = 'NO PROPORCIONADO'

    # 3) Miembro B dinámico según relación:
    # — Si ven es propietario:
    if ven.ine == prop.ine and prop.tipo == 'propietario':
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, "
            f"QUE ACREDITA CON EL CONTRATO PRIVADO DE COMPRAVENTA Y CONSTANCIA DE POSESIÓN DE FECHA VEINTITRÉS DE OCTUBRE DE DOS MIL VEINTICUATRO "
            f"EXPEDIDA POR LOS INTEGRANTES DEL ALCALDE ÚNICO CONSTITUCIONAL DE SAN ANTONIO DE LA CAL, OAXACA"
        )
    # — Si es vendedor autorizado:
    else:
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, AL IGUAL QUE CON LAS FACULTADES Y AUTORIZACIÓN SUFICIENTE PARA OBLIGARSE EN LOS TÉRMINOS DE ESTE, "
            f"TAL COMO SE ACREDITA EN EL CONTRATO DE EXCLUSIVIDAD, PROMOCIÓN Y COMISIÓN POR LA VENTA DEL BIEN INMUEBLE DE FECHA SEIS DE ENERO DE DOS MIL VEINTICINCO "
            f"OTORGADO POR EL C. JORGE EMILIO ALAVEZ AGUILAR."
        )

    # 4) Enganche y mensualidades
    eng_dia = fin.fecha_enganche.day if fin.fecha_enganche else ''
    eng_mes = meses[fin.fecha_enganche.month-1].upper() if fin.fecha_enganche else ''
    eng_anio= fin.fecha_enganche.year if fin.fecha_enganche else ''
    cant_eng  = fin.enganche or 0
    letra_eng = numero_a_letras(float(cant_eng))
    num_men   = fin.num_mensualidades
    fija      = fin.monto_mensualidad or 0
    letra_fija= numero_a_letras(float(fija))
    final     = fin.monto_pago_final or 0
    letra_fin = numero_a_letras(float(final))

    # 5) Context base
    context = {
        # Pronombres
        'SEXO_1': SEXO_1, 'SEXO_2': SEXO_2, 'SEXO_3': SEXO_3,
        'SEXO_4': SEXO_4, 'SEXO_5': SEXO_5, 'SEXO_6': SEXO_6,
        'SEXO_7': SEXO_7, 'SEXO_8': SEXO_8, 'SEXO_9': SEXO_9,
        'SEXO_16': SEXO_16,'SEXO_17': SEXO_17, 'SEXO_18': SEXO_18, 'SEXO_19': SEXO_19,

        # Fecha
        'DIA': DIA, 'MES': MES,

        # Vendedor
        'NOMBRE_VENDEDOR': ven.nombre_completo.upper(),
        'ID_INE':          ven.ine,
        'NUMERO_VENDEDOR': ven.telefono,

        # Comprador
        'NOMBRE_COMPRADOR':    cli.nombre_completo.upper(),
        'DIRECCION_COMPRADOR': cli.domicilio.upper(),
        'ID_INE_COMPRADOR':    cli.numero_id.upper(),
        'LUGAR_ORIGEN':        cli.originario.upper(),
        'ESTADO_CIVIL':        cli.estado_civil.upper(),
        'TELEFONO_COMPRADOR':  cli.telefono.upper(),
        'OCUPACION_COMPRADOR': cli.ocupacion.upper(),
        'CORREO_COMPRADOR':    correo_comprador1,

        # Coordenadas
        **coords,

        # Financiamiento
        'PRECIO_LOTE_FINANCIAMIENTO': fmt_money(fin.precio_lote),
        'LETRA_PRECIO_LOTE':          numero_a_letras(float(fin.precio_lote)),
        'APARTADO_FINANCIAMIENTO':    fmt_money(fin.apartado),
        'LETRA_APARTADO':             numero_a_letras(float(fin.apartado)),

        # Enganche y mensualidades
        'DIA_ENGANCHE':                   eng_dia,
        'MES_ENGANCHE':                   eng_mes,
        'ANIO_ENGANCHE':                  eng_anio,
        'CANTIDAD_ENGANCHE_FINANCIAMIENTO': fmt_money(cant_eng),
        'LETRA_ENGANCHE':                   letra_eng,

        'MENSUALIADES_FINANCIAMIENTO':     num_men,
        'MENSUALIDADES': num_men-1,
        'MENSUALIDADES_FIJAS':             num_men-1,
        'CANTIDAD_MENSUALIDAD_FIJA':       fmt_money(fija),
        'LETRA_MENSUALIDAD_FIJA':          letra_fija,

        'CANTIDAD_MENSUALIDAD_FINAL':      fmt_money(final),
        'LETRA_MENSUALIDAD_FINAL':         letra_fin,
        # Y la cláusula B variable:
        'CLAUSULA_B': claus_b,
    }

    # 6) Firma del cliente
    if request and tpl:
        data_url = firma_data or (request.session.get('firma_cliente_data') if request else None)
        if data_url:
            header, b64 = data_url.split(',', 1)
            img_data = base64.b64decode(b64)
            fd, tmp = tempfile.mkstemp(suffix='.png')
            with os.fdopen(fd, 'wb') as f:
                f.write(img_data)
            # Inserta la imagen de firma
            context['FIRMA_CLIENTE'] = InlineImage(tpl, tmp, width=Mm(40))
        else:
            context['FIRMA_CLIENTE'] = ''
    else:
        context['FIRMA_CLIENTE'] = ''

    # Determinar qué cláusulas adicionales existen
    tiene_pago = clausulas_adicionales and 'pago' in clausulas_adicionales and bool(clausulas_adicionales['pago'])
    tiene_deslinde = clausulas_adicionales and 'deslinde' in clausulas_adicionales and bool(clausulas_adicionales['deslinde'])
    tiene_promesa = clausulas_adicionales and 'promesa' in clausulas_adicionales and bool(clausulas_adicionales['promesa'])
    
    # Formatear cláusulas adicionales
    clausula_pago = clausulas_adicionales['pago'] if tiene_pago else ''
    clausula_deslinde = clausulas_adicionales['deslinde'] if tiene_deslinde else ''
    clausula_promesa = clausulas_adicionales['promesa'] if tiene_promesa else ''
    
    # Agregar al contexto
    context.update({
        'CLAUSULA_PAGO': clausula_pago.upper(),
        'CLAUSULA_DESLINDE': clausula_deslinde.upper(),
        'CLAUSULA_PROMESA': clausula_promesa.upper(),
    })

    return context

def build_contrato_canario_pagos_varios_context(fin, cli, ven, cliente2=None, request=None, tpl=None, firma_data=None, clausulas_adicionales=None):

    print("Entré al build de casa canario para DOS COMPRADORES a pagos")

    if clausulas_adicionales is None:
        clausulas_adicionales = {}

    # 1) Pronombres y formas según sexo para SINGULARES (igual que antes)
    def art(sex, masculino, femenino):
        return masculino if sex == 'M' else femenino

    SEXO_1 = art(ven.sexo, 'EL', 'LA')
    SEXO_2 = art(ven.sexo, 'VENDEDOR', 'VENDEDORA')
    SEXO_3 = art(cli.sexo, 'EL', 'LA')
    SEXO_4 = art(cli.sexo, 'COMPRADOR', 'COMPRADORA')
    SEXO_5 = art(cli.sexo, 'O', 'A')
    prop = fin.lote.proyecto.propietario.first()
    SEXO_6 = art(prop.sexo, 'EL', 'LA')
    SEXO_7 = art(ven.sexo, 'AL "', 'A "LA ')
    SEXO_8 = art(ven.sexo, 'DEL "', 'DE "LA ')
    SEXO_14 = art(ven.sexo, 'O', 'A')
    SEXO_15 = art(ven.sexo, 'DEL "', 'DE "LA ')
    SEXO_16 = art(ven.sexo, 'ÉSTE', 'ÉSTA')
    SEXO_20 = art(prop.sexo, 'EL', 'LA')

    # 2) Pronombres PLURALES para DOS COMPRADORES
    # Determinar género predominante para plurales
    if cliente2:
        if cli.sexo == 'M' or cliente2.sexo == 'M':
            # Si al menos uno es masculino -> masculino plural
            SEXO_9 = 'LOS'
            SEXO_10 = 'COMPRADORES'
            SEXO_11 = 'O'
            SEXO_12 = 'A "LOS '
            SEXO_13 = 'DE "LOS '
            SEXO_17 = 'ÉSTOS'
        else:
            # Ambos femeninos -> femenino plural
            SEXO_9 = 'LAS'
            SEXO_10 = 'COMPRADORAS'
            SEXO_11 = 'A'
            SEXO_12 = 'A "LAS '
            SEXO_13 = 'DE "LAS '
            SEXO_17 = 'ÉSTAS'
    else:
        # Por si acaso (aunque esta función es para varios)
        SEXO_9 = 'LOS'
        SEXO_10 = 'COMPRADORES'
        SEXO_11 = 'O'
        SEXO_12 = 'A "LOS '
        SEXO_13 = 'DE "LOS '
        SEXO_17 = 'ÉSTOS'


    # 2) Fecha actual
    hoy   = date.today()
    meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
    DIA, MES = numero_a_letras(float(hoy.day),apocopado=False), meses[hoy.month-1].upper()

    email1 = (cli.email or '')        # convierte None -> ''
    email1 = email1.strip()            # quita espacios en blanco
    if email1:
        correo_comprador1 = email1.upper()
    else:
        correo_comprador1 = 'NO PROPORCIONADO'

    email2 = (cliente2.email or '')        # convierte None -> ''
    email2 = email2.strip()            # quita espacios en blanco
    if email2:
        correo_comprador2 = email2.upper()
    else:
        correo_comprador2 = 'NO PROPORCIONADO'

    # 4) Coordenadas por cada lado (igual que antes)
    dir_fields = {}
    for dir_name in ('norte','sur','este','oeste'):
        raw = getattr(fin.lote, dir_name, '')
        metros, col = _parse_coord(raw)
        key_m = f'NUMERO_METROS_{dir_name.upper()}'
        key_c = f'COLINDANCIA_LOTE_{dir_name.upper()}'
        dir_fields[key_m] = metros
        dir_fields[key_c] = col

    # 6) Miembro B dinámico según relación (igual que antes)
    if ven.ine == prop.ine and prop.tipo == 'propietario':
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, "
            f"QUE ACREDITA CON EL CONTRATO PRIVADO DE COMPRAVENTA Y CONSTANCIA DE POSESIÓN DE FECHA VEINTITRÉS DE OCTUBRE DE DOS MIL VEINTICUATRO "
            f"EXPEDIDA POR LOS INTEGRANTES DEL ALCALDE ÚNICO CONSTITUCIONAL DE SAN ANTONIO DE LA CAL, OAXACA"
        )
    # — Si es vendedor autorizado:
    else:
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, AL IGUAL QUE CON LAS FACULTADES Y AUTORIZACIÓN SUFICIENTE PARA OBLIGARSE EN LOS TÉRMINOS DE ESTE, "
            f"TAL COMO SE ACREDITA EN EL CONTRATO DE EXCLUSIVIDAD, PROMOCIÓN Y COMISIÓN POR LA VENTA DEL BIEN INMUEBLE DE FECHA SEIS DE ENERO DE DOS MIL VEINTICINCO "
            f"OTORGADO POR EL C. JORGE EMILIO ALAVEZ AGUILAR."
        )

    # 4) Enganche y mensualidades
    eng_dia = fin.fecha_enganche.day if fin.fecha_enganche else ''
    eng_mes = meses[fin.fecha_enganche.month-1].upper() if fin.fecha_enganche else ''
    eng_anio= fin.fecha_enganche.year if fin.fecha_enganche else ''
    cant_eng  = fin.enganche or 0
    letra_eng = numero_a_letras(float(cant_eng))
    num_men   = fin.num_mensualidades
    fija      = fin.monto_mensualidad or 0
    letra_fija= numero_a_letras(float(fija))
    final     = fin.monto_pago_final or 0
    letra_fin = numero_a_letras(float(final))

    # 7) Construcción del context - con datos de AMBOS clientes
    context = {
        # Pronombres SINGULARES
        'SEXO_1': SEXO_1,
        'SEXO_2': SEXO_2,
        'SEXO_3': SEXO_3,
        'SEXO_4': SEXO_4,
        'SEXO_5': SEXO_5,
        'SEXO_6': SEXO_6,
        'SEXO_7': SEXO_7,
        'SEXO_8': SEXO_8,
        # Pronombres PLURALES
        'SEXO_9': SEXO_9,
        'SEXO_10': SEXO_10,
        'SEXO_11': SEXO_11,
        'SEXO_12': SEXO_12,
        'SEXO_13': SEXO_13,
        'SEXO_14': SEXO_14,
        'SEXO_15': SEXO_15,
        'SEXO_16': SEXO_16,
        'SEXO_17': SEXO_17,

        # Fecha
        'DIA': DIA, 'MES': MES,

        # Vendedor
        'NOMBRE_VENDEDOR': ven.nombre_completo.upper(),
        'ID_INE':          ven.ine,
        'NUMERO_VENDEDOR': ven.telefono,

        # Primer Cliente/Comprador
        'NOMBRE_COMPRADOR':   cli.nombre_completo.upper(),
        'DIRECCION_COMPRADOR':cli.domicilio.upper(),
        'ID_INE_COMPRADOR':    cli.numero_id,
        'LUGAR_ORIGEN':        cli.originario.upper(),
        'ESTADO_CIVIL':        cli.estado_civil.upper(),
        'TELEFONO_COMPRADOR':  cli.telefono.upper(),
        'OCUPACION_COMPRADOR': cli.ocupacion.upper(),
        'CORREO_COMPRADOR':    correo_comprador1,

        # Segundo Cliente/Comprador
        'NOMBRE_COMPRADOR_2':   cliente2.nombre_completo.upper() if cliente2 else '',
        'DIRECCION_COMPRADOR_2':cliente2.domicilio.upper() if cliente2 else '',
        'ID_INE_COMPRADOR_2':   cliente2.numero_id if cliente2 else '',
        'LUGAR_ORIGEN_2':       cliente2.originario.upper() if cliente2 else '',
        'ESTADO_CIVIL_2':       cliente2.estado_civil.upper() if cliente2 else '',
        'TELEFONO_COMPRADOR_2': cliente2.telefono.upper() if cliente2 else '',
        'OCUPACION_COMPRADOR_2':cliente2.ocupacion.upper() if cliente2 else '',
        'CORREO_COMPRADOR_2':   correo_comprador2 if cliente2 else '',

        # Coordenadas dinámicas
        **dir_fields,

       # Financiamiento
        'PRECIO_LOTE_FINANCIAMIENTO': fmt_money(fin.precio_lote),
        'LETRA_PRECIO_LOTE':          numero_a_letras(float(fin.precio_lote)),
        'APARTADO_FINANCIAMIENTO':    fmt_money(fin.apartado),
        'LETRA_APARTADO':             numero_a_letras(float(fin.apartado)),

        # Enganche y mensualidades
        'DIA_ENGANCHE':                   eng_dia,
        'MES_ENGANCHE':                   eng_mes,
        'ANIO_ENGANCHE':                  eng_anio,
        'CANTIDAD_ENGANCHE_FINANCIAMIENTO': fmt_money(cant_eng),
        'LETRA_ENGANCHE':                   letra_eng,

        'MENSUALIADES_FINANCIAMIENTO':     num_men,
        'MENSUALIDADES': num_men-1,
        'MENSUALIDADES_FIJAS':             f"{fija:.2f}",
        'CANTIDAD_MENSUALIDAD_FIJA':       fmt_money(fija),
        'LETRA_MENSUALIDAD_FIJA':          letra_fija,

        'CANTIDAD_MENSUALIDAD_FINAL':      fmt_money(final),
        'LETRA_MENSUALIDAD_FINAL':         letra_fin,
        # Y la cláusula B variable:
        'CLAUSULA_B': claus_b,
    }

    # 8) Firma del cliente (para DOS clientes, usar la misma firma o implementar lógica para dos firmas)
    # (Manteniendo la misma lógica por ahora)
    if request and tpl:
        data_url = firma_data or (request.session.get('firma_cliente_data') if request else None)
        if data_url:
            header, b64 = data_url.split(',', 1)
            img_data = base64.b64decode(b64)
            fd, tmp = tempfile.mkstemp(suffix='.png')
            with os.fdopen(fd, 'wb') as f:
                f.write(img_data)
            context['FIRMA_CLIENTE'] = InlineImage(tpl, tmp, width=Mm(40))
        else:
            context['FIRMA_CLIENTE'] = ''
    else:
        context['FIRMA_CLIENTE'] = ''

    # Determinar qué cláusulas adicionales existen
    tiene_pago = clausulas_adicionales and 'pago' in clausulas_adicionales and bool(clausulas_adicionales['pago'])
    tiene_deslinde = clausulas_adicionales and 'deslinde' in clausulas_adicionales and bool(clausulas_adicionales['deslinde'])
    tiene_promesa = clausulas_adicionales and 'promesa' in clausulas_adicionales and bool(clausulas_adicionales['promesa'])
    
    # Formatear cláusulas adicionales
    clausula_pago = clausulas_adicionales['pago'] if tiene_pago else ''
    clausula_deslinde = clausulas_adicionales['deslinde'] if tiene_deslinde else ''
    clausula_promesa = clausulas_adicionales['promesa'] if tiene_promesa else ''
    
    # Agregar al contexto
    context.update({
        'CLAUSULA_PAGO': clausula_pago.upper(),
        'CLAUSULA_DESLINDE': clausula_deslinde.upper(),
        'CLAUSULA_PROMESA': clausula_promesa.upper(),
    })

    return context



