# modules/marketplace/architects_entry.py
"""
Punto de entrada blindado para el panel de arquitectos.
Esta es la ÚNICA forma de acceder al panel de arquitectos.
"""

import streamlit as st

def render_architects_panel(ctx: dict):
    """
    Función pública para renderizar el panel de arquitectos.
    
    Args:
        ctx (dict): Contexto requerido con las siguientes claves:
            - architect_id: ID del arquitecto
            - architect_email: Email del arquitecto
            - subscription_active: Booleano indicando si la suscripción está activa
            - db: Módulo de base de datos (src.db)
    """
    # Validar que el contexto contiene las claves requeridas
    required_keys = ['architect_id', 'architect_email', 'subscription_active', 'db']
    for key in required_keys:
        if key not in ctx:
            st.error(f"Error: Falta la clave requerida '{key}' en el contexto.")
            return
    
    # Extraer valores del contexto
    architect_id = ctx['architect_id']
    architect_email = ctx['architect_email']
    subscription_active = ctx['subscription_active']
    db = ctx['db']
    
    # Validar que architect_id y architect_email existen y no están vacíos
    if not architect_id or not architect_email:
        st.error("Error: architect_id y architect_email son requeridos y no pueden estar vacíos.")
        return
    
    # Configurar el estado de sesión para el arquitecto
    st.session_state['architect_id'] = architect_id
    st.session_state['architect_email'] = architect_email
    st.session_state['subscription_active'] = subscription_active
    
    # Importar y llamar al flujo actual de marketplace_upload.py
    from . import marketplace_upload
    marketplace_upload.main()