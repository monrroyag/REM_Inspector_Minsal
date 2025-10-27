# REM Inspector 2.0 - Sistema de Validación de Datos

## Resumen
Este proyecto desarrolla un sistema robusto para la validación de datos en archivos `.xlsm` de la serie REM. El sistema utiliza una base de datos centralizada (`Global.mdb`) para la "glosa" y la información de versiones, permitiendo validaciones dinámicas basadas en JSON, además de aplicar validaciones fijas obligatorias sobre los nombres de archivo y el contenido de hojas específicas.

## Características

### 1. Validaciones Fijas (Hardcoded)
Estas son validaciones obligatorias integradas directamente en el código, asegurando la integridad fundamental de los archivos `.xlsm`.

*   **Convención de Nombres de Archivo:** Cada archivo `.xlsm` debe seguir el formato `[código_establecimiento][serie][mes].xlsm` (ej., `116322A05.xlsm`).
*   **Validaciones en la Hoja "NOMBRE":**
    *   El código de establecimiento (ej., `116322`) debe estar separado en celdas individuales desde `C3:H3` y coincidir con el código de establecimiento del nombre del archivo.
    *   Las celdas `B2`, `B3`, `C2:G2` deben contener datos.
    *   La celda `B6` debe contener el nombre del mes escrito en letras mayúsculas (ej., `MAYO`).
    *   Las celdas `C6:D6` deben contener la representación numérica del mes (ej., `C6=0`, `D6=5` para Mayo).
*   **Validación de Versión:** Compara la versión del archivo XLSM (extraída de `NOMBRE!A9:B9`) con la versión esperada definida en la base de datos `Global.mdb` para el año, mes y serie correspondientes.

### 2. Validaciones Basadas en JSON
Estas validaciones son dinámicas y configurables a través de archivos JSON. Permiten comparaciones flexibles entre celdas, rangos y valores constantes, utilizando la información de la base de datos `Global.mdb`.

*   **Tipos de Comparación:** `>` (mayor que), `<` (menor que), `>=` (mayor o igual que), `<=` (menor o igual que), `!=` (diferente de), `==` (igual a).
*   **Objetivos de Comparación:** Celdas con celdas, rangos con celdas, rangos con rangos, o valores con números constantes.
*   **Operadores Lógicos:** Soporte para `AND` (Y) y `OR` (O) para reglas de validación complejas.
*   **Validaciones Inter-Series:** Capacidad de comparar valores entre archivos de glosa de diferentes series. **Importante:** Las validaciones inter-series solo se ejecutarán si existen archivos `.xlsm` para *todas* las series involucradas en la validación, con el mismo código de establecimiento y mes, en el directorio `original`.
*   **Filtrado por Serie:** Las reglas JSON pueden especificar `target_series` para aplicarse solo a archivos de series específicas.

### 3. Reporte de Errores Mejorado
Los mensajes de error generados por el sistema son ahora más informativos y fáciles de entender para el usuario final:
*   Se construyen dinámicamente utilizando el `TextoPrestacion` de la glosa y el operador de comparación, eliminando la necesidad de mensajes predefinidos en el JSON.
*   Las referencias a las columnas ahora incluyen la serie, hoja y celda/rango en un formato claro (ej. "Serie: A, Hoja: A29, Celda: C64").
*   Los códigos internos (`CodigoPrestacion`) no se muestran en los mensajes de error.

## Convención de Nombres de Archivo XLSM
Los archivos `.xlsm` a validar siguen una convención de nombres específica:
`[código_establecimiento][serie][mes].xlsm`
Ejemplo: `116322A05.xlsm`
*   `116322`: Código de Establecimiento
*   `A`: Serie
*   `05`: Mes (ej., Mayo)

## Estructura del Proyecto

```
.
├── README.md
├── requirements.txt
├── main.py                     # Script principal para ejecutar validaciones
├── config/
│   └── validations.json        # Archivo de configuración de validaciones JSON
├── glosa/
│   └── Global.mdb              # Base de datos centralizada para glosas y versiones
├── original/
│   ├── 116304A07.xlsm
│   ├── 116321A01.xlsm
│   └── ...
└── src/
    ├── glosa_parser.py         # Módulo para leer y parsear la base de datos MDB
    ├── xlsm_parser.py          # Módulo para leer y parsear archivos xlsm
    ├── hardcoded_validators.py # Módulo para validaciones fijas
    ├── json_validators.py      # Módulo para el motor de validaciones JSON
    └── utils.py                # Funciones de utilidad (ej., conversión de columnas)
```

## Instrucciones de Configuración

1.  **Crear un Entorno Virtual de Python:**
    ```bash
    python -m venv venv
    ```
2.  **Activar el Entorno Virtual:**
    *   **Windows:**
        ```bash
        .\venv\Scripts\activate
        ```
    *   **macOS/Linux:**
        ```bash
        source venv/bin/activate
        ```
3.  **Instalar Dependencias:**
    ```bash
    .\venv\Scripts\pip.exe install -r requirements.txt
    ```

## Uso

Para ejecutar el validador, navega a la raíz del proyecto y ejecuta el script `main.py` usando el intérprete de Python del entorno virtual:

```bash
.\venv\Scripts\python.exe main.py
```

Puedes especificar directorios personalizados para los archivos XLSM, glosa y el archivo de configuración JSON usando los argumentos `--xlsm_dir`, `--glosa_dir` y `--config` respectivamente.

Ejemplo:
```bash
.\venv\Scripts\python.exe main.py --xlsm_dir "mis_archivos_rem" --glosa_dir "mis_glosas" --config "config/mis_reglas.json"
```

El sistema imprimirá los resultados de las validaciones directamente en la consola, indicando qué validaciones pasaron o fallaron, junto con mensajes detallados para los errores.
