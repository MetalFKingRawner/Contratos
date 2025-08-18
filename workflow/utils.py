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
    """Convierte un número a su representación en letras en español, incluyendo millones"""
    # Caso especial para cero
    if numero == 0:
        return "CERO"
    
    # Diccionarios para conversión
    unidades = ['', 'UN', 'DOS', 'TRES', 'CUATRO', 'CINCO', 'SEIS', 'SIETE', 'OCHO', 'NUEVE']
    decenas = ['', 'DIEZ', 'VEINTE', 'TREINTA', 'CUARENTA', 'CINCUENTA', 'SESENTA', 'SETENTA', 'OCHENTA', 'NOVENTA']
    especiales = {
        11: 'ONCE', 12: 'DOCE', 13: 'TRECE', 14: 'CATORCE', 15: 'QUINCE',
        16: 'DIECISÉIS', 17: 'DIECISIETE', 18: 'DIECIOCHO', 19: 'DIECINUEVE',
        20: 'VEINTE', 21: 'VEINTIUN', 22: 'VEINTIDÓS', 23: 'VEINTITRÉS',
        24: 'VEINTICUATRO', 25: 'VEINTICINCO', 26: 'VEINTISÉIS', 27: 'VEINTISIETE',
        28: 'VEINTIOCHO', 29: 'VEINTINUEVE'
    }
    
    # Manejar decimales
    entero = int(numero)
    decimales = int(round((numero - entero) * 100))
    
    # Convertir parte entera
    resultado = []
    
    # Manejar millones
    if entero >= 1000000:
        millones = entero // 1000000
        entero %= 1000000
        
        if millones == 1:
            resultado.append("UN MILLÓN")
        elif millones > 1:
            resultado.append(numero_a_letras(millones))
            if millones == 1:
                resultado.append("MILLÓN")
            else:
                resultado.append("MILLONES")
    
    # Manejar miles
    if entero >= 1000:
        miles = entero // 1000
        entero %= 1000
        
        if miles == 1:
            resultado.append("MIL")
        elif miles > 1:
            resultado.append(numero_a_letras(miles))
            resultado.append("MIL")
    
    # Convertir centenas (0-999)
    if entero > 0:
        centena = entero // 100
        resto = entero % 100
        
        if centena > 0:
            if centena == 1:
                if resto == 0:
                    resultado.append("CIEN")
                else:
                    resultado.append("CIENTO")
            elif centena == 5:
                resultado.append("QUINIENTOS")
            elif centena == 7:
                resultado.append("SETECIENTOS")
            elif centena == 9:
                resultado.append("NOVECIENTOS")
            else:
                resultado.append(unidades[centena] + "CIENTOS")
        
        if resto > 0:
            if resto in especiales:
                resultado.append(especiales[resto])
            else:
                decena = resto // 10
                unidad = resto % 10
                
                if decena > 0:
                    resultado.append(decenas[decena])
                
                if unidad > 0:
                    if decena > 0 and unidad > 0:
                        resultado.append('Y')
                    resultado.append(unidades[unidad])
    
    # Unir todas las partes
    letras = ' '.join(resultado)
    
    # Agregar decimales si existen
    if decimales > 0:
        letras += f" CON {decimales:02d}/100"
    
    return letras
