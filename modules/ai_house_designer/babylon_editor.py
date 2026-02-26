"""
Editor 3D avanzado usando Babylon.js
"""

def generate_babylon_html(rooms_data, total_width, total_depth):
    """
    Genera HTML con Babylon.js editor
    
    Args:
        rooms_data: Lista de habitaciones con coordenadas
        total_width: Ancho total de la casa
        total_depth: Profundidad total de la casa
    
    Returns:
        str: HTML completo con Babylon.js
    """
    
    import json
    rooms_js = json.dumps(rooms_data, ensure_ascii=False)


    js_scale_observer = """
                    // Solo permitir escalar en X y Z (no en Y/altura)
                    gizmoManager.gizmos.scaleGizmo.xGizmo.isEnabled = true;
                    gizmoManager.gizmos.scaleGizmo.yGizmo.isEnabled = false;
                    gizmoManager.gizmos.scaleGizmo.zGizmo.isEnabled = true;

                    console.log('Modo: Escalar (arrastra cubos en esquinas)');

                    gizmoManager.gizmos.scaleGizmo.onDragEndObservable.clear();

                    if (selectedMesh.name.startsWith('floor_')) {
                        const roomIndex = parseInt(selectedMesh.name.split('_')[1]);
                        console.log('DEBUG: Añadiendo observable para roomIndex=' + roomIndex);
                        gizmoManager.gizmos.scaleGizmo.onDragEndObservable.add(() => {
                            console.log('DEBUG: Drag finalizado!');
                            scene.registerAfterRender(function waitFrame() {
                                scene.unregisterAfterRender(waitFrame);
                                updateRoomInfo(selectedMesh, roomIndex);
                                updateBudget();
                                console.log('Paneles actualizados roomIndex=' + roomIndex);
                            });
                        });
                    } else {
                        alert('Primero selecciona una habitación con modo Seleccionar');
                        setMode('select');
                    }
"""