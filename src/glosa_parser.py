import pandas as pd
import os
import pyodbc # New dependency for MDB access
from sqlalchemy import create_engine # Import SQLAlchemy
import re # Import regex module
# Removed warnings import and filter from here, as it's handled in main.py

class LectorGlosaMDB:
    def __init__(self, ruta_mdb, year):
        self.ruta_mdb = ruta_mdb
        self.year = year
        self.engine = self._crear_motor_sqlalchemy() # Create SQLAlchemy engine
        self.glosas_df = None # This will store the combined and filtered DataFrame
        self.versions_df = None # New attribute for versions table
        self._cargar_glosas_desde_mdb()
        self._cargar_versiones_desde_mdb() # Load versions table

    def _crear_motor_sqlalchemy(self):
        """Creates a SQLAlchemy engine for the MDB file."""
        try:
            # Connection string for sqlalchemy-access
            connection_uri = (
                f"access+pyodbc:///?odbc_connect="
                f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};"
                f"DBQ={self.ruta_mdb};"
            )
            return create_engine(connection_uri)
        except Exception as e:
            print(f"  Error al crear el motor de SQLAlchemy: {e}")
            return None

    def _cargar_glosas_desde_mdb(self):
        """
        Carga las glosas desde la tabla 'Diccionario' en el archivo MDB,
        filtrando por el año especificado.
        """
        if not self.engine:
            return

        try:
            # Select columns in the order they appear in the image
            query = f"SELECT CodigoPrestacion, Mes, Year, TextoPrestacion, Hoja, Serie, Posicion, tipoDato, linea, Inicio, Fin FROM Diccionario WHERE Year = {self.year}"
            # print(f"DEBUG: Ejecutando consulta MDB para año {self.year}: {query}") # Removed debug print
            self.glosas_df = pd.read_sql(query, self.engine)

            # Convert column names to lowercase to match expected keys in json_validators.py
            self.glosas_df.columns = self.glosas_df.columns.str.lower()

            # Ensure CodigoPrestacion is string type for consistent lookups
            self.glosas_df['codigoprestacion'] = self.glosas_df['codigoprestacion'].astype(str)
            if not self.glosas_df.empty:
                # Removed debug prints
                pass 
            else:
                # print(f"DEBUG: No se cargaron glosas para el año {self.year} (DataFrame vacío).") # Removed debug print
                pass
        except pyodbc.Error as ex:
            sqlstate = ex.args[0]
            if sqlstate == '01000':
                print(f"Advertencia: No se encontraron datos de glosa para el año {self.year} en el MDB. {ex}")
            else:
                print(f"Error MDB: {ex}") # More concise error message
            # Define columns in lowercase to match the standardization
            self.glosas_df = pd.DataFrame(columns=[
                "codigoprestacion", "mes", "year", "textoprestacion", "hoja", 
                "serie", "posicion", "tipodato", "linea", "inicio", "fin"
            ])
        except Exception as e:
            print(f"Error inesperado al cargar glosas desde MDB: {e}") # More concise error message
            # Define columns in lowercase for consistency
            self.glosas_df = pd.DataFrame(columns=[
                "codigoprestacion", "mes", "year", "textoprestacion", "hoja", 
                "serie", "posicion", "tipodato", "linea", "inicio", "fin"
            ])

    def obtener_glosa_por_serie(self, serie):
        """
        Devuelve un DataFrame con las glosas para una serie específica,
        manejando el formato 'SERIE X' del MDB.
        """
        if self.glosas_df is not None:
            # Adjust comparison to handle 'SERIE A' vs 'A' using the lowercase column name
            # It seems the MDB stores series like 'SERIE A1', 'SERIE BM1', etc.
            # We need to match based on the start of the string.
            return self.glosas_df[self.glosas_df['serie'].str.upper().str.startswith(f"SERIE {serie.upper()}")]
        return pd.DataFrame()

    def obtener_info_prestacion(self, serie, codigo_prestacion):
        """
        Obtiene la información de una prestación específica para una serie y código.
        """
        df_glosa_serie = self.obtener_glosa_por_serie(serie)
        if not df_glosa_serie.empty:
            # Use lowercase column name for CodigoPrestacion
            resultado_df = df_glosa_serie[df_glosa_serie['codigoprestacion'] == str(codigo_prestacion)]
            if not resultado_df.empty:
                return resultado_df.iloc[0]
        return None

    def _cargar_versiones_desde_mdb(self):
        """
        Carga todas las versiones desde la tabla 'Version' en el archivo MDB
        en un DataFrame para filtrado en memoria.
        """
        if not self.engine:
            return

        try:
            # Using pyodbc directly to bypass potential pandas/SQLAlchemy quirks with the 'Version' table
            # Correcting column names based on user-provided image of 'Version' table structure
            query = "SELECT [Ano], [Mes], [Serie], [SerieExcel], [version] FROM [Version]"
            self.versions_df = pd.read_sql(query, self.engine)

            # Convert column names to lowercase for consistent filtering
            self.versions_df.columns = self.versions_df.columns.str.lower()

            # Ensure types are consistent for filtering
            self.versions_df['ano'] = self.versions_df['ano'].astype(int)
            self.versions_df['mes'] = self.versions_df['mes'].astype(int)
            self.versions_df['serie'] = self.versions_df['serie'].astype(str) # Added 'serie' column
            self.versions_df['serieexcel'] = self.versions_df['serieexcel'].astype(str)
            self.versions_df['version'] = self.versions_df['version'].astype(str) # Corrected from 'versiontexto' to 'version'

            # Normalize 'serieexcel' by removing 'SERIE ' prefix for easier comparison
            self.versions_df['serieexcel'] = self.versions_df['serieexcel'].str.replace('SERIE ', '', regex=False).str.strip()

            if self.versions_df.empty:
                print(f"  Advertencia: No se cargaron datos de la tabla 'Version' desde '{self.ruta_mdb}'.")
        except pyodbc.Error as ex:
            print(f"  Error MDB al cargar tabla 'Version': {ex}")
            self.versions_df = pd.DataFrame(columns=["ano", "mes", "serie", "serieexcel", "version"]) # Corrected columns
        except Exception as e:
            print(f"  Error inesperado al cargar tabla 'Version' desde MDB: {e}")
            self.versions_df = pd.DataFrame(columns=["ano", "mes", "serie", "serieexcel", "version"]) # Corrected columns

    def obtener_version_esperada(self, year, month, serie):
        """
        Obtiene la versión esperada filtrando el DataFrame de versiones cargado en memoria.
        """
        if self.versions_df is None or self.versions_df.empty:
            print(f"  Advertencia: No hay datos de versión cargados para filtrar.")
            return None

        try:
            # Adjust comparison for 'serieexcel' to handle potential 'SERIE X' format in MDB
            # The 'serie' parameter comes from the XLSM filename (e.g., 'A', 'BM')
            # The 'serieexcel' column in MDB might be 'SERIE A', 'SERIE BM', etc.
            filtered_version = self.versions_df[
                (self.versions_df['ano'] == int(year)) &
                (self.versions_df['mes'] == int(month)) &
                (self.versions_df['serieexcel'].str.upper().str.startswith(serie.upper()))
            ]

            if not filtered_version.empty:
                return filtered_version.iloc[0]['version'] # Corrected from 'versiontexto' to 'version'
            else:
                print(f"  Advertencia: No se encontró versión para Año={year}, Mes={month}, Serie={serie} en el DataFrame de versiones.")
                return None
        except Exception as e:
            print(f"  Error al filtrar versiones en memoria: {e}")
            return None

    def _normalize_version_string(self, raw_version_text):
        """
        Normaliza una cadena de versión para extraer solo el número de versión (e.g., '1.2').
        Busca patrones como 'Versión X.Y' o 'X.Y'.
        """
        if not isinstance(raw_version_text, str):
            return None
        
        # Try to find 'Versión X.Y' or 'X.Y' pattern
        match = re.search(r'(?:Versión\s*)?(\d+\.\d+)', raw_version_text, re.IGNORECASE)
        if match:
            return match.group(1) # Return only the numeric part
        return raw_version_text.strip() # Fallback to original string if no pattern found

if __name__ == "__main__":
    # Example usage (for testing purposes)
    # This part will need to be adapted based on the actual location of Global.mdb
    # and how the year is extracted from the XLSM file.
    
    # For demonstration, let's assume Global.mdb is in the parent directory
    # and we are testing with year 2025.
    directorio_actual = os.path.dirname(__file__)
    ruta_mdb_global = os.path.join(directorio_actual, '..', 'glosa', 'Global.mdb') # Corrected path to glosa/Global.mdb
    test_year = 2025 # Example year

    lector_mdb = LectorGlosaMDB(ruta_mdb_global, test_year)

    if lector_mdb.glosas_df is not None and not lector_mdb.glosas_df.empty:
        print(f"\nTotal glosas cargadas para el año {test_year}: {len(lector_mdb.glosas_df)}")
        print("\nPrimeras 5 filas del DataFrame de glosas:")
        print(lector_mdb.glosas_df.head())

        # Example of getting glosa for a specific series
        glosa_serie_a = lector_mdb.obtener_glosa_por_serie('A')
        if not glosa_serie_a.empty:
            print("\nGlosa para la Serie A (primeras 5 filas):")
            print(glosa_serie_a.head())
            
            # Example of getting info for a specific prestacion
            info_prestacion = lector_mdb.obtener_info_prestacion('A', '01010101') # Example code
            if info_prestacion is not None:
                print(f"\nInformación para CodigoPrestacion 01010101 en Serie A:\n{info_prestacion}")
            else:
                print("\nCodigoPrestacion 01010101 no encontrado en Serie A para el año y serie especificados.")
        else:
            print("\nGlosa de Serie A no cargada para el año especificado.")
    else:
        print(f"\nNo se cargaron glosas desde el MDB para el año {test_year}.")

    # Test the new version retrieval method
    print("\n--- Probando obtener_version_esperada ---")
    test_month = 1 # January
    test_serie = 'A' # Example series
    expected_version_raw = lector_mdb.obtener_version_esperada(test_year, test_month, test_serie)
    expected_version_normalized = lector_mdb._normalize_version_string(expected_version_raw)
    if expected_version_normalized:
        print(f"Versión esperada (normalizada) para Año={test_year}, Mes={test_month}, Serie={test_serie}: {expected_version_normalized}")
    else:
        print(f"No se pudo obtener la versión esperada para Año={test_year}, Mes={test_month}, Serie={test_serie}.")
