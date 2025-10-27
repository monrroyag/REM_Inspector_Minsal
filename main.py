import os
import argparse
import warnings # Import warnings module

# Suppress specific UserWarning from pandas globally
warnings.filterwarnings("ignore", category=UserWarning, module="pandas")

from src.glosa_parser import LectorGlosaMDB
from src.xlsm_parser import LectorXLSM
from src.hardcoded_validators import ValidadorFijo
from src.json_validators import ValidadorJSON

def escanear_archivos_xlsm(directorio):
    archivos_por_estab_y_mes = {}
    for nombre_archivo in os.listdir(directorio):
        if nombre_archivo.endswith(".xlsm"):
            try:
                lector = LectorXLSM(os.path.join(directorio, nombre_archivo))
                clave = (lector.codigo_establecimiento, lector.mes)
                if clave not in archivos_por_estab_y_mes:
                    archivos_por_estab_y_mes[clave] = []
                archivos_por_estab_y_mes[clave].append(lector.serie)
            except ValueError:
                continue
    return archivos_por_estab_y_mes

def main(directorio_xlsm, ruta_global_mdb, ruta_config_json):
    archivos_disponibles = escanear_archivos_xlsm(directorio_xlsm)

    for nombre_archivo in os.listdir(directorio_xlsm):
        if not nombre_archivo.endswith(".xlsm"):
            continue

        ruta_archivo_xlsm = os.path.join(directorio_xlsm, nombre_archivo)
        print(f"\n--- Procesando archivo: {nombre_archivo} ---")

        try:
            lector_xlsm = LectorXLSM(ruta_archivo_xlsm)
            lector_xlsm.cargar_libro()

            year_str = lector_xlsm.obtener_valor_celda("NOMBRE", 7, letra_col='B')
            if year_str is None:
                print(f"  Advertencia: No se pudo obtener el año de '{nombre_archivo}'. Omitiendo validaciones de glosa.")
                lector_xlsm.cerrar_libro()
                continue
            
            try:
                year = int(year_str)
            except ValueError:
                print(f"  Advertencia: El valor '{year_str}' en NOMBRE!B7 de '{nombre_archivo}' no es un año válido. Omitiendo validaciones de glosa.")
                lector_xlsm.cerrar_libro()
                continue

            # Extract month from C6:D6
            month_c6 = lector_xlsm.obtener_valor_celda("NOMBRE", 6, letra_col='C')
            month_d6 = lector_xlsm.obtener_valor_celda("NOMBRE", 6, letra_col='D')
            
            # Concatenate and convert to int, handling potential None or non-numeric values
            month_str = f"{month_c6:02d}{month_d6:02d}" if (isinstance(month_c6, int) and isinstance(month_d6, int)) else None
            
            if month_str is None or not month_str.isdigit():
                print(f"  Advertencia: No se pudo obtener un mes válido de NOMBRE!C6:D6 en '{nombre_archivo}'. Omitiendo validación de versión.")
                lector_xlsm.cerrar_libro()
                continue
            
            try:
                month = int(month_str)
                if not (1 <= month <= 12):
                    raise ValueError("Mes fuera de rango (1-12)")
            except ValueError:
                print(f"  Advertencia: El valor '{month_str}' en NOMBRE!C6:D6 de '{nombre_archivo}' no es un mes válido. Omitiendo validación de versión.")
                lector_xlsm.cerrar_libro()
                continue

            # Extract version from A9:B9
            version_excel_raw = lector_xlsm.obtener_valor_celda("NOMBRE", 9, letra_col='A')
            if version_excel_raw is None:
                print(f"  Advertencia: No se pudo obtener la versión de NOMBRE!A9:B9 en '{nombre_archivo}'. Omitiendo validación de versión.")
                lector_xlsm.cerrar_libro()
                continue
            
            # Normalize version extracted from Excel
            lector_glosa_mdb_temp = LectorGlosaMDB(ruta_global_mdb, year) # Temporarily instantiate to access normalization method
            version_excel_normalized = lector_glosa_mdb_temp._normalize_version_string(version_excel_raw)
            
            if not version_excel_normalized:
                print(f"  Advertencia: La versión '{version_excel_raw}' en NOMBRE!A9:B9 de '{nombre_archivo}' no pudo ser normalizada. Omitiendo validación de versión.")
                lector_xlsm.cerrar_libro()
                continue

            lector_glosa_mdb = LectorGlosaMDB(ruta_global_mdb, year) # Re-instantiate for full use
            if lector_glosa_mdb.glosas_df.empty:
                print(f"  Advertencia: No se cargaron glosas para el año {year} desde '{ruta_global_mdb}'. Omitiendo validaciones de glosa.")
            
            # --- New Version Validation ---
            serie_excel = lector_xlsm.serie # Get series from filename parser
            version_mdb_raw = lector_glosa_mdb.obtener_version_esperada(year, month, serie_excel)
            version_mdb_normalized = lector_glosa_mdb._normalize_version_string(version_mdb_raw)
            
            if version_mdb_normalized:
                if version_excel_normalized != version_mdb_normalized:
                    # Add error to fixed validations
                    validador_fijo = ValidadorFijo(lector_xlsm) # Initialize to add error
                    validador_fijo.errores.append(
                        f"Error de Versión: La versión en Excel (normalizada: '{version_excel_normalized}', original: '{version_excel_raw}') no coincide con la esperada en MDB (normalizada: '{version_mdb_normalized}', original: '{version_mdb_raw}') para Año={year}, Mes={month}, Serie={serie_excel}."
                    )
                else:
                    print(f"  Validación de Versión PASÓ: Versión (normalizada) '{version_excel_normalized}' coincide con MDB.")
            else:
                print(f"  Advertencia: No se pudo obtener o normalizar la versión de MDB para Año={year}, Mes={month}, Serie={serie_excel}. No se realizó la validación de versión.")
            # --- End New Version Validation ---

            validador_fijo = ValidadorFijo(lector_xlsm)
            validador_fijo.validar_todo() # Execute validation
            errores_fijos = validador_fijo.obtener_errores()
            
            validador_json = ValidadorJSON(ruta_config_json, lector_glosa_mdb, archivos_disponibles)
            validador_json.validar(lector_xlsm) # Execute validation
            errores_json = validador_json.obtener_errores()
            
            # Combine errors for reporting
            all_errors = []
            if errores_fijos:
                all_errors.extend(errores_fijos)
            # Add the version validation error if it exists
            if hasattr(validador_fijo, 'errores') and len(validador_fijo.errores) > len(errores_fijos):
                all_errors.append(validador_fijo.errores[-1]) # Assuming the version error is the last one added

            if errores_json:
                all_errors.extend(errores_json)

            if all_errors:
                print("  Validaciones FALLARON:")
                for error in all_errors:
                    print(f"    - {error}")
            else:
                print("  Todas las validaciones PASARON.")

            lector_xlsm.cerrar_libro()

        except ValueError as ve:
            print(f"  Error al procesar '{nombre_archivo}': {ve}")
        except Exception as e:
            print(f"  Error inesperado al procesar '{nombre_archivo}': {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validador de archivos XLSM para REM Inspector.")
    parser.add_argument("--xlsm_dir", type=str, default="original", help="Directorio con los archivos XLSM a validar.")
    parser.add_argument("--mdb_path", type=str, default="glosa/Global.mdb", help="Ruta al archivo Global.mdb con la glosa centralizada.")
    parser.add_argument("--config", type=str, default="config/validations.json", help="Ruta al archivo de configuración de validaciones JSON.")
    parser.add_argument("--gui", action="store_true", help="Lanzar la interfaz gráfica para gestionar reglas de validación.")
    args = parser.parse_args()

    if args.gui:
        from src.validation_gui import run_gui
        run_gui()
    else:
        main(args.xlsm_dir, args.mdb_path, args.config)
