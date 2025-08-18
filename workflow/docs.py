# workflow/docs.py

from workflow.builders import (
    build_aviso_privacidad_context,
    build_carta_intencion_context,
    build_solicitud_contrato_context,
    build_contrato_definitiva_pagos_context,
    build_contrato_definitiva_contado_context,
    build_contrato_ejidal_pagos_context,
    build_contrato_ejidal_contado_context,
    build_contrato_propiedad_contado_context,
    build_contrato_propiedad_contado_varios_context
)

DOCUMENTOS = {
    # Paso 0: Aviso de privacidad
    "aviso_privacidad": {
        "titulo":     "Aviso de Privacidad",
        "descripcion":"Acepta nuestro aviso y firma en pantalla",
        "plantilla":  "pdfs/templates/pdfs/aviso_privacidad_template.docx",
        "builder":    build_aviso_privacidad_context,
    },
    # Paso 1: Carta de Intención
    "carta_intencion": {
        "titulo":     "Carta de Intención de Compra",
        "descripcion":"Formaliza tu intención de compra.",
        "plantilla":  "pdfs/templates/pdfs/carta_intencion_template.docx",
        "builder":    build_carta_intencion_context,
    },
    # Paso 2: Solicitud de Contrato
    "solicitud_contrato": {
        "titulo":     "Solicitud de Contrato",
        "descripcion":"Información previa para tu contrato.",
        "plantilla":  "pdfs/templates/pdfs/solicitud_contrato.docx",
        "builder":    build_solicitud_contrato_context,
    },
    # Contratos Definitiva – Financiamiento
    "contrato_definitiva_pagos": {
        "titulo":     "Contrato Propiedad Definitiva (Pagos)",
        "descripcion":"Contrato con plan de pagos.",
        "plantilla":  "pdfs/templates/pdfs/contrato_definitiva_pagos.docx",
        "builder":    build_contrato_definitiva_pagos_context,
    },
    "contrato_definitiva_contado": {
        "titulo":     "Contrato Propiedad Definitiva (Contado)",
        "descripcion":"Contrato para pago al contado.",
        "plantilla":  "pdfs/templates/pdfs/contrato_definitiva_contado.docx",
        "builder":    build_contrato_definitiva_contado_context,
    },
    # Contratos Ejidal/Comunal – Financiamiento
    "contrato_ejidal_pagos": {
        "titulo":     "Contrato Ejidal y Comunal (Pagos)",
        "descripcion":"Cesión ejidal/comunal con plan de pagos.",
        "plantilla":  "pdfs/templates/pdfs/contrato_ejidal_pagos.docx",
        "builder":    build_contrato_ejidal_pagos_context,
    },
    "contrato_ejidal_contado": {
        "titulo":     "Contrato Ejidal y Comunal (Contado)",
        "descripcion":"Cesión ejidal/comunal al contado.",
        "plantilla":  "pdfs/templates/pdfs/contrato_ejidal_contado.docx",
        "builder":    build_contrato_ejidal_contado_context,
    },
    # Contratos pequeña propiedad – Financiamiento
    "contrato_propiedad_pagos": {
        "titulo":     "Contrato Pequeña Propiedad (Pagos)",
        "descripcion":"Contrato con plan de pagos.",
        "plantilla":  "pdfs/templates/pdfs/contrato_propiedad_pagos.docx",
        "builder":    build_contrato_ejidal_pagos_context,
    },
    "contrato_propiedad_contado": {
        "titulo":     "Contrato Pequeña Propiedad (Contado)",
        "descripcion":"Contrato para pago al contado.",
        "plantilla":  "pdfs/templates/pdfs/contrato_pequeña_contado_2.docx",
        "builder":    build_contrato_propiedad_contado_context,
    },
    "contrato_propiedad_contado_varios": {
        "titulo":     "Contrato Pequeña Propiedad varios compradores(Contado)",
        "descripcion":"Contrato para pago al contado de varios compradores.",
        "plantilla":  "pdfs/templates/pdfs/contrato_pequeña_contado_varios.docx",
        "builder":    build_contrato_propiedad_contado_varios_context,
    },
}

