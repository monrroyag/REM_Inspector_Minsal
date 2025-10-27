import sys
import json
import os
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton,
    QLineEdit, QLabel, QMessageBox, QComboBox, QTextEdit, QDialog, QFormLayout,
    QGroupBox, QGridLayout, QSizePolicy
)
from PyQt6.QtCore import Qt
from src.glosa_parser import LectorGlosaMDB

VALIDATIONS_FILE = 'config/validations.json'
MDB_PATH = 'glosa/Global.mdb'
DEFAULT_YEAR = 2025 # Default year for glosa lookup

# --- Nuevo Widget para editar componentes de suma de prestaciones ---
class PrestacionSumEditor(QGroupBox):
    def __init__(self, lector_glosa, parent=None):
        super().__init__("Componentes de Suma", parent)
        self.lector_glosa = lector_glosa
        self.components = [] # List of prestacion components
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()

        # Table to display components
        self.components_table = QTableWidget()
        self.components_table.setColumnCount(4) # Code, Series, Column/Range, Text
        self.components_table.setHorizontalHeaderLabels(["Código", "Serie", "Columna/Rango", "Texto Prestación"])
        self.components_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.components_table.itemSelectionChanged.connect(self._on_component_selection_changed)
        main_layout.addWidget(self.components_table)

        # Input fields for a single component
        component_input_group = QGroupBox("Añadir/Editar Componente")
        component_input_layout = QFormLayout()
        component_input_group.setLayout(component_input_layout)

        self.comp_code_input = QLineEdit()
        self.comp_code_input.setPlaceholderText("Código de Prestación")
        self.comp_code_input.textChanged.connect(self._update_comp_prestacion_text)
        self.comp_prestacion_label = QLabel("")
        component_input_layout.addRow("Código:", self.comp_code_input)
        component_input_layout.addRow("Texto Prestación:", self.comp_prestacion_label)

        self.comp_series_input = QLineEdit()
        self.comp_series_input.setPlaceholderText("Serie (ej: A)")
        component_input_layout.addRow("Serie (opcional):", self.comp_series_input)

        self.comp_col_offset_input = QLineEdit()
        self.comp_col_offset_input.setPlaceholderText("Offset Columna (ej: 1) o Rango (ej: 1-4)")
        component_input_layout.addRow("Columna/Rango:", self.comp_col_offset_input)

        main_layout.addWidget(component_input_group)

        # Buttons for component actions
        comp_button_layout = QHBoxLayout()
        self.add_comp_button = QPushButton("Añadir Componente")
        self.add_comp_button.clicked.connect(self._add_component)
        self.update_comp_button = QPushButton("Actualizar Componente")
        self.update_comp_button.clicked.connect(self._update_component)
        self.update_comp_button.setEnabled(False)
        self.delete_comp_button = QPushButton("Eliminar Componente")
        self.delete_comp_button.clicked.connect(self._delete_component)
        self.delete_comp_button.setEnabled(False)
        self.clear_comp_button = QPushButton("Limpiar Campos")
        self.clear_comp_button.clicked.connect(self._clear_component_inputs)

        comp_button_layout.addWidget(self.add_comp_button)
        comp_button_layout.addWidget(self.update_comp_button)
        comp_button_layout.addWidget(self.delete_comp_button)
        comp_button_layout.addWidget(self.clear_comp_button)
        main_layout.addLayout(comp_button_layout)

        self.setLayout(main_layout)
        self._populate_components_table()

    def _update_comp_prestacion_text(self):
        code = self.comp_code_input.text().strip()
        series = self.comp_series_input.text().strip() or "A" # Default series for lookup
        if code:
            info = self.lector_glosa.obtener_info_prestacion(series, code)
            if info is not None and not info.empty:
                self.comp_prestacion_label.setText(info["textoprestacion"].strip())
            else:
                self.comp_prestacion_label.setText("No encontrado")
        else:
            self.comp_prestacion_label.setText("")

    def _populate_components_table(self):
        self.components_table.setRowCount(0)
        for i, comp in enumerate(self.components):
            self.components_table.insertRow(i)
            code = comp.get("codigo", "")
            series = comp.get("series", "")
            col_offset = comp.get("column_offset", "")
            col_range_start = comp.get("column_offset_start", "")
            col_range_end = comp.get("column_offset_end", "")

            col_info = ""
            if col_offset:
                col_info = f"COL{col_offset}"
            elif col_range_start and col_range_end:
                col_info = f"COL{col_range_start}-{col_range_end}"
            
            self.components_table.setItem(i, 0, QTableWidgetItem(code))
            self.components_table.setItem(i, 1, QTableWidgetItem(series))
            self.components_table.setItem(i, 2, QTableWidgetItem(col_info))
            
            # Get prestacion text for display
            info = self.lector_glosa.obtener_info_prestacion(series or "A", code)
            prestacion_text = info["textoprestacion"].strip() if info is not None and not info.empty else "No encontrado"
            self.components_table.setItem(i, 3, QTableWidgetItem(prestacion_text))
        self.components_table.resizeColumnsToContents()
        self.components_table.horizontalHeader().setStretchLastSection(True)

    def _on_component_selection_changed(self):
        selected_items = self.components_table.selectedItems()
        if selected_items:
            self.update_comp_button.setEnabled(True)
            self.delete_comp_button.setEnabled(True)
            self.add_comp_button.setEnabled(False)
            row = selected_items[0].row()
            self._load_component_into_editor(self.components[row])
        else:
            self.update_comp_button.setEnabled(False)
            self.delete_comp_button.setEnabled(False)
            self.add_comp_button.setEnabled(True)
            self._clear_component_inputs()

    def _load_component_into_editor(self, comp_data):
        self.comp_code_input.setText(comp_data.get("codigo", ""))
        self.comp_series_input.setText(comp_data.get("series", ""))
        
        if "column_offset" in comp_data:
            self.comp_col_offset_input.setText(str(comp_data["column_offset"]))
        elif "column_offset_start" in comp_data and "column_offset_end" in comp_data:
            self.comp_col_offset_input.setText(f"{comp_data['column_offset_start']}-{comp_data['column_offset_end']}")
        else:
            self.comp_col_offset_input.clear()
        self._update_comp_prestacion_text()

    def _get_component_from_inputs(self):
        comp = {"type": "prestacion"} # Components are always prestacion type
        code = self.comp_code_input.text().strip()
        series = self.comp_series_input.text().strip()
        col_offset_str = self.comp_col_offset_input.text().strip()

        if not code:
            QMessageBox.warning(self, "Advertencia", "El código de prestación no puede estar vacío.")
            return None
        comp["codigo"] = code
        if series:
            comp["series"] = series
        
        if '-' in col_offset_str:
            try:
                start, end = map(int, col_offset_str.split('-'))
                comp["column_offset_start"] = start
                comp["column_offset_end"] = end
            except ValueError:
                QMessageBox.warning(self, "Advertencia", "Formato de rango de columna inválido. Usa 'inicio-fin'.")
                return None
        elif col_offset_str:
            try:
                comp["column_offset"] = int(col_offset_str)
            except ValueError:
                QMessageBox.warning(self, "Advertencia", "Offset de columna inválido. Debe ser un número entero.")
                return None
        else:
            QMessageBox.warning(self, "Advertencia", "Offset o rango de columna no puede estar vacío para prestación.")
            return None
        return comp

    def _add_component(self):
        new_comp = self._get_component_from_inputs()
        if new_comp:
            self.components.append(new_comp)
            self._populate_components_table()
            self._clear_component_inputs()

    def _update_component(self):
        selected_items = self.components_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Advertencia", "Selecciona un componente para actualizar.")
            return
        row = selected_items[0].row()
        updated_comp = self._get_component_from_inputs()
        if updated_comp:
            self.components[row] = updated_comp
            self._populate_components_table()
            self._clear_component_inputs()
            self.update_comp_button.setEnabled(False)
            self.delete_comp_button.setEnabled(False)
            self.add_comp_button.setEnabled(True)

    def _delete_component(self):
        selected_items = self.components_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Advertencia", "Selecciona un componente para eliminar.")
            return
        row = selected_items[0].row()
        del self.components[row]
        self._populate_components_table()
        self._clear_component_inputs()
        self.update_comp_button.setEnabled(False)
        self.delete_comp_button.setEnabled(False)
        self.add_comp_button.setEnabled(True)

    def _clear_component_inputs(self):
        self.comp_code_input.clear()
        self.comp_series_input.clear()
        self.comp_col_offset_input.clear()
        self.comp_prestacion_label.clear()
        self.components_table.clearSelection()

    def set_components(self, components_list):
        self.components = components_list
        self._populate_components_table()
        self._clear_component_inputs()

    def get_components(self):
        return self.components

# --- Widget para editar un operando (LHS o RHS de una regla) ---
class OperandEditor(QGroupBox):
    def __init__(self, title, lector_glosa, parent=None):
        super().__init__(title, parent)
        self.lector_glosa = lector_glosa
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout()
        self.setLayout(layout)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["prestacion", "constant", "suma de prestaciones"])
        self.type_combo.currentIndexChanged.connect(self._update_fields)
        layout.addRow("Tipo:", self.type_combo)

        # --- Campos para 'prestacion' ---
        self.prestacion_group = QWidget()
        prestacion_layout = QFormLayout(self.prestacion_group)
        prestacion_layout.setContentsMargins(0, 0, 0, 0)
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("Código de Prestación")
        self.code_input.textChanged.connect(self._update_prestacion_text)
        self.prestacion_label = QLabel("")
        prestacion_layout.addRow("Código:", self.code_input)
        prestacion_layout.addRow("Texto Prestación:", self.prestacion_label)
        self.series_input = QLineEdit()
        self.series_input.setPlaceholderText("Serie (ej: A)")
        prestacion_layout.addRow("Serie (opcional):", self.series_input)
        self.col_offset_input = QLineEdit()
        self.col_offset_input.setPlaceholderText("Offset Columna (ej: 1) o Rango (ej: 1-4)")
        prestacion_layout.addRow("Columna/Rango:", self.col_offset_input)
        layout.addRow(self.prestacion_group)

        # --- Campo para 'constant' ---
        self.constant_value_input = QLineEdit()
        self.constant_value_input.setPlaceholderText("Valor Constante")
        layout.addRow("Valor Constante:", self.constant_value_input)

        # --- Editor para 'suma de prestaciones' ---
        self.sum_prestacion_editor = PrestacionSumEditor(self.lector_glosa, self)
        layout.addRow(self.sum_prestacion_editor)

        self._update_fields() # Llamada inicial para establecer la visibilidad correcta

    def _update_fields(self):
        op_type = self.type_combo.currentText()
        is_prestacion = (op_type == "prestacion")
        is_constant = (op_type == "constant")
        is_sum_prestacion = (op_type == "suma de prestaciones")

        self.prestacion_group.setVisible(is_prestacion)
        self.constant_value_input.setVisible(is_constant)
        self.sum_prestacion_editor.setVisible(is_sum_prestacion)
        self.prestacion_label.setText("")

    def _update_prestacion_text(self):
        code = self.code_input.text().strip()
        series = self.series_input.text().strip() or "A"
        if code:
            info = self.lector_glosa.obtener_info_prestacion(series, code)
            self.prestacion_label.setText(info["textoprestacion"].strip() if info is not None and not info.empty else "No encontrado")
        else:
            self.prestacion_label.setText("")

    def set_operand(self, operand_data):
        op_type = operand_data.get("type", "prestacion")
        self.type_combo.setCurrentText(op_type)

        if op_type == "prestacion":
            self.code_input.setText(operand_data.get("codigo", ""))
            self.series_input.setText(operand_data.get("series", ""))
            if "column_offset" in operand_data:
                self.col_offset_input.setText(str(operand_data["column_offset"]))
            elif "column_offset_start" in operand_data and "column_offset_end" in operand_data:
                self.col_offset_input.setText(f"{operand_data['column_offset_start']}-{operand_data['column_offset_end']}")
            else:
                self.col_offset_input.clear()
            self._update_prestacion_text()
        elif op_type == "constant":
            self.constant_value_input.setText(str(operand_data.get("value", "")))
        elif op_type == "suma de prestaciones":
            self.sum_prestacion_editor.set_components(operand_data.get("components", []))

    def get_operand(self):
        operand = {}
        op_type = self.type_combo.currentText()
        operand["type"] = op_type

        if op_type == "prestacion":
            code = self.code_input.text().strip()
            if not code:
                QMessageBox.warning(self, "Advertencia", f"El código de prestación en '{self.title()}' no puede estar vacío.")
                return None
            operand["codigo"] = code
            
            series = self.series_input.text().strip()
            if series:
                operand["series"] = series

            col_offset_str = self.col_offset_input.text().strip()
            if not col_offset_str:
                QMessageBox.warning(self, "Advertencia", f"El offset o rango de columna en '{self.title()}' no puede estar vacío.")
                return None
            if '-' in col_offset_str:
                try:
                    start, end = map(int, col_offset_str.split('-'))
                    operand["column_offset_start"] = start
                    operand["column_offset_end"] = end
                except ValueError:
                    QMessageBox.warning(self, "Advertencia", f"Formato de rango de columna en '{self.title()}' inválido. Usa 'inicio-fin'.")
                    return None
            else:
                try:
                    operand["column_offset"] = int(col_offset_str)
                except ValueError:
                    QMessageBox.warning(self, "Advertencia", f"Offset de columna en '{self.title()}' inválido. Debe ser un número entero.")
                    return None
        elif op_type == "constant":
            value = self.constant_value_input.text().strip()
            if not value:
                QMessageBox.warning(self, "Advertencia", f"El valor constante en '{self.title()}' no puede estar vacío.")
                return None
            try: operand["value"] = int(value)
            except ValueError:
                try: operand["value"] = float(value)
                except ValueError: operand["value"] = value
        elif op_type == "suma de prestaciones":
            components = self.sum_prestacion_editor.get_components()
            if not components:
                QMessageBox.warning(self, "Advertencia", f"Una 'suma de prestaciones' en '{self.title()}' debe tener al menos un componente.")
                return None
            operand["components"] = components
        return operand

    def clear(self):
        self.type_combo.setCurrentIndex(0)
        self.code_input.clear()
        self.series_input.clear()
        self.col_offset_input.clear()
        self.constant_value_input.clear()
        self.prestacion_label.clear()
        self.sum_prestacion_editor.set_components([])

# --- Nuevo Diálogo para editar condiciones ---
class RuleConditionEditorDialog(QDialog):
    def __init__(self, current_conditions, lector_glosa, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editar Condiciones de Regla")
        self.setGeometry(200, 200, 1000, 700)
        self.lector_glosa = lector_glosa
        self.conditions = current_conditions if current_conditions else {"logical_operator": "AND", "rules": []}
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # --- Tabla de Sub-Reglas ---
        self.rules_table = QTableWidget()
        self.rules_table.setColumnCount(5)
        self.rules_table.setHorizontalHeaderLabels(["LHS Tipo", "LHS Valor", "Operador", "RHS Tipo", "RHS Valor"])
        self.rules_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.rules_table.itemSelectionChanged.connect(self._on_sub_rule_selection_changed)
        main_layout.addWidget(self.rules_table)

        # --- Editor de Sub-Reglas ---
        sub_rule_editor_group = QGroupBox("Detalles de Sub-Regla")
        sub_rule_layout = QGridLayout(sub_rule_editor_group)
        
        self.lhs_editor = OperandEditor("LHS (Lado Izquierdo)", self.lector_glosa)
        self.rhs_editor = OperandEditor("RHS (Lado Derecho)", self.lector_glosa)

        operator_layout = QVBoxLayout()
        operator_layout.addStretch()
        operator_layout.addWidget(QLabel("Operador:"))
        self.operator_combo = QComboBox()
        self.operator_map = {
            "==": "igual a", "!=": "diferente de", "<": "menor que",
            "<=": "menor o igual que", ">": "mayor que", ">=": "mayor o igual que",
        }
        self.reverse_operator_map = {v: k for k, v in self.operator_map.items()}
        self.operator_combo.addItems(self.operator_map.values())
        operator_layout.addWidget(self.operator_combo)
        operator_layout.addStretch()

        sub_rule_layout.addWidget(self.lhs_editor, 0, 0)
        sub_rule_layout.addLayout(operator_layout, 0, 1)
        sub_rule_layout.addWidget(self.rhs_editor, 0, 2)
        main_layout.addWidget(sub_rule_editor_group)

        # --- Botones de Acción para Sub-Reglas ---
        sub_rule_button_layout = QHBoxLayout()
        self.add_sub_rule_button = QPushButton("Añadir Sub-Regla")
        self.add_sub_rule_button.clicked.connect(self._add_sub_rule)
        self.update_sub_rule_button = QPushButton("Actualizar Sub-Regla")
        self.update_sub_rule_button.clicked.connect(self._update_sub_rule)
        self.update_sub_rule_button.setEnabled(False)
        self.delete_sub_rule_button = QPushButton("Eliminar Sub-Regla")
        self.delete_sub_rule_button.clicked.connect(self._delete_sub_rule)
        self.delete_sub_rule_button.setEnabled(False)
        self.clear_sub_rule_button = QPushButton("Limpiar Campos")
        self.clear_sub_rule_button.clicked.connect(self._clear_sub_rule_inputs)
        sub_rule_button_layout.addWidget(self.add_sub_rule_button)
        sub_rule_button_layout.addWidget(self.update_sub_rule_button)
        sub_rule_button_layout.addWidget(self.delete_sub_rule_button)
        sub_rule_button_layout.addWidget(self.clear_sub_rule_button)
        main_layout.addLayout(sub_rule_button_layout)

        # --- Botones del Diálogo ---
        dialog_button_layout = QHBoxLayout()
        self.ok_button = QPushButton("Aceptar")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.clicked.connect(self.reject)
        dialog_button_layout.addStretch()
        dialog_button_layout.addWidget(self.ok_button)
        dialog_button_layout.addWidget(self.cancel_button)
        main_layout.addLayout(dialog_button_layout)

        self._populate_sub_rules_table()

    def _populate_sub_rules_table(self):
        self.rules_table.setRowCount(0)
        for i, rule in enumerate(self.conditions.get("rules", [])):
            self.rules_table.insertRow(i)
            lhs = rule["lhs"]
            rhs = rule["rhs"]
            operator = rule["operator"]

            self.rules_table.setItem(i, 0, QTableWidgetItem(lhs.get("type", "")))
            self.rules_table.setItem(i, 1, QTableWidgetItem(self._get_operand_display_text(lhs)))
            self.rules_table.setItem(i, 2, QTableWidgetItem(self.operator_map.get(operator, operator)))
            self.rules_table.setItem(i, 3, QTableWidgetItem(rhs.get("type", "")))
            self.rules_table.setItem(i, 4, QTableWidgetItem(self._get_operand_display_text(rhs)))
        self.rules_table.resizeColumnsToContents()
        self.rules_table.horizontalHeader().setStretchLastSection(True)

    def _get_operand_display_text(self, operand_data):
        if operand_data.get("type") == "constant":
            return str(operand_data.get("value", ""))
        elif operand_data.get("type") == "prestacion":
            code = operand_data.get("codigo", "")
            series = operand_data.get("series", "")
            col_offset = operand_data.get("column_offset", "")
            col_range_start = operand_data.get("column_offset_start", "")
            col_range_end = operand_data.get("column_offset_end", "")

            col_info = ""
            if col_offset:
                col_info = f"COL{col_offset}"
            elif col_range_start and col_range_end:
                col_info = f"COL{col_range_start}-{col_range_end}"
            
            return f"Cód: {code} (Serie: {series}, {col_info})"
        elif operand_data.get("type") == "suma de prestaciones":
            components = operand_data.get("components", [])
            if not components:
                return "SUM()"
            
            component_strings = []
            for comp in components:
                code = comp.get("codigo", "")
                series = comp.get("series", "")
                col_offset = comp.get("column_offset", "")
                col_range_start = comp.get("column_offset_start", "")
                col_range_end = comp.get("column_offset_end", "")

                col_info = ""
                if col_offset:
                    col_info = f"COL{col_offset}"
                elif col_range_start and col_range_end:
                    col_info = f"COL{col_range_start}-{col_range_end}"
                
                component_strings.append(f"Cód: {code} ({series}, {col_info})")
            return f"SUM({', '.join(component_strings)})"
        return ""

    def _on_sub_rule_selection_changed(self):
        selected_items = self.rules_table.selectedItems()
        if selected_items:
            self.update_sub_rule_button.setEnabled(True)
            self.delete_sub_rule_button.setEnabled(True)
            self.add_sub_rule_button.setEnabled(False) # Disable add when editing
            row = selected_items[0].row()
            self._load_sub_rule_into_editor(self.conditions["rules"][row])
        else:
            self.update_sub_rule_button.setEnabled(False)
            self.delete_sub_rule_button.setEnabled(False)
            self.add_sub_rule_button.setEnabled(True)
            self._clear_sub_rule_inputs()

    def _load_sub_rule_into_editor(self, rule_data):
        self.lhs_editor.set_operand(rule_data.get("lhs", {}))
        self.rhs_editor.set_operand(rule_data.get("rhs", {}))
        operator = rule_data.get("operator", "==")
        self.operator_combo.setCurrentText(self.operator_map.get(operator, operator))

    def _add_sub_rule(self):
        lhs_operand = self.lhs_editor.get_operand()
        rhs_operand = self.rhs_editor.get_operand()
        operator = self.reverse_operator_map.get(self.operator_combo.currentText(), self.operator_combo.currentText())

        if lhs_operand is None or rhs_operand is None:
            return # Error message already shown by _get_operand_from_inputs

        new_sub_rule = {"lhs": lhs_operand, "operator": operator, "rhs": rhs_operand}
        self.conditions["rules"].append(new_sub_rule)
        self._populate_sub_rules_table()
        self._clear_sub_rule_inputs()

    def _update_sub_rule(self):
        selected_items = self.rules_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Advertencia", "Selecciona una sub-regla para actualizar.")
            return

        row = selected_items[0].row()
        lhs_operand = self.lhs_editor.get_operand()
        rhs_operand = self.rhs_editor.get_operand()
        operator = self.reverse_operator_map.get(self.operator_combo.currentText(), self.operator_combo.currentText())

        if lhs_operand is None or rhs_operand is None:
            return

        updated_sub_rule = {"lhs": lhs_operand, "operator": operator, "rhs": rhs_operand}
        self.conditions["rules"][row] = updated_sub_rule
        self._populate_sub_rules_table()
        self._clear_sub_rule_inputs()
        self.update_sub_rule_button.setEnabled(False)
        self.delete_sub_rule_button.setEnabled(False)
        self.add_sub_rule_button.setEnabled(True)

    def _delete_sub_rule(self):
        selected_items = self.rules_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Advertencia", "Selecciona una sub-regla para eliminar.")
            return

        row = selected_items[0].row()
        del self.conditions["rules"][row]
        self._populate_sub_rules_table()
        self._clear_sub_rule_inputs()
        self.update_sub_rule_button.setEnabled(False)
        self.delete_sub_rule_button.setEnabled(False)
        self.add_sub_rule_button.setEnabled(True)

    def _clear_sub_rule_inputs(self):
        self.lhs_editor.clear()
        self.rhs_editor.clear()
        self.operator_combo.setCurrentIndex(0)
        self.rules_table.clearSelection()


    def get_conditions(self):
        # Default to AND if not explicitly set or if the combo box was removed
        self.conditions["logical_operator"] = "AND" 
        return self.conditions

class ValidationApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gestor de Reglas de Validación")
        self.setGeometry(100, 100, 1000, 700)
        self.lector_glosa = LectorGlosaMDB(MDB_PATH, DEFAULT_YEAR)
        self.rules = self.load_rules()
        self.init_ui()

    def load_rules(self):
        try:
            with open(VALIDATIONS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                rules_dict = {rule["name"]: rule for rule in data.get("validations", [])}
                return rules_dict
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            QMessageBox.critical(self, "Error", "Error al leer el archivo de validaciones. Asegúrate de que sea un JSON válido.")
            return {}

    def save_rules(self):
        try:
            rules_list = list(self.rules.values())
            with open(VALIDATIONS_FILE, 'w', encoding='utf-8') as f:
                json.dump({"validations": rules_list}, f, indent=4, ensure_ascii=False)
            QMessageBox.information(self, "Éxito", "Reglas guardadas correctamente.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al guardar las reglas: {e}")

    def init_ui(self):
        main_layout = QVBoxLayout()

        input_form_layout = QFormLayout()
        
        self.rule_name_input = QLineEdit()
        self.rule_name_input.setPlaceholderText("Nombre único de la Regla")
        input_form_layout.addRow("Nombre de la Regla:", self.rule_name_input)

        self.target_series_input = QLineEdit()
        self.target_series_input.setPlaceholderText("Ej: A, BM (separar por comas si son múltiples)")
        input_form_layout.addRow("Series Objetivo:", self.target_series_input)

        self.conditions_summary_label = QLabel("Condiciones: No definidas")
        self.conditions_summary_label.setWordWrap(True)
        self.edit_conditions_button = QPushButton("Editar Condiciones...")
        self.edit_conditions_button.clicked.connect(self._open_condition_editor)
        
        conditions_layout = QHBoxLayout()
        conditions_layout.addWidget(self.conditions_summary_label)
        conditions_layout.addWidget(self.edit_conditions_button)
        input_form_layout.addRow("Definir Condiciones:", conditions_layout)

        main_layout.addLayout(input_form_layout)

        button_layout = QHBoxLayout()
        self.add_button = QPushButton("Agregar Regla")
        self.add_button.clicked.connect(self.add_rule)
        self.edit_button = QPushButton("Guardar Edición")
        self.edit_button.clicked.connect(self.edit_rule)
        self.edit_button.setEnabled(False)
        self.delete_button = QPushButton("Eliminar Regla")
        self.delete_button.clicked.connect(self.delete_rule)
        self.delete_button.setEnabled(False)
        self.clear_button = QPushButton("Limpiar Campos")
        self.clear_button.clicked.connect(self.clear_inputs)

        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.edit_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addWidget(self.clear_button)

        self.rules_table = QTableWidget()
        self.rules_table.setColumnCount(3)
        self.rules_table.setHorizontalHeaderLabels(["Nombre", "Series Objetivo", "Resumen Condiciones"])
        self.rules_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.rules_table.itemSelectionChanged.connect(self.on_selection_changed)

        main_layout.addLayout(button_layout)
        main_layout.addWidget(self.rules_table)

        self.setLayout(main_layout)
        self.current_editing_conditions = {"logical_operator": "AND", "rules": []} # Store conditions being edited
        self.populate_table()

    def _open_condition_editor(self):
        dialog = RuleConditionEditorDialog(self.current_editing_conditions, self.lector_glosa, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.current_editing_conditions = dialog.get_conditions()
            self._update_conditions_summary()

    def _update_conditions_summary(self):
        if self.current_editing_conditions and self.current_editing_conditions.get("rules"):
            num_rules = len(self.current_editing_conditions["rules"])
            op = self.current_editing_conditions.get("logical_operator", "AND")
            self.conditions_summary_label.setText(f"Condiciones: {num_rules} sub-regla(s) con operador '{op}'")
        else:
            self.conditions_summary_label.setText("Condiciones: No definidas")

    def populate_table(self):
        self.rules_table.setRowCount(0)
        for rule_name, rule_data in self.rules.items():
            row_position = self.rules_table.rowCount()
            self.rules_table.insertRow(row_position)
            self.rules_table.setItem(row_position, 0, QTableWidgetItem(rule_name))
            
            target_series = rule_data.get("target_series", "")
            if isinstance(target_series, list):
                target_series = ", ".join(target_series)
            self.rules_table.setItem(row_position, 1, QTableWidgetItem(target_series))

            conditions = rule_data.get("conditions", {})
            num_rules = len(conditions.get("rules", []))
            op = conditions.get("logical_operator", "AND")
            summary_text = f"{num_rules} sub-regla(s) con '{op}'" if num_rules > 0 else "No definidas"
            self.rules_table.setItem(row_position, 2, QTableWidgetItem(summary_text))
        self.rules_table.resizeColumnsToContents()
        self.rules_table.horizontalHeader().setStretchLastSection(True)

    def on_selection_changed(self):
        selected_items = self.rules_table.selectedItems()
        if selected_items:
            self.edit_button.setEnabled(True)
            self.delete_button.setEnabled(True)
            row = selected_items[0].row()
            rule_name = self.rules_table.item(row, 0).text()
            rule_data = self.rules.get(rule_name, {})

            self.rule_name_input.setText(rule_name)
            
            target_series = rule_data.get("target_series", "")
            if isinstance(target_series, list):
                target_series = ", ".join(target_series)
            self.target_series_input.setText(target_series)
            
            self.current_editing_conditions = rule_data.get("conditions", {"logical_operator": "AND", "rules": []})
            self._update_conditions_summary()
        else:
            self.edit_button.setEnabled(False)
            self.delete_button.setEnabled(False)
            self.clear_inputs()

    def add_rule(self):
        rule_name = self.rule_name_input.text().strip()
        target_series_str = self.target_series_input.text().strip()
        conditions = self.current_editing_conditions

        if not rule_name:
            QMessageBox.warning(self, "Advertencia", "El nombre de la regla no puede estar vacío.")
            return
        if not conditions.get("rules"):
            QMessageBox.warning(self, "Advertencia", "Las condiciones de la regla no pueden estar vacías. Por favor, define al menos una sub-regla.")
            return

        if rule_name in self.rules:
            QMessageBox.warning(self, "Advertencia", f"La regla '{rule_name}' ya existe. Usa 'Guardar Edición' para modificarla.")
            return
        
        target_series = [s.strip() for s in target_series_str.split(',')] if target_series_str else []
        if len(target_series) == 1:
            target_series = target_series[0]

        new_rule = {"name": rule_name, "conditions": conditions}
        if target_series:
            new_rule["target_series"] = target_series

        self.rules[rule_name] = new_rule
        self.save_rules()
        self.populate_table()
        self.clear_inputs()

    def edit_rule(self):
        selected_items = self.rules_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Advertencia", "Selecciona una regla para editar.")
            return

        old_rule_name = self.rules_table.item(selected_items[0].row(), 0).text()
        new_rule_name = self.rule_name_input.text().strip()
        new_target_series_str = self.target_series_input.text().strip()
        new_conditions = self.current_editing_conditions

        if not new_rule_name:
            QMessageBox.warning(self, "Advertencia", "El nombre de la regla no puede estar vacío.")
            return
        if not new_conditions.get("rules"):
            QMessageBox.warning(self, "Advertencia", "Las condiciones de la regla no pueden estar vacías. Por favor, define al menos una sub-regla.")
            return

        if old_rule_name != new_rule_name and new_rule_name in self.rules:
            QMessageBox.warning(self, "Advertencia", f"Ya existe una regla con el nombre '{new_rule_name}'.")
            return
        
        new_target_series = [s.strip() for s in new_target_series_str.split(',')] if new_target_series_str else []
        if len(new_target_series) == 1:
            new_target_series = new_target_series[0]

        # Update rule name if changed
        if old_rule_name != new_rule_name:
            self.rules[new_rule_name] = self.rules.pop(old_rule_name)

        self.rules[new_rule_name]["conditions"] = new_conditions
        if new_target_series:
            self.rules[new_rule_name]["target_series"] = new_target_series
        elif "target_series" in self.rules[new_rule_name]:
            del self.rules[new_rule_name]["target_series"]

        self.save_rules()
        self.populate_table()
        self.clear_inputs()
        self.edit_button.setEnabled(False)
        self.delete_button.setEnabled(False)

    def delete_rule(self):
        selected_items = self.rules_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Advertencia", "Selecciona una regla para eliminar.")
            return

        rule_name_to_delete = self.rules_table.item(selected_items[0].row(), 0).text()

        reply = QMessageBox.question(self, "Confirmar Eliminación",
                                     f"¿Estás seguro de que quieres eliminar la regla '{rule_name_to_delete}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            if rule_name_to_delete in self.rules:
                del self.rules[rule_name_to_delete]
                self.save_rules()
                self.populate_table()
                self.clear_inputs()
                self.edit_button.setEnabled(False)
                self.delete_button.setEnabled(False)

    def clear_inputs(self):
        self.rule_name_input.clear()
        self.target_series_input.clear()
        self.current_editing_conditions = {"logical_operator": "AND", "rules": []}
        self._update_conditions_summary()
        self.rules_table.clearSelection()
        self.edit_button.setEnabled(False)
        self.delete_button.setEnabled(False)

# --- Nueva ventana para visualizar validaciones en Markdown ---
class MarkdownViewerDialog(QDialog):
    def __init__(self, rules, parent=None):
        super().__init__(parent)
        self.rules = rules
        self.selected_folders = []
        self.setWindowTitle("Visualizador de Validaciones (Markdown)")
        self.setGeometry(150, 150, 800, 600)
        self.init_ui()
        self.generate_markdown()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        # --- Panel de Selección de Carpetas ---
        folders_group = QGroupBox("Selección de Carpetas")
        folders_layout = QVBoxLayout(folders_group)
        
        self.folder_list_widget = QListWidget()
        self.folder_list_widget.setToolTip("Carpetas seleccionadas para una futura operación.")
        folders_layout.addWidget(self.folder_list_widget)
        
        folder_button_layout = QHBoxLayout()
        add_folder_button = QPushButton("Añadir Carpeta")
        add_folder_button.clicked.connect(self.add_folder)
        remove_folder_button = QPushButton("Quitar Carpeta Seleccionada")
        remove_folder_button.clicked.connect(self.remove_folder)
        folder_button_layout.addWidget(add_folder_button)
        folder_button_layout.addWidget(remove_folder_button)
        folders_layout.addLayout(folder_button_layout)
        
        main_layout.addWidget(folders_group)

        # --- Panel de Visualización de Markdown ---
        markdown_group = QGroupBox("Validaciones en Formato Markdown")
        markdown_layout = QVBoxLayout(markdown_group)
        
        self.markdown_display = QTextEdit()
        self.markdown_display.setReadOnly(True)
        markdown_layout.addWidget(self.markdown_display)
        
        copy_button = QPushButton("Copiar Todo al Portapapeles")
        copy_button.clicked.connect(self.copy_to_clipboard)
        markdown_layout.addWidget(copy_button)
        
        main_layout.addWidget(markdown_group)

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta")
        if folder and folder not in self.selected_folders:
            self.selected_folders.append(folder)
            self.folder_list_widget.addItem(QListWidgetItem(folder))

    def remove_folder(self):
        selected_items = self.folder_list_widget.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            folder_path = item.text()
            if folder_path in self.selected_folders:
                self.selected_folders.remove(folder_path)
            self.folder_list_widget.takeItem(self.folder_list_widget.row(item))

    def generate_markdown(self):
        markdown_text = "# Resumen de Reglas de Validación\n\n"
        for rule_name, rule_data in self.rules.items():
            markdown_text += f"## Regla: `{rule_name}`\n\n"
            
            target_series = rule_data.get("target_series", "Cualquiera")
            if isinstance(target_series, list):
                target_series = ", ".join(target_series)
            markdown_text += f"- **Series Objetivo:** `{target_series}`\n"
            
            conditions = rule_data.get("conditions", {})
            op = conditions.get("logical_operator", "AND")
            markdown_text += f"- **Operador Lógico:** `{op}`\n"
            
            markdown_text += "- **Condiciones:**\n"
            
            sub_rules = conditions.get("rules", [])
            if not sub_rules:
                markdown_text += "  - *No hay condiciones definidas.*\n"
            else:
                for i, sub_rule in enumerate(sub_rules):
                    lhs = self._format_operand(sub_rule.get('lhs', {}))
                    rhs = self._format_operand(sub_rule.get('rhs', {}))
                    operator = sub_rule.get('operator', '?')
                    markdown_text += f"  - **{i+1}:** `{lhs}` **{operator}** `{rhs}`\n"
            markdown_text += "\n---\n\n"
            
        self.markdown_display.setMarkdown(markdown_text)

    def _format_operand(self, operand):
        op_type = operand.get("type")
        if op_type == "constant":
            return f"Constante({operand.get('value')})"
        elif op_type == "prestacion":
            code = operand.get('codigo', '')
            series = operand.get('series', 'A')
            col = ""
            if 'column_offset' in operand:
                col = f"Columna_Offset={operand['column_offset']}"
            elif 'column_offset_start' in operand:
                col = f"Rango_Columnas={operand['column_offset_start']}-{operand['column_offset_end']}"
            return f"Prestación(Código={code}, Serie={series}, {col})"
        elif op_type == "suma de prestaciones":
            components = [self._format_operand(c) for c in operand.get("components", [])]
            return f"Suma({', '.join(components)})"
        return "Operando_Desconocido"

    def copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.markdown_display.toPlainText())
        QMessageBox.information(self, "Éxito", "El contenido ha sido copiado al portapapeles.")

# --- Nueva ventana para visualizar validaciones en Markdown ---
class MarkdownViewerDialog(QDialog):
    def __init__(self, rules, parent=None):
        super().__init__(parent)
        self.rules = rules
        self.selected_folders = []
        self.setWindowTitle("Visualizador de Validaciones (Markdown)")
        self.setGeometry(150, 150, 800, 600)
        self.init_ui()
        self.generate_markdown()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        # --- Panel de Selección de Carpetas ---
        folders_group = QGroupBox("Selección de Carpetas")
        folders_layout = QVBoxLayout(folders_group)
        
        self.folder_list_widget = QListWidget()
        self.folder_list_widget.setToolTip("Carpetas seleccionadas para una futura operación.")
        folders_layout.addWidget(self.folder_list_widget)
        
        folder_button_layout = QHBoxLayout()
        add_folder_button = QPushButton("Añadir Carpeta")
        add_folder_button.clicked.connect(self.add_folder)
        remove_folder_button = QPushButton("Quitar Carpeta Seleccionada")
        remove_folder_button.clicked.connect(self.remove_folder)
        folder_button_layout.addWidget(add_folder_button)
        folder_button_layout.addWidget(remove_folder_button)
        folders_layout.addLayout(folder_button_layout)
        
        main_layout.addWidget(folders_group)

        # --- Panel de Visualización de Markdown ---
        markdown_group = QGroupBox("Validaciones en Formato Markdown")
        markdown_layout = QVBoxLayout(markdown_group)
        
        self.markdown_display = QTextEdit()
        self.markdown_display.setReadOnly(True)
        markdown_layout.addWidget(self.markdown_display)
        
        copy_button = QPushButton("Copiar Todo al Portapapeles")
        copy_button.clicked.connect(self.copy_to_clipboard)
        markdown_layout.addWidget(copy_button)
        
        main_layout.addWidget(markdown_group)

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta")
        if folder and folder not in self.selected_folders:
            self.selected_folders.append(folder)
            self.folder_list_widget.addItem(QListWidgetItem(folder))

    def remove_folder(self):
        selected_items = self.folder_list_widget.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            folder_path = item.text()
            if folder_path in self.selected_folders:
                self.selected_folders.remove(folder_path)
            self.folder_list_widget.takeItem(self.folder_list_widget.row(item))

    def generate_markdown(self):
        markdown_text = "# Resumen de Reglas de Validación\n\n"
        for rule_name, rule_data in self.rules.items():
            markdown_text += f"## Regla: `{rule_name}`\n\n"
            
            target_series = rule_data.get("target_series", "Cualquiera")
            if isinstance(target_series, list):
                target_series = ", ".join(target_series)
            markdown_text += f"- **Series Objetivo:** `{target_series}`\n"
            
            conditions = rule_data.get("conditions", {})
            op = conditions.get("logical_operator", "AND")
            markdown_text += f"- **Operador Lógico:** `{op}`\n"
            
            markdown_text += "- **Condiciones:**\n"
            
            sub_rules = conditions.get("rules", [])
            if not sub_rules:
                markdown_text += "  - *No hay condiciones definidas.*\n"
            else:
                for i, sub_rule in enumerate(sub_rules):
                    lhs = self._format_operand(sub_rule.get('lhs', {}))
                    rhs = self._format_operand(sub_rule.get('rhs', {}))
                    operator = sub_rule.get('operator', '?')
                    markdown_text += f"  - **{i+1}:** `{lhs}` **{operator}** `{rhs}`\n"
            markdown_text += "\n---\n\n"
            
        self.markdown_display.setMarkdown(markdown_text)

    def _format_operand(self, operand):
        op_type = operand.get("type")
        if op_type == "constant":
            return f"Constante({operand.get('value')})"
        elif op_type == "prestacion":
            code = operand.get('codigo', '')
            series = operand.get('series', 'A')
            col = ""
            if 'column_offset' in operand:
                col = f"Columna_Offset={operand['column_offset']}"
            elif 'column_offset_start' in operand:
                col = f"Rango_Columnas={operand['column_offset_start']}-{operand['column_offset_end']}"
            return f"Prestación(Código={code}, Serie={series}, {col})"
        elif op_type == "suma de prestaciones":
            components = [self._format_operand(c) for c in operand.get("components", [])]
            return f"Suma({', '.join(components)})"
        return "Operando_Desconocido"

    def copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.markdown_display.toPlainText())
        QMessageBox.information(self, "Éxito", "El contenido ha sido copiado al portapapeles.")

def run_gui():
    app = QApplication(sys.argv)
    ex = ValidationApp()
    ex.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    run_gui()
