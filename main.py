import os
import argparse
from src.glosa_parser import LectorGlosa
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

def main(directorio_xlsm, directorio_glosa, ruta_config_json):
    print("--- Inicializando ---")
    lector_glosa = LectorGlosa(directorio_glosa)
    lector_glosa.cargar_todas_glosas()

    archivos_disponibles = escanear_archivos_xlsm(directorio_xlsm)
    validador_json = ValidadorJSON(ruta_config_json, lector_glosa, archivos_disponibles)
    print("--- Inicialización Completa ---")

    for nombre_archivo in os.listdir(directorio_xlsm):
        if not nombre_archivo.endswith(".xlsm"):
            continue

        ruta_archivo = os.path.join(directorio_xlsm, nombre_archivo)
        print(f"\n--- Validando archivo: {nombre_archivo} ---")

        try:
            lector_xlsm = LectorXLSM(ruta_archivo)
            lector_xlsm.cargar_libro()

            print("Ejecutando validaciones fijas...")
            validador_fijo = ValidadorFijo(lector_xlsm)
            if validador_fijo.validar_todo():
                print("  Validaciones fijas PASARON.")
            else:
                print("  Validaciones fijas FALLARON:")
                for error in validador_fijo.obtener_errores():
                    print(f"    - {error}")

            print("Ejecutando validaciones JSON...")
            if validador_json.validar(lector_xlsm):
                print("  Validaciones JSON PASARON.")
            else:
                print("  Validaciones JSON FALLARON:")
                for error in validador_json.obtener_errores():
                    print(f"    - {error}")

            lector_xlsm.cerrar_libro()

        except ValueError as ve:
            print(f"  Omitiendo archivo por error: {ve}")
        except Exception as e:
            print(f"  Ocurrió un error inesperado: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validador de archivos XLSM para REM Inspector.")
    parser.add_argument("--xlsm_dir", type=str, default="original", help="Directorio con los archivos XLSM a validar.")
    parser.add_argument("--glosa_dir", type=str, default="glosa", help="Directorio con los archivos de glosa.")
    parser.add_argument("--config", type=str, default="config/validations.json", help="Ruta al archivo de configuración de validaciones JSON.")
    args = parser.parse_args()

    main(args.xlsm_dir, args.glosa_dir, args.config)
