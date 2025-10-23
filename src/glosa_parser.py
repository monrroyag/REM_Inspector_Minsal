import pandas as pd
import os
from openpyxl import load_workbook
import xlrd

class LectorGlosa:
    def __init__(self, directorio_glosa):
        self.directorio_glosa = directorio_glosa
        self.glosas = {}

    def _obtener_extension_archivo(self, ruta_archivo):
        return os.path.splitext(ruta_archivo)[1].lower()

    def cargar_archivo_glosa(self, ruta_archivo):
        extension = self._obtener_extension_archivo(ruta_archivo)
        try:
            if extension in ['.xlsx', '.xlsm']:
                df = pd.read_excel(ruta_archivo)
            elif extension == '.xls':
                df = pd.read_excel(ruta_archivo, engine='xlrd')
            else:
                print(f"Omitiendo tipo de archivo no soportado: {ruta_archivo}")
                return None
            
            nombre_archivo = os.path.basename(ruta_archivo)
            serie_match = nombre_archivo.replace("GLOSA_S", "").split(".")[0]
            serie = serie_match.upper()

            df = df.iloc[:, :10]
            df.columns = [
                "CodigoPrestacion", "TextoPrestacion", "Serie", "Year", 
                "tipodato", "posicion", "hoja", "linea", "inicio", "fin"
            ]
            
            df['CodigoPrestacion'] = df['CodigoPrestacion'].astype(str)

            self.glosas[serie] = df
            print(f"Glosa cargada para la serie {serie} desde {ruta_archivo}")
            return df
        except Exception as e:
            print(f"Error al cargar el archivo de glosa {ruta_archivo}: {e}")
            return None

    def cargar_todas_glosas(self):
        for nombre_archivo in os.listdir(self.directorio_glosa):
            if nombre_archivo.startswith("GLOSA_S") and (nombre_archivo.endswith(".xlsx") or nombre_archivo.endswith(".xls")):
                ruta_archivo = os.path.join(self.directorio_glosa, nombre_archivo)
                self.cargar_archivo_glosa(ruta_archivo)

    def obtener_glosa_por_serie(self, serie):
        return self.glosas.get(serie.upper())

    def obtener_info_prestacion(self, serie, codigo_prestacion):
        df_glosa = self.obtener_glosa_por_serie(serie)
        if df_glosa is not None:
            resultado_df = df_glosa[df_glosa['CodigoPrestacion'] == str(codigo_prestacion)]
            if not resultado_df.empty:
                return resultado_df.iloc[0]
        return None

if __name__ == "__main__":
    directorio_actual = os.path.dirname(__file__)
    ruta_glosa = os.path.join(directorio_actual, '..', 'glosa')
    
    lector = LectorGlosa(ruta_glosa)
    lector.cargar_todas_glosas()

    if 'A' in lector.glosas:
        print("\nGlosa para la Serie A:")
        print(lector.obtener_glosa_por_serie('A').head())
        
        info_prestacion = lector.obtener_info_prestacion('A', '01010101')
        if info_prestacion is not None:
            print(f"\nInformación para CodigoPrestacion 01010101 en Serie A:\n{info_prestacion}")
        else:
            print("\nCodigoPrestacion 01010101 no encontrado en Serie A.")
    else:
        print("\nGlosa de Serie A no cargada.")

    if 'BM' in lector.glosas:
        print("\nGlosa para la Serie BM:")
        print(lector.obtener_glosa_por_serie('BM').head())
