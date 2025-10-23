import os
from src.xlsm_parser import LectorXLSM
from src.utils import nombre_mes_a_numero

class ValidadorFijo:
    def __init__(self, lector_xlsm: LectorXLSM):
        self.lector_xlsm = lector_xlsm
        self.errores = []

    def _agregar_error(self, mensaje):
        self.errores.append(mensaje)

    def obtener_errores(self):
        return self.errores

    def validar_todo(self):
        """
        Ejecuta todas las validaciones fijas.
        Devuelve True si todas las validaciones pasan, False en caso contrario.
        """
        self.errores = []
        
        if not self._validar_convencion_nombre_archivo():
            return False

        self._validar_hoja_nombre()

        return not self.errores

    def _validar_convencion_nombre_archivo(self):
        """
        Valida la convención del nombre del archivo.
        """
        if not (self.lector_xlsm.codigo_establecimiento and 
                self.lector_xlsm.serie and 
                self.lector_xlsm.mes):
            self._agregar_error(f"El nombre de archivo '{os.path.basename(self.lector_xlsm.ruta_archivo)}' no sigue la convención esperada.")
            return False
        return True

    def _validar_hoja_nombre(self):
        """
        Realiza todas las validaciones fijas en la hoja "NOMBRE".
        """
        nombre_hoja = "NOMBRE"
        
        if not self.lector_xlsm.obtener_hoja(nombre_hoja):
            self._agregar_error(f"La hoja '{nombre_hoja}' no se encontró en {os.path.basename(self.lector_xlsm.ruta_archivo)}")
            return

        self._validar_codigo_establecimiento(nombre_hoja)
        self._validar_celdas_requeridas(nombre_hoja)
        self._validar_nombre_mes(nombre_hoja)
        self._validar_numero_mes(nombre_hoja)

    def _validar_codigo_establecimiento(self, nombre_hoja):
        """
        Valida que el código de establecimiento en C3:H3 coincida con el del nombre del archivo.
        """
        valores_rango = self.lector_xlsm.obtener_valores_rango(nombre_hoja, "C3", "H3")
        
        if not valores_rango or not valores_rango[0]:
            self._agregar_error(f"El rango NOMBRE!C3:H3 está vacío o no se pudo leer.")
            return

        codigo_desde_celdas = "".join(str(valor) for valor in valores_rango[0] if valor is not None)
        
        if codigo_desde_celdas != self.lector_xlsm.codigo_establecimiento:
            self._agregar_error(f"El código de establecimiento no coincide: en el nombre del archivo es '{self.lector_xlsm.codigo_establecimiento}', pero en NOMBRE!C3:H3 es '{codigo_desde_celdas}'.")

    def _validar_celdas_requeridas(self, nombre_hoja):
        """
        Valida que las celdas B2, B3 y C2:G2 contengan datos.
        """
        celdas_requeridas = ["B2", "B3"]
        for ref_celda in celdas_requeridas:
            valor = self.lector_xlsm.obtener_valor_celda(nombre_hoja, int(ref_celda[1:]), letra_col=ref_celda[0])
            if valor is None or str(valor).strip() == "":
                self._agregar_error(f"La celda requerida NOMBRE!{ref_celda} está vacía.")

        valores_rango = self.lector_xlsm.obtener_valores_rango(nombre_hoja, "C2", "G2")
        if not valores_rango or not any(celda is not None and str(celda).strip() != "" for celda in valores_rango[0]):
             self._agregar_error(f"El rango requerido NOMBRE!C2:G2 está vacío.")

    def _validar_nombre_mes(self, nombre_hoja):
        """
        Valida que la celda B6 contenga el nombre del mes correcto en mayúsculas.
        """
        nombre_mes_celda = self.lector_xlsm.obtener_valor_celda(nombre_hoja, 6, letra_col='B')
        
        if not nombre_mes_celda or str(nombre_mes_celda).strip() == "":
            self._agregar_error("El nombre del mes en NOMBRE!B6 está vacío.")
            return

        numero_mes_esperado = self.lector_xlsm.mes
        
        mapa_meses = {
            "01": "ENERO", "02": "FEBRERO", "03": "MARZO", "04": "ABRIL",
            "05": "MAYO", "06": "JUNIO", "07": "JULIO", "08": "AGOSTO",
            "09": "SEPTIEMBRE", "10": "OCTUBRE", "11": "NOVIEMBRE", "12": "DICIEMBRE"
        }
        nombre_mes_esperado = mapa_meses.get(numero_mes_esperado)

        if str(nombre_mes_celda).upper() != nombre_mes_esperado:
            self._agregar_error(f"El nombre del mes no coincide: en el archivo es '{numero_mes_esperado}' (esperado '{nombre_mes_esperado}'), pero en NOMBRE!B6 es '{nombre_mes_celda}'.")

    def _validar_numero_mes(self, nombre_hoja):
        """
        Valida que las celdas C6:D6 contengan la representación numérica correcta del mes.
        """
        numero_mes_archivo = self.lector_xlsm.mes
        
        val_c6 = self.lector_xlsm.obtener_valor_celda(nombre_hoja, 6, letra_col='C')
        val_d6 = self.lector_xlsm.obtener_valor_celda(nombre_hoja, 6, letra_col='D')

        if val_c6 is None or val_d6 is None:
            self._agregar_error("El número del mes en NOMBRE!C6 o NOMBRE!D6 está vacío.")
            return

        mes_desde_celdas = f"{val_c6}{val_d6}"
        
        if mes_desde_celdas != numero_mes_archivo:
            self._agregar_error(f"El número del mes no coincide: en el archivo es '{numero_mes_archivo}', pero en NOMBRE!C6:D6 es '{mes_desde_celdas}'.")

# Ejemplo de uso (para fines de prueba)
if __name__ == "__main__":
    directorio_actual = os.path.dirname(__file__)
    ruta_archivo_xlsm = os.path.join(directorio_actual, '..', 'original', '116322A05.xlsm')

    try:
        lector = LectorXLSM(ruta_archivo_xlsm)
        lector.cargar_libro()

        validador = ValidadorFijo(lector)
        if validador.validar_todo():
            print(f"Validaciones fijas pasaron para {os.path.basename(ruta_archivo_xlsm)}")
        else:
            print(f"Validaciones fijas fallaron para {os.path.basename(ruta_archivo_xlsm)}:")
            for error in validador.obtener_errores():
                print(f"  - {error}")
        
        lector.cerrar_libro()

    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}")
