import json
import pandas as pd
from src.glosa_parser import LectorGlosa
from src.xlsm_parser import LectorXLSM
from src.utils import columna_a_letra_excel

class ValidadorJSON:
    def __init__(self, ruta_archivo_json, lector_glosa: LectorGlosa, archivos_disponibles: dict):
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
        for regla in self.reglas:
            self._evaluar_regla(regla, lector_xlsm)
        return not self.errores

    def _evaluar_regla(self, regla, lector_xlsm):
        condiciones = regla.get("conditions", {})
        reglas_a_verificar = condiciones.get("rules", [])
        operador_logico = condiciones.get("logical_operator", "AND").upper()

        # Lógica para validación inter-series
        series_en_regla = {sub_regla[lado].get("series") for sub_regla in reglas_a_verificar for lado in ["lhs", "rhs"] if "series" in sub_regla[lado]}
        if len(series_en_regla) > 1:
            clave_archivo = (lector_xlsm.codigo_establecimiento, lector_xlsm.mes)
            series_disponibles = self.archivos_disponibles.get(clave_archivo, [])
            if not series_en_regla.issubset(set(series_disponibles)):
                print(f"Omitiendo regla inter-series '{regla.get('name')}' porque no todos los archivos de series requeridos están presentes para {clave_archivo}.")
                return

        resultados = []
        mensajes_regla = []
        for sub_regla in reglas_a_verificar:
            info_lhs = self._obtener_valor(sub_regla["lhs"], lector_xlsm)
            info_rhs = self._obtener_valor(sub_regla["rhs"], lector_xlsm)
            operador = sub_regla["operator"]

            if info_lhs["valor"] is None or info_rhs["valor"] is None:
                resultados.append(False)
                # If values are missing, we can't form a complete message, but we can note it.
                if info_lhs["valor"] is None:
                    mensajes_regla.append(f"Valor no encontrado para '{info_lhs['texto_prestacion']}' en {info_lhs['columna_formateada']}.")
                if info_rhs["valor"] is None:
                    mensajes_regla.append(f"Valor no encontrado para '{info_rhs['texto_prestacion']}' en {info_rhs['columna_formateada']}.")
                continue

            resultado = self._realizar_comparacion(info_lhs["valor"], operador, info_rhs["valor"])
            resultados.append(resultado)

            # Construir el mensaje de la sub-regla
            op_texto = self._obtener_texto_operador(operador)
            if sub_regla["rhs"].get("type") == "constant":
                mensaje_sub_regla = (
                    f"'{info_lhs['texto_prestacion']}' ({info_lhs['columna_formateada']}) "
                    f"debe ser {op_texto} {info_rhs['valor']}."
                )
            else:
                mensaje_sub_regla = (
                    f"'{info_lhs['texto_prestacion']}' ({info_lhs['columna_formateada']}) "
                    f"debe ser {op_texto} '{info_rhs['texto_prestacion']}' ({info_rhs['columna_formateada']})."
                )
            mensajes_regla.append(mensaje_sub_regla)

        resultado_final = False
        if operador_logico == "AND":
            resultado_final = all(resultados)
        elif operador_logico == "OR":
            resultado_final = any(resultados)

        if not resultado_final:
            custom_message = regla.get('message')
            if custom_message:
                error_message = f"Validación '{regla.get('name', 'sin nombre')}' falló: {custom_message}"
            else:
                # Generar mensaje adaptativo
                error_message = self._generar_mensaje_adaptativo(regla, reglas_a_verificar, operador_logico, resultados, lector_xlsm)
            self._agregar_error(error_message)

    def _generar_mensaje_adaptativo(self, regla, reglas_a_verificar, operador_logico, resultados_comparacion, lector_xlsm):
        nombre_regla = regla.get('name', 'sin nombre')
        
        # Recopilar información detallada de cada sub-regla
        detalles_sub_reglas = []
        for i, sub_regla in enumerate(reglas_a_verificar):
            info_lhs = self._obtener_valor(sub_regla["lhs"], lector_xlsm)
            info_rhs = self._obtener_valor(sub_regla["rhs"], lector_xlsm)
            operador = sub_regla["operator"]
            op_texto = self._obtener_texto_operador(operador)

            if info_lhs is None or info_rhs is None:
                # If values are missing, we can't form a complete message, but we can note it.
                # This case should ideally be handled earlier in _evaluar_regla, but as a safeguard
                continue
            
            rhs_type = sub_regla["rhs"].get("type")
            rhs_text = info_rhs["texto_prestacion"] if rhs_type != "constant" else str(info_rhs["valor"])

            detalles_sub_reglas.append({
                "lhs_texto": info_lhs["texto_prestacion"],
                "lhs_columna": info_lhs["columna_formateada"],
                "rhs_texto": rhs_text,
                "rhs_valor": info_rhs["valor"],
                "rhs_type": rhs_type,
                "operator": operador,
                "op_texto": op_texto,
                "resultado": resultados_comparacion[i] if i < len(resultados_comparacion) else False
            })
        
        if len(detalles_sub_reglas) > 1 and all(d["operator"] == detalles_sub_reglas[0]["operator"] and d["rhs_type"] == detalles_sub_reglas[0]["rhs_type"] and d["rhs_valor"] == detalles_sub_reglas[0]["rhs_valor"] for d in detalles_sub_reglas):
            
            # Extract just the column letter for comparison to group by actual Excel column
            all_excel_cols = [d["lhs_columna"].split(',')[1].strip().split(':')[1].strip()[0] if 'Celda' in d["lhs_columna"] else d["lhs_columna"].split(',')[1].strip().split(':')[1].strip().split(' ')[0][0] for d in detalles_sub_reglas]
            unique_excel_cols = list(set(all_excel_cols))

            # Use "y" for AND, "o" for OR in the combined message
            join_word = " y " if operador_logico == "AND" else " o "

            if len(unique_excel_cols) == 1: # All LHS are in the same Excel column (e.g., F11 and F12 are both in column F)
                prestaciones_texto = []
                for detalle in detalles_sub_reglas:
                    prestaciones_texto.append(f"'{detalle['lhs_texto']}' ({detalle['lhs_columna'].split(',')[1].strip()})")
                
                combined_lhs_text = join_word.join(prestaciones_texto)
                
                common_op_text = detalles_sub_reglas[0]["op_texto"]
                common_rhs_text = detalles_sub_reglas[0]["rhs_texto"]
                common_sheet = detalles_sub_reglas[0]["lhs_columna"].split(',')[0].strip() # Extract sheet name

                return (
                    f"{common_sheet}, {combined_lhs_text} "
                    f"deben ser {common_op_text} {common_rhs_text}."
                )
            else: # LHS columns are different, list them individually
                mensajes_individuales = []
                for detalle in detalles_sub_reglas:
                    mensajes_individuales.append(
                        f"'{detalle['lhs_texto']}' ({detalle['lhs_columna']}) "
                        f"debe ser {detalle['op_texto']} {detalle['rhs_texto']}"
                    )
                return f"Validación '{nombre_regla}' falló: {f' {join_word} '.join(mensajes_individuales)}."

        # Si no se pueden agrupar o es una sola regla, generar mensajes individuales
        mensajes_regla_fallida = []
        for detalle in detalles_sub_reglas:
            if not detalle["resultado"]: # Only include messages for rules that failed
                if detalle["rhs_type"] == "constant":
                    mensaje_sub_regla = (
                        f"'{detalle['lhs_texto']}' ({detalle['lhs_columna']}) "
                        f"debe ser {detalle['op_texto']} {detalle['rhs_valor']}."
                    )
                else:
                    mensaje_sub_regla = (
                        f"'{detalle['lhs_texto']}' ({detalle['lhs_columna']}) "
                        f"debe ser {detalle['op_texto']} '{detalle['rhs_texto']}' ({detalle['lhs_columna']})."
                    )
                mensajes_regla_fallida.append(mensaje_sub_regla)
        
        if mensajes_regla_fallida:
            return f"Validación '{nombre_regla}' falló: {f' {join_word} '.join(mensajes_regla_fallida)}"
        else:
            return f"Validación '{nombre_regla}' falló." # Should not happen if result_final is False

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

            nombre_hoja = info_prestacion["hoja"]
            fila = info_prestacion["linea"]
            
            try:
                indice_col_inicio = int(info_prestacion["inicio"])
            except (ValueError, TypeError):
                print(f"Advertencia: Valor 'inicio' inválido para CodigoPrestacion '{codigo}': {info_prestacion['inicio']}")
                return None

            if "column_offset" in operando:
                indice_col = indice_col_inicio + operando["column_offset"]
                letra_col = columna_a_letra_excel(indice_col)
                valor_celda = lector_xlsm.obtener_valor_celda(nombre_hoja, fila, letra_col=letra_col)
                return {
                    "valor": valor_celda,
                    "texto_prestacion": info_prestacion["TextoPrestacion"].strip(), # Remove extra spaces
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
                    "texto_prestacion": info_prestacion["TextoPrestacion"].strip(), # Remove extra spaces
                    "columna_formateada": f"Hoja: {nombre_hoja}, {rango_formateado}"
                }
        
        return {"valor": None, "texto_prestacion": info_prestacion["TextoPrestacion"].strip() if info_prestacion and "TextoPrestacion" in info_prestacion else "", "columna_formateada": ""}

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
    glosa_path = os.path.join('..', 'glosa')
    lector_glosa = LectorGlosa(glosa_path)
    lector_glosa.cargar_todas_glosas()

    xlsm_file_path = os.path.join('..', 'original', '116322A05.xlsm')
    lector_xlsm = LectorXLSM(xlsm_file_path)
    lector_xlsm.cargar_libro()

    validador_json = ValidadorJSON('config/validations.json', lector_glosa)
    
    if validador_json.validar(lector_xlsm):
        print("Todas las validaciones JSON pasaron.")
    else:
        print("Validaciones JSON fallaron:")
        for error in validador_json.obtener_errores():
            print(f"  - {error}")

    lector_xlsm.cerrar_libro()
