import string

def columna_a_letra_excel(indice_col):
    """
    Convierte un índice de columna (base 1) a su representación en letra de Excel.
    Ejemplo: 1 -> 'A', 26 -> 'Z', 27 -> 'AA'
    """
    if not isinstance(indice_col, int) or indice_col < 1:
        raise ValueError("El índice de la columna debe ser un entero positivo (base 1).")

    resultado = ""
    while indice_col > 0:
        indice_col, remanente = divmod(indice_col - 1, 26)
        resultado = string.ascii_uppercase[remanente] + resultado
    return resultado

def letra_excel_a_columna(letra_col):
    """
    Convierte una letra de columna de Excel a su índice (base 1).
    Ejemplo: 'A' -> 1, 'Z' -> 26, 'AA' -> 27
    """
    if not isinstance(letra_col, str) or not letra_col.isalpha():
        raise ValueError("La letra de la columna debe ser un string con solo caracteres alfabéticos.")

    letra_col = letra_col.upper()
    resultado = 0
    for caracter in letra_col:
        resultado = resultado * 26 + (ord(caracter) - ord('A') + 1)
    return resultado

def nombre_mes_a_numero(nombre_mes):
    """
    Convierte un nombre de mes en español (mayúsculas) a su número de dos dígitos.
    Ejemplo: 'ENERO' -> '01', 'MAYO' -> '05'
    """
    mapa_meses = {
        "ENERO": "01", "FEBRERO": "02", "MARZO": "03", "ABRIL": "04",
        "MAYO": "05", "JUNIO": "06", "JULIO": "07", "AGOSTO": "08",
        "SEPTIEMBRE": "09", "OCTUBRE": "10", "NOVIEMBRE": "11", "DICIEMBRE": "12"
    }
    return mapa_meses.get(nombre_mes.upper(), None)
