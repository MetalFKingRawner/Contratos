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