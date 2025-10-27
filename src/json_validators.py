import json
import pandas as pd
from src.glosa_parser import LectorGlosaMDB
from src.xlsm_parser import LectorXLSM
from src.utils import columna_a_letra_excel

class ValidadorJSON:
    def __init__(self, ruta_archivo_json, lector_glosa: LectorGlosaMDB, archivos_disponibles: dict):
        self.reglas = self._cargar_reglas(ruta_archivo_json)
        self.lector_glosa = lector_glosa
        self.archivos_disponibles = archivos_disponibles
        self.errores = []

    def _cargar_reglas(self, ruta_archivo):
        try:
            with open(ruta_archivo, 'r', encoding='utf-8') as f:
                datos = json.load(f)
                return datos.get("validations", [])
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error al cargar o parsear el archivo JSON {ruta_archivo}: {e}")
            return []

    def obtener_errores(self):
        return self.errores

    def validar(self, lector_xlsm: LectorXLSM):
        self.errores = []
        current_file_series = lector_xlsm.serie

        for regla in self.reglas:
            target_series = regla.get("target_series")

            # Check if the rule applies to the current file's series
            if target_series:
                if isinstance(target_series, str):
                    if current_file_series != target_series:
                        continue # Skip rule if it doesn't match the current file's series
                elif isinstance(target_series, list):
                    if current_file_series not in target_series:
                        continue # Skip rule if it doesn't match any of the target series
            
            self._evaluar_regla_individual(regla, lector_xlsm)
        return not self.errores

    def _evaluar_regla_individual(self, regla, lector_xlsm):
        condiciones = regla.get("conditions", {})
        reglas_a_verificar = condiciones.get("rules", [])
        operador_logico = condiciones.get("logical_operator", "AND").upper()

        # Lógica para validación inter-series
        # This logic should still apply for inter-series rules, regardless of target_series
        series_en_regla = {sub_regla[lado].get("series") for sub_regla in reglas_a_verificar for lado in ["lhs", "rhs"] if "series" in sub_regla[lado]}
        
        # Filter out None from series_en_regla, as it might come from rules without explicit series
        series_en_regla = {s for s in series_en_regla if s is not None}

        if len(series_en_regla) > 1: # This indicates an inter-series rule
            clave_archivo = (lector_xlsm.codigo_establecimiento, lector_xlsm.mes)
            series_disponibles = self.archivos_disponibles.get(clave_archivo, [])
            
            # Check if all series mentioned in the rule are available among the processed files
            if not series_en_regla.issubset(set(series_disponibles)):
                print(f"Omitiendo regla inter-series '{regla.get('name')}' porque no todos los archivos de series requeridos están presentes para {clave_archivo}.")
                return

        resultados = []
        # Collect missing value errors separately to avoid redundancy
        missing_value_errors = []

        for sub_regla in reglas_a_verificar:
            info_lhs = self._obtener_valor(sub_regla["lhs"], lector_xlsm)
            info_rhs = self._obtener_valor(sub_regla["rhs"], lector_xlsm)
            operador = sub_regla["operator"]

            # Check for missing values and add concise error messages
            if info_lhs["valor"] is None:
                missing_value_errors.append(f"Valor no encontrado para '{info_lhs['texto_prestacion']}' en {info_lhs['columna_formateada']}.")
                resultados.append(False)
            if info_rhs["valor"] is None:
                missing_value_errors.append(f"Valor no encontrado para '{info_rhs['texto_prestacion']}' en {info_rhs['columna_formateada']}.")
                resultados.append(False)
            
            if info_lhs["valor"] is None or info_rhs["valor"] is None:
                continue # Skip comparison if values are missing

            resultado = self._realizar_comparacion(info_lhs["valor"], operador, info_rhs["valor"])
            resultados.append(resultado)

        # Add collected missing value errors to self.errores
        # Only add unique missing value errors
        for error_msg in list(set(missing_value_errors)):
            self._agregar_error(f"Validación '{regla.get('name', 'sin nombre')}' falló: {error_msg}")

        resultado_final = False
        if operador_logico == "AND":
            resultado_final = all(resultados)
        elif operador_logico == "OR":
            resultado_final = any(resultados)

        # Only generate the main failure message if there are actual comparison failures
        # and no specific missing value errors have already covered the failure.
        # Also, avoid adding a generic "falló" message if specific messages are already present.
        if not resultado_final and not missing_value_errors:
            custom_message = regla.get('message')
            if custom_message:
                error_message = f"Validación '{regla.get('name', 'sin nombre')}' falló: {custom_message}"
            else:
                error_message = self._generar_mensaje_adaptativo(regla, reglas_a_verificar, operador_logico, resultados, lector_xlsm)
            self._agregar_error(error_message)
        elif not resultado_final and not any(resultados) and not missing_value_errors: # If all rules failed and no specific messages were generated
            self._agregar_error(f"Validación '{regla.get('name', 'sin nombre')}' falló.")

        # Removed redundant code block

    def _generar_mensaje_adaptativo(self, regla, reglas_a_verificar, operador_logico, resultados_comparacion, lector_xlsm):
        nombre_regla = regla.get('name', 'sin nombre')
        join_word = " y " if operador_logico == "AND" else " o " # Initialize join_word

        mensajes_fallidos_concisos = []
        for i, sub_regla in enumerate(reglas_a_verificar):
            if not resultados_comparacion[i]: # Solo generar mensaje para reglas que fallaron
                info_lhs = self._obtener_valor(sub_regla["lhs"], lector_xlsm)
                info_rhs = self._obtener_valor(sub_regla["rhs"], lector_xlsm)
                operador = sub_regla["operator"]
                op_texto = self._obtener_texto_operador(operador)

                lhs_display = info_lhs["texto_prestacion"]
                rhs_display = info_rhs["texto_prestacion"] if sub_regla["rhs"].get("type") != "constant" else str(info_rhs["valor"])
                
                # Simplificar la referencia a la columna, mostrando solo la celda o rango
                # Extract series, sheet, and cell/range for LHS
                lhs_serie = sub_regla["lhs"].get("series", lector_xlsm.serie)
                lhs_col_info = info_lhs["columna_formateada"]
                lhs_hoja = "N/A"
                lhs_celda_o_rango = "N/A"

                if "Hoja: " in lhs_col_info:
                    parts = lhs_col_info.split(", ")
                    for part in parts:
                        if part.startswith("Hoja: "):
                            lhs_hoja = part.replace("Hoja: ", "")
                        elif part.startswith("Celda: ") or part.startswith("Rango: "):
                            lhs_celda_o_rango = part.replace("Celda: ", "").replace("Rango: ", "")
                
                lhs_full_ref = f"Serie: {lhs_serie}, Hoja: {lhs_hoja}, Celda: {lhs_celda_o_rango}"

                # Extract series, sheet, and cell/range for RHS
                rhs_serie = sub_regla["rhs"].get("series", lector_xlsm.serie)
                rhs_col_info = info_rhs["columna_formateada"]
                rhs_hoja = "N/A"
                rhs_celda_o_rango = "N/A"

                if "Hoja: " in rhs_col_info:
                    parts = rhs_col_info.split(", ")
                    for part in parts:
                        if part.startswith("Hoja: "):
                            rhs_hoja = part.replace("Hoja: ", "")
                        elif part.startswith("Celda: ") or part.startswith("Rango: "):
                            rhs_celda_o_rango = part.replace("Celda: ", "").replace("Rango: ", "")
                
                rhs_full_ref = f"Serie: {rhs_serie}, Hoja: {rhs_hoja}, Celda: {rhs_celda_o_rango}"

                if sub_regla["rhs"].get("type") == "constant":
                    mensajes_fallidos_concisos.append(
                        f"'{lhs_display}' ({lhs_full_ref}) debe ser {op_texto} {rhs_display} (actual: {info_lhs['valor']})."
                    )
                else:
                    mensajes_fallidos_concisos.append(
                        f"'{lhs_display}' ({lhs_full_ref}) debe ser {op_texto} '{rhs_display}' ({rhs_full_ref}) (actual: {info_lhs['valor']} vs {info_rhs['valor']})."
                    )
        
        if mensajes_fallidos_concisos:
            # Combine messages for a single rule into a more readable format
            return f"Validación '{nombre_regla}' falló: {join_word.join(mensajes_fallidos_concisos)}"
        else:
            return f"Validación '{nombre_regla}' falló." # Fallback, should not be reached if results_comparacion is accurate

    def _obtener_valor(self, operando, lector_xlsm):
        tipo_operando = operando.get("type")
        if tipo_operando == "constant":
            return {
                "valor": operando.get("value"),
                "texto_prestacion": "valor constante", # Placeholder, not used for constants
                "columna_formateada": "" # Not applicable for constants
            }
        
        if tipo_operando == "prestacion":
            serie = operando.get("series", lector_xlsm.serie)
            codigo = operando.get("codigo")
            
            info_prestacion = self.lector_glosa.obtener_info_prestacion(serie, codigo)
            if info_prestacion is None:
                print(f"Advertencia: CodigoPrestacion '{codigo}' no encontrado en la glosa para la serie '{serie}'.")
                return {
                    "valor": None,
                    "texto_prestacion": f"Prestación '{codigo}' (Serie {serie})",
                    "columna_formateada": "N/A"
                }

            # Access columns using lowercase names
            nombre_hoja = info_prestacion["hoja"]
            fila = info_prestacion["linea"]
            
            try:
                indice_col_inicio = int(info_prestacion["inicio"])
            except (ValueError, TypeError):
                print(f"Advertencia: Valor 'inicio' inválido para CodigoPrestacion '{codigo}': {info_prestacion['inicio']}")
                return {
                    "valor": None,
                    "texto_prestacion": info_prestacion["textoprestacion"].strip() if info_prestacion and "textoprestacion" in info_prestacion else f"Prestación '{codigo}' (Serie {serie})",
                    "columna_formateada": "N/A"
                }

            if "column_offset" in operando:
                indice_col = indice_col_inicio + operando["column_offset"]
                letra_col = columna_a_letra_excel(indice_col)
                
                valor_celda = lector_xlsm.obtener_valor_celda(nombre_hoja, fila, letra_col=letra_col)
                return {
                    "valor": valor_celda,
                    "texto_prestacion": info_prestacion["textoprestacion"].strip(), # Remove extra spaces
                    "columna_formateada": f"Hoja: {nombre_hoja}, Celda: {letra_col}{fila}"
                }
            
            elif "column_offset_start" in operando and "column_offset_end" in operando:
                offset_inicio = operando["column_offset_start"]
                offset_fin = operando["column_offset_end"]
                
                total = 0
                letras_columnas = []
                
                for offset in range(offset_inicio, offset_fin + 1):
                    indice_col = indice_col_inicio + offset
                    letra_col = columna_a_letra_excel(indice_col)
                    letras_columnas.append(letra_col)
                    valor = lector_xlsm.obtener_valor_celda(nombre_hoja, fila, letra_col=letra_col)
                    if isinstance(valor, (int, float)):
                        total += valor
                
                rango_formateado = ""
                if len(letras_columnas) == 1:
                    rango_formateado = f"Celda: {letras_columnas[0]}{fila}"
                elif len(letras_columnas) > 1:
                    rango_formateado = f"Rango: {letras_columnas[0]}{fila} a {letras_columnas[-1]}{fila}"

                return {
                    "valor": total,
                    "texto_prestacion": info_prestacion["textoprestacion"].strip(), # Remove extra spaces
                    "columna_formateada": f"Hoja: {nombre_hoja}, {rango_formateado}"
                }
        
        return {"valor": None, "texto_prestacion": info_prestacion["textoprestacion"].strip() if info_prestacion and "textoprestacion" in info_prestacion else "", "columna_formateada": ""}

    def _realizar_comparacion(self, lhs, op, rhs):
        mapa_op = {
            "==": lambda a, b: a == b, "!=": lambda a, b: a != b,
            "<": lambda a, b: a < b, "<=": lambda a, b: a <= b,
            ">": lambda a, b: a > b, ">=": lambda a, b: a >= b,
        }
        if op in mapa_op:
            return mapa_op[op](lhs, rhs)
        else:
            print(f"Advertencia: Operador no soportado '{op}'.")
            return False

    def _obtener_texto_operador(self, operador):
        mapa_texto_op = {
            "==": "igual a",
            "!=": "diferente de",
            "<": "menor que",
            "<=": "menor o igual que",
            ">": "mayor que",
            ">=": "mayor o igual que",
        }
        return mapa_texto_op.get(operador, operador)

    def _agregar_error(self, mensaje):
        self.errores.append(mensaje)

if __name__ == "__main__":
    import os
    # For local testing, assume a dummy Global.mdb path and year
    directorio_actual = os.path.dirname(__file__)
    ruta_mdb_global_test = os.path.join(directorio_actual, '..', 'Global.mdb') # Adjust if Global.mdb is elsewhere
    test_year = 2025 # Example year for testing

    lector_glosa_mdb_test = LectorGlosaMDB(ruta_mdb_global_test, test_year)

    xlsm_file_path = os.path.join('..', 'original', '116322A05.xlsm') # Example XLSM file
    lector_xlsm = LectorXLSM(xlsm_file_path)
    lector_xlsm.cargar_libro()

    # Dummy archivos_disponibles for testing purposes
    archivos_disponibles_test = {
        (lector_xlsm.codigo_establecimiento, lector_xlsm.mes): [lector_xlsm.serie]
    }

    validador_json = ValidadorJSON('config/validations.json', lector_glosa_mdb_test, archivos_disponibles_test)
    
    if validador_json.validar(lector_xlsm):
        print("Todas las validaciones JSON pasaron.")
    else:
        print("Validaciones JSON fallaron:")
        for error in validador_json.obtener_errores():
            print(f"  - {error}")

    lector_xlsm.cerrar_libro()
