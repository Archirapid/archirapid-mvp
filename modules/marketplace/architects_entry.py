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
    
    # Validar que architect_id existe y no está vacío
    if not architect_id:
        st.error("Error: architect_id es requerido y no puede estar vacío.")
        return
    # architect_email se usa para contexto, pero puede venir vacío si el formulario
    # no lo envió; en ese caso lo aceptamos para no bloquear el acceso.
    if not architect_email:
        st.warning("Aviso: email del arquitecto no proporcionado, se usará valor vacío.")
    
    # Configurar el estado de sesión para el arquitecto
    st.session_state['architect_id'] = architect_id
    st.session_state['architect_email'] = architect_email
    st.session_state['subscription_active'] = subscription_active
    
    # Importar y llamar al flujo actual de marketplace_upload.py
    from . import marketplace_upload
    marketplace_upload.main()