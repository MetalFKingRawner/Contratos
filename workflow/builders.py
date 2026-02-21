# workflow/builders.py
import os, base64, tempfile
from docxtpl import DocxTemplate,InlineImage
from docx.shared import Mm
from datetime import date
from django.conf import settings
from workflow.utils import numero_a_letras, calcular_superficie
from requests import request
from django.db.models import Count
from datetime import date, timedelta

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

def calcular_distribucion_meses_fuertes(total_meses, cantidad_meses_fuertes, frecuencia=None):
    """
    Replica exactamente la lógica de JavaScript para Commeta.
    """
    # Caso especial: si todos los meses son fuertes
    if cantidad_meses_fuertes >= total_meses:
        return list(range(1, total_meses + 1))
    
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
        if cantidad_meses_fuertes == 0:
            return []
        
        espaciado = max(1, total_meses // cantidad_meses_fuertes)
        meses_fuertes = []
        
        # Comenzar desde el primer mes disponible
        for i in range(cantidad_meses_fuertes):
            mes = min((i * espaciado) + 1, total_meses)
            meses_fuertes.append(mes)
        
        # Eliminar duplicados y ordenar
        meses_unicos = sorted(set(meses_fuertes))
        meses_filtrados = [mes for mes in meses_unicos if mes <= total_meses]
        
        # Si nos faltan meses fuertes, agregar al final
        meses_finales = list(meses_filtrados)
        while len(meses_finales) < cantidad_meses_fuertes and meses_finales[-1] < total_meses:
            nuevo_mes = min(meses_finales[-1] + 1, total_meses)
            if nuevo_mes not in meses_finales:
                meses_finales.append(nuevo_mes)
        
        return sorted(meses_finales[:cantidad_meses_fuertes])
        
def build_financiamiento_context(fin, cli, ven, request=None, tpl=None, firma_data=None, 
                                 is_commeta=False, fin_commeta=None, **kwargs):
    """
    Context para Tabla de Financiamiento - Compatible con Normal y Commeta
    """
    clausulas_adicionales = kwargs.get('clausulas_adicionales', {})
    cliente2 = kwargs.get('cliente2', None)
    tramite = kwargs.get('tramite', None)
    
    # 1) Fecha actual
    hoy = date.today()
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
             "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    
    # 2) Cálculos iniciales (comunes para ambos)
    resta_apartado = float(fin.precio_lote) - float(fin.apartado)
    resta_enganche = resta_apartado - float(fin.enganche or 0)
    
    # 3) Lógica específica para Commeta - DETERMINAR MESES FUERTES
    meses_fuertes = []
    if is_commeta and fin_commeta:
        if fin_commeta.tipo_esquema == 'meses_fuertes':
            if fin_commeta.usar_meses_especificos and fin_commeta.meses_fuertes_calculados:
                meses_fuertes = fin_commeta.meses_fuertes_calculados
            else:
                meses_fuertes = calcular_distribucion_meses_fuertes(
                    total_meses=fin.num_mensualidades,
                    cantidad_meses_fuertes=fin_commeta.cantidad_meses_fuertes,
                    frecuencia=fin_commeta.frecuencia_meses_fuertes
                )
    
    # 4) Generar lista de pagos según el tipo
    pagos = []
    saldo_actual = resta_enganche
    
    if fin.tipo_pago == 'financiado' and fin.num_mensualidades:
        fecha_pago = fin.fecha_primer_pago
        
        for i in range(1, fin.num_mensualidades + 1):
            cuota = 0
            
            if is_commeta and fin_commeta:
                # ========== LÓGICA COMMETA ==========
                
                # Determinar si es el último mes
                es_ultimo_mes = (i == fin.num_mensualidades)
                
                if fin_commeta.tipo_esquema == 'meses_fuertes':
                    # --- ESQUEMA MESES FUERTES ---
                    if es_ultimo_mes and fin.monto_pago_final:
                        # Pago final explícito
                        cuota = float(fin.monto_pago_final)
                    elif es_ultimo_mes:
                        # Último pago = saldo restante
                        cuota = saldo_actual
                    elif i in meses_fuertes:
                        # Mes fuerte
                        cuota = float(fin_commeta.monto_mes_fuerte)
                    else:
                        # Mes normal
                        cuota = float(fin_commeta.monto_mensualidad_normal or 0)
                
                elif fin_commeta.tipo_esquema == 'mensualidades_fijas':
                    # --- ESQUEMA MENSUALIDADES FIJAS ---
                    if es_ultimo_mes and fin.monto_pago_final:
                        cuota = float(fin.monto_pago_final)
                    elif es_ultimo_mes:
                        cuota = saldo_actual
                    else:
                        cuota = float(fin.monto_mensualidad or 0)
                
                else:
                    # --- ESQUEMA DE GRACIA (caso PROBADON) ---
                    # Todos los meses tienen cuota 0 excepto el último
                    if es_ultimo_mes:
                        # El último pago liquida todo el saldo
                        cuota = saldo_actual
                    else:
                        # Período de gracia: cuota = 0
                        cuota = 0.0
            
            else:
                # ========== LÓGICA FINANCIAMIENTO NORMAL ==========
                if i == fin.num_mensualidades:
                    # Último pago = saldo actual
                    cuota = saldo_actual
                else:
                    cuota = float(fin.monto_mensualidad)
            
            # Calcular saldo final
            saldo_final = max(0, saldo_actual - cuota)
            
            pagos.append({
                'numero': i,
                'fecha': fecha_pago.strftime("%d/%m/%Y") if fecha_pago else '',
                'saldo_inicial': fmt_money(saldo_actual),
                'cuota': fmt_money(cuota),
                'saldo_final': fmt_money(saldo_final),
            })
            
            # Actualizar para siguiente pago
            saldo_actual = saldo_final
            if fecha_pago:
                # Avanzar un mes
                try:
                    if fecha_pago.month == 12:
                        fecha_pago = fecha_pago.replace(year=fecha_pago.year + 1, month=1)
                    else:
                        fecha_pago = fecha_pago.replace(month=fecha_pago.month + 1)
                except:
                    pass

    # 5) Pronombres según sexo
    def art(sex, masculino, femenino):
        return masculino if sex == 'M' else femenino

    SEXO_COM = art(cli.sexo, 'COMPRADOR', 'COMPRADORA')
    SEXO_VEN = art(ven.sexo, 'VENDEDOR', 'VENDEDORA')
    
    if cliente2:
        SEXO_COM2 = art(cliente2.sexo, 'COMPRADOR', 'COMPRADORA')

    # 6) Construir contexto base
    context = {
        'FECHA': hoy.strftime("%d/%m/%Y"),
        'FECHA_APARTADO': fin.creado_en.strftime("%d/%m/%Y") if fin.creado_en else hoy.strftime("%d/%m/%Y"),
        'FECHA_ENGANCHE': fin.fecha_enganche.strftime("%d/%m/%Y") if fin.fecha_enganche else '',
        
        'LOTE': fin.lote.identificador,
        'NOMBRE_CLIENTE': cli.nombre_completo.upper(),
        'NOMBRE_COMPRADOR': cli.nombre_completo.upper(),
        'NOMBRE_VENDEDOR': ven.nombre_completo.upper(),
        
        'PRECIO_LOTE': fmt_money(fin.precio_lote),
        'APARTADO': fmt_money(fin.apartado),
        'ENGANCHE': fmt_money(fin.enganche) if fin.enganche else '',
        'NUM_MENSUALIDADES': fin.num_mensualidades,
        
        'RESTA_APARTADO': fmt_money(resta_apartado),
        'RESTA_ENGANCHE': fmt_money(resta_enganche),
        
        'pagos': pagos,
        
        'SEXO_COM': SEXO_COM,
        'SEXO_VEN': SEXO_VEN,
        
        'ES_COMMETA': is_commeta,
    }
    
    # 7) Segundo cliente
    if cliente2:
        context.update({
            'NOMBRE_CLIENTE2': cliente2.nombre_completo.upper(),
            'NOMBRE_COMPRADOR2': cliente2.nombre_completo.upper(),
            'SEXO_COM2': SEXO_COM2,
        })
    
    # 8) Campos específicos Commeta
    if is_commeta and fin_commeta:
        # Determinar montos según esquema
        if fin_commeta.tipo_esquema == 'meses_fuertes':
            abono_normal = float(fin_commeta.monto_mensualidad_normal or 0)
            abono_fuerte = float(fin_commeta.monto_mes_fuerte or 0)
            periodo_fuerte = fin_commeta.frecuencia_meses_fuertes
        elif fin_commeta.tipo_esquema == 'mensualidades_fijas':
            abono_normal = float(fin.monto_mensualidad or 0)
            abono_fuerte = 0
            periodo_fuerte = None
        else:
            # Esquema de gracia u otro
            abono_normal = 0
            abono_fuerte = 0
            periodo_fuerte = None
        
        context.update({
            'ABONO_NORMAL': fmt_money(abono_normal),
            'ABONO_FUERTE': fmt_money(abono_fuerte) if abono_fuerte else '',
            'PERIODO_FUERTE': periodo_fuerte,
            'TIPO_ESQUEMA': fin_commeta.tipo_esquema,
            'CANTIDAD_MESES_FUERTES': fin_commeta.cantidad_meses_fuertes if hasattr(fin_commeta, 'cantidad_meses_fuertes') else '',
        })
    
    # 9) Firma
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

    return context
                                     
def build_carta_intencion_context(fin, cli, ven,request=None, tpl=None, firma_data=None, tramite=None, fecha=None):
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
            'SUPERFICIE':            fin.lote.superficie_m2,
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
        context['FIRMA_VENDEDOR'] = crear_firma_unificada(tramite.firma_vendedor)
        
    else:
        # Valores por defecto si no hay template
        context['FIRMA_CLIENTE'] = ''
        context['FIRMA_VENDEDOR'] = ''

    return context
    
def build_solicitud_contrato_context(fin, cli, ven, request=None, tpl=None, firma_data=None, tramite=None):
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

    nombre_bene =''
    clave_bene = ''
    telefono_bene = ''
    correo_bene = ''

    if tramite.beneficiario_1:
        nombre_bene = tramite.beneficiario_1.nombre_completo
        clave_bene = tramite.beneficiario_1.numero_id
        telefono_bene = tramite.beneficiario_1.telefono
        correo_bene = tramite.beneficiario_1.email

    coords = {}
    for lado in ('norte','sur','este','oeste'):
        raw = getattr(fin.lote, lado, '')
        m, c = _parse_coord(raw)
        coords[f'LOTE_{lado.upper()}'] = m
        coords[f'COLINDA_{lado.upper()}'] = c

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
        'NACIONALIDAD':       cli.nacionalidad.upper(),
        'DIRECCION_CLIENTE':  cli.domicilio.upper(),
        'RFC_CLIENTE':        rfc_comprador,  # asume tienes campo rfc en Cliente
        'CLAVE_CLIENTE':      cli.numero_id,
        # Beneficiario
        'NOMBRE_BENE': nombre_bene.upper(),
        'CLAVE_BENE': clave_bene.upper(),
        'TELEFONO_BENE': telefono_bene,
        'CORREO_BENE': correo_bene.upper(),
        # Lote y financiamiento
        'NOMBRE_LOTE':        str(fin.lote.proyecto.nombre).upper(),
        'NUMERO_LOTE':        fin.lote.identificador,
        **coords,
        'METROS_CUAD': fin.lote.superficie_m2,
        # Vendedor
        'NOMBRE_VENDEDOR':    ven.nombre_completo.upper(),
    }

    # 3) Campos según tipo_pago
    if fin.tipo_pago == 'contado':
        context.update({
            'PRECIO_LOTE_CONT':        f"${fin.precio_lote:,.2f}",
            'CANTIDAD_APARTADO_CONT':  f"${fin.apartado:,.2f}",
            'FECHA_PAGO_COMPLETO':     fin.fecha_pago_completo.strftime("%d/%m/%Y"),
            'CANTIDAD_PAGO_TOTAL':     f"${(fin.precio_lote - fin.apartado):,.2f}",
        })
    else:
        # financiado
        context.update({
            'PRECIO_LOTE_FIN':        f"${fin.precio_lote:,.2f}",
            'CANTIDAD_APARTADO_FIN':  f"${fin.apartado:,.2f}",
            'CANTIDAD_ENGANCHE':      f"${fin.enganche:,.2f}",
            'FECHA_ENGANCHE':         fin.fecha_enganche.strftime("%d/%m/%Y") if fin.fecha_enganche else '',
            'NUM_MENSUALIDAD':        fin.num_mensualidades,
            'DIA_PAGO':               fin.fecha_primer_pago.day if fin.fecha_primer_pago else '',
        })

    # 6) Firma
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
        context['FIRMA_VENDEDOR'] = crear_firma_unificada(tramite.firma_vendedor)
        
    else:
        # Valores por defecto si no hay template
        context['FIRMA_CLIENTE'] = ''
        context['FIRMA_VENDEDOR'] = ''

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

def build_contrato_propiedad_contado_context(fin, cli, ven, request=None, tpl=None, firma_data=None, clausulas_adicionales=None, tramite=None, fecha=None):

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
    if fecha == None:
        dia_actual = date.today()
    else:
        dia_actual = fecha
    email = (cli.email or '')        # convierte None -> ''
    email = email.strip()            # quita espacios en blanco
    if email:
        correo_comprador = email.upper()
    else:
        correo_comprador = 'NO PROPORCIONADO'

    testigo1 = (tramite.testigo_1_nombre or '')        # convierte None -> ''
    if testigo1:
        test1 = testigo1.upper()
    else:
        test1 = testigo1
    
    testigo2 = (tramite.testigo_2_nombre or '')        # convierte None -> ''
    if testigo2:
        test2 = testigo2.upper()
    else:
        test2 = testigo2

    tipo = fin.lote.proyecto.tipo_contrato.upper()

# 3) Miembro B dinámico según relación:
    # — Si ven es propietario:
    if ven.ine == prop.ine and prop.tipo == 'propietario' and tipo == 'PEQUEÑA PROPIEDAD':
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, "
            f"QUE ACREDITA CON EL CONTRATO PRIVADO DE COMPRAVENTA, CONSTANCIA DE POSESIÓN Y APEO Y DESLINDE DE FECHA {fecha_posesion} "
            f"EXPEDIDOS POR {autoridad}"
        )
    
    elif ven.ine == prop.ine and prop.tipo == 'propietario':
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, "
            f"QUE ACREDITA CON EL CONTRATO PRIVADO DE COMPRAVENTA, CONSTANCIA DE POSESIÓN Y APEO Y DESLINDE DE FECHA {fecha_posesion} "
            f"EXPEDIDA POR {autoridad}"
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
            f", OTORGADO POR {SEXO_20}  C. {prop.nombre_completo.upper()}"
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
        'ANIO': numero_a_letras(float(dia_actual.year),apocopado=False),

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
        'IDENTIFICADOR_LOTE':  fin.lote.identificador,
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
        'NOMBRE_TESTIGO2': test2,
        'NOMBRE_TESTIGO1': test1,

    }

    # 6) Firma
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
        context['FIRMA_VENDEDOR'] = crear_firma_unificada(tramite.firma_vendedor)
        context['FIRMA_TESTIGO1'] = crear_firma_unificada(tramite.testigo_1_firma)
        context['FIRMA_TESTIGO2'] = crear_firma_unificada(tramite.testigo_2_firma)
        context['FIRMA_BENE'] = crear_firma_unificada(tramite.beneficiario_1_firma)
        
    else:
        # Valores por defecto si no hay template
        context['FIRMA_CLIENTE'] = ''
        context['FIRMA_VENDEDOR'] = ''
        context['FIRMA_TESTIGO1'] = ''
        context['FIRMA_TESTIGO2'] = ''
        context['FIRMA_BENE'] = ''

    # Determinar qué cláusulas adicionales existen
    tiene_pago = clausulas_adicionales and 'pago' in clausulas_adicionales and bool(clausulas_adicionales['pago'])
    tiene_deslinde = clausulas_adicionales and 'deslinde' in clausulas_adicionales and bool(clausulas_adicionales['deslinde'])
    tiene_promesa = clausulas_adicionales and 'promesa' in clausulas_adicionales and bool(clausulas_adicionales['promesa'])
    
    # Formatear cláusulas adicionales
    clausula_pago = clausulas_adicionales['pago'] if tiene_pago else ''
    clausula_deslinde = clausulas_adicionales['deslinde'] if tiene_deslinde else ''
    clausula_promesa = clausulas_adicionales['promesa'] if tiene_promesa else ''
    
    if tiene_pago:
        clausula_e = "E."
        clausula_f = "F."
    else:
        clausula_e = "D."
        clausula_f = "E."

    # Agregar al contexto
    context.update({
        'CLAUSULA_PAGO': clausula_pago.upper(),
        'LETRA_E': clausula_e,
        'LETRA_F': clausula_f,
        'CLAUSULA_DESLINDE': clausula_deslinde.upper(),
        'CLAUSULA_PROMESA': clausula_promesa.upper(),
    })

    return context

def build_contrato_propiedad_contado_varios_context(fin, cli, ven, cliente2=None,request=None, tpl=None, firma_data=None, clausulas_adicionales=None, tramite=None, fecha=None):

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
    if fecha == None:
        pago = date.today()
    else:
        pago = fecha
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

    testigo1 = (tramite.testigo_1_nombre or '')        # convierte None -> ''
    if testigo1:
        test1 = testigo1.upper()
    else:
        test1 = testigo1
    
    testigo2 = (tramite.testigo_2_nombre or '')        # convierte None -> ''
    if testigo2:
        test2 = testigo2.upper()
    else:
        test2 = testigo2

    tipo = fin.lote.proyecto.tipo_contrato.upper()

    # 6) Miembro B dinámico según relación (igual que antes)
    if ven.ine == prop.ine and prop.tipo == 'propietario' and tipo == 'PEQUEÑA PROPIEDAD':
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, "
            f"QUE ACREDITA CON EL CONTRATO PRIVADO DE COMPRAVENTA, CONSTANCIA DE POSESIÓN Y APEO Y DESLINDE DE FECHA {fecha_posesion} "
            f"EXPEDIDOS POR {autoridad}"
        )
    
    elif ven.ine == prop.ine and prop.tipo == 'propietario':
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, "
            f"QUE ACREDITA CON EL CONTRATO PRIVADO DE COMPRAVENTA, CONSTANCIA DE POSESIÓN Y APEO Y DESLINDE DE FECHA {fecha_posesion} "
            f"EXPEDIDA POR {autoridad}"
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
            f"TAL COMO SE ACREDITA EN EL CONTRATO DE EXCLUSIVIDAD, PROMOCIÓN Y COMISIÓN POR LA VENTA DEL BIEN INMUEBLE DE FECHA {fecha_contrato}"
            f", OTORGADO POR {SEXO_20}  C. {prop.nombre_completo.upper()}"
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
        'ANIO': numero_a_letras(float(pago.year),apocopado=False),

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
        'NOMBRE_TESTIGO2': test2,
        'NOMBRE_TESTIGO1': test1,
    }

    # 6) Firma
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
        context['FIRMA_CLIENTE2'] = crear_firma_unificada(tramite.firma_cliente2)
        context['FIRMA_VENDEDOR'] = crear_firma_unificada(tramite.firma_vendedor)
        context['FIRMA_TESTIGO1'] = crear_firma_unificada(tramite.testigo_1_firma)
        context['FIRMA_TESTIGO2'] = crear_firma_unificada(tramite.testigo_2_firma)
        context['FIRMA_BENE'] = crear_firma_unificada(tramite.beneficiario_1_firma)
        
    else:
        # Valores por defecto si no hay template
        context['FIRMA_CLIENTE'] = ''
        context['FIRMA_CLIENTE_2'] = ''
        context['FIRMA_VENDEDOR'] = ''
        context['FIRMA_TESTIGO1'] = ''
        context['FIRMA_TESTIGO2'] = ''
        context['FIRMA_BENE'] = ''

    # Determinar qué cláusulas adicionales existen
    tiene_pago = clausulas_adicionales and 'pago' in clausulas_adicionales and bool(clausulas_adicionales['pago'])
    tiene_deslinde = clausulas_adicionales and 'deslinde' in clausulas_adicionales and bool(clausulas_adicionales['deslinde'])
    tiene_promesa = clausulas_adicionales and 'promesa' in clausulas_adicionales and bool(clausulas_adicionales['promesa'])
    
    # Formatear cláusulas adicionales
    clausula_pago = clausulas_adicionales['pago'] if tiene_pago else ''
    clausula_deslinde = clausulas_adicionales['deslinde'] if tiene_deslinde else ''
    clausula_promesa = clausulas_adicionales['promesa'] if tiene_promesa else ''
    
    if tiene_pago:
        clausula_e = "E."
        clausula_f = "F."
    else:
        clausula_e = "D."
        clausula_f = "E."

    # Agregar al contexto
    context.update({
        'CLAUSULA_PAGO': clausula_pago.upper(),
        'LETRA_E': clausula_e,
        'LETRA_F': clausula_f,
        'CLAUSULA_DESLINDE': clausula_deslinde.upper(),
        'CLAUSULA_PROMESA': clausula_promesa.upper(),
    })

    return context

def build_contrato_propiedad_pagos_context(fin, cli, ven, request=None, tpl=None, firma_data=None, clausulas_adicionales=None, tramite=None, fecha=None):

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

    SEXO_11 = art(tramite.beneficiario_1.sexo, 'EL', 'LA') #Referente al beneficiario
    SEXO_12 = art(tramite.beneficiario_1.sexo, 'O', 'A') #Referente al beneficiario


    # 2) Fecha actual
    if fecha == None:
        hoy = date.today()
    else:
        hoy = fecha
    meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
    DIA, MES = numero_a_letras(float(hoy.day),apocopado=False), meses[hoy.month-1].upper()
    ANIO = numero_a_letras(float(hoy.year),apocopado=False)

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

    testigo1 = (tramite.testigo_1_nombre or '')        # convierte None -> ''
    if testigo1:
        test1 = testigo1.upper()
    else:
        test1 = testigo1
    
    testigo2 = (tramite.testigo_2_nombre or '')        # convierte None -> ''
    if testigo2:
        test2 = testigo2.upper()
    else:
        test2 = testigo2

    bene = (tramite.beneficiario_1.nombre_completo or '')        # convierte None -> ''
    if bene:
        benef = bene.upper()
    else:
        benef = bene
    
    bene_telefono = (tramite.beneficiario_1.telefono or '')
    bene_correo = (tramite.beneficiario_1.email or '')
    if bene_correo:
        bene_correo1 = bene_correo.upper()
    else:
        bene_correo1 = bene_correo
    bene_id = (tramite.beneficiario_1.numero_id or '')

    tipo = fin.lote.proyecto.tipo_contrato.upper()

    # 3) Miembro B dinámico según relación:
    # — Si ven es propietario:
    if ven.ine == prop.ine and prop.tipo == 'propietario' and tipo == 'PEQUEÑA PROPIEDAD':
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, "
            f"QUE ACREDITA CON EL CONTRATO PRIVADO DE COMPRAVENTA, CONSTANCIA DE POSESIÓN Y APEO Y DESLINDE DE FECHA {fecha_posesion} "
            f"EXPEDIDOS POR {autoridad}"
        )
    
    elif ven.ine == prop.ine and prop.tipo == 'propietario':
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, "
            f"QUE ACREDITA CON EL CONTRATO PRIVADO DE COMPRAVENTA, CONSTANCIA DE POSESIÓN Y APEO Y DESLINDE DE FECHA {fecha_posesion} "
            f"EXPEDIDA POR {autoridad}"
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
            f", OTORGADO POR {SEXO_20}  C. {prop.nombre_completo.upper()}"
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
        'DIA': DIA, 'MES': MES, 'ANIO': ANIO,

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

        'MENSUALIDADES_FINANCIAMIENTO':     num_men,
        'MENSUALIDADES': num_men-1,
        'MENSUALIDADES_FIJAS':             num_men-1,
        'CANTIDAD_MENSUALIDAD_FIJA':       fmt_money(fija),
        'LETRA_MENSUALIDAD_FIJA':          letra_fija,

        'CANTIDAD_MENSUALIDAD_FINAL':      fmt_money(final),
        'LETRA_MENSUALIDAD_FINAL':         letra_fin,
        # Y la cláusula B variable:
        'CLAUSULA_B': claus_b,
        'NOMBRE_TESTIGO2': test2,
        'NOMBRE_TESTIGO1': test1,

        #BENEFICIARIO
        'SEXO_11':SEXO_11,
        'SEXO_12': SEXO_12,
        'NOMBRE_BENE': benef,
        'ID_BENE': bene_id,
        'NUMERO_BENE': bene_telefono,
        'CORREO_BENE':bene_correo1,
    }

    # 6) Firma
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
        context['FIRMA_VENDEDOR'] = crear_firma_unificada(tramite.firma_vendedor)
        context['FIRMA_TESTIGO1'] = crear_firma_unificada(tramite.testigo_1_firma)
        context['FIRMA_TESTIGO2'] = crear_firma_unificada(tramite.testigo_2_firma)
        context['FIRMA_BENE'] = crear_firma_unificada(tramite.beneficiario_1_firma)
        
    else:
        # Valores por defecto si no hay template
        context['FIRMA_CLIENTE'] = ''
        context['FIRMA_VENDEDOR'] = ''
        context['FIRMA_TESTIGO1'] = ''
        context['FIRMA_TESTIGO2'] = ''
        context['FIRMA_BENE'] = ''

    # Determinar qué cláusulas adicionales existen
    tiene_pago = clausulas_adicionales and 'pago' in clausulas_adicionales and bool(clausulas_adicionales['pago'])
    tiene_deslinde = clausulas_adicionales and 'deslinde' in clausulas_adicionales and bool(clausulas_adicionales['deslinde'])
    tiene_promesa = clausulas_adicionales and 'promesa' in clausulas_adicionales and bool(clausulas_adicionales['promesa'])
    
    # Formatear cláusulas adicionales
    clausula_pago = clausulas_adicionales['pago'] if tiene_pago else ''
    clausula_deslinde = clausulas_adicionales['deslinde'] if tiene_deslinde else ''
    clausula_promesa = clausulas_adicionales['promesa'] if tiene_promesa else ''
    
    if tiene_pago:
        clausula_e = "E."
        clausula_f = "F."
        clausula_g = "G."
    else:
        clausula_e = "D."
        clausula_f = "E."
        clausula_g = "F."

    # Agregar al contexto
    context.update({
        'CLAUSULA_PAGO': clausula_pago.upper(),
        'LETRA_E': clausula_e,
        'LETRA_F': clausula_f,
        'LETRA_G': clausula_g,
        'CLAUSULA_DESLINDE': clausula_deslinde.upper(),
        'CLAUSULA_PROMESA': clausula_promesa.upper(),
    })

    return context

def build_contrato_propiedad_pagos_varios_context(fin, cli, ven, cliente2=None,request=None, tpl=None, firma_data=None, clausulas_adicionales=None, tramite=None, fecha=None):

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

    SEXO_21 = art(tramite.beneficiario_1.sexo, 'EL', 'LA') #Referente al beneficiario
    SEXO_22 = art(tramite.beneficiario_1.sexo, 'EL', 'LA') #Referente al beneficiario

    # 2) Fecha actual
    if fecha == None:
        hoy = date.today()
    else:
        hoy = fecha
    meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
    DIA, MES = numero_a_letras(float(hoy.day),apocopado=False), meses[hoy.month-1].upper()
    ANIO = numero_a_letras(float(hoy.year),apocopado=False)

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

    testigo1 = (tramite.testigo_1_nombre or '')        # convierte None -> ''
    if testigo1:
        test1 = testigo1.upper()
    else:
        test1 = testigo1
    
    testigo2 = (tramite.testigo_2_nombre or '')        # convierte None -> ''
    if testigo2:
        test2 = testigo2.upper()
    else:
        test2 = testigo2

    bene = (tramite.beneficiario_1.nombre_completo or '')        # convierte None -> ''
    if bene:
        benef = bene.upper()
    else:
        benef = bene

    bene_telefono = (tramite.beneficiario_1.telefono or '')
    bene_correo = (tramite.beneficiario_1.email or '')
    if bene_correo:
        bene_correo1 = bene_correo.upper()
    else:
        bene_correo1 = bene_correo
    bene_id = (tramite.beneficiario_1.numero_id or '')

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

    tipo = fin.lote.proyecto.tipo_contrato.upper()

    # 6) Miembro B dinámico según relación (igual que antes)
    if ven.ine == prop.ine and prop.tipo == 'propietario' and tipo == 'PEQUEÑA PROPIEDAD':
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, "
            f"QUE ACREDITA CON EL CONTRATO PRIVADO DE COMPRAVENTA, CONSTANCIA DE POSESIÓN Y APEO Y DESLINDE DE FECHA {fecha_posesion} "
            f"EXPEDIDOS POR {autoridad}"
        )
    
    elif ven.ine == prop.ine and prop.tipo == 'propietario':
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, "
            f"QUE ACREDITA CON EL CONTRATO PRIVADO DE COMPRAVENTA, CONSTANCIA DE POSESIÓN Y APEO Y DESLINDE DE FECHA {fecha_posesion} "
            f"EXPEDIDA POR {autoridad}"
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
            f"TAL COMO SE ACREDITA EN EL CONTRATO DE EXCLUSIVIDAD, PROMOCIÓN Y COMISIÓN POR LA VENTA DEL BIEN INMUEBLE DE FECHA {fecha_contrato}"
            f", OTORGADO POR {SEXO_20}  C. {prop.nombre_completo.upper()}"
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
        'DIA': DIA, 'MES': MES, 'ANIO': ANIO,

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

        'MENSUALIDADES_FINANCIAMIENTO':     num_men,
        'MENSUALIDADES': num_men-1,
        'MENSUALIDADES_FIJAS':             f"{fija:.2f}",
        'CANTIDAD_MENSUALIDAD_FIJA':       fmt_money(fija),
        'LETRA_MENSUALIDAD_FIJA':          letra_fija,

        'CANTIDAD_MENSUALIDAD_FINAL':      fmt_money(final),
        'LETRA_MENSUALIDAD_FINAL':         letra_fin,
        # Y la cláusula B variable:
        'CLAUSULA_B': claus_b,
        'NOMBRE_TESTIGO2': test2,
        'NOMBRE_TESTIGO1': test1,

        #BENEFICIARIO
        'SEXO_21':SEXO_21,
        'SEXO_22': SEXO_22,
        'NOMBRE_BENE': benef,
        'ID_BENE': bene_id,
        'NUMERO_BENE': bene_telefono,
        'CORREO_BENE':bene_correo1,
    }

    # 6) Firma
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
        context['FIRMA_CLIENTE2'] = crear_firma_unificada(tramite.firma_cliente2)
        context['FIRMA_VENDEDOR'] = crear_firma_unificada(tramite.firma_vendedor)
        context['FIRMA_TESTIGO1'] = crear_firma_unificada(tramite.testigo_1_firma)
        context['FIRMA_TESTIGO2'] = crear_firma_unificada(tramite.testigo_2_firma)
        context['FIRMA_BENE'] = crear_firma_unificada(tramite.beneficiario_1_firma)
        
    else:
        # Valores por defecto si no hay template
        context['FIRMA_CLIENTE'] = ''
        context['FIRMA_CLIENTE_2'] = ''
        context['FIRMA_VENDEDOR'] = ''
        context['FIRMA_TESTIGO1'] = ''
        context['FIRMA_TESTIGO2'] = ''
        context['FIRMA_BENE'] = ''

    # Determinar qué cláusulas adicionales existen
    tiene_pago = clausulas_adicionales and 'pago' in clausulas_adicionales and bool(clausulas_adicionales['pago'])
    tiene_deslinde = clausulas_adicionales and 'deslinde' in clausulas_adicionales and bool(clausulas_adicionales['deslinde'])
    tiene_promesa = clausulas_adicionales and 'promesa' in clausulas_adicionales and bool(clausulas_adicionales['promesa'])
    
    # Formatear cláusulas adicionales
    clausula_pago = clausulas_adicionales['pago'] if tiene_pago else ''
    clausula_deslinde = clausulas_adicionales['deslinde'] if tiene_deslinde else ''
    clausula_promesa = clausulas_adicionales['promesa'] if tiene_promesa else ''
    
    if tiene_pago:
        clausula_e = "E."
        clausula_f = "F."
        clausula_g = "G."
    else:
        clausula_e = "D."
        clausula_f = "E."
        clausula_g = "F."

    # Agregar al contexto
    context.update({
        'CLAUSULA_PAGO': clausula_pago.upper(),
        'LETRA_E': clausula_e,
        'LETRA_F': clausula_f,
        'LETRA_G': clausula_g,
        'CLAUSULA_DESLINDE': clausula_deslinde.upper(),
        'CLAUSULA_PROMESA': clausula_promesa.upper(),
    })

    return context

def build_contrato_ejidal_contado_context(fin, cli, ven, request=None, tpl=None, firma_data=None, clausulas_adicionales=None, tramite=None, fecha=None):

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
    if fecha == None:
        cesion = date.today()
    else:
        cesion = fecha
    pago = fin.fecha_pago_completo
    meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
    ANIO_CESION = numero_a_letras(float(cesion.year),apocopado=False)

    email1 = (cli.email or '')        # convierte None -> ''
    email1 = email1.strip()            # quita espacios en blanco
    if email1:
        correo_comprador1 = email1.upper()
    else:
        correo_comprador1 = 'NO PROPORCIONADO'
    
    testigo1 = (tramite.testigo_1_nombre or '')        # convierte None -> ''
    if testigo1:
        test1 = testigo1.upper()
    else:
        test1 = testigo1
    
    testigo2 = (tramite.testigo_2_nombre or '')        # convierte None -> ''
    if testigo2:
        test2 = testigo2.upper()
    else:
        test2 = testigo2

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

    # NUEVO: Obtener información del proyecto para determinar tipo de documento
    proyecto = fin.lote.proyecto
    
    # Determinar el texto según el documento disponible
    if proyecto.incluir_cesion_derechos:
        tipo_documento_texto = "CESIÓN DE DERECHOS"
    elif proyecto.incluir_constancia_cesion:
        tipo_documento_texto = "CONSTANCIA DE CESIÓN DE DERECHOS"
    else:
        # Por defecto, aunque en ejido debería tener al menos uno
        tipo_documento_texto = "CONSTANCIA DE POSESIÓN"

    # 3) Miembro B dinámico según relación:
    # — Si ven es propietario:
    if ven.ine == prop.ine and prop.tipo == 'propietario':
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, "
            f"QUE ACREDITA CON LA {tipo_documento_texto} DE FECHA {fecha_posesion}"
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
        'ANIO_CESION': ANIO_CESION,

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
        'NOMBRE_TESTIGO2': test2,
        'NOMBRE_TESTIGO1': test1,

        # NUEVO: También puedes incluir el tipo de documento como variable separada si lo necesitas
        'TIPO_DOCUMENTO_EJIDAL': tipo_documento_texto,
    }

    # 6) Firma
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
        context['FIRMA_VENDEDOR'] = crear_firma_unificada(tramite.firma_vendedor)
        context['FIRMA_TESTIGO1'] = crear_firma_unificada(tramite.testigo_1_firma)
        context['FIRMA_TESTIGO2'] = crear_firma_unificada(tramite.testigo_2_firma)
        context['FIRMA_BENE'] = crear_firma_unificada(tramite.beneficiario_1_firma)
        
    else:
        # Valores por defecto si no hay template
        context['FIRMA_CLIENTE'] = ''
        context['FIRMA_VENDEDOR'] = ''
        context['FIRMA_TESTIGO1'] = ''
        context['FIRMA_TESTIGO2'] = ''
        context['FIRMA_BENE'] = ''
    

    # Determinar qué cláusulas adicionales existen
    tiene_pago = clausulas_adicionales and 'pago' in clausulas_adicionales and bool(clausulas_adicionales['pago'])
    tiene_deslinde = clausulas_adicionales and 'deslinde' in clausulas_adicionales and bool(clausulas_adicionales['deslinde'])
    tiene_promesa = clausulas_adicionales and 'promesa' in clausulas_adicionales and bool(clausulas_adicionales['promesa'])
    
    # Formatear cláusulas adicionales
    clausula_pago = clausulas_adicionales['pago'] if tiene_pago else ''
    clausula_deslinde = clausulas_adicionales['deslinde'] if tiene_deslinde else ''
    clausula_promesa = clausulas_adicionales['promesa'] if tiene_promesa else ''
    
    if tiene_pago:
        clausula_e = "E."
        clausula_f = "F."
    else:
        clausula_e = "D."
        clausula_f = "E."

    # Agregar al contexto
    context.update({
        'CLAUSULA_PAGO': clausula_pago.upper(),
        'LETRA_E': clausula_e,
        'LETRA_F': clausula_f,
        'CLAUSULA_DESLINDE': clausula_deslinde.upper(),
        'CLAUSULA_PROMESA': clausula_promesa.upper(),
    })

    return context

def build_contrato_ejidal_contado_varios_context(fin, cli, ven, cliente2=None,request=None, tpl=None, firma_data=None, clausulas_adicionales=None, tramite=None, fecha=None):
    
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
    if fecha == None:
        cesion = date.today()
    else:
        cesion = fecha
    pago = fin.fecha_pago_completo
    meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
    ANIO_CESION = numero_a_letras(float(cesion.year),apocopado=False)

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

    testigo1 = (tramite.testigo_1_nombre or '')        # convierte None -> ''
    if testigo1:
        test1 = testigo1.upper()
    else:
        test1 = testigo1
    
    testigo2 = (tramite.testigo_2_nombre or '')        # convierte None -> ''
    if testigo2:
        test2 = testigo2.upper()
    else:
        test2 = testigo2

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

    # NUEVO: Obtener información del proyecto para determinar tipo de documento
    proyecto = fin.lote.proyecto
    
    # Determinar el texto según el documento disponible
    if proyecto.incluir_cesion_derechos:
        tipo_documento_texto = "CESIÓN DE DERECHOS"
    elif proyecto.incluir_constancia_cesion:
        tipo_documento_texto = "CONSTANCIA DE CESIÓN DE DERECHOS"
    else:
        # Por defecto, aunque en ejido debería tener al menos uno
        tipo_documento_texto = "CONSTANCIA DE POSESIÓN"

    
    # 3) Miembro B dinámico según relación:
    # — Si ven es propietario:
    if ven.ine == prop.ine and prop.tipo == 'propietario':
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, "
            f"QUE ACREDITA CON LA {tipo_documento_texto} DE FECHA {fecha_posesion}"
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
        'ANIO_CESION': ANIO_CESION,

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
        'NOMBRE_TESTIGO2': test2,
        'NOMBRE_TESTIGO1': test1,

        # NUEVO: También puedes incluir el tipo de documento como variable separada si lo necesitas
        'TIPO_DOCUMENTO_EJIDAL': tipo_documento_texto,
    }

    # 6) Firma
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
        context['FIRMA_CLIENTE2'] = crear_firma_unificada(tramite.firma_cliente2)
        context['FIRMA_VENDEDOR'] = crear_firma_unificada(tramite.firma_vendedor)
        context['FIRMA_TESTIGO1'] = crear_firma_unificada(tramite.testigo_1_firma)
        context['FIRMA_TESTIGO2'] = crear_firma_unificada(tramite.testigo_2_firma)
        context['FIRMA_BENE'] = crear_firma_unificada(tramite.beneficiario_1_firma)
        
    else:
        # Valores por defecto si no hay template
        context['FIRMA_CLIENTE'] = ''
        context['FIRMA_CLIENTE_2'] = ''
        context['FIRMA_VENDEDOR'] = ''
        context['FIRMA_TESTIGO1'] = ''
        context['FIRMA_TESTIGO2'] = ''
        context['FIRMA_BENE'] = ''
    

    # Determinar qué cláusulas adicionales existen
    tiene_pago = clausulas_adicionales and 'pago' in clausulas_adicionales and bool(clausulas_adicionales['pago'])
    tiene_deslinde = clausulas_adicionales and 'deslinde' in clausulas_adicionales and bool(clausulas_adicionales['deslinde'])
    tiene_promesa = clausulas_adicionales and 'promesa' in clausulas_adicionales and bool(clausulas_adicionales['promesa'])
    
    # Formatear cláusulas adicionales
    clausula_pago = clausulas_adicionales['pago'] if tiene_pago else ''
    clausula_deslinde = clausulas_adicionales['deslinde'] if tiene_deslinde else ''
    clausula_promesa = clausulas_adicionales['promesa'] if tiene_promesa else ''
    
    if tiene_pago:
        clausula_e = "E."
        clausula_f = "F."
    else:
        clausula_e = "D."
        clausula_f = "E."

    # Agregar al contexto
    context.update({
        'CLAUSULA_PAGO': clausula_pago.upper(),
        'LETRA_E': clausula_e,
        'LETRA_F': clausula_f,
        'CLAUSULA_DESLINDE': clausula_deslinde.upper(),
        'CLAUSULA_PROMESA': clausula_promesa.upper(),
    })

    return context

def build_contrato_ejidal_pagos_context(fin, cli, ven, request=None, tpl=None, firma_data=None, clausulas_adicionales=None, tramite=None, fecha=None):

    print("Entré al build de ejido a pagos de un comprador")
    #print("Esta es la firma del cliente: "+ firma_data)
    #print("Esta es la firma en request: " + request.session.get('firma_cliente_data'))

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

    SEXO_11 = art(tramite.beneficiario_1.sexo, 'O', 'A')  #SEXO REFERENTE AL BENEFICIARIO
    SEXO_12 = art(tramite.beneficiario_1.sexo, 'EL', 'LA') #EL/LA REFERENTE AL BENEFICIARIO

    # 2) Fecha de cesión (hoy, o fin.fecha_enganche)
    if fecha == None:
        cesion = date.today()
    else:
        cesion = fecha
    meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
    DIA_CESION = numero_a_letras(float(cesion.day),apocopado=False)
    MES_CESION = meses[cesion.month-1].upper()
    ANIO_CESION = numero_a_letras(float(cesion.year),apocopado=False)

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

    testigo1 = (tramite.testigo_1_nombre or '')        # convierte None -> ''
    if testigo1:
        test1 = testigo1.upper()
    else:
        test1 = testigo1
    
    testigo2 = (tramite.testigo_2_nombre or '')        # convierte None -> ''
    if testigo2:
        test2 = testigo2.upper()
    else:
        test2 = testigo2

    # NUEVO: Obtener información del proyecto para determinar tipo de documento
    proyecto = fin.lote.proyecto
    
    # Determinar el texto según el documento disponible
    if proyecto.incluir_cesion_derechos:
        tipo_documento_texto = "CESIÓN DE DERECHOS"
    elif proyecto.incluir_constancia_cesion:
        tipo_documento_texto = "CONSTANCIA DE CESIÓN DE DERECHOS"
    else:
        # Por defecto, aunque en ejido debería tener al menos uno
        tipo_documento_texto = "CONSTANCIA DE POSESIÓN"
        
    # 3) Miembro B dinámico según relación:
    # — Si ven es propietario:
    if ven.ine == prop.ine and prop.tipo == 'propietario':
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, "
            f"QUE ACREDITA CON LA {tipo_documento_texto} DE FECHA {fecha_posesion}"
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

    bene = (tramite.beneficiario_1.nombre_completo or '')        # convierte None -> ''
    if bene:
        benef = bene.upper()
    else:
        benef = bene

    bene_correo = (tramite.beneficiario_1.email or '')
    if bene_correo:
        bene_correo1 = bene_correo.upper()
    else:
        bene_correo1 = bene_correo

    # 5) Construcción del context
    context = {
        'DIA' : DIA_CESION,
        'MES' : MES_CESION,
        'ANIO': ANIO_CESION,
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
        'SEXO_11': SEXO_11,
        'SEXO_12': SEXO_12,

        'NOMBRE_VENDEDOR':    ven.nombre_completo.upper(),
        'NOMBRE_COMPRADOR':   cli.nombre_completo.upper(),

        'DIRECCION_LOTE':     fin.lote.proyecto.ubicacion.upper(),
        'IDENTIFICADOR_LOTE': fin.lote.identificador,
        'LETRA_IDENTIFICADOR': obtener_letra_identificador(fin.lote),  # Cambio aquí

        'DIA_CESION':  DIA_CESION,
        'MES_CESION':  MES_CESION,
        'ANIO_CESION': ANIO_CESION,

        'FECHA_DOCUMENTO': fecha_posesion,
        'NOMBRE_CESION': autoridad,

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

        'MENSUALIDADES_FINANCIAMIENTO':     num_men,
        'MENSUALIDADES': num_men-1,
        'MENSUALIDADES_FIJAS':             num_men-1,
        'CANTIDAD_MENSUALIDAD_FIJA':       fmt_money(monto_fija),
        'LETRA_MENSUALIDAD_FIJA':          letra_fija,

        'CANTIDAD_MENSUALIDAD_FINAL':      fmt_money(monto_final),
        'LETRA_MENSUALIDAD_FINAL':         letra_final,

        'CLAUSULA_B': claus_b,
        'NOMBRE_TESTIGO2': test2,
        'NOMBRE_TESTIGO1': test1,
        #nom_bene = None #Nombre del beneficiario
        #id_bene = None #Clave ine beneficiarii
        #num_bene = None #Número del beneficiario
        #correo_bene = None #Correo del beneficiario
        'NOMBRE_BENE': benef,
        'ID_BENE': tramite.beneficiario_1.numero_id,
        'NUMERO_BENE': tramite.beneficiario_1.telefono,
        'CORREO_BENE': bene_correo1,

        # NUEVO: También puedes incluir el tipo de documento como variable separada si lo necesitas
        'TIPO_DOCUMENTO_EJIDAL': tipo_documento_texto,
    }

    # 6) Firma
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
        context['FIRMA_VENDEDOR'] = crear_firma_unificada(tramite.firma_vendedor)
        context['FIRMA_TESTIGO1'] = crear_firma_unificada(tramite.testigo_1_firma)
        context['FIRMA_TESTIGO2'] = crear_firma_unificada(tramite.testigo_2_firma)
        context['FIRMA_BENE'] = crear_firma_unificada(tramite.beneficiario_1_firma)
        
    else:
        # Valores por defecto si no hay template
        context['FIRMA_CLIENTE'] = ''
        context['FIRMA_VENDEDOR'] = ''
        context['FIRMA_TESTIGO1'] = ''
        context['FIRMA_TESTIGO2'] = ''
        context['FIRMA_BENE'] = ''

    # Determinar qué cláusulas adicionales existen
    tiene_pago = clausulas_adicionales and 'pago' in clausulas_adicionales and bool(clausulas_adicionales['pago'])
    tiene_deslinde = clausulas_adicionales and 'deslinde' in clausulas_adicionales and bool(clausulas_adicionales['deslinde'])
    tiene_promesa = clausulas_adicionales and 'promesa' in clausulas_adicionales and bool(clausulas_adicionales['promesa'])
    
    # Formatear cláusulas adicionales
    clausula_pago = clausulas_adicionales['pago'] if tiene_pago else ''
    clausula_deslinde = clausulas_adicionales['deslinde'] if tiene_deslinde else ''
    clausula_promesa = clausulas_adicionales['promesa'] if tiene_promesa else ''
    
    if tiene_pago:
        clausula_e = "E."
        clausula_f = "F."
        clausula_g = "G."
    else:
        clausula_e = "D."
        clausula_f = "E."
        clausula_g = "F."

    # Agregar al contexto
    context.update({
        'CLAUSULA_PAGO': clausula_pago.upper(),
        'LETRA_E': clausula_e,
        'LETRA_F': clausula_f,
        'LETRA_G': clausula_g,
        'CLAUSULA_DESLINDE': clausula_deslinde.upper(),
        'CLAUSULA_PROMESA': clausula_promesa.upper(),
    })

    return context

def build_contrato_ejidal_pagos_varios_context(fin, cli, ven, cliente2=None,request=None, tpl=None, firma_data=None, clausulas_adicionales=None, tramite=None, fecha=None):
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
    SEXO_7 = art(ven.sexo, 'AL "', 'A "LA ')
    SEXO_8 = art(ven.sexo, 'DEL "', 'DE "LA ')

    # 2) Fecha de cesión (hoy, o fin.fecha_enganche)
    if fecha == None:
        cesion = date.today()
    else:
        cesion = fecha
    meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
    DIA_CESION = numero_a_letras(float(cesion.day), apocopado=False)
    MES_CESION = meses[cesion.month-1].upper()
    ANIO_CESION = numero_a_letras(float(cesion.year),apocopado=False)

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
            SEXO_11 = 'A LOS'
        else:
            # Ambos femeninos -> femenino plural
            SEXO_2 = 'LAS'               # cedatario (comprador)
            SEXO_3 = 'CEDATARIAS' # palabra completa
            SEXO_6 = 'DE "LAS '
            SEXO_9 = 'A "LAS '
            SEXO_10 = 'A'
            SEXO_11 = 'A LAS'
    else:
        # Por si acaso (aunque esta función es para varios)
        SEXO_2 = 'LOS'               # cedatario (comprador)
        SEXO_3 = 'CEDATARIOS' # palabra completa
        SEXO_6 = 'DE "LOS '
        SEXO_9 = 'A "LOS '
        SEXO_10 = 'O'
        SEXO_11 = 'A LOS'

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
    
    testigo1 = (tramite.testigo_1_nombre or '')        # convierte None -> ''
    if testigo1:
        test1 = testigo1.upper()
    else:
        test1 = testigo1
    
    testigo2 = (tramite.testigo_2_nombre or '')        # convierte None -> ''
    if testigo2:
        test2 = testigo2.upper()
    else:
        test2 = testigo2

    SEXO_21 = art(tramite.beneficiario_1.sexo, 'EL', 'LA') #Referente al beneficiario
    SEXO_22 = art(tramite.beneficiario_1.sexo, 'O', 'A') #Referente al beneficiario
    
    bene = (tramite.beneficiario_1.nombre_completo or '')        # convierte None -> ''
    if bene:
        benef = bene.upper()
    else:
        benef = bene
    
    bene_telefono = (tramite.beneficiario_1.telefono or '')
    bene_correo = (tramite.beneficiario_1.email or '')
    if bene_correo:
        bene_correo1 = bene_correo.upper()
    else:
        bene_correo1 = bene_correo
    bene_id = (tramite.beneficiario_1.numero_id or '')

    # NUEVO: Obtener información del proyecto para determinar tipo de documento
    proyecto = fin.lote.proyecto
    
    # Determinar el texto según el documento disponible
    if proyecto.incluir_cesion_derechos:
        tipo_documento_texto = "CESIÓN DE DERECHOS"
    elif proyecto.incluir_constancia_cesion:
        tipo_documento_texto = "CONSTANCIA DE CESIÓN DE DERECHOS"
    else:
        # Por defecto, aunque en ejido debería tener al menos uno
        tipo_documento_texto = "CONSTANCIA DE POSESIÓN"

    # 3) Miembro B dinámico según relación:
    # — Si ven es propietario:
    if ven.ine == prop.ine and prop.tipo == 'propietario':
        claus_b = (
            f"QUE CUENTA CON CAPACIDAD LEGAL PARA CELEBRAR EL PRESENTE CONTRATO, "
            f"QUE ACREDITA CON LA {tipo_documento_texto} DE FECHA {fecha_posesion}"
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
        'ANIO': ANIO_CESION,
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
        'SEXO_11': SEXO_11,

        'NOMBRE_VENDEDOR':    ven.nombre_completo.upper(),
        'NOMBRE_COMPRADOR':   cli.nombre_completo.upper(),

        'DIRECCION_LOTE':     fin.lote.proyecto.ubicacion.upper(),
        'IDENTIFICADOR_LOTE': fin.lote.identificador,
        'LETRA_IDENTIFICADOR': obtener_letra_identificador(fin.lote),  # Cambio aquí

        'DIA_CESION':  DIA_CESION,
        'MES_CESION':  MES_CESION,
        'ANIO_CESION': ANIO_CESION,

        'FECHA_DOCUMENTO': fecha_posesion,
        'NOMBRE_CESION': autoridad,

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

        'MENSUALIDADES_FINANCIAMIENTO':     num_men,
        'MENSUALIDADES': num_men-1,
        'MENSUALIDADES_FIJAS':             num_men-1,
        'CANTIDAD_MENSUALIDAD_FIJA':       fmt_money(monto_fija),
        'LETRA_MENSUALIDAD_FIJA':          letra_fija,

        'CANTIDAD_MENSUALIDAD_FINAL':      fmt_money(monto_final),
        'LETRA_MENSUALIDAD_FINAL':         letra_final,

        'CLAUSULA_B': claus_b,
        'NOMBRE_TESTIGO2': test2,
        'NOMBRE_TESTIGO1': test1,

        #BENEFICIARIO
        'SEXO_22':SEXO_21,
        'SEXO_21': SEXO_22,
        'NOMBRE_BENE': benef,
        'ID_BENE': bene_id,
        'NUMERO_BENE': bene_telefono,
        'CORREO_BENE':bene_correo1,
        # NUEVO: También puedes incluir el tipo de documento como variable separada si lo necesitas
        'TIPO_DOCUMENTO_EJIDAL': tipo_documento_texto,
    }

    # 6) Firma
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
        context['FIRMA_CLIENTE2'] = crear_firma_unificada(tramite.firma_cliente2)
        context['FIRMA_VENDEDOR'] = crear_firma_unificada(tramite.firma_vendedor)
        context['FIRMA_TESTIGO1'] = crear_firma_unificada(tramite.testigo_1_firma)
        context['FIRMA_TESTIGO2'] = crear_firma_unificada(tramite.testigo_2_firma)
        context['FIRMA_BENE'] = crear_firma_unificada(tramite.beneficiario_1_firma)
        
    else:
        # Valores por defecto si no hay template
        context['FIRMA_CLIENTE'] = ''
        context['FIRMA_CLIENTE2'] = ''
        context['FIRMA_VENDEDOR'] = ''
        context['FIRMA_TESTIGO1'] = ''
        context['FIRMA_TESTIGO2'] = ''
        context['FIRMA_BENE'] = ''

    # Determinar qué cláusulas adicionales existen
    tiene_pago = clausulas_adicionales and 'pago' in clausulas_adicionales and bool(clausulas_adicionales['pago'])
    tiene_deslinde = clausulas_adicionales and 'deslinde' in clausulas_adicionales and bool(clausulas_adicionales['deslinde'])
    tiene_promesa = clausulas_adicionales and 'promesa' in clausulas_adicionales and bool(clausulas_adicionales['promesa'])
    
    # Formatear cláusulas adicionales
    clausula_pago = clausulas_adicionales['pago'] if tiene_pago else ''
    clausula_deslinde = clausulas_adicionales['deslinde'] if tiene_deslinde else ''
    clausula_promesa = clausulas_adicionales['promesa'] if tiene_promesa else ''
    
    if tiene_pago:
        clausula_e = "E."
        clausula_f = "F."
        clausula_g = "G."
    else:
        clausula_e = "D."
        clausula_f = "E."
        clausula_g = "F."

    # Agregar al contexto
    context.update({
        'CLAUSULA_PAGO': clausula_pago.upper(),
        'LETRA_E': clausula_e,
        'LETRA_F': clausula_f,
        'LETRA_G': clausula_g,
        'CLAUSULA_DESLINDE': clausula_deslinde.upper(),
        'CLAUSULA_PROMESA': clausula_promesa.upper(),
    })
    
    return context

def build_contrato_canario_contado_context(fin, cli, ven, request=None, tpl=None, firma_data=None, clausulas_adicionales=None, tramite=None, fecha=None):

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
    if fecha == None:
        dia_actual = date.today()
    else:
        dia_actual = fecha
    email = (cli.email or '')        # convierte None -> ''
    email = email.strip()            # quita espacios en blanco
    if email:
        correo_comprador = email.upper()
    else:
        correo_comprador = 'NO PROPORCIONADO'

    testigo1 = (tramite.testigo_1_nombre or '')        # convierte None -> ''
    if testigo1:
        test1 = testigo1.upper()
    else:
        test1 = testigo1
    
    testigo2 = (tramite.testigo_2_nombre or '')        # convierte None -> ''
    if testigo2:
        test2 = testigo2.upper()
    else:
        test2 = testigo2

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
            f"TAL COMO SE ACREDITA EN EL CONTRATO DE EXCLUSIVIDAD, PROMOCIÓN Y COMISIÓN POR LA VENTA DEL BIEN INMUEBLE DE FECHA SEIS DE ENERO DE DOS MIL VEINTICINCO"
            f", OTORGADO POR EL C. JORGE EMILIO ALAVEZ AGUILAR."
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
        'ANIO': numero_a_letras(float(dia_actual.year),apocopado=False),

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
        'NOMBRE_TESTIGO2': test2,
        'NOMBRE_TESTIGO1': test1,
    }

    # 6) Firma
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
        context['FIRMA_VENDEDOR'] = crear_firma_unificada(tramite.firma_vendedor)
        context['FIRMA_TESTIGO1'] = crear_firma_unificada(tramite.testigo_1_firma)
        context['FIRMA_TESTIGO2'] = crear_firma_unificada(tramite.testigo_2_firma)
        context['FIRMA_BENE'] = crear_firma_unificada(tramite.beneficiario_1_firma)
        
    else:
        # Valores por defecto si no hay template
        context['FIRMA_CLIENTE'] = ''
        context['FIRMA_VENDEDOR'] = ''
        context['FIRMA_TESTIGO1'] = ''
        context['FIRMA_TESTIGO2'] = ''
        context['FIRMA_BENE'] = ''

    # Determinar qué cláusulas adicionales existen
    tiene_pago = clausulas_adicionales and 'pago' in clausulas_adicionales and bool(clausulas_adicionales['pago'])
    tiene_deslinde = clausulas_adicionales and 'deslinde' in clausulas_adicionales and bool(clausulas_adicionales['deslinde'])
    tiene_promesa = clausulas_adicionales and 'promesa' in clausulas_adicionales and bool(clausulas_adicionales['promesa'])
    
    # Formatear cláusulas adicionales
    clausula_pago = clausulas_adicionales['pago'] if tiene_pago else ''
    clausula_deslinde = clausulas_adicionales['deslinde'] if tiene_deslinde else ''
    clausula_promesa = clausulas_adicionales['promesa'] if tiene_promesa else ''
    
    if tiene_pago:
        clausula_e = "E."
        clausula_f = "F."
    else:
        clausula_e = "D."
        clausula_f = "E."

    # Agregar al contexto
    context.update({
        'CLAUSULA_PAGO': clausula_pago.upper(),
        'LETRA_E': clausula_e,
        'LETRA_F': clausula_f,
        'CLAUSULA_DESLINDE': clausula_deslinde.upper(),
        'CLAUSULA_PROMESA': clausula_promesa.upper(),
    })

    return context

def build_contrato_canario_contado_varios_context(fin, cli, ven, cliente2=None,request=None, tpl=None, firma_data=None, clausulas_adicionales=None, tramite=None, fecha=None):
    
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
    if fecha == None:
        pago = date.today()
    else:
        pago = fecha
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

    testigo1 = (tramite.testigo_1_nombre or '')        # convierte None -> ''
    if testigo1:
        test1 = testigo1.upper()
    else:
        test1 = testigo1
    
    testigo2 = (tramite.testigo_2_nombre or '')        # convierte None -> ''
    if testigo2:
        test2 = testigo2.upper()
    else:
        test2 = testigo2

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
            f"TAL COMO SE ACREDITA EN EL CONTRATO DE EXCLUSIVIDAD, PROMOCIÓN Y COMISIÓN POR LA VENTA DEL BIEN INMUEBLE DE FECHA SEIS DE ENERO DE DOS MIL VEINTICINCO, "
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
        'ANIO': numero_a_letras(float(pago.year),apocopado=False),

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
        'NOMBRE_TESTIGO2': test2,
        'NOMBRE_TESTIGO1': test1,
    }

    # 6) Firma
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
        context['FIRMA_CLIENTE2'] = crear_firma_unificada(tramite.firma_cliente2)
        context['FIRMA_VENDEDOR'] = crear_firma_unificada(tramite.firma_vendedor)
        context['FIRMA_TESTIGO1'] = crear_firma_unificada(tramite.testigo_1_firma)
        context['FIRMA_TESTIGO2'] = crear_firma_unificada(tramite.testigo_2_firma)
        context['FIRMA_BENE'] = crear_firma_unificada(tramite.beneficiario_1_firma)
        
    else:
        # Valores por defecto si no hay template
        context['FIRMA_CLIENTE'] = ''
        context['FIRMA_CLIENTE_2'] = ''
        context['FIRMA_VENDEDOR'] = ''
        context['FIRMA_TESTIGO1'] = ''
        context['FIRMA_TESTIGO2'] = ''
        context['FIRMA_BENE'] = ''

    # 9) Cláusulas adicionales
    # Determinar qué cláusulas adicionales existen
    tiene_pago = clausulas_adicionales and 'pago' in clausulas_adicionales and bool(clausulas_adicionales['pago'])
    tiene_deslinde = clausulas_adicionales and 'deslinde' in clausulas_adicionales and bool(clausulas_adicionales['deslinde'])
    tiene_promesa = clausulas_adicionales and 'promesa' in clausulas_adicionales and bool(clausulas_adicionales['promesa'])
    
    # Formatear cláusulas adicionales
    clausula_pago = clausulas_adicionales['pago'] if tiene_pago else ''
    clausula_deslinde = clausulas_adicionales['deslinde'] if tiene_deslinde else ''
    clausula_promesa = clausulas_adicionales['promesa'] if tiene_promesa else ''
    
    if tiene_pago:
        clausula_e = "E."
        clausula_f = "F."
    else:
        clausula_e = "D."
        clausula_f = "E."

    # Agregar al contexto
    context.update({
        'CLAUSULA_PAGO': clausula_pago.upper(),
        'LETRA_E': clausula_e,
        'LETRA_F': clausula_f,
        'CLAUSULA_DESLINDE': clausula_deslinde.upper(),
        'CLAUSULA_PROMESA': clausula_promesa.upper(),
    })

    return context

def build_contrato_canario_pagos_context(fin, cli, ven, request=None, tpl=None, firma_data=None, clausulas_adicionales=None, tramite=None, fecha=None):

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

    SEXO_11 = art(tramite.beneficiario_1.sexo, 'EL', 'LA') #Referente al beneficiario
    SEXO_12 = art(tramite.beneficiario_1.sexo, 'O', 'A') #Referente al beneficiario

    # 2) Fecha actual
    if fecha == None:
        hoy = date.today()
    else:
        hoy = fecha
    meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
    DIA, MES = numero_a_letras(float(hoy.day),apocopado=False), meses[hoy.month-1].upper()
    ANIO = numero_a_letras(float(hoy.year),apocopado=False)

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

    testigo1 = (tramite.testigo_1_nombre or '')        # convierte None -> ''
    if testigo1:
        test1 = testigo1.upper()
    else:
        test1 = testigo1
    
    testigo2 = (tramite.testigo_2_nombre or '')        # convierte None -> ''
    if testigo2:
        test2 = testigo2.upper()
    else:
        test2 = testigo2

    bene = (tramite.beneficiario_1.nombre_completo or '')        # convierte None -> ''
    if bene:
        benef = bene.upper()
    else:
        benef = bene
    
    bene_telefono = (tramite.beneficiario_1.telefono or '')
    bene_correo = (tramite.beneficiario_1.email or '')
    if bene_correo:
        bene_correo1 = bene_correo.upper()
    else:
        bene_correo1 = bene_correo
    bene_id = (tramite.beneficiario_1.numero_id or '')

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
            f"TAL COMO SE ACREDITA EN EL CONTRATO DE EXCLUSIVIDAD, PROMOCIÓN Y COMISIÓN POR LA VENTA DEL BIEN INMUEBLE DE FECHA SEIS DE ENERO DE DOS MIL VEINTICINCO, "
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
        'DIA': DIA, 'MES': MES, 'ANIO':ANIO,

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

        'MENSUALIDADES_FINANCIAMIENTO':     num_men,
        'MENSUALIDADES': num_men-1,
        'MENSUALIDADES_FIJAS':             num_men-1,
        'CANTIDAD_MENSUALIDAD_FIJA':       fmt_money(fija),
        'LETRA_MENSUALIDAD_FIJA':          letra_fija,

        'CANTIDAD_MENSUALIDAD_FINAL':      fmt_money(final),
        'LETRA_MENSUALIDAD_FINAL':         letra_fin,
        # Y la cláusula B variable:
        'CLAUSULA_B': claus_b,
        'NOMBRE_TESTIGO2': test2,
        'NOMBRE_TESTIGO1': test1,

        #BENEFICIARIO
        'SEXO_11':SEXO_11,
        'SEXO_12': SEXO_12,
        'NOMBRE_BENE': benef,
        'ID_BENE': bene_id,
        'NUMERO_BENE': bene_telefono,
        'CORREO_BENE':bene_correo1,
    }

    # 6) Firma
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
        context['FIRMA_VENDEDOR'] = crear_firma_unificada(tramite.firma_vendedor)
        context['FIRMA_TESTIGO1'] = crear_firma_unificada(tramite.testigo_1_firma)
        context['FIRMA_TESTIGO2'] = crear_firma_unificada(tramite.testigo_2_firma)
        context['FIRMA_BENE'] = crear_firma_unificada(tramite.beneficiario_1_firma)
        
    else:
        # Valores por defecto si no hay template
        context['FIRMA_CLIENTE'] = ''
        context['FIRMA_VENDEDOR'] = ''
        context['FIRMA_TESTIGO1'] = ''
        context['FIRMA_TESTIGO2'] = ''
        context['FIRMA_BENE'] = ''

    # Determinar qué cláusulas adicionales existen
    tiene_pago = clausulas_adicionales and 'pago' in clausulas_adicionales and bool(clausulas_adicionales['pago'])
    tiene_deslinde = clausulas_adicionales and 'deslinde' in clausulas_adicionales and bool(clausulas_adicionales['deslinde'])
    tiene_promesa = clausulas_adicionales and 'promesa' in clausulas_adicionales and bool(clausulas_adicionales['promesa'])
    
    # Formatear cláusulas adicionales
    clausula_pago = clausulas_adicionales['pago'] if tiene_pago else ''
    clausula_deslinde = clausulas_adicionales['deslinde'] if tiene_deslinde else ''
    clausula_promesa = clausulas_adicionales['promesa'] if tiene_promesa else ''
    
    if tiene_pago:
        clausula_e = "E."
        clausula_f = "F."
        clausula_g = "G."
    else:
        clausula_e = "D."
        clausula_f = "E."
        clausula_g = "F."

    # Agregar al contexto
    context.update({
        'CLAUSULA_PAGO': clausula_pago.upper(),
        'LETRA_E': clausula_e,
        'LETRA_F': clausula_f,
        'LETRA_G': clausula_g,
        'CLAUSULA_DESLINDE': clausula_deslinde.upper(),
        'CLAUSULA_PROMESA': clausula_promesa.upper(),
    })

    return context

def build_contrato_canario_pagos_varios_context(fin, cli, ven, cliente2=None,request=None, tpl=None, firma_data=None, clausulas_adicionales=None, tramite=None, fecha=None):

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
    if fecha == None:
        hoy = date.today()
    else:
        hoy = fecha
    meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
    DIA, MES = numero_a_letras(float(hoy.day),apocopado=False), meses[hoy.month-1].upper()
    ANIO = numero_a_letras(float(hoy.year),apocopado=False)

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

    testigo1 = (tramite.testigo_1_nombre or '')        # convierte None -> ''
    if testigo1:
        test1 = testigo1.upper()
    else:
        test1 = testigo1
    
    testigo2 = (tramite.testigo_2_nombre or '')        # convierte None -> ''
    if testigo2:
        test2 = testigo2.upper()
    else:
        test2 = testigo2

    SEXO_21 = art(tramite.beneficiario_1.sexo, 'EL', 'LA') #Referente al beneficiario
    SEXO_22 = art(tramite.beneficiario_1.sexo, 'O', 'A') #Referente al beneficiario

    bene = (tramite.beneficiario_1.nombre_completo or '')        # convierte None -> ''
    if bene:
        benef = bene.upper()
    else:
        benef = bene

    bene_telefono = (tramite.beneficiario_1.telefono or '')
    bene_correo = (tramite.beneficiario_1.email or '')
    if bene_correo:
        bene_correo1 = bene_correo.upper()
    else:
        bene_correo1 = bene_correo
    bene_id = (tramite.beneficiario_1.numero_id or '')

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
            f"TAL COMO SE ACREDITA EN EL CONTRATO DE EXCLUSIVIDAD, PROMOCIÓN Y COMISIÓN POR LA VENTA DEL BIEN INMUEBLE DE FECHA SEIS DE ENERO DE DOS MIL VEINTICINCO, "
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
        'DIA': DIA, 'MES': MES, 'ANIO': ANIO,

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

        'MENSUALIDADES_FINANCIAMIENTO':     num_men,
        'MENSUALIDADES': num_men-1,
        'MENSUALIDADES_FIJAS':             f"{fija:.2f}",
        'CANTIDAD_MENSUALIDAD_FIJA':       fmt_money(fija),
        'LETRA_MENSUALIDAD_FIJA':          letra_fija,

        'CANTIDAD_MENSUALIDAD_FINAL':      fmt_money(final),
        'LETRA_MENSUALIDAD_FINAL':         letra_fin,
        # Y la cláusula B variable:
        'CLAUSULA_B': claus_b,
        'NOMBRE_TESTIGO2': test2,
        'NOMBRE_TESTIGO1': test1,

        #BENEFICIARIO
        'SEXO_21':SEXO_21,
        'SEXO_22': SEXO_22,
        'NOMBRE_BENE': benef,
        'ID_BENE': bene_id,
        'NUMERO_BENE': bene_telefono,
        'CORREO_BENE':bene_correo1,
    }

    # 6) Firma
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
        context['FIRMA_CLIENTE2'] = crear_firma_unificada(tramite.firma_cliente2)
        context['FIRMA_VENDEDOR'] = crear_firma_unificada(tramite.firma_vendedor)
        context['FIRMA_TESTIGO1'] = crear_firma_unificada(tramite.testigo_1_firma)
        context['FIRMA_TESTIGO2'] = crear_firma_unificada(tramite.testigo_2_firma)
        context['FIRMA_BENE'] = crear_firma_unificada(tramite.beneficiario_1_firma)
        
    else:
        # Valores por defecto si no hay template
        context['FIRMA_CLIENTE'] = ''
        context['FIRMA_CLIENTE_2'] = ''
        context['FIRMA_VENDEDOR'] = ''
        context['FIRMA_TESTIGO1'] = ''
        context['FIRMA_TESTIGO2'] = ''
        context['FIRMA_BENE'] = ''

    # Determinar qué cláusulas adicionales existen
    tiene_pago = clausulas_adicionales and 'pago' in clausulas_adicionales and bool(clausulas_adicionales['pago'])
    tiene_deslinde = clausulas_adicionales and 'deslinde' in clausulas_adicionales and bool(clausulas_adicionales['deslinde'])
    tiene_promesa = clausulas_adicionales and 'promesa' in clausulas_adicionales and bool(clausulas_adicionales['promesa'])
    
    # Formatear cláusulas adicionales
    clausula_pago = clausulas_adicionales['pago'] if tiene_pago else ''
    clausula_deslinde = clausulas_adicionales['deslinde'] if tiene_deslinde else ''
    clausula_promesa = clausulas_adicionales['promesa'] if tiene_promesa else ''
    
    if tiene_pago:
        clausula_e = "E."
        clausula_f = "F."
        clausula_g = "G."
    else:
        clausula_e = "D."
        clausula_f = "E."
        clausula_g = "F."

    # Agregar al contexto
    context.update({
        'CLAUSULA_PAGO': clausula_pago.upper(),
        'LETRA_E': clausula_e,
        'LETRA_F': clausula_f,
        'LETRA_G': clausula_g,
        'CLAUSULA_DESLINDE': clausula_deslinde.upper(),
        'CLAUSULA_PROMESA': clausula_promesa.upper(),
    })

    return context

def calcular_porcentaje_moratorio(monto_vencido: float) -> int:
    """
    Calcula el porcentaje de interés moratorio mensual basado en el monto del pago vencido.

    Lógica derivada del ejemplo del cliente:
      - Pago de $4,500 → 23% → interés = $1,035 (dentro del rango $1,000–$1,100)

    Para pagos variables (meses fuertes), el porcentaje escala inversamente
    para mantener el monto del interés en un rango proporcional y razonable.

    Retorna un número entero (%).

    NOTE: Esta función es una aproximación basada en información incompleta del cliente.
          Ajustar los parámetros TASA_BASE, MONTO_BASE y RANGO_* según se aclare.
    """
    # ── Parámetros base (derivados del ejemplo del cliente) ──────────────────
    TASA_BASE   = 23      # % que aplica al monto de referencia
    MONTO_BASE  = 4_500   # monto de mensualidad "normal" de referencia
    INTERES_OBJ = round(MONTO_BASE * TASA_BASE / 100, 2)  # ~$1,035 objetivo

    # ── Límites de seguridad para el porcentaje resultante ───────────────────
    TASA_MINIMA = 5   # nunca bajar de este % (evita que meses fuertes sean irrisorios)
    TASA_MAXIMA = 30  # nunca superar este % (evita mora abusiva en meses normales bajos)

    if monto_vencido <= 0:
        return 0

    # Porcentaje que produciría el mismo monto de interés que en el caso base
    # Escala inversamente: a mayor monto, menor tasa (pero el peso en pesos sube igual)
    porcentaje = (INTERES_OBJ / monto_vencido) * 100

    # Clampear dentro de los límites y redondear a entero
    porcentaje = max(TASA_MINIMA, min(TASA_MAXIMA, porcentaje))

    return round(porcentaje)


def calcular_interes_moratorio(monto_vencido: float) -> dict:
    """
    Calcula el interés moratorio completo para un pago vencido.

    Retorna un dict con:
      - porcentaje: tasa aplicada (int, %)
      - interes:    monto del interés en pesos (float)
      - total:      monto_vencido + interes (float)
      - porcentaje_letras: tasa en texto para cláusula del contrato
      - interes_letras:    monto de interés en letras (usa tu numero_a_letras)
      - total_letras:      total en letras
    """
    porcentaje = calcular_porcentaje_moratorio(monto_vencido)
    interes    = round(monto_vencido * porcentaje / 100, 2)
    total      = round(monto_vencido + interes, 2)

    return {
        "porcentaje":         porcentaje,
        "interes":            interes,
        "total":              total,
        "porcentaje_letras":  numero_a_letras(porcentaje, apocopado=False),
        "interes_letras":     numero_a_letras(interes),
        "total_letras":       numero_a_letras(total),
    }

def get_monto_mensualidad_normal(fin) -> float:
    """
    Obtiene el monto de la mensualidad base según el esquema de pagos.
    - Si no es Commeta o no tiene detalle → fin.monto_mensualidad
    - Si es Commeta con meses fuertes     → fin.detalle_commeta.monto_mensualidad_normal
    - Si es Commeta con mensualidades fijas → fin.monto_mensualidad
    """
    if not fin.es_commeta:
        return float(fin.monto_mensualidad or 0)

    # Es Commeta: verificar si tiene detalle y qué esquema usa
    try:
        detalle = fin.detalle_commeta
    except Exception:
        # Es Commeta pero aún no tiene detalle_commeta creado
        return float(fin.monto_mensualidad or 0)

    if detalle.tipo_esquema == 'meses_fuertes':
        return float(detalle.monto_mensualidad_normal or 0)

    # tipo_esquema == 'mensualidades_fijas'
    return float(fin.monto_mensualidad or 0)

def get_porcentaje_cometa(lotes):

    lote = int(lotes)

    # AMBAR: L2, L8, L9
    if lote in [2, 8, 9]:
        return 5

    # AQUA: L4,L5,L6,L10,L11,L13,L14,L15,L40,L41,L42,L43,L44,L45,L46,L47,L48,L49,L50
    if lote in [4, 5, 6, 10, 11, 13, 14, 15, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50]:
        return 18

    # AQUA: L12
    if lote == 12:
        return 8

    # AQUA: L16
    if lote == 16:
        return 7

    # MAGNETITA: L17,L18,L19,L29,L30,L31,L32,L34,L52,L53
    if lote in [17, 18, 19, 29, 30, 31, 32, 34, 52, 53]:
        return 23

    # PLATINO: L20,L21,L22,L24,L25,L26,L27,L28,L35,L36,L37,L38,L39,L54,L55,L56,L57,L58
    if lote in [20, 21, 22, 24, 25, 26, 27, 28, 35, 36, 37, 38, 39, 54, 55, 56, 57, 58]:
        return 29

    # PLATINO: L23
    if lote == 23:
        return 9

    return 0

def build_contrato_commeta_pagos_context(fin, cli, ven, request=None, tpl=None, firma_data=None, clausulas_adicionales=None, tramite=None, fecha=None):

    print("Entré al build de commeta a pagos de un comprador")
    
    if clausulas_adicionales is None:
        clausulas_adicionales = {}

    # 1) Pronombres según sexo (necesitarás un campo sexo en Cliente y Vendedor)
    def art(sex, masculino, femenino):
        return masculino if sex == 'M' else femenino

    SEXO_1 = art(cli.sexo, 'EL', 'LA')               # cedente (vendedor)
    SEXO_2 = art(cli.sexo, 'O', 'A')                # letra
    SEXO_4 = art(cli.sexo, "AL", "A LA")
    SEXO_5 = art(cli.sexo, 'DEL "', 'DE "LA ')
    
    SEXO_6 = art(tramite.beneficiario_1.sexo, 'O', 'A')  #SEXO REFERENTE AL BENEFICIARIO
    SEXO_7 = art(tramite.beneficiario_1.sexo, 'EL', 'LA') #EL/LA REFERENTE AL BENEFICIARIO

    # 2) Fecha de cesión (hoy, o fin.fecha_enganche)
    if fecha == None:
        cesion = date.today()
    else:
        cesion = fecha
    meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
    DIA = numero_a_letras(float(cesion.day),apocopado=False)
    MES = meses[cesion.month-1].upper()
    ANIO = numero_a_letras(float(cesion.year),apocopado=False)

    fecha_inicio = fin.fecha_primer_pago

    dia_ini = numero_a_letras(float(fecha_inicio.day), apocopado=False)
    mes_ini = meses[fecha_inicio.month-1].upper()
    anio_ini = numero_a_letras(float(fecha_inicio.year),apocopado=False)

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
    monto_fija = get_monto_mensualidad_normal(fin)
    moratorio  = calcular_interes_moratorio(monto_fija)

    email1 = (cli.email or '')        # convierte None -> ''
    email1 = email1.strip()            # quita espacios en blanco
    if email1:
        correo_comprador1 = email1.upper()
    else:
        correo_comprador1 = 'NO PROPORCIONADO'

    testigo1 = (tramite.testigo_1_nombre or '')        # convierte None -> ''
    if testigo1:
        test1 = testigo1.upper()
    else:
        test1 = testigo1
    
    testigo2 = (tramite.testigo_2_nombre or '')        # convierte None -> ''
    if testigo2:
        test2 = testigo2.upper()
    else:
        test2 = testigo2

    bene = (tramite.beneficiario_1.nombre_completo or '')        # convierte None -> ''
    if bene:
        benef = bene.upper()
    else:
        benef = bene

    bene_numero = (tramite.beneficiario_1.telefono or '')
    if bene_numero:
        bene_numero1 = bene_numero
    else:
        bene_numero1 = 'NO ESPECIFICADO'

    bene_correo = (tramite.beneficiario_1.email or '')
    if bene_correo:
        bene_correo1 = bene_correo.upper()
    else:
        bene_correo1 = 'NO ESPECIFICADO'

    vecino = (tramite.vecino or '')
    if vecino:
        vecin = vecino.upper()
    else:
        vecin = 'NO ESPECIFICADO'

    LUGAR_FIRMA_OPCIONES = {
        False: "EN LA COMUNIDAD DE SAN ANTONIO DE LA CAL, MUNICIPIO DE SU MISMO NOMBRE, OAXACA DE JUÁREZ",
        True:  "EN LA COMUNIDAD SANTA MARIA TONAMECA, MUNICIPIO DE SU MISMO NOMBRE, DISTRITO DE POCHUTLA, ESTADO DE OAXACA",
    }

    # 5) Construcción del context
    context = {
        'LUGAR_FIRMA': LUGAR_FIRMA_OPCIONES[tramite.es_tonameca],
        'DIA' : DIA,
        'MES' : MES,
        'ANIO': ANIO,
        'SEXO_1': SEXO_1,
        'SEXO_2': SEXO_2,
        'SEXO_4': SEXO_4,
        'SEXO_5': SEXO_5,
        'SEXO_6': SEXO_6,
        'SEXO_7': SEXO_7,

        'NOMBRE_CEDA':   cli.nombre_completo.upper(),

        'ID_LOTE': fin.lote.identificador,
        'MANZ': fin.lote.manzana,
        
        'DOMICILIO':cli.domicilio.upper(),
        'ID_CESA':   cli.numero_id,
        'LUGAR_ORIGEN':       cli.originario.upper(),
        'ESTADO_CIVIL':       cli.estado_civil.upper(),
        'TELEFONO': cli.telefono,
        'OCUPACION':cli.ocupacion.upper(),
        'CORREO':   correo_comprador1,
        'VECINO': vecin,
        'EDAD': tramite.edad_cliente_1,

        **coords,

        'PRECIO_LOTE_FINANCIAMIENTO': fmt_money(fin.precio_lote),
        'LETRA_PRECIO_LOTE':          numero_a_letras(float(fin.precio_lote)),
        'APARTADO':    fmt_money(fin.apartado),
        'LETRA_APARTADO':             numero_a_letras(float(fin.apartado)),

        'DIA_ENGANCHE':               eng_dia,
        'MES_ENGANCHE':               eng_mes,
        'ANIO_ENGANCHE':              eng_anio,
        'CANTIDAD_ENGANCHE_FINANCIAMIENTO': fmt_money(cant_eng),
        'LETRA_ENGANCHE':                  letra_eng,

        'FECHA_INICIO': fecha_inicio.day,
        'DIA_PAGO': (fecha_inicio + timedelta(days=3)).day,
        'METROS_CUADRADOS': fin.lote.superficie_m2,
        'PORCENTAJE': get_porcentaje_cometa(fin.lote.identificador),

        'NOMBRE_TEST2': test2,
        'NOMBRE_TEST1': test1,
        'ID_TEST2': tramite.testigo_2_idmex or '',
        'ID_TEST1': tramite.testigo_1_idmex or '',
        'NOMBRE_BENE': benef,
        'ID_BENE': tramite.beneficiario_1.numero_id,
        'NUMERO_BENE': bene_numero1,
        'CORREO_BENE': bene_correo1,
    }

    # 6) Firma
    if request and tpl:
        # Tamaño consistente para TODAS las firmas
        FIRMA_ANCHO = 40  # 40mm de ancho
        FIRMA_ALTO = 15   # 15mm de alto
        
        # Función reutilizable para procesar firmas
        def crear_firma_unificada(data_url, prueba=None):
            if not data_url:
                return ''
            ancho = FIRMA_ANCHO
            alto = FIRMA_ALTO
            if prueba == 'si':
                ancho = 20  # 40mm de ancho
                alto = 9.25   # 15mm de alto
            
            try:
                # Decodificar base64
                header, b64 = data_url.split(',', 1)
                img_data = base64.b64decode(b64)
                
                # Crear archivo temporal
                fd, temp_path = tempfile.mkstemp(suffix='.png')
                with os.fdopen(fd, 'wb') as f:
                    f.write(img_data)
                # ✅ MISMO TAMAÑO para todas las firmas
                return InlineImage(tpl, temp_path, width=Mm(ancho), height=Mm(alto))
                
            except Exception as e:
                print(f"Error al procesar firma: {e}")
                return ''
        
        # Procesar cada firma con el mismo tamaño
        context['FIRMA_CLIENTE'] = crear_firma_unificada(firma_data)
        context['FIRMA_VENDEDOR'] = crear_firma_unificada(tramite.firma_vendedor)
        context['FIRMA_TESTIGO1'] = crear_firma_unificada(tramite.testigo_1_firma)
        context['FIRMA_TESTIGO2'] = crear_firma_unificada(tramite.testigo_2_firma)
        context['FIRMA_BENE'] = crear_firma_unificada(tramite.beneficiario_1_firma)
        
    else:
        # Valores por defecto si no hay template
        context['FIRMA_CLIENTE'] = ''
        context['FIRMA_VENDEDOR'] = ''
        context['FIRMA_TESTIGO1'] = ''
        context['FIRMA_TESTIGO2'] = ''
        context['FIRMA_BENE'] = ''

    return context

def build_contrato_commeta_pagos_varios_context(fin, cli, ven, cliente2=None, request=None, tpl=None, firma_data=None, clausulas_adicionales=None, tramite=None, fecha=None):

    print("Entré al build de commeta a pagos de un comprador")
    
    if clausulas_adicionales is None:
        clausulas_adicionales = {}

    # 1) Pronombres según sexo (necesitarás un campo sexo en Cliente y Vendedor)
    def art(sex, masculino, femenino):
        return masculino if sex == 'M' else femenino

    SEXO_6 = art(tramite.beneficiario_1.sexo, 'O', 'A')  #SEXO REFERENTE AL BENEFICIARIO
    SEXO_7 = art(tramite.beneficiario_1.sexo, 'EL', 'LA') #EL/LA REFERENTE AL BENEFICIARIO

    if cliente2:
        if cli.sexo == 'M' or cliente2.sexo == 'M':
            # Si al menos uno es masculino -> masculino plural
            
            SEXO_1 = 'LOS'               # cedatario (comprador)
            SEXO_5 = 'DE "LOS '
            SEXO_4 = 'A "LOS '
            SEXO_2 = 'O'
        else:
            # Ambos femeninos -> femenino plural
            SEXO_1 = 'LAS'               # cedatario (comprador)
            SEXO_5 = 'DE "LAS '
            SEXO_4 = 'A "LAS '
            SEXO_2 = 'A'
    else:
        # Por si acaso (aunque esta función es para varios)
        SEXO_1 = 'LOS'               # cedatario (comprador)
        SEXO_5 = 'DE "LOS '
        SEXO_4 = 'A "LOS '
        SEXO_2 = 'O'

    # 2) Fecha de cesión (hoy, o fin.fecha_enganche)
    if fecha == None:
        cesion = date.today()
    else:
        cesion = fecha
    meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
    DIA = numero_a_letras(float(cesion.day),apocopado=False)
    MES = meses[cesion.month-1].upper()
    ANIO = numero_a_letras(float(cesion.year),apocopado=False)

    fecha_inicio = fin.fecha_primer_pago

    dia_ini = numero_a_letras(float(fecha_inicio.day), apocopado=False)
    mes_ini = meses[fecha_inicio.month-1].upper()
    anio_ini = numero_a_letras(float(fecha_inicio.year),apocopado=False)

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
    monto_fija = get_monto_mensualidad_normal(fin)
    moratorio  = calcular_interes_moratorio(monto_fija)

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

    testigo1 = (tramite.testigo_1_nombre or '')        # convierte None -> ''
    if testigo1:
        test1 = testigo1.upper()
    else:
        test1 = testigo1
    
    testigo2 = (tramite.testigo_2_nombre or '')        # convierte None -> ''
    if testigo2:
        test2 = testigo2.upper()
    else:
        test2 = testigo2

    bene = (tramite.beneficiario_1.nombre_completo or '')        # convierte None -> ''
    if bene:
        benef = bene.upper()
    else:
        benef = bene

    bene_numero = (tramite.beneficiario_1.telefono or '')
    if bene_numero:
        bene_numero1 = bene_numero
    else:
        bene_numero1 = 'NO ESPECIFICADO'

    bene_correo = (tramite.beneficiario_1.email or '')
    if bene_correo:
        bene_correo1 = bene_correo.upper()
    else:
        bene_correo1 = 'NO ESPECIFICADO'

    vecino = (tramite.vecino or '')
    if vecino:
        vecin = vecino.upper()
    else:
        vecin = 'NO ESPECIFICADO'

    LUGAR_FIRMA_OPCIONES = {
        False: "EN LA COMUNIDAD DE SAN ANTONIO DE LA CAL, MUNICIPIO DE SU MISMO NOMBRE, OAXACA DE JUÁREZ",
        True:  "EN LA COMUNIDAD SANTA MARIA TONAMECA, MUNICIPIO DE SU MISMO NOMBRE, DISTRITO DE POCHUTLA, ESTADO DE OAXACA",
    }

    # 5) Construcción del context
    context = {
        'LUGAR_FIRMA': LUGAR_FIRMA_OPCIONES[tramite.es_tonameca],
        'DIA' : DIA,
        'MES' : MES,
        'ANIO': ANIO,
        'SEXO_1': SEXO_1,
        'SEXO_2': SEXO_2,
        'SEXO_4': SEXO_4,
        'SEXO_5': SEXO_5,
        'SEXO_6': SEXO_6,
        'SEXO_7': SEXO_7,

        'NOMBRE_CEDA':   cli.nombre_completo.upper(),

        'ID_LOTE': fin.lote.identificador,
        'MANZ': fin.lote.manzana,
        
        'DOMICILIO':cli.domicilio.upper(),
        'ID_CESA':   cli.numero_id,
        'LUGAR_ORIGEN':       cli.originario.upper(),
        'ESTADO_CIVIL':       cli.estado_civil.upper(),
        'TELEFONO': cli.telefono,
        'OCUPACION':cli.ocupacion.upper(),
        'CORREO':   correo_comprador1,
        'VECINO': vecin,
        'EDAD': tramite.edad_cliente_1,

        # Segundo Cliente/Comprador
        'NOMBRE_CEDA_2':   cliente2.nombre_completo.upper() if cliente2 else '',
        'DOMICILIO_2':cliente2.domicilio.upper() if cliente2 else '',
        'ID_CESA_2':   cliente2.numero_id.upper() if cliente2 else '',
        'LUGAR_ORIGEN_2':       cliente2.originario.upper() if cliente2 else '',
        'ESTADO_CIVIL_2':       cliente2.estado_civil.upper() if cliente2 else '',
        'TELEFONO_2': cliente2.telefono.upper() if cliente2 else '',
        'OCUPACION_2':cliente2.ocupacion.upper() if cliente2 else '',
        'CORREO_2':   correo_comprador2 if cliente2 else '',
        'VECINO_2': vecin,
        'EDAD_2': tramite.edad_cliente_2,

        **coords,

        'PRECIO_LOTE_FINANCIAMIENTO': fmt_money(fin.precio_lote),
        'LETRA_PRECIO_LOTE':          numero_a_letras(float(fin.precio_lote)),
        'APARTADO':    fmt_money(fin.apartado),
        'LETRA_APARTADO':             numero_a_letras(float(fin.apartado)),

        'DIA_ENGANCHE':               eng_dia,
        'MES_ENGANCHE':               eng_mes,
        'ANIO_ENGANCHE':              eng_anio,
        'CANTIDAD_ENGANCHE_FINANCIAMIENTO': fmt_money(cant_eng),
        'LETRA_ENGANCHE':                  letra_eng,

        'FECHA_INICIO': fecha_inicio.day,
        'DIA_PAGO': (fecha_inicio + timedelta(days=3)).day,
        'METROS_CUADRADOS': fin.lote.superficie_m2,
        'PORCENTAJE': get_porcentaje_cometa(fin.lote.identificador),

        'NOMBRE_TEST2': test2,
        'NOMBRE_TEST1': test1,
        'ID_TEST2': tramite.testigo_2_idmex or '',
        'ID_TEST1': tramite.testigo_1_idmex or '',
        'NOMBRE_BENE': benef,
        'ID_BENE': tramite.beneficiario_1.numero_id,
        'NUMERO_BENE': bene_numero1,
        'CORREO_BENE': bene_correo1,
    }

    # 6) Firma
    if request and tpl:
        # Tamaño consistente para TODAS las firmas
        FIRMA_ANCHO = 40  # 40mm de ancho
        FIRMA_ALTO = 15   # 15mm de alto
        
        # Función reutilizable para procesar firmas
        def crear_firma_unificada(data_url, prueba=None):
            if not data_url:
                return ''
            ancho = FIRMA_ANCHO
            alto = FIRMA_ALTO
            if prueba == 'si':
                ancho = 20  # 40mm de ancho
                alto = 9.25   # 15mm de alto
            
            try:
                # Decodificar base64
                header, b64 = data_url.split(',', 1)
                img_data = base64.b64decode(b64)
                
                # Crear archivo temporal
                fd, temp_path = tempfile.mkstemp(suffix='.png')
                with os.fdopen(fd, 'wb') as f:
                    f.write(img_data)
                # ✅ MISMO TAMAÑO para todas las firmas
                return InlineImage(tpl, temp_path, width=Mm(ancho), height=Mm(alto))
                
            except Exception as e:
                print(f"Error al procesar firma: {e}")
                return ''
        
        # Procesar cada firma con el mismo tamaño
        context['FIRMA_CLIENTE'] = crear_firma_unificada(firma_data)
        context['FIRMA_VENDEDOR'] = crear_firma_unificada(tramite.firma_vendedor)
        context['FIRMA_TESTIGO1'] = crear_firma_unificada(tramite.testigo_1_firma)
        context['FIRMA_TESTIGO2'] = crear_firma_unificada(tramite.testigo_2_firma)
        context['FIRMA_BENE'] = crear_firma_unificada(tramite.beneficiario_1_firma)
        
    else:
        # Valores por defecto si no hay template
        context['FIRMA_CLIENTE'] = ''
        context['FIRMA_VENDEDOR'] = ''
        context['FIRMA_TESTIGO1'] = ''
        context['FIRMA_TESTIGO2'] = ''
        context['FIRMA_BENE'] = ''

    return context

