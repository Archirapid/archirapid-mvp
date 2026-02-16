"""
Editor interactivo de planos 2D con validación IA
"""
import streamlit as st
from typing import Dict, List
import json

class InteractiveFloorEditor:
    """Editor de planos con ajustes en tiempo real"""
    
    def __init__(self, design, ai_validator):
        self.design = design
        self.ai_validator = ai_validator
    
    def render(self):
        """Renderiza el editor completo"""
        
        st.markdown("### ✏️ Editor de Distribución")
        st.caption("Ajusta las dimensiones de cada habitación. La IA te guiará en tiempo real.")
        
        # Separar habitaciones por categorías
        main_rooms = []
        service_rooms = []
        extras = []
        
        for room in self.design.rooms:
            code = room.room_type.code.lower()
            if any(x in code for x in ['salon', 'cocina', 'dormitorio']):
                main_rooms.append(room)
            elif any(x in code for x in ['bano', 'pasillo', 'bodega']):
                service_rooms.append(room)
            else:
                extras.append(room)
        
        # Tabs por categoría
        tab1, tab2, tab3 = st.tabs(["🏠 Espacios Principales", "🔧 Servicios", "🌿 Extras"])
        
        changes_made = False
        validation_messages = []
        
        with tab1:
            for room in main_rooms:
                changes, msgs = self._render_room_editor(room, "main")
                if changes:
                    changes_made = True
                validation_messages.extend(msgs)
        
        with tab2:
            for room in service_rooms:
                changes, msgs = self._render_room_editor(room, "service")
                if changes:
                    changes_made = True
                validation_messages.extend(msgs)
        
        with tab3:
            for room in extras:
                changes, msgs = self._render_room_editor(room, "extra")
                if changes:
                    changes_made = True
                validation_messages.extend(msgs)
        
        if validation_messages:
            st.markdown("---")
            st.markdown("### 🤖 Validación en Tiempo Real")
            for msg in validation_messages:
                if "✅" in msg:
                    st.success(msg)
                elif "⚠️" in msg:
                    st.warning(msg)
                elif "❌" in msg:
                    st.error(msg)
        
        if changes_made:
            st.markdown("---")
            if st.button("💾 Aplicar Cambios", type="primary"):
                st.session_state["design_modified"] = True
                st.success("✅ Cambios aplicados")
                st.rerun()
    
    def _render_room_editor(self, room, category: str):
        """Renderiza editor de una habitación"""
        
        changes_made = False
        messages = []
        
        with st.container():
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                st.markdown(f"**{room.room_type.name}**")
            
            with col2:
                st.caption(f"Actual: {room.area_m2:.0f} m²")
            
            with col3:
                if category == "main":
                    color = "🔵"
                elif category == "service":
                    color = "🟠"
                else:
                    color = "🟢"
                st.caption(color)
            
            min_val = float(room.room_type.min_m2)
            max_val = float(room.room_type.max_m2)
            current_val = float(room.area_m2)
            
            new_area = st.slider(
                f"m² {room.room_type.name}",
                min_value=min_val,
                max_value=max_val,
                value=current_val,
                step=0.5,
                key=f"editor_{room.room_type.code}_{id(room)}",
                label_visibility="collapsed"
            )
            
            if abs(new_area - current_val) > 0.1:
                changes_made = True
                room.area_m2 = new_area
                validation = self._validate_room_size(room, new_area)
                messages.append(validation)
            
            st.markdown("---")
        
        return changes_made, messages
    
    def _validate_room_size(self, room, new_area: float) -> str:
        """Valida tamaño de habitación"""
        
        code = room.room_type.code.lower()
        name = room.room_type.name
        
        if 'salon' in code or 'cocina' in code:
            if new_area < 25:
                return f"⚠️ **{name}**: {new_area:.0f}m² es pequeño. Recomendado: 30m²+"
            elif new_area > 45:
                return f"⚠️ **{name}**: {new_area:.0f}m² muy grande"
            else:
                return f"✅ **{name}**: {new_area:.0f}m² - Adecuado"
        
        elif 'dormitorio' in code and 'principal' in code:
            if new_area < 12:
                return f"❌ **{name}**: {new_area:.0f}m² muy pequeño. Mínimo: 12m²"
            elif new_area < 15:
                return f"⚠️ **{name}**: {new_area:.0f}m² justo. Recomendado: 16-20m²"
            else:
                return f"✅ **{name}**: {new_area:.0f}m² - Correcto"
        
        elif 'dormitorio' in code:
            if new_area < 9:
                return f"❌ **{name}**: {new_area:.0f}m² muy pequeño. Mínimo: 9m²"
            else:
                return f"✅ **{name}**: {new_area:.0f}m² - Correcto"
        
        elif 'bano' in code or 'baño' in code:
            if new_area < 4:
                return f"❌ **{name}**: {new_area:.0f}m² muy pequeño. Mínimo: 4m²"
            elif new_area < 5:
                return f"⚠️ **{name}**: {new_area:.0f}m² justo. Recomendado: 6m²"
            else:
                return f"✅ **{name}**: {new_area:.0f}m² - Adecuado"
        
        else:
            return f"✅ **{name}**: {new_area:.0f}m²"
