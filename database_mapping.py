"""
🗄️ MAPEO DE INTERACCIONES CON database.db
Generado: 2026-02-15
"""

TABLA_ARCHIVOS = {
    "plots": [
        "modules/marketplace/owners.py - Insertar/actualizar fincas publicadas por propietarios",
        "modules/marketplace/utils.py - Funciones CRUD (insert_plot, list_published_plots)",
        "modules/marketplace/client_panel.py - Consultar fincas compradas/reservadas por clientes",
        "modules/ai_house_designer/flow.py - Cargar datos de parcela para diseño",
        "app.py - Listar fincas en marketplace"
    ],
    
    "projects": [
        "modules/marketplace/utils.py - CRUD de proyectos arquitectónicos",
        "modules/marketplace/project_search.py - Búsqueda de proyectos compatibles",
        "app.py - Marketplace de proyectos"
    ],
    
    "architects": [
        "modules/marketplace/utils.py - Registro de arquitectos",
        "app.py - Login de arquitectos"
    ],
    
    "clients": [
        "modules/marketplace/utils.py - Registro de clientes",
        "modules/marketplace/client_panel.py - Panel de cliente",
        "app.py - Login de clientes"
    ],
    
    "owners": [
        "modules/marketplace/owners.py - Registro y gestión de propietarios",
        "app.py - Login de propietarios"
    ],
    
    "users": [
        "app.py - Sistema de autenticación unificado",
        "modules/marketplace/utils.py - insert_user, verificación de usuarios"
    ],
    
    "reservations": [
        "modules/marketplace/client_panel.py - Reservas de fincas por clientes",
        "modules/marketplace/utils.py - insert_reservation"
    ],
    
    "proposals": [
        "modules/marketplace/architect_proposals.py - Propuestas de arquitectos a fincas",
        "modules/marketplace/client_panel.py - Ver propuestas recibidas"
    ],
    
    "client_interests": [
        "modules/marketplace/project_search.py - Guardar interés de cliente en proyecto",
        "modules/marketplace/client_panel.py - Ver intereses guardados"
    ],
    
    "subscriptions": [
        "backend/main.py - Gestión de suscripciones de arquitectos",
        "modules/marketplace/utils.py - Verificar límites de plan"
    ],
    
    "service_providers": [
        "modules/marketplace/utils.py - CRUD de proveedores de servicios",
        "backend/main.py - Asignación de servicios post-venta"
    ],
    
    "service_assignments": [
        "backend/main.py - Asignar constructores/topógrafos a ventas",
        "modules/marketplace/client_panel.py - Ver servicios asignados"
    ],
    
    "payments": [
        "modules/marketplace/payment_flow.py - Procesar pagos de clientes",
        "modules/marketplace/client_panel.py - Historial de pagos"
    ],
    
    "project_purchases": [
        "modules/marketplace/project_search.py - Compra de proyectos (memoria, CAD)",
        "modules/marketplace/client_panel.py - Proyectos comprados"
    ],
    
    "additional_services": [
        "backend/main.py - Servicios adicionales cotizados post-venta",
        "modules/marketplace/client_panel.py - Ver servicios adicionales"
    ],
    
    "ventas_proyectos": [
        "backend/main.py - Registro de ventas de proyectos (legacy)"
    ],
    
    "proyectos": [
        "backend/main.py - Tabla legacy de proyectos en español"
    ],
    
    "arquitectos": [
        "backend/main.py - Tabla legacy de arquitectos en español"
    ]
}

# Imprimir resumen
for tabla, archivos in TABLA_ARCHIVOS.items():
    print(f"\n📋 {tabla.upper()}")
    print("=" * 70)
    for archivo in archivos:
        print(f"  • {archivo}")
