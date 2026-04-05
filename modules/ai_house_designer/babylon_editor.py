"""
Editor 3D avanzado usando Babylon.js
v3.2 - FIX 2026-04-05: dimensiones precisas (applyDimensions no llama generateLayoutJS),
       generateLayoutJS respeta width/depth existentes, packRows elimina huecos,
       notifyParentLayout sincroniza JSON al padre Streamlit via postMessage
"""

def generate_babylon_html(rooms_data, total_width, total_depth, roof_type="Dos aguas (clásico, eficiente)", plot_area_m2=0, foundation_type="Losa de hormigón (suelos blandos)", house_style="Moderno", cost_per_m2=1600):
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

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>ArchiRapid - Editor 3D</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: Arial, sans-serif; background: #1a1a2e; overflow: hidden; }}
        #renderCanvas {{ width: 100vw; height: 100vh; display: block; }}

        /* TOOLBAR IZQUIERDO */
        #toolbar {{
            position: absolute; top: 20px; left: 20px;
            background: rgba(0,0,0,0.88); padding: 14px;
            border-radius: 12px; color: white; width: 210px;
            border: 1px solid rgba(255,255,255,0.1);
            max-height: calc(100vh - 40px);
            overflow-y: auto;
            overflow-x: hidden;
            scrollbar-width: thin;
            scrollbar-color: rgba(52,152,219,0.5) transparent;
            transition: width 0.25s ease, padding 0.25s ease;
        }}
        #toolbar::-webkit-scrollbar {{ width: 4px; }}
        #toolbar::-webkit-scrollbar-track {{ background: transparent; }}
        #toolbar::-webkit-scrollbar-thumb {{ background: rgba(52,152,219,0.5); border-radius: 2px; }}
        #toolbar.collapsed {{
            width: 42px; padding: 10px 8px; overflow: hidden;
        }}
        #toolbar.collapsed .tool-btn,
        #toolbar.collapsed hr.divider,
        #toolbar.collapsed #edit-panel,
        #toolbar.collapsed #fence-options,
        #toolbar.collapsed h3 span {{ display: none; }}
        #toolbar.collapsed h3 {{ margin: 0; font-size: 18px; text-align: center; }}
        #toggle-toolbar {{
            float: right; background: none; border: none;
            color: rgba(255,255,255,0.6); cursor: pointer;
            font-size: 14px; padding: 0; line-height: 1;
        }}
        #toggle-toolbar:hover {{ color: white; }}
        #toolbar h3 {{ margin: 0 0 10px 0; font-size: 14px; opacity: 0.8; }}
        .tool-btn {{
            display: block; width: 100%; padding: 8px 10px;
            margin: 4px 0; background: rgba(52,152,219,0.2);
            border: 1px solid rgba(52,152,219,0.5); color: white;
            border-radius: 6px; cursor: pointer; font-size: 13px;
            transition: background 0.2s;
        }}
        .tool-btn:hover {{ background: rgba(52,152,219,0.4); }}
        .tool-btn.active {{ background: rgba(52,152,219,0.7); border-color: #3498DB; }}
        .tool-btn.green {{ background: rgba(46,204,113,0.25); border-color: #2ECC71; }}
        .tool-btn.green:hover {{ background: rgba(46,204,113,0.45); }}
        hr.divider {{ margin: 8px 0; border: none; border-top: 1px solid rgba(255,255,255,0.15); }}

        /* PANEL NUMÉRICO DE EDICIÓN */
        #edit-panel {{
            display: none;
            margin-top: 10px;
            padding: 10px;
            background: rgba(52,152,219,0.1);
            border: 1px solid rgba(52,152,219,0.4);
            border-radius: 8px;
        }}
        #edit-panel h4 {{ margin: 0 0 8px 0; font-size: 12px; color: #3498DB; }}
        #edit-panel label {{ font-size: 11px; opacity: 0.7; display: block; margin-top: 6px; }}
        #edit-panel input {{
            width: 100%; padding: 5px 8px; margin-top: 3px;
            background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.3);
            border-radius: 4px; color: white; font-size: 13px;
        }}
        #edit-panel input:focus {{ outline: none; border-color: #3498DB; }}
        #btn-apply {{
            display: block; width: 100%; padding: 7px;
            margin-top: 8px; background: rgba(46,204,113,0.3);
            border: 1px solid #2ECC71; color: white;
            border-radius: 5px; cursor: pointer; font-size: 13px;
        }}
        #btn-apply:hover {{ background: rgba(46,204,113,0.55); }}

        /* CTE SEMÁFORO */
        #cte-status {{
            margin-top: 8px; padding: 6px 8px;
            border-radius: 6px; font-size: 11px;
            display: none;
        }}
        #cte-status.ok {{ background: rgba(46,204,113,0.2); border: 1px solid #2ECC71; color: #2ECC71; }}
        #cte-status.warn {{ background: rgba(230,126,34,0.2); border: 1px solid #E67E22; color: #E67E22; }}
        #cte-status.fail {{ background: rgba(231,76,60,0.2); border: 1px solid #E74C3C; color: #E74C3C; }}

        /* PANEL INFO DERECHO */
        #info-panel {{
            position: absolute; top: 20px; right: 20px;
            background: rgba(0,0,0,0.88); padding: 14px;
            border-radius: 12px; color: white; width: 230px;
            border: 1px solid rgba(52,152,219,0.3);
        }}
        #info-panel h3 {{ margin: 0 0 8px 0; color: #3498DB; font-size: 14px; }}
        #room-info p {{ margin: 4px 0; font-size: 12px; }}

        /* PANEL PRESUPUESTO */
        #budget-panel {{
            position: absolute; top: 260px; right: 20px;
            background: rgba(46,204,113,0.12); padding: 12px;
            border-radius: 8px; color: white; width: 230px;
            border: 2px solid #2ECC71;
        }}
        #budget-panel h3 {{ margin: 0 0 6px 0; color: #2ECC71; font-size: 14px; }}
        #budget-info p {{ margin: 3px 0; font-size: 12px; }}

        /* BRÚJULA */
        #compass-wrap {{
            position: absolute; bottom: 80px; right: 20px;
            background: rgba(0,0,0,0.75); border-radius: 50%;
            width: 74px; height: 74px;
            border: 1px solid rgba(255,215,0,0.4);
            display: flex; align-items: center; justify-content: center;
        }}

        /* PANEL AVISO */
        #warning-panel {{
            position: absolute; bottom: 20px; right: 20px;
            background: rgba(230,126,34,0.12); padding: 10px;
            border-radius: 8px; color: white; width: 230px;
            border: 2px solid #E67E22;
        }}
        #warning-panel h3 {{ margin: 0 0 6px 0; color: #E67E22; font-size: 13px; }}
        #warning-panel p {{ font-size: 11px; line-height: 1.5; margin: 3px 0; }}
    </style>
    <script src="https://cdn.babylonjs.com/babylon.js"></script>
    <script src="https://cdn.babylonjs.com/gui/babylon.gui.min.js"></script>
    <script src="https://cdn.babylonjs.com/materialsLibrary/babylonjs.materials.min.js"></script>
    <script src="https://cdn.babylonjs.com/serializers/babylonjs.serializers.min.js"></script>
</head>
<body>
    <canvas id="renderCanvas"></canvas>

    <!-- TOOLBAR IZQUIERDO -->
    <div id="toolbar">
        <h3>🛠️ <span>Herramientas</span>
            <button id="toggle-toolbar" onclick="toggleToolbar()" title="Colapsar/Expandir">◀</button>
        </h3>
        <button class="tool-btn active" id="btn-select" onclick="setMode('select')">🖱️ Seleccionar</button>
        <button class="tool-btn" id="btn-move"   onclick="setMode('move')">↔️ Mover habitación</button>
        <button class="tool-btn" id="btn-scale"  onclick="setMode('scale')">📐 Editar dimensiones</button>

        <!-- PANEL NUMÉRICO — aparece al seleccionar en modo Editar dimensiones -->
        <div id="edit-panel">
            <h4>✏️ Editar dimensiones</h4>
            <div id="edit-room-name" style="font-size:12px; font-weight:bold; margin-bottom:4px;"></div>
            <label>Ancho (m)</label>
            <input type="number" id="input-width" min="1" max="20" step="0.1">
            <label>Fondo (m)</label>
            <input type="number" id="input-depth" min="1" max="20" step="0.1">
            <button id="btn-apply" onclick="applyDimensions()">✅ Aplicar</button>
            <div id="cte-status"></div>
            <div style="margin-top:10px;border-top:1px solid #555;padding-top:8px;">
              <label style="color:#aaa;font-size:11px;">Material Fachada</label>
              <select id="mat-select" onchange="applyMaterialPBR(selectedIndex, this.value)"
                      style="width:100%;background:#2a2a2a;color:#fff;border:1px solid #555;
                             border-radius:4px;padding:4px;margin-top:4px;font-size:12px;">
                <option value="">-- Sin material PBR --</option>
                <option value="ladrillo_cara_vista">Ladrillo Cara Vista -- 85€/m²</option>
                <option value="madera_laminada">Madera Laminada CLT -- 320€/m²</option>
                <option value="piedra_caliza">Piedra Caliza -- 145€/m²</option>
                <option value="hormigon_visto">Hormigón Visto HA-25 -- 95€/m²</option>
                <option value="plancha_acero_corten">Acero Corten -- 210€/m²</option>
              </select>
            </div>
        </div>

        <button class="tool-btn" id="btn-fence" onclick="toggleFence()">🧱 Cerramiento OFF</button>
        <div id="fence-options" style="display:none; margin-top:6px;">
            <select id="fence-style" style="width:100%;padding:4px;background:#1a1a2e;color:white;border:1px solid #3498DB;border-radius:4px;font-size:12px;">
                <option value="verja">⛓️ Verja metálica (1.8m)</option>
                <option value="muro">🧱 Muro de cemento (2.0m)</option>
            </select>
            <div id="fence-info" style="margin-top:8px; padding:8px; background:rgba(52,152,219,0.1);
                 border:1px solid rgba(52,152,219,0.3); border-radius:6px; font-size:11px; display:none;">
                <p style="margin:2px 0;">📏 <strong id="fence-dim-w">—</strong> × <strong id="fence-dim-d">—</strong> m</p>
                <p style="margin:2px 0;">📐 Superficie: <strong id="fence-area">—</strong> m²</p>
                <p style="margin:2px 0;">📏 Perímetro: <strong id="fence-perim">—</strong> m lineales</p>
                <p style="margin:2px 0; color:#2ECC71;">🏗️ Máx. construible: <strong id="fence-build">—</strong> m²</p>
            </div>
        </div>

        <!-- MEP Instalaciones -->
        <div style="margin-top:8px;border-top:1px solid #1e293b;padding-top:8px;">
          <div onclick="document.getElementById('mep_panel').style.display=document.getElementById('mep_panel').style.display==='none'?'block':'none'"
               style="cursor:pointer;color:#F5A623;font-size:11px;font-weight:700;letter-spacing:1px;
                      display:flex;align-items:center;justify-content:space-between;padding:4px 0;">
            <span>⚙️ INSTALACIONES MEP</span><span id="mep_toggle_arrow">▼</span>
          </div>
          <div id="mep_panel" style="display:none;">
            <!-- Ground transparency slider -->
            <div style="margin:6px 0;font-size:10px;color:#94a3b8;">Transparencia suelo</div>
            <div style="display:flex;align-items:center;gap:6px;margin-bottom:8px;">
              <span style="font-size:10px;color:#64748b;">🏔️</span>
              <input id="ground_alpha_slider" type="range" min="0" max="1" step="0.1" value="1"
                     oninput="setGroundTransparency(parseFloat(this.value))"
                     style="flex:1;accent-color:#F5A623;cursor:pointer;">
              <span style="font-size:10px;color:#64748b;">👁️</span>
            </div>
            <!-- Layer toggles -->
            <button id="mep_btn_sewage"     onclick="toggleMEPLayer('sewage')"
              style="width:100%;margin:2px 0;padding:5px 6px;background:#1e293b;border:1px solid #334155;
                     border-radius:6px;color:#94a3b8;font-size:10px;cursor:pointer;text-align:left;">
              🚽 Saneamiento
            </button>
            <button id="mep_btn_water"      onclick="toggleMEPLayer('water')"
              style="width:100%;margin:2px 0;padding:5px 6px;background:#1e293b;border:1px solid #334155;
                     border-radius:6px;color:#94a3b8;font-size:10px;cursor:pointer;text-align:left;">
              💧 Agua
            </button>
            <button id="mep_btn_electrical" onclick="toggleMEPLayer('electrical')"
              style="width:100%;margin:2px 0;padding:5px 6px;background:#1e293b;border:1px solid #334155;
                     border-radius:6px;color:#94a3b8;font-size:10px;cursor:pointer;text-align:left;">
              ⚡ Eléctrico
            </button>
            <button id="mep_btn_rainwater"  onclick="toggleMEPLayer('rainwater')"
              style="width:100%;margin:2px 0;padding:5px 6px;background:#1e293b;border:1px solid #334155;
                     border-radius:6px;color:#94a3b8;font-size:10px;cursor:pointer;text-align:left;">
              🌧️ Recogida Agua
            </button>
            <button id="mep_btn_domotics"   onclick="toggleMEPLayer('domotics')"
              style="width:100%;margin:2px 0;padding:5px 6px;background:#1e293b;border:1px solid #334155;
                     border-radius:6px;color:#94a3b8;font-size:10px;cursor:pointer;text-align:left;">
              📡 Domótica
            </button>
            <div style="margin-top:6px;padding:4px 6px;background:#0f172a;border-radius:4px;
                        font-size:9px;color:#475569;line-height:1.4;">
              Las capas MEP se construyen automáticamente con los datos del proyecto.
            </div>
          </div>
        </div>

        <hr class="divider">
        <button class="tool-btn" onclick="setTopView()">🔝 Vista Planta</button>
        <button class="tool-btn" onclick="setIsoView()">🏠 Vista 3D</button>
        <button class="tool-btn" onclick="setStreetView()">🚶 Vista Calle</button>
        <button class="tool-btn" id="btn-style" onclick="toggleStylePanel()">🎨 Estilo</button>
        
        <hr style="margin: 10px 0; border-color: rgba(255,255,255,0.2);">
        <button class="tool-btn" id="btn-capture" onclick="captureAllViews()"
                style="background: rgba(155,89,182,0.3); border-color: #9B59B6;">
            📸 Capturar Vistas
        </button>
        <div id="capture-status" style="font-size:11px; color:#9B59B6; margin-top:5px; display:none;">
            ✅ ZIP descargado — sube el archivo en Streamlit
        </div>
        <div id="capture-thumbs" style="display:none; margin-top:8px;">
            <p style="font-size:10px; color:#9B59B6; margin:0 0 4px 0;">Miniaturas capturadas:</p>
            <div id="thumb-grid" style="display:flex; flex-wrap:wrap; gap:3px;"></div>
        </div>
        
        <hr class="divider">
        <button class="tool-btn" id="btn-roof" onclick="toggleRoof()">🏠 Tejado OFF</button>
        <button class="tool-btn" id="btn-found" onclick="toggleFoundation()">🏗️ Cimientos OFF</button>
        <hr class="divider">
        <button class="tool-btn" onclick="resetLayout()">↩️ Reset Layout</button>
        <button class="tool-btn" onclick="undoLastAction()">⬅️ Deshacer</button>
        <button class="tool-btn" id="btn-delete" onclick="deleteSelected()" style="background:rgba(231,76,60,0.25);border-color:#E74C3C;">🗑️ Borrar seleccionado</button>
        <hr class="divider">
        <div style="font-size:10px;color:#F5A623;font-weight:700;letter-spacing:1px;margin-bottom:5px;">📍 POSICIÓN EN PARCELA</div>
        <div style="display:flex;align-items:center;gap:4px;margin-bottom:3px;">
          <span style="font-size:9px;color:#94a3b8;width:14px;">X</span>
          <input type="range" id="slider-offset-x" min="0" max="0" step="0.5" value="0"
                 style="flex:1;accent-color:#F5A623;height:14px;" oninput="onPlotOffsetChange()">
          <span id="offset-x-val" style="font-size:9px;color:white;width:26px;text-align:right;">0m</span>
        </div>
        <div style="display:flex;align-items:center;gap:4px;margin-bottom:4px;">
          <span style="font-size:9px;color:#94a3b8;width:14px;">Z</span>
          <input type="range" id="slider-offset-z" min="0" max="0" step="0.5" value="0"
                 style="flex:1;accent-color:#F5A623;height:14px;" oninput="onPlotOffsetChange()">
          <span id="offset-z-val" style="font-size:9px;color:white;width:26px;text-align:right;">0m</span>
        </div>
        <div id="retranqueo-ok"   style="font-size:9px;color:#10B981;margin-bottom:3px;">✅ Retranqueo 3m OK</div>
        <div id="retranqueo-warn" style="display:none;font-size:9px;color:#EF4444;margin-bottom:3px;">⚠️ Fuera de retranqueo</div>
        <hr class="divider">
        <button class="tool-btn green" onclick="saveChanges()">💾 Guardar JSON</button>
        <button class="tool-btn green" id="btn-glb" onclick="exportGLB()">📦 Exportar 3D (.glb)</button>
    </div>

    <!-- PANEL INFO DERECHO -->
    <div id="info-panel">
        <h3>📊 Info Habitación</h3>
        <div id="room-info">
            <p style="color:#888;">Selecciona una habitación</p>
        </div>
    </div>

    <!-- PANEL PRESUPUESTO -->
    <div id="budget-panel">
        <h3>💰 Presupuesto</h3>
        <div id="budget-info">
            <p><strong>Superficie:</strong> <span id="total-area">0</span> m²</p>
            <p><strong>Coste aprox:</strong> <span id="total-cost">€0</span></p>
            <p style="font-size:11px; color:#888; margin-top:4px;" id="budget-diff"></p>
        </div>
    </div>

    <!-- PANEL ESTILOS -->
    <div id="style-panel" style="display:none; position:absolute; top:20px; right:500px;
         background:rgba(0,0,0,0.88); padding:14px; border-radius:12px; color:white;
         width:220px; border:1px solid rgba(155,89,182,0.5);">
        <h3 style="margin:0 0 4px 0; font-size:13px; color:#9B59B6;">🎨 Estilo Fachada</h3>
        <p style="margin:0 0 10px 0; font-size:10px; color:#aaa; line-height:1.4;">
            Aplicado desde el Paso 1: <strong style="color:#C39BD3;">{house_style}</strong>.<br>
            Puedes ajustar solo la fachada aquí.
        </p>
        <div style="display:flex; flex-direction:column; gap:6px;">
            <button id="style-btn-Moderno" onclick="applyStyleUI('Moderno')"
                style="padding:7px; background:rgba(146,146,144,0.3); border:1px solid #929290;
                       color:white; border-radius:6px; cursor:pointer; font-size:12px; text-align:left;">
                🏢 Moderno — Hormigón blanco
            </button>
            <button id="style-btn-Rural" onclick="applyStyleUI('Rural')"
                style="padding:7px; background:rgba(120,109,88,0.3); border:1px solid #786D58;
                       color:white; border-radius:6px; cursor:pointer; font-size:12px; text-align:left;">
                🏡 Rural — Piedra beige
            </button>
            <button id="style-btn-Andaluz" onclick="applyStyleUI('Andaluz')"
                style="padding:7px; background:rgba(245,240,224,0.3); border:1px solid #F5F0E0;
                       color:white; border-radius:6px; cursor:pointer; font-size:12px; text-align:left;">
                💃 Andaluz — Cal blanca
            </button>
            <button id="style-btn-Montaña" onclick="applyStyleUI('Montaña')"
                style="padding:7px; background:rgba(99,88,72,0.3); border:1px solid #635848;
                       color:white; border-radius:6px; cursor:pointer; font-size:12px; text-align:left;">
                ⛰️ Montaña — Piedra oscura
            </button>
            <button id="style-btn-Playa" onclick="applyStyleUI('Playa')"
                style="padding:7px; background:rgba(240,232,210,0.3); border:1px solid #F0E8D2;
                       color:white; border-radius:6px; cursor:pointer; font-size:12px; text-align:left;">
                🌊 Playa — Arena clara
            </button>
            <button id="style-btn-Ecológico" onclick="applyStyleUI('Ecológico')"
                style="padding:7px; background:rgba(130,116,94,0.3); border:1px solid #82745E;
                       color:white; border-radius:6px; cursor:pointer; font-size:12px; text-align:left;">
                🌿 Ecológico — Tierra natural
            </button>
        </div>
        <p id="style-applied" style="margin:8px 0 0 0; font-size:11px; color:#9B59B6; text-align:center;"></p>
    </div>

    <!-- PANEL CIMIENTOS -->
    <div id="found-panel" style="display:none; position:absolute; top:20px; right:500px;
         background:rgba(0,0,0,0.88); padding:14px; border-radius:12px; color:white;
         width:200px; border:1px solid rgba(139,90,43,0.5);">
        <h3 style="margin:0 0 8px 0; font-size:13px; color:#CD853F;">🏗️ Cimientos</h3>
        <p style="font-size:11px; opacity:0.7; margin-bottom:4px;">Tipo seleccionado:</p>
        <p id="found-type-label" style="font-size:12px; color:#DEB887; margin-bottom:8px; font-weight:bold;"></p>
        <p style="font-size:10px; opacity:0.6; line-height:1.4;">
            Visible al rotar la cámara hacia abajo (Vista 3D).
        </p>
    </div>

    <!-- PANEL TEJADO -->
    <div id="roof-panel" style="display:none; position:absolute; top:20px; right:290px;
         background:rgba(0,0,0,0.88); padding:14px; border-radius:12px; color:white;
         width:200px; border:1px solid rgba(255,165,0,0.4);">
        <h3 style="margin:0 0 10px 0; font-size:13px; color:#F39C12;">🏠 Tejado</h3>
        <p style="font-size:11px; opacity:0.7; margin-bottom:6px;">Material:</p>
        <select id="roof-material" onchange="changeRoofMaterial(this.value)"
                style="width:100%; background:#222; color:white; border:1px solid #F39C12;
                       border-radius:4px; padding:5px; font-size:12px; margin-bottom:8px;">
            <option value="teja">🟤 Teja árabe</option>
            <option value="pizarra">⚫ Pizarra</option>
            <option value="zinc">🔵 Zinc</option>
            <option value="sandwich">⬜ Panel sándwich</option>
            <option value="vegetal">🟢 Cubierta vegetal</option>
        </select>
        <p style="font-size:11px; opacity:0.7; margin-bottom:4px;">Voladizo: <span id="overhang-val">0.6m</span></p>
        <input type="range" id="overhang-slider" min="0" max="15" value="6"
               oninput="changeOverhang(this.value)"
               style="width:100%; accent-color:#F39C12;">
    </div>

    <!-- PANEL AVISO -->
    <div id="compass-wrap">
        <canvas id="compass-canvas" width="70" height="70"></canvas>
    </div>

    <div id="warning-panel">
        <h3>⚠️ Importante</h3>
        <p>Los cambios requieren <strong>validación por arquitecto</strong> antes de construcción.</p>
        <p style="color:#E67E22; margin-top:4px;">⚠️ No garantizan cumplimiento CTE</p>
    </div>

    <script>
        // ================================================
        // DATOS
        // ================================================
        const roomsData = {rooms_js};
        const totalWidth = {total_width};
        const totalDepth = {total_depth};
        const plotAreaM2 = {plot_area_m2};
        // Dimensiones parcela: proporción 4:5 (estándar catastral rectangular)
        // Si plot_area_m2=0 usamos totalWidth+10 como fallback
        const plotW = plotAreaM2 > 0 ? Math.round(Math.sqrt(plotAreaM2 * 0.8)) : totalWidth + 10;
        const plotD = plotAreaM2 > 0 ? Math.round(plotAreaM2 / plotW)           : totalDepth + 10;
        const plotX = (totalWidth  - plotW) / 2;  // centrado respecto a casa
        const plotZ = (totalDepth  - plotD) / 2;
        const roofType = "{roof_type}";
        const houseStyle = "{house_style}";
        let _currentStyle = "{house_style}";   // mutable — se actualiza en applyStyle()
        const WALL_H = 2.7;
        const WALL_T = 0.15;
        // Color de pared exterior según estilo elegido en Paso 1
        const STYLE_WALL_COLORS = {{
            'Rural':          [0.75, 0.68, 0.55],
            'Montaña':        [0.72, 0.65, 0.52],
            'Ecológico':      [0.80, 0.72, 0.58],
            'Andaluz':        [0.96, 0.94, 0.88],
            'Clásico':        [0.93, 0.90, 0.83],
            'Playa':          [0.94, 0.91, 0.82],
            'Moderno':        [0.92, 0.92, 0.90],
            'Contemporáneo':  [0.90, 0.90, 0.88],
        }};
        const _wc = STYLE_WALL_COLORS[houseStyle] || [0.92, 0.92, 0.90];
        const WALL_COLOR = new BABYLON.Color3(_wc[0], _wc[1], _wc[2]);

        // Config 3D por estilo arquitectónico — tejado, extras y chimenea
        const STYLE_3D_CONFIG = {{
            'Moderno':       {{ roofColor: [0.20, 0.20, 0.22], extras: [],                  chimney: false }},
            'Playa':         {{ roofColor: [0.90, 0.90, 0.85], extras: ['sea','terrace'],    chimney: false }},
            'Rural':         {{ roofColor: [0.62, 0.31, 0.14], extras: ['tree','tree'],      chimney: true  }},
            'Montaña':       {{ roofColor: [0.22, 0.22, 0.28], extras: ['tree','tree'],      chimney: true  }},
            'Andaluz':       {{ roofColor: [0.68, 0.33, 0.16], extras: ['patio'],            chimney: false }},
            'Ecológico':     {{ roofColor: [0.33, 0.45, 0.25], extras: ['tree'],             chimney: false }},
            'Clásico':       {{ roofColor: [0.65, 0.32, 0.14], extras: [],                  chimney: true  }},
            'Contemporáneo': {{ roofColor: [0.18, 0.18, 0.20], extras: [],                  chimney: false }},
        }};
        const styleConf = STYLE_3D_CONFIG[houseStyle] || STYLE_3D_CONFIG['Moderno'];

        const COST_PER_M2 = {cost_per_m2}; // €/m² configurado por el arquitecto

        // ── PBR Materials DB ─────────────────────────────────────────────────
        const MATERIALS_DB = {{
            "ladrillo_cara_vista": {{name:"Ladrillo Cara Vista", price_m2:85, roughness:0.85, metallic:0.0, color:"#C4845A", texUrl:"https://cdn.babylonjs.com/Assets/textures/brick_diffuse.jpg"}},
            "madera_laminada":     {{name:"Madera Laminada (CLT)", price_m2:320, roughness:0.75, metallic:0.0, color:"#A0724A", texUrl:"https://cdn.babylonjs.com/Assets/textures/wood_diffuse.jpg"}},
            "piedra_caliza":       {{name:"Piedra Caliza", price_m2:145, roughness:0.90, metallic:0.0, color:"#C8B89A", texUrl:"https://cdn.babylonjs.com/Assets/textures/stone_diffuse.jpg"}},
            "hormigon_visto":      {{name:"Hormigón Visto HA-25", price_m2:95, roughness:0.80, metallic:0.05, color:"#9E9E9E", texUrl:"https://cdn.babylonjs.com/Assets/textures/concrete_diffuse.jpg"}},
            "plancha_acero_corten":{{name:"Plancha Acero Corten", price_m2:210, roughness:0.70, metallic:0.85, color:"#8B4513", texUrl:"https://cdn.babylonjs.com/Assets/textures/rust_diffuse.jpg"}}
        }};
        // material_id asignado por mesh index: roomsData[i].material_id
        // (se guarda cuando el usuario selecciona material desde el panel)

        // Mínimos CTE por tipo de habitación (m²)
        const CTE_MIN = {{
            'salon': 14, 'cocina': 6, 'dormitorio_principal': 10,
            'dormitorio': 6, 'bano': 2.5, 'aseo': 1.5,
            'pasillo': 0, 'garaje': 12, 'porche': 0,
            'distribuidor': 0, 'piscina': 0, 'huerto': 0
        }};

        // ================================================
        // ESCENA
        // ================================================
        const canvas = document.getElementById('renderCanvas');
        const engine = new BABYLON.Engine(canvas, true);
        const scene  = new BABYLON.Scene(engine);
        scene.clearColor = new BABYLON.Color4(0.1, 0.1, 0.18, 1);

        // Cámara isométrica
        const camera = new BABYLON.ArcRotateCamera(
            "cam", Math.PI/4, Math.PI/3.2, Math.max(plotW, plotD, totalWidth, totalDepth) * 1.55,
            new BABYLON.Vector3(totalWidth/2, 0, totalDepth/2), scene
        );
        camera.attachControl(canvas, true);
        camera.lowerRadiusLimit = 5;
        camera.upperRadiusLimit = 80;
        camera.upperBetaLimit = Math.PI * 0.85;  // permite ver desde abajo (cimientos)
        camera.lowerBetaLimit = 0.1;             // permite ver desde casi arriba

        // Luces
        const hemi = new BABYLON.HemisphericLight("hemi", new BABYLON.Vector3(0,1,0), scene);
        hemi.intensity = 0.85;
        const dirLight = new BABYLON.DirectionalLight("dir", new BABYLON.Vector3(-1,-2,-1), scene);
        dirLight.intensity = 0.5;
        dirLight.position = new BABYLON.Vector3(totalWidth/2 + 20, 30, -10);

        // Sombras suaves (emisor: tejado + paredes; receptor: suelo + plantas)
        const shadowGen = new BABYLON.ShadowGenerator(512, dirLight);
        shadowGen.useExponentialShadowMap = true;
        shadowGen.forceBackFacesOnly = true;

        // Centro del plot (= centro de la casa por construcción de plotX/plotZ)
        const plotCX = totalWidth / 2;
        const plotCZ = totalDepth / 2;

        // Suelo exterior (tierra/contexto) — cubre plot + margen generoso
        const groundW = Math.max(plotW, totalWidth) + 24;
        const groundD = Math.max(plotD, totalDepth) + 24;
        const ground = BABYLON.MeshBuilder.CreateGround("ground", {{
            width: groundW, height: groundD
        }}, scene);
        const groundMat = new BABYLON.StandardMaterial("gMat", scene);
        groundMat.diffuseColor = new BABYLON.Color3(0.36, 0.58, 0.36);
        ground.material = groundMat;
        ground.receiveShadows = true;
        ground.position.set(plotCX, 0, plotCZ);
        window.groundMesh = ground;

        // Plano de parcela — delimita exactamente los m² reales de la finca
        const plotPlane = BABYLON.MeshBuilder.CreateGround("plotPlane", {{
            width: plotW, height: plotD
        }}, scene);
        const plotMat = new BABYLON.StandardMaterial("plotMat", scene);
        plotMat.diffuseColor = new BABYLON.Color3(0.44, 0.72, 0.44);
        plotPlane.material = plotMat;
        plotPlane.position.set(plotCX, 0.003, plotCZ);

        // Grid 1m — sobre toda la parcela
        const gridSize = Math.max(plotW, plotD, totalWidth, totalDepth) + 12;
        const gridMat = new BABYLON.GridMaterial("gridMat", scene);
        gridMat.majorUnitFrequency = 5;
        gridMat.minorUnitVisibility = 0.45;
        gridMat.gridRatio = 1;
        gridMat.mainColor  = new BABYLON.Color3(1,1,1);
        gridMat.lineColor  = new BABYLON.Color3(0.3,0.5,0.7);
        gridMat.opacity    = 0.55;
        gridMat.backFaceCulling = false;
        const gridPlane = BABYLON.MeshBuilder.CreateGround("gridPlane",
            {{width: gridSize, height: gridSize}}, scene);
        gridPlane.material  = gridMat;
        gridPlane.position.set(plotCX, 0.01, plotCZ);
        gridPlane.isPickable = false;
        window.gridPlaneMesh = gridPlane;

        // Borde naranja del límite de parcela (4 líneas finas a y=0.02)
        const borderColor = new BABYLON.Color3(0.95, 0.55, 0.10);
        const borderH = 0.12, borderT = 0.18;
        [['bN', plotCX, plotCZ + plotD/2, plotW, borderT],
         ['bS', plotCX, plotCZ - plotD/2, plotW, borderT],
         ['bE', plotCX + plotW/2, plotCZ, borderT, plotD + borderT*2],
         ['bO', plotCX - plotW/2, plotCZ, borderT, plotD + borderT*2]
        ].forEach(([id, bx, bz, bw, bd]) => {{
            const b = BABYLON.MeshBuilder.CreateBox('border_'+id,
                {{width: bw, height: borderH, depth: bd}}, scene);
            b.position.set(bx, 0.02, bz);
            const bm = new BABYLON.StandardMaterial('bm_'+id, scene);
            bm.diffuseColor = borderColor;
            bm.emissiveColor = new BABYLON.Color3(0.3, 0.15, 0.0);
            b.material = bm;
            b.isPickable = false;
        }});

        // Etiqueta m² en el suelo (GUI Babylon)
        if (plotAreaM2 > 0) {{
            const guiUI = BABYLON.GUI.AdvancedDynamicTexture.CreateFullscreenUI("plotUI", true, scene);
            const plotLbl = new BABYLON.GUI.TextBlock("plotLbl");
            plotLbl.text = plotAreaM2.toLocaleString('es-ES') + " m²  ·  " + plotW + "m × " + plotD + "m";
            plotLbl.color = "rgba(255,240,200,0.92)";
            plotLbl.fontSize = 15;
            plotLbl.fontWeight = "bold";
            plotLbl.outlineWidth = 3;
            plotLbl.outlineColor = "rgba(0,0,0,0.8)";
            guiUI.addControl(plotLbl);
            const lblNode = new BABYLON.TransformNode("lblNode", scene);
            lblNode.position.set(plotCX, 0.5, plotCZ - plotD/2 + 3);
            plotLbl.linkWithMesh(lblNode);
            plotLbl.linkOffsetY = -18;
        }}

        // ================================================
        // HIGHLIGHT
        // ================================================
        const hlLayer = new BABYLON.HighlightLayer("hl", scene);

        // ================================================
        // CONSTRUIR HABITACIONES
        // ================================================
        // roomsData[i] → suelo + 4 paredes + etiqueta
        // Guardamos referencias para reconstruir paredes

        // GUI para etiquetas flotantes de habitaciones
        const roomGuiUI = BABYLON.GUI.AdvancedDynamicTexture.CreateFullscreenUI("roomLabels", true, scene);

        function buildRoom(i) {{
            const room = roomsData[i];
            const rx = room.x, rz = room.z, rw = room.width, rd = room.depth;

            // Suelo
            const floor = BABYLON.MeshBuilder.CreateBox(`floor_${{i}}`, {{
                width: rw - 0.05, height: 0.06, depth: rd - 0.05
            }}, scene);
            floor.position.set(rx + rw/2, 0.03, rz + rd/2);
            const fMat = new BABYLON.StandardMaterial(`fMat_${{i}}`, scene);

            // Color por zona
            const zone = (room.zone || '').toLowerCase();
            if (zone === 'day')        fMat.diffuseColor = new BABYLON.Color3(0.96, 0.94, 0.88);
            else if (zone === 'night') fMat.diffuseColor = new BABYLON.Color3(0.88, 0.93, 0.98);
            else if (zone === 'wet')   fMat.diffuseColor = new BABYLON.Color3(0.85, 0.95, 0.98);
            else if (zone === 'exterior') fMat.diffuseColor = new BABYLON.Color3(0.75, 0.90, 0.70);
            else if (zone === 'garden' && (room.code||'').toLowerCase().includes('panel'))
                                          fMat.diffuseColor = new BABYLON.Color3(0.95, 0.85, 0.20);
            else if (zone === 'garden' && ['caseta','apero','bomba'].some(x => (room.code||'').toLowerCase().includes(x)))
                                          fMat.diffuseColor = new BABYLON.Color3(0.70, 0.70, 0.70);  // gris caseta/aperos
            else if (zone === 'garden' && (room.code||'').toLowerCase().includes('huerto'))
                                          fMat.diffuseColor = new BABYLON.Color3(0.18, 0.48, 0.12);  // verde oscuro huerto
            else if (zone === 'garden')   fMat.diffuseColor = new BABYLON.Color3(0.20, 0.55, 0.85);
            else                          fMat.diffuseColor = new BABYLON.Color3(0.94, 0.93, 0.90);

            floor.material = fMat;
            floor.receiveShadows = true;

            // Paredes solo en zonas habitables
            if (zone !== 'garden' && zone !== 'exterior') {{
                _buildWalls(i, rx, rz, rw, rd);
                _buildWindows(i, rx, rz, rw, rd);
            }}

            // Etiqueta
            _buildLabel(i, rx, rz, rw, rd);
        }}

        function _buildWalls(i, rx, rz, rw, rd) {{
            const wMat = new BABYLON.StandardMaterial(`wMat_${{i}}`, scene);
            wMat.diffuseColor = WALL_COLOR;

            // Trasera (z-)
            const bw = BABYLON.MeshBuilder.CreateBox(`wall_back_${{i}}`,
                {{width: rw, height: WALL_H, depth: WALL_T}}, scene);
            bw.position.set(rx+rw/2, WALL_H/2, rz);
            bw.material = wMat;

            // Frontal (z+) semi-transparente
            const fw = BABYLON.MeshBuilder.CreateBox(`wall_front_${{i}}`,
                {{width: rw, height: WALL_H, depth: WALL_T}}, scene);
            fw.position.set(rx+rw/2, WALL_H/2, rz+rd);
            const fwMat = wMat.clone(`fwMat_${{i}}`);
            fwMat.alpha = 0.28;
            fw.material = fwMat;

            // Izquierda
            const lw = BABYLON.MeshBuilder.CreateBox(`wall_left_${{i}}`,
                {{width: WALL_T, height: WALL_H, depth: rd}}, scene);
            lw.position.set(rx, WALL_H/2, rz+rd/2);
            lw.material = wMat;

            // Derecha
            const rw_ = BABYLON.MeshBuilder.CreateBox(`wall_right_${{i}}`,
                {{width: WALL_T, height: WALL_H, depth: rd}}, scene);
            rw_.position.set(rx+rw, WALL_H/2, rz+rd/2);
            rw_.material = wMat;

            // Sombras — paredes como emisores
            [bw, fw, lw, rw_].forEach(w => shadowGen.addShadowCaster(w, false));

            // Marcador de puerta — caja delgada sobre la pared correcta según zona
            const zone = (roomsData[i].zone || '').toLowerCase();
            const code = (roomsData[i].code || '').toLowerCase();
            const DOOR_W = 0.95, DOOR_H = 2.05, DOOR_D = 0.12;
            const doorMat = new BABYLON.StandardMaterial(`doorMat_${{i}}`, scene);
            doorMat.diffuseColor = new BABYLON.Color3(0.85, 0.70, 0.40);
            doorMat.emissiveColor = new BABYLON.Color3(0.3, 0.22, 0.08);

            if (zone === 'exterior') {{
                // Porche: puerta centrada en pared norte (z-) hacia salón
                const d = BABYLON.MeshBuilder.CreateBox(`door_${{i}}`,
                    {{width: DOOR_W, height: DOOR_H, depth: DOOR_D}}, scene);
                d.position.set(rx + rw/2, DOOR_H/2, rz - 0.08);
                d.material = doorMat;
            }} else if (zone === 'day') {{
                // Salón/cocina: puerta en z- (hacia porche)
                const d1 = BABYLON.MeshBuilder.CreateBox(`door_${{i}}_a`,
                    {{width: DOOR_W, height: DOOR_H, depth: DOOR_D}}, scene);
                d1.position.set(rx + rw*0.25, DOOR_H/2, rz - 0.08);
                d1.material = doorMat;
                // Segunda puerta en z+ (hacia pasillo)
                const d2 = BABYLON.MeshBuilder.CreateBox(`door_${{i}}_b`,
                    {{width: DOOR_W, height: DOOR_H, depth: DOOR_D}}, scene);
                d2.position.set(rx + rw*0.25, DOOR_H/2, rz + rd + 0.08);
                d2.material = doorMat;
            }} else if (zone === 'service') {{
                // Garaje: portón en z- (fachada) + puerta peatonal en x- (hacia salón)
                const portMat = new BABYLON.StandardMaterial(`portMat_${{i}}`, scene);
                portMat.diffuseColor = new BABYLON.Color3(0.8, 0.5, 0.1);
                const port = BABYLON.MeshBuilder.CreateBox(`door_${{i}}_port`,
                    {{width: DOOR_W*2.5, height: DOOR_H, depth: DOOR_D}}, scene);
                port.position.set(rx + rw/2, DOOR_H/2, rz - 0.08);
                port.material = portMat;
                const dp = BABYLON.MeshBuilder.CreateBox(`door_${{i}}_ped`,
                    {{width: DOOR_D, height: DOOR_H, depth: DOOR_W}}, scene);
                dp.position.set(rx, DOOR_H/2, rz + rd/2);
                dp.material = doorMat;
            }} else if (zone === 'night' || zone === 'wet') {{
                // Dormitorios/baños: puerta en z- (hacia pasillo)
                const d = BABYLON.MeshBuilder.CreateBox(`door_${{i}}`,
                    {{width: DOOR_W, height: DOOR_H, depth: DOOR_D}}, scene);
                d.position.set(rx + rw*0.25, DOOR_H/2, rz - 0.08);
                d.material = doorMat;
            }}
        }}

        function _disposeWalls(i) {{
            // Paredes
            ['wall_back_','wall_front_','wall_left_','wall_right_'].forEach(pre => {{
                ['', '_L', '_R', '_B', '_T'].forEach(suf => {{
                    const m = scene.getMeshByName(pre + i + suf);
                    if (m) {{ m.material && m.material.dispose(); m.dispose(); }}
                }});
            }});
            // Marcadores de puerta
            ['door_'].forEach(pre => {{
                ['', '_a', '_b', '_port', '_ped'].forEach(suf => {{
                    const m = scene.getMeshByName(pre + i + suf);
                    if (m) {{ m.material && m.material.dispose(); m.dispose(); }}
                }});
            }});
            // Ventanas
            ['back','front','left','right'].forEach(side => {{
                const m = scene.getMeshByName(`win_${{i}}_${{side}}`);
                if (m) {{ m.material && m.material.dispose(); m.dispose(); }}
            }});
            // Materiales
            ['wMat_','fwMat_','doorMat_','portMat_','winMat_'].forEach(pre => {{
                const mat = scene.getMaterialByName(pre + i);
                if (mat) mat.dispose();
            }});
        }}

        // ================================================
        // VENTANAS — detección de pared exterior + cristal semitransparente
        // ================================================
        function _isExteriorWall(i, side) {{
            const r = roomsData[i];
            for (let j = 0; j < roomsData.length; j++) {{
                if (i === j) continue;
                const n = roomsData[j];
                const nZone = (n.zone || '').toLowerCase();
                // Zonas abiertas no bloquean ventanas
                if (nZone === 'garden' || nZone === 'exterior') continue;
                if (side === 'back') {{
                    if (Math.abs((n.z + n.depth) - r.z) < 0.35 &&
                        n.x < r.x + r.width - 0.1 && n.x + n.width > r.x + 0.1) return false;
                }} else if (side === 'front') {{
                    if (Math.abs(n.z - (r.z + r.depth)) < 0.35 &&
                        n.x < r.x + r.width - 0.1 && n.x + n.width > r.x + 0.1) return false;
                }} else if (side === 'left') {{
                    if (Math.abs((n.x + n.width) - r.x) < 0.35 &&
                        n.z < r.z + r.depth - 0.1 && n.z + n.depth > r.z + 0.1) return false;
                }} else if (side === 'right') {{
                    if (Math.abs(n.x - (r.x + r.width)) < 0.35 &&
                        n.z < r.z + r.depth - 0.1 && n.z + n.depth > r.z + 0.1) return false;
                }}
            }}
            return true;
        }}

        function _buildWindows(i, rx, rz, rw, rd) {{
            const zone = (roomsData[i].zone || '').toLowerCase();
            if (!['day','night','wet','service','circ'].includes(zone)) return;
            const isWet   = (zone === 'wet');
            const WIN_D   = 0.20;  // > WALL_T(0.15) para que sobresalga y sea visible
            const WIN_SILL = 0.9;
            const WIN_H   = isWet ? 0.55 : 1.15;
            const WIN_W_H = isWet ? Math.min(rw * 0.35, 0.7) : Math.min(rw * 0.50, 1.40);
            const WIN_W_V = isWet ? Math.min(rd * 0.35, 0.7) : Math.min(rd * 0.50, 1.40);
            const winY    = WIN_SILL + WIN_H / 2;

            // Material base (plantilla)
            const winMat = new BABYLON.StandardMaterial(`winMat_${{i}}`, scene);
            winMat.diffuseColor  = new BABYLON.Color3(0.55, 0.82, 0.98);
            winMat.emissiveColor = new BABYLON.Color3(0.08, 0.25, 0.45);
            winMat.alpha = 0.52;
            winMat.backFaceCulling = false;

            ['back','front','left','right'].forEach(side => {{
                if (!_isExteriorWall(i, side)) return;
                const wallLen = (side === 'back' || side === 'front') ? rw : rd;
                if (wallLen < 1.2) return;
                let bx, bz, bw, bd;
                if (side === 'back') {{
                    bw = WIN_W_H; bd = WIN_D; bx = rx + rw/2; bz = rz;
                }} else if (side === 'front') {{
                    bw = WIN_W_H; bd = WIN_D; bx = rx + rw/2; bz = rz + rd;
                }} else if (side === 'left') {{
                    bw = WIN_D; bd = WIN_W_V; bx = rx; bz = rz + rd/2;
                }} else {{
                    bw = WIN_D; bd = WIN_W_V; bx = rx + rw; bz = rz + rd/2;
                }}
                const win = BABYLON.MeshBuilder.CreateBox(
                    `win_${{i}}_${{side}}`, {{width: bw, height: WIN_H, depth: bd}}, scene);
                win.position.set(bx, winY, bz);
                win.material = winMat.clone(`winMat_${{i}}_${{side}}`);
                win.isPickable = false;
            }});
        }}

        function _buildLabel(i, rx, rz, rw, rd) {{
            // Limpiar etiqueta anterior si existe (rebuild)
            const oldCtrl = roomGuiUI.getControlByName(`lbl_txt_${{i}}`);
            if (oldCtrl) roomGuiUI.removeControl(oldCtrl);
            const oldNode = scene.getTransformNodeByName(`lbl_node_${{i}}`);
            if (oldNode) oldNode.dispose();

            const room = roomsData[i];
            const labelText = room.name || room.code || '';
            if (!labelText) return;

            const lbl = new BABYLON.GUI.TextBlock(`lbl_txt_${{i}}`);
            lbl.text = labelText;
            lbl.color = "rgba(255,255,255,0.95)";
            lbl.fontSize = 13;
            lbl.fontWeight = "bold";
            lbl.outlineWidth = 3;
            lbl.outlineColor = "rgba(0,0,0,0.85)";
            roomGuiUI.addControl(lbl);

            const node = new BABYLON.TransformNode(`lbl_node_${{i}}`, scene);
            node.position.set(rx + rw/2, WALL_H * 0.45, rz + rd/2);
            lbl.linkWithMesh(node);
            lbl.linkOffsetY = -12;
        }}

        // Construir todas las habitaciones
        roomsData.forEach((_, i) => buildRoom(i));
        try {{ buildMEPLayers(roomsData); }} catch(e) {{ console.warn('MEP init error:', e); }}

        // Área original para presupuesto
        let originalTotalArea = roomsData.reduce((s, r) => s + (r.area_m2 || 0), 0);

        // ================================================
        // GIZMO — solo para MOVER
        // ================================================
        const gizmoManager = new BABYLON.GizmoManager(scene);
        gizmoManager.positionGizmoEnabled = false;
        gizmoManager.rotationGizmoEnabled = false;
        gizmoManager.scaleGizmoEnabled    = false;

        let selectedMesh  = null;
        let selectedIndex = null;
        let currentMode   = 'select';

        // ================================================
        // SELECCIÓN POR CLICK
        // ================================================
        scene.onPointerDown = function(evt, pickResult) {{
            if (currentMode === 'wall') return; // el modo wall tiene su propio handler

            if (!pickResult.hit) return;
            const mesh = pickResult.pickedMesh;
            if (!mesh) return;

            // Solo seleccionar suelos y paredes de habitaciones
            const isFloor = mesh.name.startsWith('floor_');
            const isWall  = mesh.name.startsWith('wall_');
            if (!isFloor && !isWall) return;

            // Extraer índice
            const parts = mesh.name.split('_');
            const idx = parseInt(parts[parts.length - 1]);
            if (isNaN(idx)) return;

            selectedMesh  = scene.getMeshByName(`floor_${{idx}}`);
            selectedIndex = idx;

            // Highlight
            hlLayer.removeAllMeshes();
            hlLayer.addMesh(selectedMesh, BABYLON.Color3.Yellow());

            updateRoomInfo(idx);

            // FIX #4: gizmo habilitado para TODAS las zonas
            if (currentMode === 'move') {{
                gizmoManager.attachToMesh(selectedMesh);
                gizmoManager.positionGizmoEnabled = true;
                // Guard: positionGizmo puede tardar un frame en crearse
                const _pg = gizmoManager.gizmos && gizmoManager.gizmos.positionGizmo;
                if (_pg) {{
                    if (_pg.xGizmo) _pg.xGizmo.isEnabled = true;
                    if (_pg.yGizmo) _pg.yGizmo.isEnabled = false;
                    if (_pg.zGizmo) _pg.zGizmo.isEnabled = true;
                    _pg.onDragEndObservable.clear();
                    _pg.onDragEndObservable.add(() => {{
                        saveSnapshot();
                        const f = scene.getMeshByName(`floor_${{idx}}`);
                        if (f) {{
                            roomsData[idx].x = f.position.x - roomsData[idx].width / 2;
                            roomsData[idx].z = f.position.z - roomsData[idx].depth / 2;
                        }}
                        rebuildScene(roomsData);
                        updateBudget();
                    }});
                }}
                showToast('↔️ Arrastra para mover: ' + roomsData[idx].name);
            }}

            // Si estamos en modo scale, mostrar panel numérico
            if (currentMode === 'scale') {{
                showEditPanel(idx);
            }}
        }};

        // ================================================
        // MODOS
        // ================================================
        function setMode(mode) {{
            currentMode = mode;

            // Reset visual botones
            document.querySelectorAll('.tool-btn').forEach(b =>
                b.classList.remove('active'));

            // Desconectar gizmo
            gizmoManager.positionGizmoEnabled = false;
            gizmoManager.scaleGizmoEnabled    = false;
            gizmoManager.attachToMesh(null);

            // Ocultar panel edición
            document.getElementById('edit-panel').style.display = 'none';
            document.getElementById('cte-status').style.display = 'none';

            if (mode === 'select') {{
                document.getElementById('btn-select').classList.add('active');

            }} else if (mode === 'move') {{
                document.getElementById('btn-move').classList.add('active');
                // FIX #4: gizmo para todas las zonas — selecciona antes de activar modo
                if (selectedMesh && selectedIndex !== null) {{
                    gizmoManager.attachToMesh(selectedMesh);
                    gizmoManager.positionGizmoEnabled = true;
                    const _pg2 = gizmoManager.gizmos && gizmoManager.gizmos.positionGizmo;
                    if (_pg2) {{
                        if (_pg2.xGizmo) _pg2.xGizmo.isEnabled = true;
                        if (_pg2.yGizmo) _pg2.yGizmo.isEnabled = false;
                        if (_pg2.zGizmo) _pg2.zGizmo.isEnabled = true;
                        _pg2.onDragEndObservable.clear();
                        _pg2.onDragEndObservable.add(() => {{
                            saveSnapshot();
                            const f = scene.getMeshByName(`floor_${{selectedIndex}}`);
                            if (f) {{
                                roomsData[selectedIndex].x = f.position.x - roomsData[selectedIndex].width / 2;
                                roomsData[selectedIndex].z = f.position.z - roomsData[selectedIndex].depth / 2;
                            }}
                            rebuildScene(roomsData);
                            updateBudget();
                        }});
                    }}
                    showToast('↔️ Arrastra: ' + roomsData[selectedIndex].name);
                }} else {{
                    showToast('Primero selecciona una habitación');
                    setMode('select');
                }}

            }} else if (mode === 'scale') {{
                document.getElementById('btn-scale').classList.add('active');
                if (selectedIndex !== null) {{
                    showEditPanel(selectedIndex);
                }} else {{
                    showToast('Primero selecciona una habitación');
                    setMode('select');
                }}

            }} else if (mode === 'wall') {{
                document.getElementById('btn-wall').classList.add('active');
                startWallMode();
            }}
        }}

        // ================================================
        // SINCRONIZAR PAREDES AL SUELO (tras mover)
        // ================================================
        function syncWallsToFloor(i) {{
            const floor = scene.getMeshByName(`floor_${{i}}`);
            if (!floor) return;
            const bounds = floor.getBoundingInfo().boundingBox;
            const rx = bounds.minimumWorld.x;
            const rz = bounds.minimumWorld.z;
            const rw = bounds.maximumWorld.x - rx;
            const rd = bounds.maximumWorld.z - rz;

            // Actualizar roomsData
            roomsData[i].x = rx;
            roomsData[i].z = rz;
            roomsData[i].width = rw;
            roomsData[i].depth = rd;

            _disposeWalls(i);
            const zoneS = (roomsData[i].zone || '').toLowerCase();
            if (zoneS !== 'garden' && zoneS !== 'exterior') {{
                _buildWalls(i, rx, rz, rw, rd);
                _buildWindows(i, rx, rz, rw, rd);
            }}
            _buildLabel(i, rx, rz, rw, rd);
        }}

        // ================================================
        // MOTOR LAYOUT JS — puerto de architec_layout.py
        // Redistribuye toda la planta sin colisiones
        // ================================================
        function classifyZone(code, name) {{
            const c = (code + name).toLowerCase();
            if (['piscin','pool','huerto','caseta','apero','panel','solar','bomba'].some(x => c.includes(x))) return 'garden';
            if (['porche','terraza'].some(x => c.includes(x))) return 'exterior';
            if (['garaje','garage','bodega'].some(x => c.includes(x))) return 'service';
            if (['pasillo','distribuidor','hall','recibidor'].some(x => c.includes(x))) return 'circ';
            if (['bano','baño','aseo','wc'].some(x => c.includes(x))) return 'wet';
            if (['dormitorio','habitacion','suite'].some(x => c.includes(x))) return 'night';
            return 'day';
        }}

        function generateLayoutJS(rooms) {{
            // Si ya tienen coordenadas y dimensiones, devolver tal cual (no recalcular)
            const alreadyPositioned = rooms.length > 0 && rooms.every(
                r => typeof r.x === 'number' && typeof r.z === 'number'
                  && typeof r.width === 'number' && r.width > 0
                  && typeof r.depth === 'number' && r.depth > 0
            );
            if (alreadyPositioned) return rooms;

            const FILA1_D = 4.5, FILA3_D = 3.5, PASILLO_H = 1.2;
            const rs = rooms.map(r => ({{
                ...r,
                area: Math.max(r.area_m2 || 2, 2),
                zone: r.zone || classifyZone(r.code||'', r.name||'')
            }}));
            const day   = rs.filter(r => r.zone === 'day');
            const night = rs.filter(r => r.zone === 'night').sort((a,b) => b.area - a.area);
            const wet   = rs.filter(r => r.zone === 'wet');
            const svc   = rs.filter(r => r.zone === 'service');
            const ext   = rs.filter(r => r.zone === 'exterior');
            const gdn   = rs.filter(r => r.zone === 'garden');
            const garajes   = svc.filter(r => (r.code||'').toLowerCase().includes('garaje') || (r.code||'').toLowerCase().includes('garage'));
            const otrosSvc  = svc.filter(r => !garajes.includes(r));
            const laterales = gdn.filter(r => !((r.code||'').toLowerCase().includes('piscin') || (r.code||'').toLowerCase().includes('pool')));
            const layout = [];
            // Ancho casa desde fila noche
            const nightW = night.map(r => Math.max(Math.round(r.area/FILA3_D*10)/10, 2.8));
            const banoW  = wet.map(r => Math.min(Math.max(Math.round(r.area/FILA3_D*10)/10, 1.5), 2.5));
            const fila3 = [];
            let bi = 0;
            for (let i=0; i<night.length; i++) {{
                if (bi < wet.length) {{ fila3.push({{r:wet[bi], w:banoW[bi], d:FILA3_D}}); bi++; }}
                fila3.push({{r:night[i], w:nightW[i], d:FILA3_D}});
            }}
            while (bi < wet.length) {{ fila3.push({{r:wet[bi], w:banoW[bi], d:FILA3_D}}); bi++; }}
            let houseW = Math.min(Math.max(fila3.reduce((s,i)=>s+i.w,0), 8), 18);
            // Fila 1: día + garaje
            let garajeW = 0;
            const garajeItems = garajes.map(r => {{ const gw=Math.max(Math.round(r.area/FILA1_D*10)/10,3.5); garajeW+=gw; return {{r,w:gw}}; }});
            const dayAvail = Math.max(houseW - garajeW, 5);
            const dayTotal = day.reduce((s,r)=>s+r.area,0) || 1;
            let xd = 0;
            day.forEach((r,idx) => {{
                let w = idx===day.length-1 ? Math.max(dayAvail-xd,3) : Math.max(Math.round(dayAvail*(r.area/dayTotal)*10)/10,3);
                layout.push({{x:xd, z:0, width:w, depth:FILA1_D, name:r.name, code:r.code, zone:r.zone, area_m2:r.area}});
                xd += w;
            }});
            let xo = xd;
            otrosSvc.forEach(r => {{ const w=Math.max(Math.round(r.area/FILA1_D*10)/10,2); layout.push({{x:xo,z:0,width:w,depth:FILA1_D,name:r.name,code:r.code,zone:r.zone,area_m2:r.area}}); xo+=w; }});
            let xg = houseW - garajeW;
            garajeItems.forEach(item => {{ layout.push({{x:xg,z:0,width:item.w,depth:FILA1_D,name:item.r.name,code:item.r.code,zone:item.r.zone,area_m2:item.r.area}}); xg+=item.w; }});
            // Pasillo
            const pasilloR = rs.find(r=>r.zone==='circ');
            layout.push({{x:0, z:FILA1_D, width:houseW, depth:PASILLO_H, name:pasilloR?pasilloR.name:'Distribuidor', code:pasilloR?pasilloR.code:'pasillo', zone:'circ', area_m2:houseW*PASILLO_H}});
            // Fila 3: noche
            const zF3 = FILA1_D + PASILLO_H;
            let xc = 0;
            fila3.forEach(item => {{ layout.push({{x:xc,z:zF3,width:item.w,depth:item.d,name:item.r.name,code:item.r.code,zone:item.r.zone,area_m2:item.r.area}}); xc+=item.w; }});
            const zBot = zF3 + FILA3_D;
            // Porche
            ext.forEach(r => {{ const d=Math.max(Math.round(r.area/houseW*10)/10,2); layout.push({{x:0,z:zBot,width:houseW,depth:d,name:r.name,code:r.code,zone:r.zone,area_m2:r.area}}); }});
            // Laterales
            let xl=houseW+3, zl=0;
            laterales.forEach(r => {{ const lw=Math.round(Math.sqrt(r.area*1.3)*10)/10; const ld=Math.round(r.area/lw*10)/10; layout.push({{x:xl,z:zl,width:lw,depth:ld,name:r.name,code:r.code,zone:r.zone,area_m2:r.area}}); zl+=ld+1; }});
            // Normalizar
            if (layout.length > 0) {{
                const minX = Math.min(...layout.map(i=>i.x));
                const minZ = Math.min(...layout.map(i=>i.z));
                const ox = Math.max(0,-minX)+2, oz = Math.max(0,-minZ)+2;
                layout.forEach(i => {{ i.x+=ox; i.z+=oz; }});
            }}
            return layout;
        }}

        function rebuildScene(newLayout) {{
            // Eliminar todos los meshes de habitaciones
            roomsData.forEach((_,i) => {{
                // Suelo (con su material)
                const floorM = scene.getMeshByName(`floor_${{i}}`);
                if (floorM) {{ if (floorM.material) floorM.material.dispose(); floorM.dispose(); }}
                // Paredes, puertas y ventanas
                _disposeWalls(i);
            }});
            hlLayer.removeAllMeshes();
            // Actualizar roomsData con nueva geometría
            newLayout.forEach((item, i) => {{
                if (roomsData[i]) {{
                    roomsData[i].x = item.x;
                    roomsData[i].z = item.z;
                    roomsData[i].width = item.width;
                    roomsData[i].depth = item.depth;
                    roomsData[i].area_m2 = item.area_m2 !== undefined ? item.area_m2 : roomsData[i].area_m2;
                }}
            }});
            // Reconstruir todos
            roomsData.forEach((_,i) => buildRoom(i));
            try {{ buildMEPLayers(roomsData); }} catch(e) {{ console.warn('MEP rebuild error:', e); }}
            // Z-anchor: re-posicionar chimenea/paneles solares sobre el tejado actual
            try {{ buildStyleExtras(_currentStyle); }} catch(e) {{ console.warn('StyleExtras rebuild error:', e); }}
            // FIX #1: rebuild roof & panels only when active — prevents ghost panels on move/dimension
            try {{
                if (typeof roofActive !== 'undefined' && roofActive) {{
                    if (typeof roofMesh !== 'undefined' && roofMesh) {{ roofMesh.dispose(); roofMesh = null; }}
                    buildRoof();
                    buildSolarPanels();
                }}
            }} catch(e) {{ console.warn('Roof rebuild error:', e); }}
            selectedMesh = null;
            selectedIndex = null;
            updateBudget();
            notifyParentLayout();
            showToast('✅ Planta redistribuida');
        }}

        // ================================================
        // PANEL NUMÉRICO — EDITAR DIMENSIONES
        // ================================================
        function showEditPanel(i) {{
            const room = roomsData[i];
            document.getElementById('edit-room-name').textContent = room.name;
            document.getElementById('input-width').value = room.width.toFixed(2);
            document.getElementById('input-depth').value = room.depth.toFixed(2);
            document.getElementById('edit-panel').style.display = 'block';
            checkCTE(i, room.width, room.depth);
        }}

        function applyDimensions() {{
            if (selectedIndex === null) return;
            const newW = parseFloat(document.getElementById('input-width').value);
            const newD = parseFloat(document.getElementById('input-depth').value);
            if (isNaN(newW) || isNaN(newD) || newW < 0.5 || newD < 0.5) {{
                showToast('Dimensiones no válidas (mínimo 0.5m)');
                return;
            }}
            saveSnapshot();
            // Actualizar dimensiones Y área en roomsData — NO llamar generateLayoutJS
            // (generateLayoutJS recalcularía el ancho desde área, destruyendo la edición del usuario)
            roomsData[selectedIndex].width   = newW;
            roomsData[selectedIndex].depth   = newD;
            roomsData[selectedIndex].area_m2 = parseFloat((newW * newD).toFixed(2));
            // Reempaquetar filas para cerrar huecos sin redistribuir toda la planta
            packRows();
            rebuildScene(roomsData);
            _resetPosSliders();
            checkCTE(selectedIndex, newW, newD);
            updateBudget();
            notifyParentLayout();
            // Mantener panel abierto con valores actualizados
            showEditPanel(selectedIndex);
        }}

        // ================================================
        // PACK ROWS — eliminar huecos tras redimensionar/mover
        // Agrupa habitaciones por fila Z y reempaqueta X de izq a der
        // ================================================
        function packRows() {{
            const SNAP = 0.6;  // tolerancia agrupación de filas (m)
            // Separar jardín/exterior (posición libre) del resto
            const fixed  = roomsData.filter(r => {{
                const z = (r.zone||'').toLowerCase();
                return z === 'garden' || z === 'exterior';
            }});
            const packing = roomsData.filter(r => {{
                const z = (r.zone||'').toLowerCase();
                return z !== 'garden' && z !== 'exterior';
            }});
            if (packing.length === 0) return;
            // Agrupar por fila: usar el z más frecuente como clave
            const rows = {{}};
            packing.forEach(r => {{
                let key = null;
                for (const k of Object.keys(rows)) {{
                    if (Math.abs(parseFloat(k) - r.z) < SNAP) {{ key = k; break; }}
                }}
                if (key === null) {{ key = r.z.toFixed(2); rows[key] = []; }}
                rows[key].push(r);
            }});
            // Reempaquetar cada fila de izquierda a derecha
            for (const key of Object.keys(rows)) {{
                const row = rows[key];
                row.sort((a, b) => a.x - b.x);
                const rowZ  = parseFloat(key);
                const rowD  = Math.max(...row.map(r => r.depth));
                let   curX  = Math.min(...row.map(r => r.x));  // anclar al leftmost
                row.forEach(r => {{
                    r.x = curX;
                    r.z = rowZ;
                    r.depth = rowD;  // unificar profundidad de fila
                    curX += r.width;
                }});
            }}
        }}

        // ================================================
        // MATERIALES PBR — aplicar textura + guardar en metadata
        // ================================================
        function applyMaterialPBR(meshIndex, materialId) {{
            const matDef = MATERIALS_DB[materialId];
            if (!matDef) return;
            // Guardar en metadata del room
            if (roomsData[meshIndex]) roomsData[meshIndex].material_id = materialId;
            // Aplicar a floor mesh
            const floor = scene.getMeshByName(`floor_${{meshIndex}}`);
            if (!floor) return;
            // Crear PBRMaterial si Babylon soporta
            let pbr;
            try {{
                pbr = new BABYLON.PBRMaterial(`pbr_${{materialId}}_${{meshIndex}}`, scene);
                pbr.roughness  = matDef.roughness;
                pbr.metallic   = matDef.metallic;
                // Albedo desde color hex como fallback (textura es opcional/async)
                const r = parseInt(matDef.color.slice(1,3),16)/255;
                const g = parseInt(matDef.color.slice(3,5),16)/255;
                const b = parseInt(matDef.color.slice(5,7),16)/255;
                pbr.albedoColor = new BABYLON.Color3(r, g, b);
                // Intentar cargar textura (no bloquea si falla)
                try {{
                    const tex = new BABYLON.Texture(matDef.texUrl, scene);
                    tex.onLoadObservable.addOnce(() => {{ pbr.albedoTexture = tex; }});
                }} catch(e) {{}}
                if (floor.material) floor.material.dispose();
                floor.material = pbr;
            }} catch(e) {{
                // Fallback: StandardMaterial con color
                const std = new BABYLON.StandardMaterial(`std_${{materialId}}_${{meshIndex}}`, scene);
                const r = parseInt(matDef.color.slice(1,3),16)/255;
                const g = parseInt(matDef.color.slice(3,5),16)/255;
                const b = parseInt(matDef.color.slice(5,7),16)/255;
                std.diffuseColor = new BABYLON.Color3(r, g, b);
                if (floor.material) floor.material.dispose();
                floor.material = std;
            }}
            notifyParentLayout();
            showToast(`Material: ${{matDef.name}}`);
        }}

        function getMeshAreaM2(meshIndex) {{
            // Área real = width * depth del roomsData
            const r = roomsData[meshIndex];
            if (!r) return 0;
            return parseFloat(((r.width || 0) * (r.depth || 0)).toFixed(2));
        }}

        // ================================================
        // NOTIFY PARENT — envía layout JSON al padre Streamlit via postMessage
        // El padre (app.py) escucha 'archirapid_layout_update' y guarda en session_state
        // ================================================
        function notifyParentLayout() {{
            try {{
                const payload = {{
                    type: 'archirapid_layout_update',
                    rooms: roomsData.map(r => ({{
                        name:    r.name,
                        code:    r.code    || '',
                        zone:    r.zone    || '',
                        x:       parseFloat((r.x     || 0).toFixed(3)),
                        z:       parseFloat((r.z     || 0).toFixed(3)),
                        width:   parseFloat((r.width || 0).toFixed(3)),
                        depth:   parseFloat((r.depth || 0).toFixed(3)),
                        area_m2: parseFloat((r.area_m2 || r.width * r.depth || 0).toFixed(2))
                    }}))
                }};
                window.parent.postMessage(JSON.stringify(payload), '*');
            }} catch(e) {{
                console.warn('notifyParentLayout error:', e);
            }}
        }}

        // ================================================
        // VALIDACIÓN CTE
        // ================================================
        function checkCTE(i, w, d) {{
            const room  = roomsData[i];
            const code  = (room.code || room.name || '').toLowerCase();
            const area  = w * d;
            const minW  = 2.5; // ancho mínimo CTE cualquier habitación habitable

            let minArea = 0;
            for (const key in CTE_MIN) {{
                if (code.includes(key)) {{ minArea = CTE_MIN[key]; break; }}
            }}

            const cteEl = document.getElementById('cte-status');
            cteEl.style.display = 'block';

            if (area < minArea) {{
                cteEl.className = 'fail';
                cteEl.textContent = `❌ CTE: mínimo ${{minArea}}m² para ${{room.name}} (actual ${{area.toFixed(1)}}m²)`;
            }} else if (w < minW && minArea > 0) {{
                cteEl.className = 'warn';
                cteEl.textContent = `⚠️ Ancho mínimo CTE: 2.5m (actual ${{w.toFixed(2)}}m)`;
            }} else if (area < minArea * 1.1 && minArea > 0) {{
                cteEl.className = 'warn';
                cteEl.textContent = `⚠️ Cerca del mínimo CTE: ${{minArea}}m²`;
            }} else {{
                cteEl.className = 'ok';
                cteEl.textContent = `✅ Cumple CTE (${{area.toFixed(1)}}m²)`;
            }}
        }}

        // ================================================
        // ACTUALIZAR PANEL INFO
        // ================================================
        function updateRoomInfo(i) {{
            const floor = scene.getMeshByName(`floor_${{i}}`);
            if (!floor) return;
            const bounds = floor.getBoundingInfo().boundingBox;
            const w = bounds.maximumWorld.x - bounds.minimumWorld.x;
            const d = bounds.maximumWorld.z - bounds.minimumWorld.z;
            const area = w * d;
            const room = roomsData[i];

            document.getElementById('room-info').innerHTML = `
                <p><strong style="color:#3498DB;">${{room.name}}</strong></p>
                <p>📐 Ancho: <strong>${{w.toFixed(2)}}m</strong></p>
                <p>📐 Fondo: <strong>${{d.toFixed(2)}}m</strong></p>
                <p>📦 Área: <strong>${{area.toFixed(1)}}m²</strong></p>
                <p style="color:#888; font-size:11px;">Original: ${{room.area_m2}}m²</p>
            `;
        }}

        // ================================================
        // PRESUPUESTO
        // ================================================
        function updateBudget() {{
            let total = 0;
            roomsData.forEach((r, i) => {{
                const f = scene.getMeshByName(`floor_${{i}}`);
                if (f) {{
                    const b = f.getBoundingInfo().boundingBox;
                    total += (b.maximumWorld.x - b.minimumWorld.x) *
                             (b.maximumWorld.z - b.minimumWorld.z);
                }}
            }});
            const cost = total * COST_PER_M2;
            const origCost = originalTotalArea * COST_PER_M2;
            const diff = cost - origCost;
            document.getElementById('total-area').textContent = total.toFixed(1);
            document.getElementById('total-cost').textContent =
                '€' + cost.toLocaleString('es-ES', {{maximumFractionDigits:0}});
            const de = document.getElementById('budget-diff');
            if (Math.abs(diff) > 100) {{
                const sign = diff > 0 ? '+' : '';
                de.textContent = `${{sign}}€${{diff.toLocaleString('es-ES',{{maximumFractionDigits:0}})}} vs original`;
                de.style.color = diff > 0 ? '#E67E22' : '#2ECC71';
            }} else {{
                de.textContent = 'Sin cambios significativos';
                de.style.color = '#888';
            }}
        }}
        updateBudget();

        // ================================================
        // VISTAS CÁMARA
        // ================================================
        function setTopView() {{
            camera.setPosition(new BABYLON.Vector3(totalWidth/2, Math.max(totalWidth,totalDepth)*1.6, totalDepth/2));
            camera.setTarget(new BABYLON.Vector3(totalWidth/2, 0, totalDepth/2));
        }}
        function setIsoView() {{
            camera.alpha  = Math.PI/4;
            camera.beta   = Math.PI/3.2;
            camera.radius = Math.max(totalWidth, totalDepth) * 2.2;
            camera.setTarget(new BABYLON.Vector3(totalWidth/2, 0, totalDepth/2));
        }}
        function setStreetView() {{
            // Vista desde la calle (sur) a altura de persona mirando la fachada principal
            const dist = Math.max(totalWidth, totalDepth) * 1.5;
            camera.setTarget(new BABYLON.Vector3(totalWidth/2, WALL_H * 0.55, totalDepth/2));
            camera.setPosition(new BABYLON.Vector3(totalWidth/2, WALL_H * 0.9, totalDepth/2 - dist));
        }}

        // ================================================
        // GUARDAR JSON (cable intacto con Python)
        // ================================================
        function saveChanges() {{
            const layout = [];
            roomsData.forEach((room, i) => {{
                const floor = scene.getMeshByName(`floor_${{i}}`);
                if (floor) {{
                    const b = floor.getBoundingInfo().boundingBox;
                    const w = b.maximumWorld.x - b.minimumWorld.x;
                    const d = b.maximumWorld.z - b.minimumWorld.z;
                    layout.push({{
                        index: i,
                        name:  room.name,
                        original_area: room.area_m2,
                        x: parseFloat(b.minimumWorld.x.toFixed(2)),
                        z: parseFloat(b.minimumWorld.z.toFixed(2)),
                        width: parseFloat(w.toFixed(2)),
                        depth: parseFloat(d.toFixed(2)),
                        new_area: parseFloat((w*d).toFixed(2))
                    }});
                }}
            }});

            // Añadir tabiques custom si existen
            if (window.customWalls && window.customWalls.length > 0) {{
                layout.push({{
                    index: 'custom_walls',
                    name: 'Tabiques personalizados',
                    custom_walls: window.customWalls,
                    original_area: 0, new_area: 0
                }});
            }}

            const json = JSON.stringify(layout, null, 2);
            const blob = new Blob([json], {{type:'application/json'}});
            const url  = URL.createObjectURL(blob);
            const a    = document.createElement('a');
            a.href     = url;
            a.download = 'archirapid_layout_modificado.json';
            a.click();

            showToast('✅ JSON guardado. Súbelo en Documentación (Paso 4)');
        }}

        // ================================================
        // EXPORTAR GLB
        // ================================================
        function exportGLB() {{
            showToast('⏳ Generando modelo 3D...');
            BABYLON.GLTF2Export.GLBAsync(scene, "archirapid_modelo3d", {{
                shouldExportNode: (node) => {{
                    // Excluir suelo, grid y cámara — solo exportar habitaciones
                    const n = node.name || '';
                    return !n.startsWith('ground') && !n.startsWith('gridPlane') &&
                           !n.startsWith('cam') && !n.startsWith('hemi') &&
                           !n.startsWith('dir') && !n.startsWith('label');
                }}
            }}).then(glb => {{
                glb.downloadFiles();
                showToast('✅ Modelo 3D descargado (.glb)');
            }}).catch(err => {{
                console.error('GLB error:', err);
                showToast('⚠️ Error exportando GLB: ' + err.message);
            }});
        }}

        // ================================================
        // HISTORIAL — Reset y Undo
        // ================================================
        const initialRoomsData = JSON.parse(JSON.stringify(roomsData));
        const actionHistory = [];

        function saveSnapshot() {{
            actionHistory.push({{
                rooms: JSON.parse(JSON.stringify(roomsData)),
                walls: JSON.parse(JSON.stringify(window.customWalls || []))
            }});
            if (actionHistory.length > 20) actionHistory.shift();
        }}

        // ================================================
        // CERRAMIENTO PERIMETRAL AUTOMÁTICO
        // ================================================
        window.customWalls = [];
        let fenceActive = false;
        // ── Posición casa en parcela (S7) ────────────────────────────────────
        const RETRANQUEO = 3.0;       // retranqueo legal estándar (m)
        let _houseOffsetX = 0;
        let _houseOffsetZ = 0;
        let _basePosData  = null;     // posiciones de habitaciones SIN offset
        let fenceMeshes = [];

        // ─── MEP Layer Manager ────────────────────────────────────────────────────
        const MEPLayers = {{
          sewage:     {{ meshes: [], visible: false, color: [0.35, 0.35, 0.35], label: "Saneamiento",    emoji: "🚽" }},
          water:      {{ meshes: [], visible: false, color: [0.18, 0.45, 0.85], label: "Agua",           emoji: "💧" }},
          electrical: {{ meshes: [], visible: false, color: [1.00, 0.45, 0.00], label: "Eléctrico",      emoji: "⚡" }},
          rainwater:  {{ meshes: [], visible: false, color: [0.10, 0.60, 0.30], label: "Recogida Agua",  emoji: "🌧️" }},
          domotics:   {{ meshes: [], visible: false, color: [0.60, 0.20, 0.80], label: "Domótica",       emoji: "📡" }}
        }};

        function toggleMEPLayer(layerName) {{
          const layer = MEPLayers[layerName];
          if (!layer) return;
          layer.visible = !layer.visible;
          layer.meshes.forEach(m => {{ m.isVisible = layer.visible; }});
          const btn = document.getElementById("mep_btn_" + layerName);
          if (btn) {{
            btn.style.background = layer.visible ? "#1a472a" : "#1e293b";
            btn.style.borderColor = layer.visible ? "#22c55e" : "#334155";
            btn.style.color = layer.visible ? "#86efac" : "#94a3b8";
            btn.textContent = layer.emoji + " " + layer.label + (layer.visible ? " ✓" : "");
          }}
        }}

        function setGroundTransparency(alpha) {{
          // alpha: 0.0 = invisible, 1.0 = opaque
          if (window.groundMesh) window.groundMesh.visibility = alpha;
          if (window.gridPlaneMesh) window.gridPlaneMesh.visibility = alpha;
          const slider = document.getElementById("ground_alpha_slider");
          if (slider && parseFloat(slider.value) !== alpha) slider.value = alpha;
        }}

        function buildMEPLayers(rooms) {{
            // Guard: skip if no rooms
            if (!rooms || rooms.length === 0) return;
            try {{

            // Clear existing MEP meshes before rebuild
            Object.values(MEPLayers).forEach(layer => {{
                layer.meshes.forEach(m => {{ try {{ m.dispose(); }} catch(e) {{}} }});
                layer.meshes = [];
            }});

            const BURIED_Y = -0.4;
            const WATER_Y  = 0.5;
            const ELEC_Y   = WALL_H - 0.2;

            function mepLine(name, pts, col, layer) {{
                if (!pts || pts.length < 2) return;
                try {{
                const ln = BABYLON.MeshBuilder.CreateLines(name, {{points: pts}}, scene);
                ln.color      = col;
                ln.isPickable = false;
                ln.isVisible  = layer.visible;
                layer.meshes.push(ln);
                }} catch(e) {{}}
            }}
            // Tubos 3D para saneamiento (grosor real, radio 6cm)
            function mepTube(name, pts, col, layer) {{
                if (!pts || pts.length < 2) return;
                try {{
                const tube = BABYLON.MeshBuilder.CreateTube(name, {{path: pts, radius: 0.06, tessellation: 6, cap: 3}}, scene);
                const mat  = new BABYLON.StandardMaterial(name + '_m', scene);
                mat.diffuseColor  = col;
                mat.specularColor = new BABYLON.Color3(0.1, 0.1, 0.1);
                tube.material   = mat;
                tube.isPickable  = false;
                tube.isVisible   = layer.visible;
                layer.meshes.push(tube);
                }} catch(e) {{}}
            }}

            // Habitaciones interiores: excluir garden/exterior (paneles, piscina, huerto…)
            const _GARDEN_CODES = ['panel','solar','piscin','pool','huerto','caseta','apero','bomba'];
            const habRooms = rooms.filter(r => {{
                const z = (r.zone||'').toLowerCase();
                const c = (r.code||'').toLowerCase();
                return z !== 'garden' && z !== 'exterior' &&
                       !_GARDEN_CODES.some(x => c.includes(x));
            }});
            const _baseRooms = habRooms.length > 0 ? habRooms : rooms;

            // Room bounding box — solo habitaciones interiores
            const houseMaxZ = Math.max(..._baseRooms.map(r => r.z + r.depth));
            const houseMaxX = Math.max(..._baseRooms.map(r => r.x + r.width));
            const houseMinX = Math.min(..._baseRooms.map(r => r.x));

            // Wet rooms: need water + sewage
            const wetRooms = _baseRooms.filter(r =>
                ['bano','aseo','cocina'].some(c =>
                    (r.code||'').toLowerCase().includes(c) ||
                    (r.name||'').toLowerCase().includes(c)
                )
            );

            // ── SANEAMIENTO ───────────────────────────────────────────────────
            const SEW = new BABYLON.Color3(0.50, 0.28, 0.05);   // marrón tierra (diferenciado)
            const collectorZ = houseMaxZ + 0.3;
            mepTube('sewage_collector', [
                new BABYLON.Vector3(houseMinX, BURIED_Y, collectorZ),
                new BABYLON.Vector3(houseMaxX, BURIED_Y, collectorZ)
            ], SEW, MEPLayers.sewage);
            wetRooms.forEach((r, idx) => {{
                const cx = r.x + r.width / 2, cz = r.z + r.depth / 2;
                mepTube(`sewage_drop_${{idx}}`, [
                    new BABYLON.Vector3(cx, 0, cz),
                    new BABYLON.Vector3(cx, BURIED_Y, cz)
                ], SEW, MEPLayers.sewage);
                mepTube(`sewage_run_${{idx}}`, [
                    new BABYLON.Vector3(cx, BURIED_Y, cz),
                    new BABYLON.Vector3(cx, BURIED_Y, collectorZ)
                ], SEW, MEPLayers.sewage);
            }});
            // Fosa séptica — semisumergida, tapa visible al nivel del suelo
            const fosaX = houseMaxX + 2.5, fosaZ = houseMaxZ * 0.5;
            const fosa  = BABYLON.MeshBuilder.CreateBox('sewage_fosa',
                {{width:2, height:1.2, depth:1.5}}, scene);
            fosa.position.set(fosaX, -0.8, fosaZ);   // mayormente enterrada
            const fosaMat = new BABYLON.StandardMaterial('mep_fosa_mat', scene);
            fosaMat.diffuseColor = new BABYLON.Color3(0.45, 0.30, 0.10);  // ocre tierra
            fosaMat.alpha = 0.92;
            fosa.material  = fosaMat;
            fosa.isPickable = false;
            fosa.isVisible  = MEPLayers.sewage.visible;
            MEPLayers.sewage.meshes.push(fosa);
            // Tapa registro hierro (disco gris en superficie)
            const fosaTapa = BABYLON.MeshBuilder.CreateCylinder('fosa_tapa',
                {{diameter:0.8, height:0.06, tessellation:16}}, scene);
            fosaTapa.position.set(fosaX, 0.04, fosaZ);  // tapa a ras de suelo
            const tapaMat = new BABYLON.StandardMaterial('fosa_tapa_mat', scene);
            tapaMat.diffuseColor = new BABYLON.Color3(0.30, 0.30, 0.30);
            fosaTapa.material   = tapaMat;
            fosaTapa.isPickable  = false;
            fosaTapa.isVisible   = MEPLayers.sewage.visible;
            MEPLayers.sewage.meshes.push(fosaTapa);
            // Colector → fosa
            mepTube('sewage_to_fosa', [
                new BABYLON.Vector3(houseMaxX, BURIED_Y, collectorZ),
                new BABYLON.Vector3(fosaX - 1, BURIED_Y, fosaZ)
            ], SEW, MEPLayers.sewage);

            // ── AGUA ──────────────────────────────────────────────────────────
            const WAT = new BABYLON.Color3(0.18, 0.45, 0.85);
            const manifoldZ = houseMaxZ * 0.5;
            // Acometida agua — esfera azul oscuro en fachada oeste (red municipal)
            const watAcometida = BABYLON.MeshBuilder.CreateSphere('water_acometida',
                {{diameter:0.35, segments:8}}, scene);
            watAcometida.position.set(houseMinX - 1.0, WATER_Y, manifoldZ);
            const watAcMat = new BABYLON.StandardMaterial('water_ac_mat', scene);
            watAcMat.diffuseColor = new BABYLON.Color3(0.08, 0.28, 0.70);
            watAcometida.material   = watAcMat;
            watAcometida.isPickable  = false;
            watAcometida.isVisible   = MEPLayers.water.visible;
            MEPLayers.water.meshes.push(watAcometida);
            mepLine('water_from_street', [
                new BABYLON.Vector3(houseMinX - 1.0, WATER_Y, manifoldZ),
                new BABYLON.Vector3(houseMinX - 0.5, WATER_Y, manifoldZ)
            ], WAT, MEPLayers.water);
            mepLine('water_manifold', [
                new BABYLON.Vector3(houseMinX - 0.5, WATER_Y, manifoldZ),
                new BABYLON.Vector3(houseMaxX + 0.2, WATER_Y, manifoldZ)
            ], WAT, MEPLayers.water);
            wetRooms.forEach((r, idx) => {{
                const cx = r.x + r.width / 2, cz = r.z + r.depth / 2;
                mepLine(`water_branch_${{idx}}`, [
                    new BABYLON.Vector3(cx, WATER_Y, manifoldZ),
                    new BABYLON.Vector3(cx, WATER_Y, cz),
                    new BABYLON.Vector3(cx, 0.05, cz)
                ], WAT, MEPLayers.water);
            }});

            // ── ELÉCTRICO ─────────────────────────────────────────────────────
            const ELC = new BABYLON.Color3(1.0, 0.45, 0.0);
            const panelX  = houseMinX + 0.3;
            const trunkZ  = _baseRooms[0] ? _baseRooms[0].z + _baseRooms[0].depth / 2 : houseMaxZ * 0.5;
            // Cuadro eléctrico / ICP en fachada exterior oeste (caja amarilla)
            const elecBox = BABYLON.MeshBuilder.CreateBox('elec_cuadro',
                {{width:0.15, height:0.45, depth:0.35}}, scene);
            elecBox.position.set(houseMinX - 0.08, 1.3, trunkZ);
            const elecBoxMat = new BABYLON.StandardMaterial('elec_cuadro_mat', scene);
            elecBoxMat.diffuseColor = new BABYLON.Color3(0.90, 0.80, 0.05);
            elecBox.material   = elecBoxMat;
            elecBox.isPickable  = false;
            elecBox.isVisible   = MEPLayers.electrical.visible;
            MEPLayers.electrical.meshes.push(elecBox);
            // Acometida eléctrica desde la calle (cable entrante oeste → cuadro)
            mepLine('elec_acometida', [
                new BABYLON.Vector3(houseMinX - 1.8, ELEC_Y, trunkZ),
                new BABYLON.Vector3(houseMinX - 0.08, ELEC_Y, trunkZ),
                new BABYLON.Vector3(houseMinX - 0.08, 1.55, trunkZ)
            ], ELC, MEPLayers.electrical);
            mepLine('elec_trunk', [
                new BABYLON.Vector3(panelX, ELEC_Y, trunkZ),
                new BABYLON.Vector3(houseMaxX + 0.1, ELEC_Y, trunkZ)
            ], ELC, MEPLayers.electrical);
            _baseRooms.forEach((r, idx) => {{
                const cx = r.x + r.width / 2, cz = r.z + r.depth / 2;
                mepLine(`elec_drop_${{idx}}`, [
                    new BABYLON.Vector3(cx, ELEC_Y, trunkZ),
                    new BABYLON.Vector3(cx, ELEC_Y, cz)
                ], ELC, MEPLayers.electrical);
            }});

            // ── RECOGIDA AGUA (canalones) ─────────────────────────────────────
            const RAIN = new BABYLON.Color3(0.1, 0.6, 0.3);
            const gutY = WALL_H + 0.05;
            mepLine('rain_gutter_front', [
                new BABYLON.Vector3(houseMinX - 0.2, gutY, houseMaxZ + 0.2),
                new BABYLON.Vector3(houseMaxX + 0.2, gutY, houseMaxZ + 0.2)
            ], RAIN, MEPLayers.rainwater);
            mepLine('rain_gutter_back', [
                new BABYLON.Vector3(houseMinX - 0.2, gutY, -0.2),
                new BABYLON.Vector3(houseMaxX + 0.2, gutY, -0.2)
            ], RAIN, MEPLayers.rainwater);
            [[-0.2, houseMaxZ + 0.2],[houseMaxX + 0.2, houseMaxZ + 0.2],
             [-0.2, -0.2],[houseMaxX + 0.2, -0.2]].forEach(([dx, dz], idx) => {{
                mepLine(`rain_down_${{idx}}`, [
                    new BABYLON.Vector3(dx, gutY, dz),
                    new BABYLON.Vector3(dx, 0, dz)
                ], RAIN, MEPLayers.rainwater);
            }});

            // ── DOMÓTICA (canalización datos) ─────────────────────────────────
            const DOM = new BABYLON.Color3(0.6, 0.2, 0.8);
            mepLine('dom_trunk', [
                new BABYLON.Vector3(panelX, ELEC_Y - 0.15, trunkZ),
                new BABYLON.Vector3(houseMaxX + 0.1, ELEC_Y - 0.15, trunkZ)
            ], DOM, MEPLayers.domotics);
            _baseRooms.forEach((r, idx) => {{
                const cx = r.x + r.width / 2, cz = r.z + r.depth / 2;
                mepLine(`dom_drop_${{idx}}`, [
                    new BABYLON.Vector3(cx, ELEC_Y - 0.15, trunkZ),
                    new BABYLON.Vector3(cx, ELEC_Y - 0.15, cz)
                ], DOM, MEPLayers.domotics);
            }});

            }} catch(mepErr) {{ console.warn('MEP build error (non-fatal):', mepErr); }}
        }}

        function toggleFence() {{
            if (fenceActive) {{
                // Quitar cerramiento
                fenceMeshes.forEach(m => {{ m.material && m.material.dispose(); m.dispose(); }});
                fenceMeshes = [];
                fenceActive = false;
                document.getElementById('btn-fence').textContent = '🧱 Cerramiento OFF';
                document.getElementById('btn-fence').classList.remove('active');
                document.getElementById('fence-options').style.display = 'none';
                showToast('Cerramiento eliminado');
            }} else {{
                document.getElementById('fence-options').style.display = 'block';
                buildFence();
                fenceActive = true;
                document.getElementById('btn-fence').textContent = '🧱 Cerramiento ON';
                document.getElementById('btn-fence').classList.add('active');
                // Mostrar dimensiones reales de la finca
                const perim = Math.round((plotW + plotD) * 2);
                const buildable = Math.round(plotW * plotD * 0.33);
                document.getElementById('fence-dim-w').textContent = plotW;
                document.getElementById('fence-dim-d').textContent = plotD;
                document.getElementById('fence-area').textContent = (plotW * plotD).toLocaleString('es-ES');
                document.getElementById('fence-perim').textContent = perim;
                document.getElementById('fence-build').textContent = buildable.toLocaleString('es-ES');
                document.getElementById('fence-info').style.display = 'block';
                showToast('Cerramiento: ' + plotW + 'm × ' + plotD + 'm · ' + (plotW*plotD) + 'm²');
            }}
        }}

        function buildFence() {{
            // Limpiar previo
            fenceMeshes.forEach(m => {{ m.material && m.material.dispose(); m.dispose(); }});
            fenceMeshes = [];

            const style  = document.getElementById('fence-style').value;
            const FENCE_H = style === 'muro' ? 2.0 : 1.8;
            const FENCE_T = style === 'muro' ? 0.20 : 0.05;
            const alpha   = style === 'muro' ? 1.0  : 0.65;

            const mat = new BABYLON.StandardMaterial('fenceMat', scene);
            if (style === 'muro') {{
                mat.diffuseColor = new BABYLON.Color3(0.78, 0.76, 0.72);  // cemento gris
            }} else {{
                mat.diffuseColor  = new BABYLON.Color3(0.30, 0.30, 0.30);  // metal oscuro
                mat.emissiveColor = new BABYLON.Color3(0.05, 0.05, 0.05);
                mat.alpha = alpha;
            }}

            // Perímetro: 4 lados del plot
            // Lado Sur (fachada) — con huecos para portón (4m) + puerta (1.2m)
            const GATE_CAR  = 4.0;   // portón vehículo
            const GATE_PED  = 1.2;   // puerta peatonal
            const GATE_GAP  = 0.3;   // separación entre ambas
            const gateStart = plotX + 2.0;  // offset desde esquina

            // Sur (fachada entrada — z pequeño, frente al porche)
            _fenceSegH('fs_left', plotX, plotZ,
                        gateStart, FENCE_H, FENCE_T, mat);
            _fenceSegH('fs_mid', gateStart + GATE_CAR + GATE_GAP, plotZ,
                        gateStart + GATE_CAR + GATE_GAP + GATE_PED + GATE_GAP, FENCE_H, FENCE_T, mat);
            _fenceSegH('fs_right', gateStart + GATE_CAR + GATE_GAP + GATE_PED + GATE_GAP, plotZ,
                        plotX + plotW, FENCE_H, FENCE_T, mat);

            // Norte (fachada trasera — z grande)
            const backGateX = plotX + plotW/2 - GATE_PED/2;
            _fenceSegH('fn_left',  plotX, plotZ + plotD, backGateX, FENCE_H, FENCE_T, mat);
            _fenceSegH('fn_right', backGateX + GATE_PED, plotZ + plotD,
                        plotX + plotW, FENCE_H, FENCE_T, mat);

            // Oeste completo
            _fenceSegV('fw', plotX, plotZ, plotZ + plotD, FENCE_H, FENCE_T, mat);

            // Este completo
            _fenceSegV('fe', plotX + plotW, plotZ, plotZ + plotD, FENCE_H, FENCE_T, mat);

            // Marcadores de puertas
            _fenceGate('gate_car', gateStart, plotZ, GATE_CAR, FENCE_H);
            _fenceGate('gate_ped', gateStart + GATE_CAR + GATE_GAP, plotZ, GATE_PED, FENCE_H);
            _fenceGate('gate_back', backGateX, plotZ + plotD, GATE_PED, FENCE_H);
        }}

        function _fenceSegH(id, x1, z, x2, h, t, mat) {{
            const len = x2 - x1;
            if (len < 0.1) return;
            const m = BABYLON.MeshBuilder.CreateBox('fence_'+id,
                {{width: len, height: h, depth: t}}, scene);
            m.position.set(x1 + len/2, h/2, z);
            m.material = mat;
            fenceMeshes.push(m);
        }}

        function _fenceSegV(id, x, z1, z2, h, t, mat) {{
            const len = z2 - z1;
            if (len < 0.1) return;
            const m = BABYLON.MeshBuilder.CreateBox('fence_'+id,
                {{width: t, height: h, depth: len}}, scene);
            m.position.set(x, h/2, z1 + len/2);
            m.material = mat;
            fenceMeshes.push(m);
        }}

        function _fenceGate(id, x, z, w, h) {{
            const mat = new BABYLON.StandardMaterial('gate_mat_'+id, scene);
            mat.diffuseColor  = new BABYLON.Color3(0.9, 0.75, 0.1);  // dorado
            mat.emissiveColor = new BABYLON.Color3(0.2, 0.15, 0.0);
            mat.alpha = 0.5;
            const m = BABYLON.MeshBuilder.CreateBox('fence_'+id,
                {{width: w, height: h, depth: 0.05}}, scene);
            m.position.set(x + w/2, h/2, z);
            m.material = mat;
            fenceMeshes.push(m);
        }}

        // Al cambiar estilo, reconstruir si está activo
        document.getElementById('fence-style').addEventListener('change', () => {{
            if (fenceActive) buildFence();
        }});

        // ================================================
        // RESET LAYOUT — volver al estado inicial
        // ================================================
        function resetLayout() {{
            saveSnapshot();
            // Limpiar cerramientos personalizados
            window.customWalls.forEach(cw => {{
                const m = scene.getMeshByName(cw.id);
                if (m) {{ m.material && m.material.dispose(); m.dispose(); }}
            }});
            window.customWalls = [];
            // Restaurar roomsData original
            roomsData.length = 0;
            initialRoomsData.forEach(r => roomsData.push(JSON.parse(JSON.stringify(r))));
            // Reconstruir escena
            const newLayout = generateLayoutJS(roomsData);
            rebuildScene(newLayout);
            showToast('↩️ Layout restaurado al original');
        }}

        // ================================================
        // UNDO — deshacer última acción
        // ================================================
        function undoLastAction() {{
            if (actionHistory.length === 0) {{
                showToast('⚠️ No hay acciones para deshacer');
                return;
            }}
            const prev = actionHistory.pop();
            // Restaurar cerramientos
            window.customWalls.forEach(cw => {{
                const m = scene.getMeshByName(cw.id);
                if (m) {{ m.material && m.material.dispose(); m.dispose(); }}
            }});
            window.customWalls = prev.walls;
            // Reconstruir cerramientos guardados
            prev.walls.forEach(cw => {{
                const dx = cw.x2 - cw.x1, dz = cw.z2 - cw.z1;
                const len = Math.sqrt(dx*dx + dz*dz);
                const ang = Math.atan2(dx, dz);
                const m = BABYLON.MeshBuilder.CreateBox(cw.id,
                    {{width:len, height:WALL_H, depth:WALL_T}}, scene);
                m.position.set((cw.x1+cw.x2)/2, WALL_H/2, (cw.z1+cw.z2)/2);
                m.rotation.y = ang;
                const mat = new BABYLON.StandardMaterial(cw.id+'m', scene);
                mat.diffuseColor = new BABYLON.Color3(0.65,0.45,0.25);
                m.material = mat;
            }});
            // Restaurar roomsData
            roomsData.length = 0;
            prev.rooms.forEach(r => roomsData.push(r));
            const newLayout = generateLayoutJS(roomsData);
            rebuildScene(newLayout);
            showToast('⬅️ Acción deshecha');
        }}

        // ================================================
        // DELETE — borrar elemento seleccionado
        // ================================================
        // Primer clic activa modo confirmación; segundo clic dentro de 3s confirma.
        let _deleteConfirmPending = false;
        let _deleteConfirmTimer  = null;

        function deleteSelected() {{
            // ── Habitación seleccionada ───────────────────────────────────────
            if (selectedIndex !== null) {{
                // Contar solo habitaciones interiores (no garden/exterior)
                const interiorCount = roomsData.filter(r => {{
                    const z = (r.zone||'').toLowerCase();
                    return z !== 'garden' && z !== 'exterior';
                }}).length;
                if (interiorCount <= 2) {{
                    showToast('⚠️ Mínimo 2 habitaciones — no se puede borrar más');
                    return;
                }}
                // Doble-clic de confirmación
                if (!_deleteConfirmPending) {{
                    _deleteConfirmPending = true;
                    const rName = roomsData[selectedIndex].name;
                    showToast(`🗑️ ¿Borrar "${{rName}}"? Pulsa de nuevo para confirmar`);
                    document.getElementById('btn-delete').style.background = 'rgba(231,76,60,0.6)';
                    clearTimeout(_deleteConfirmTimer);
                    _deleteConfirmTimer = setTimeout(() => {{
                        _deleteConfirmPending = false;
                        document.getElementById('btn-delete').style.background = 'rgba(231,76,60,0.25)';
                        showToast('❌ Borrado cancelado');
                    }}, 3000);
                    return;
                }}
                // Segunda pulsación — confirmar borrado
                clearTimeout(_deleteConfirmTimer);
                _deleteConfirmPending = false;
                document.getElementById('btn-delete').style.background = 'rgba(231,76,60,0.25)';
                saveSnapshot();
                const deletedName = roomsData[selectedIndex].name;
                roomsData.splice(selectedIndex, 1);
                selectedMesh = null;
                selectedIndex = null;
                hlLayer.removeAllMeshes();
                document.getElementById('room-info').innerHTML =
                    '<p style="color:#888;">Selecciona una habitación</p>';
                document.getElementById('edit-panel').style.display = 'none';
                // Redistribuir layout completo
                const newLayout = generateLayoutJS(roomsData);
                rebuildScene(newLayout);
                _resetPosSliders();   // resetear offsets tras borrado
                showToast(`🗑️ "${{deletedName}}" eliminada — planta redistribuida`);
                return;
            }}
            // ── Cerramiento seleccionado ──────────────────────────────────────
            if (selectedMesh && selectedMesh.name.startsWith('cwall_')) {{
                saveSnapshot();
                const idx = window.customWalls.findIndex(cw => cw.id === selectedMesh.name);
                if (idx !== -1) window.customWalls.splice(idx, 1);
                selectedMesh.material && selectedMesh.material.dispose();
                selectedMesh.dispose();
                selectedMesh = null;
                hlLayer.removeAllMeshes();
                document.getElementById('room-info').innerHTML =
                    '<p style="color:#888;">Selecciona una habitación</p>';
                showToast('🗑️ Cerramiento eliminado');
                return;
            }}
            showToast('⚠️ Selecciona una habitación o cerramiento para borrar');
        }}

        // Tecla Supr/Delete para borrar rápido
        window.addEventListener('keydown', (e) => {{
            if (e.key === 'Delete' || e.key === 'Backspace') deleteSelected();
        }});

        // ================================================
        // POSICIÓN DE LA CASA EN LA PARCELA (S7)
        // ================================================
        function _resetPosSliders() {{
            _basePosData = null;
            _houseOffsetX = 0;
            _houseOffsetZ = 0;
            const slX = document.getElementById('slider-offset-x');
            const slZ = document.getElementById('slider-offset-z');
            if (slX) {{ slX.value = 0; }}
            if (slZ) {{ slZ.value = 0; }}
            const vX = document.getElementById('offset-x-val');
            const vZ = document.getElementById('offset-z-val');
            if (vX) vX.textContent = '0m';
            if (vZ) vZ.textContent = '0m';
        }}

        function onPlotOffsetChange() {{
            const ox = parseFloat(document.getElementById('slider-offset-x').value) || 0;
            const oz = parseFloat(document.getElementById('slider-offset-z').value) || 0;
            document.getElementById('offset-x-val').textContent = ox.toFixed(1) + 'm';
            document.getElementById('offset-z-val').textContent = oz.toFixed(1) + 'm';
            _houseOffsetX = ox;
            _houseOffsetZ = oz;

            // Verificar retranqueo en los cuatro lados
            const leftOK  = (ox - plotX) >= RETRANQUEO - 0.05;
            const rightOK = (plotX + plotW - (ox + totalWidth)) >= RETRANQUEO - 0.05;
            const frontOK = (oz - plotZ) >= RETRANQUEO - 0.05;
            const backOK  = (plotZ + plotD - (oz + totalDepth)) >= RETRANQUEO - 0.05;
            const allOK   = leftOK && rightOK && frontOK && backOK;
            document.getElementById('retranqueo-ok').style.display   = allOK ? 'block' : 'none';
            document.getElementById('retranqueo-warn').style.display  = allOK ? 'none'  : 'block';

            // Guardar posiciones base la primera vez (antes de aplicar ningún offset)
            if (!_basePosData || _basePosData.length !== roomsData.length) {{
                _basePosData = roomsData.map(r => ({{ x: r.x, z: r.z }}));
            }}

            // Desplazar todas las habitaciones
            roomsData.forEach((r, i) => {{
                r.x = _basePosData[i].x + ox;
                r.z = _basePosData[i].z + oz;
            }});
            rebuildScene(roomsData);
        }}

        // ================================================
        function showToast(msg) {{
            let t = document.getElementById('toast');
            if (!t) {{
                t = document.createElement('div');
                t.id = 'toast';
                t.style.cssText = 'position:fixed;bottom:80px;left:50%;transform:translateX(-50%);'
                    + 'background:rgba(0,0,0,0.85);color:white;padding:10px 20px;'
                    + 'border-radius:20px;font-size:13px;z-index:9999;pointer-events:none;'
                    + 'transition:opacity 0.3s;';
                document.body.appendChild(t);
            }}
            t.textContent = msg;
            t.style.opacity = '1';
            clearTimeout(window._toastTimer);
            window._toastTimer = setTimeout(() => t.style.opacity = '0', 3000);
        }}

        // ================================================
        // TEJADO 3D
        // ================================================
        let roofMesh = null;
        let roofActive = false;

        function buildRoof() {{
            if (roofMesh) {{ roofMesh.dispose(); roofMesh = null; }}

            // Calcular bounding box de TODA la casa (solo habitaciones interiores)
            const interiorZones = ['day','night','wet','circ','service'];
            const houseRooms = roomsData.filter(r => interiorZones.includes((r.zone||'').toLowerCase()));
            if (houseRooms.length === 0) return;

            const minX = Math.min(...houseRooms.map(r => r.x));
            const minZ = Math.min(...houseRooms.map(r => r.z));
            const maxX = Math.max(...houseRooms.map(r => r.x + r.width));
            const maxZ = Math.max(...houseRooms.map(r => r.z + r.depth));
            const hW = maxX - minX;  // ancho total casa
            const hD = maxZ - minZ;  // fondo total casa
            const hCX = minX + hW / 2;  // centro X
            const hCZ = minZ + hD / 2;  // centro Z
            const wallH = 2.7;           // altura paredes
            const roofH = hW * 0.28;     // altura cumbrera (28% del ancho)
            const overhang = 0.6;        // voladizo perimetral

            // Material tejado
            const rMat = new BABYLON.StandardMaterial('roofMat', scene);
            if (roofType.includes('Plana') || roofType.includes('Invertida')) {{
                rMat.diffuseColor = new BABYLON.Color3(0.55, 0.55, 0.58);
            }} else {{
                rMat.diffuseColor = new BABYLON.Color3(0.72, 0.36, 0.18);
            }}
            rMat.specularColor = new BABYLON.Color3(0.1, 0.1, 0.1);
            // Override con color del estilo arquitectónico elegido en Paso 1
            const _rc = styleConf.roofColor;
            rMat.diffuseColor = new BABYLON.Color3(_rc[0], _rc[1], _rc[2]);

            const rType = roofType.toLowerCase();

            if (rType.includes('plana') || rType.includes('invertida')) {{
                // TEJADO PLANO — losa horizontal con parapeto
                roofMesh = BABYLON.MeshBuilder.CreateBox('roof', {{
                    width: hW + overhang * 2,
                    height: 0.25,
                    depth: hD + overhang * 2
                }}, scene);
                roofMesh.position.set(hCX, wallH + 0.12, hCZ);

            }} else if (rType.includes('un agua')) {{
                // TEJADO A UN AGUA — plano inclinado de norte a sur
                const path1 = [
                    new BABYLON.Vector3(minX - overhang, wallH, minZ - overhang),
                    new BABYLON.Vector3(maxX + overhang, wallH, minZ - overhang)
                ];
                const path2 = [
                    new BABYLON.Vector3(minX - overhang, wallH + roofH, maxZ + overhang),
                    new BABYLON.Vector3(maxX + overhang, wallH + roofH, maxZ + overhang)
                ];
                roofMesh = BABYLON.MeshBuilder.CreateRibbon('roof', {{
                    pathArray: [path1, path2], sideOrientation: BABYLON.Mesh.DOUBLESIDE
                }}, scene);

            }} else if (rType.includes('cuatro')) {{
                // TEJADO A CUATRO AGUAS — 4 faldones que convergen en cumbrera central
                const apex = new BABYLON.Vector3(hCX, wallH + roofH, hCZ);
                const corners = [
                    [new BABYLON.Vector3(minX - overhang, wallH, minZ - overhang),
                     new BABYLON.Vector3(maxX + overhang, wallH, minZ - overhang), apex],
                    [new BABYLON.Vector3(maxX + overhang, wallH, minZ - overhang),
                     new BABYLON.Vector3(maxX + overhang, wallH, maxZ + overhang), apex],
                    [new BABYLON.Vector3(maxX + overhang, wallH, maxZ + overhang),
                     new BABYLON.Vector3(minX - overhang, wallH, maxZ + overhang), apex],
                    [new BABYLON.Vector3(minX - overhang, wallH, maxZ + overhang),
                     new BABYLON.Vector3(minX - overhang, wallH, minZ - overhang), apex],
                ];
                const parts = [];
                corners.forEach((tri, i) => {{
                    const t = BABYLON.MeshBuilder.CreateRibbon(`roof_${{i}}`, {{
                        pathArray: [[tri[0], tri[2]], [tri[1], tri[2]]],
                        sideOrientation: BABYLON.Mesh.DOUBLESIDE
                    }}, scene);
                    t.material = rMat;
                    parts.push(t);
                }});
                roofMesh = BABYLON.Mesh.MergeMeshes(parts, true, true);
                if (roofMesh) roofMesh.name = 'roof';

            }} else {{
                // DOS AGUAS — por defecto (más común en España)
                // Cumbrera a lo largo del eje X (de este a oeste)
                const path1 = [
                    new BABYLON.Vector3(minX - overhang, wallH, minZ - overhang),
                    new BABYLON.Vector3(minX - overhang, wallH + roofH, hCZ),
                    new BABYLON.Vector3(minX - overhang, wallH, maxZ + overhang)
                ];
                const path2 = [
                    new BABYLON.Vector3(maxX + overhang, wallH, minZ - overhang),
                    new BABYLON.Vector3(maxX + overhang, wallH + roofH, hCZ),
                    new BABYLON.Vector3(maxX + overhang, wallH, maxZ + overhang)
                ];
                roofMesh = BABYLON.MeshBuilder.CreateRibbon('roof', {{
                    pathArray: [path1, path2], sideOrientation: BABYLON.Mesh.DOUBLESIDE
                }}, scene);
            }}

            if (roofMesh) {{
                roofMesh.material = rMat;
                roofMesh.isPickable = false;
                shadowGen.addShadowCaster(roofMesh, false);
            }}
        }}

        // ================================================
        // EXTRAS DE ESTILO 3D — chimenea, piscina, terraza, árboles, patio
        // ================================================
        let styleMeshes = [];

        function clearStyleExtras() {{
            styleMeshes.forEach(m => {{
                try {{ if (m.material) m.material.dispose(); m.dispose(); }} catch(e) {{}}
            }});
            styleMeshes = [];
        }}

        function buildStyleExtras(overrideStyle) {{
            clearStyleExtras();
            const conf = STYLE_3D_CONFIG[overrideStyle || houseStyle] || STYLE_3D_CONFIG['Moderno'];
            // Centro real de la casa — desplazado si el usuario ha movido la vivienda en parcela
            const hX = totalWidth / 2 + _houseOffsetX;
            const hZ = totalDepth / 2 + _houseOffsetZ;
            const wallH = 2.7;

            // --- CHIMENEA — centrada sobre la casa, visible desde cámara NE ---
            if (conf.chimney) {{
                const chimMat = new BABYLON.StandardMaterial('chimMat', scene);
                chimMat.diffuseColor = new BABYLON.Color3(0.32, 0.28, 0.24);
                // Fuste — sale desde el nivel de paredes hacia arriba
                const chimBase = BABYLON.MeshBuilder.CreateBox('chimBase', {{width:0.70, height:2.2, depth:0.70}}, scene);
                chimBase.position.set(hX - 0.5, wallH + 1.1, hZ + 1);
                chimBase.material = chimMat; chimBase.isPickable = false;
                styleMeshes.push(chimBase);
                // Remate superior más ancho
                const chimTop = BABYLON.MeshBuilder.CreateBox('chimTop', {{width:0.95, height:0.22, depth:0.95}}, scene);
                chimTop.position.set(hX - 0.5, wallH + 2.31, hZ + 1);
                chimTop.material = chimMat; chimTop.isPickable = false;
                styleMeshes.push(chimTop);
            }}

            // --- EXTRAS SEGÚN ESTILO ---
            // Árboles en los laterales este/oeste — siempre visibles desde cámara NE
            const treePositions = [
                [-3.2, hZ * 0.5],              // oeste, cuarto norte
                [totalWidth + 3.2, hZ * 0.5],  // este, cuarto norte
                [-3.2, hZ * 1.5],              // oeste, cuarto sur
                [totalWidth + 3.2, hZ * 1.5]   // este, cuarto sur
            ];
            let treeCount = 0;
            conf.extras.forEach((extra) => {{
                if (extra === 'pool') {{
                    // Piscina — al norte de la casa (visible desde cámara NE)
                    const bordeMat = new BABYLON.StandardMaterial('poolBordeMat', scene);
                    bordeMat.diffuseColor = new BABYLON.Color3(0.90, 0.88, 0.82);
                    const borde = BABYLON.MeshBuilder.CreateBox('pool_borde', {{width:5.2, height:0.22, depth:3.8}}, scene);
                    borde.position.set(hX, 0.11, totalDepth + 3.5);
                    borde.material = bordeMat; borde.isPickable = false;
                    styleMeshes.push(borde);
                    const poolMat = new BABYLON.StandardMaterial('poolMat', scene);
                    poolMat.diffuseColor = new BABYLON.Color3(0.20, 0.55, 0.85);
                    poolMat.alpha = 0.88;
                    const pool = BABYLON.MeshBuilder.CreateBox('pool', {{width:4.5, height:0.55, depth:3.1}}, scene);
                    pool.position.set(hX, 0.28, totalDepth + 3.5);
                    pool.material = poolMat; pool.isPickable = false;
                    styleMeshes.push(pool);

                }} else if (extra === 'terrace') {{
                    // Terraza — al norte de la casa (visible desde cámara NE)
                    const terrMat = new BABYLON.StandardMaterial('terrMat', scene);
                    terrMat.diffuseColor = new BABYLON.Color3(0.88, 0.84, 0.72);
                    const terr = BABYLON.MeshBuilder.CreateBox('terrace', {{
                        width: Math.max(totalWidth * 0.65, 4), height: 0.14, depth: 2.8
                    }}, scene);
                    terr.position.set(hX, 0.07, totalDepth + 1.8);
                    terr.material = terrMat; terr.isPickable = false;
                    styleMeshes.push(terr);

                }} else if (extra === 'patio') {{
                    // Patio andaluz con fuente — al este (visible desde NE)
                    const patioMat = new BABYLON.StandardMaterial('patioMat', scene);
                    patioMat.diffuseColor = new BABYLON.Color3(0.85, 0.78, 0.65);
                    const patio = BABYLON.MeshBuilder.CreateBox('patio', {{width:3.5, height:0.08, depth:3.5}}, scene);
                    patio.position.set(totalWidth + 2.5, 0.04, hZ);
                    patio.material = patioMat; patio.isPickable = false;
                    styleMeshes.push(patio);
                    const fuenteMat = new BABYLON.StandardMaterial('fuenteMat', scene);
                    fuenteMat.diffuseColor = new BABYLON.Color3(0.20, 0.45, 0.75);
                    const fuente = BABYLON.MeshBuilder.CreateCylinder('fuente', {{diameter:0.9, height:0.45, tessellation:12}}, scene);
                    fuente.position.set(totalWidth + 2.5, 0.27, hZ);
                    fuente.material = fuenteMat; fuente.isPickable = false;
                    styleMeshes.push(fuente);

                }} else if (extra === 'sea') {{
                    // Playa+mar siempre FUERA del cerramiento (más allá del límite norte del solar)
                    const fenceNorthZ = plotCZ + plotD / 2;  // borde norte del solar
                    const seaW = plotW + 20;                 // cubre todo el ancho del solar + margen
                    const sandMat = new BABYLON.StandardMaterial('sandMat', scene);
                    sandMat.diffuseColor = new BABYLON.Color3(0.94, 0.87, 0.68);
                    const sand = BABYLON.MeshBuilder.CreateBox('sea_sand', {{
                        width: seaW, height: 0.10, depth: 6.0
                    }}, scene);
                    sand.position.set(plotCX, 0.05, fenceNorthZ + 4.0);
                    sand.material = sandMat; sand.isPickable = false;
                    styleMeshes.push(sand);
                    const seaMat = new BABYLON.StandardMaterial('seaMat', scene);
                    seaMat.diffuseColor = new BABYLON.Color3(0.08, 0.48, 0.78);
                    seaMat.specularColor = new BABYLON.Color3(0.6, 0.8, 1.0);
                    seaMat.alpha = 0.88;
                    const sea = BABYLON.MeshBuilder.CreateBox('sea_water', {{
                        width: seaW, height: 0.14, depth: 12.0
                    }}, scene);
                    sea.position.set(plotCX, 0.07, fenceNorthZ + 13.0);
                    sea.material = seaMat; sea.isPickable = false;
                    styleMeshes.push(sea);

                }} else if (extra === 'tree') {{
                    // Árbol en lateral — siempre visible desde cámara NE
                    const pos = treePositions[treeCount % treePositions.length];
                    treeCount++;
                    const trunkMat = new BABYLON.StandardMaterial('trunkMat' + treeCount, scene);
                    trunkMat.diffuseColor = new BABYLON.Color3(0.42, 0.28, 0.14);
                    const trunk = BABYLON.MeshBuilder.CreateCylinder('trunk' + treeCount, {{diameter:0.42, height:2.2, tessellation:8}}, scene);
                    trunk.position.set(pos[0], 1.1, pos[1]);
                    trunk.material = trunkMat; trunk.isPickable = false;
                    styleMeshes.push(trunk);
                    const foliageMat = new BABYLON.StandardMaterial('foliageMat' + treeCount, scene);
                    foliageMat.diffuseColor = new BABYLON.Color3(0.18, 0.50, 0.15);
                    const foliage = BABYLON.MeshBuilder.CreateSphere('foliage' + treeCount, {{diameter:3.0, segments:6}}, scene);
                    foliage.position.set(pos[0], 3.3, pos[1]);
                    foliage.material = foliageMat; foliage.isPickable = false;
                    styleMeshes.push(foliage);
                }}
            }});
        }}

        // Colores por material
        const ROOF_COLORS = {{
            'teja':      new BABYLON.Color3(0.72, 0.36, 0.18),
            'pizarra':   new BABYLON.Color3(0.25, 0.25, 0.30),
            'zinc':      new BABYLON.Color3(0.55, 0.60, 0.65),
            'sandwich':  new BABYLON.Color3(0.75, 0.75, 0.78),
            'vegetal':   new BABYLON.Color3(0.30, 0.55, 0.25),
        }};
        let currentRoofMaterial = 'teja';
        let currentOverhang = 0.6;

        function changeRoofMaterial(mat) {{
            currentRoofMaterial = mat;
            if (roofMesh && roofMesh.material) {{
                roofMesh.material.diffuseColor = ROOF_COLORS[mat] || ROOF_COLORS['teja'];
                showToast('Material: ' + document.getElementById('roof-material').options[
                    document.getElementById('roof-material').selectedIndex].text);
            }}
        }}

        function changeOverhang(val) {{
            currentOverhang = parseFloat(val) / 10;
            document.getElementById('overhang-val').textContent = currentOverhang.toFixed(1) + 'm';
            if (roofActive) {{ buildRoof(); }}
        }}

        function toggleRoof() {{
            const btn = document.getElementById('btn-roof');
            if (roofActive) {{
                if (roofMesh) {{ roofMesh.dispose(); roofMesh = null; }}
                // Quitar paneles del tejado al desactivar
                solarMeshes.forEach(m => {{ m.dispose(); }});
                solarMeshes = [];
                // Restaurar visibilidad del floor garden de paneles
                roomsData.forEach((r, i) => {{
                    if ((r.code||'').toLowerCase().includes('panel') || (r.code||'').toLowerCase().includes('solar')) {{
                        const floorMesh = scene.getMeshByName(`floor_${{i}}`);
                        if (floorMesh) floorMesh.isVisible = true;
                    }}
                }});
                roofActive = false;
                btn.textContent = '🏠 Tejado OFF';
                btn.classList.remove('active');
                document.getElementById('roof-panel').style.display = 'none';
                showToast('Tejado ocultado');
                try {{ buildMEPLayers(roomsData); }} catch(e) {{}}

            }} else {{
                buildRoof();
                roofActive = true;
                btn.textContent = '🏠 Tejado ON';
                btn.classList.add('active');
                document.getElementById('roof-panel').style.display = 'block';
                showToast('Tejado: ' + roofType.split('(')[0].trim());
                buildSolarPanels();
                try {{ buildMEPLayers(roomsData); }} catch(e) {{}}
            }}
        }}                                                                                                                             
        // ================================================
        // PANELES SOLARES EN TEJADO
        // ================================================
        let solarMeshes = [];

        function buildSolarPanels() {{
            // Limpiar paneles previos
            solarMeshes.forEach(m => {{ m.material && m.material.dispose(); m.dispose(); }});
            solarMeshes = [];

            // Buscar habitaciones de paneles solares en roomsData
            const panelRooms = roomsData.filter(r =>
                (r.code||'').toLowerCase().includes('panel') ||
                (r.code||'').toLowerCase().includes('solar')
            );
            if (panelRooms.length === 0) return;

            // Ocultar el suelo garden de paneles mientras tejado está ON
            roomsData.forEach((r, i) => {{
                if ((r.code||'').toLowerCase().includes('panel') || (r.code||'').toLowerCase().includes('solar')) {{
                    const floorMesh = scene.getMeshByName(`floor_${{i}}`);
                    if (floorMesh) floorMesh.isVisible = false;
                }}
            }});

            // Calcular bounding box de la casa (solo zonas habitables)
            const houseRooms = roomsData.filter(r => {{
                const z = (r.zone||'').toLowerCase();
                return z !== 'garden' && z !== 'exterior';
            }});
            if (houseRooms.length === 0) return;

            const minX = Math.min(...houseRooms.map(r => r.x));
            const maxX = Math.max(...houseRooms.map(r => r.x + r.width));
            const minZ = Math.min(...houseRooms.map(r => r.z));
            const maxZ = Math.max(...houseRooms.map(r => r.z + r.depth));
            const houseW = maxX - minX;
            const houseCX = (minX + maxX) / 2;

            // Calcular altura del tejado en el punto sur
            // La cumbrera está en el centro, el alero en los extremos
            const roofPitch = 0.35;  // pendiente estándar
            const roofAleroZ = minZ;  // fachada sur (z menor = sur en nuestro sistema)
            const roofHeight = WALL_H + (houseW / 2) * roofPitch;
            const roofMidHeight = WALL_H + 0.1;

            // Material panel solar — azul oscuro con brillo
            const panMat = new BABYLON.StandardMaterial('solarMat', scene);
            panMat.diffuseColor = new BABYLON.Color3(0.05, 0.15, 0.45);
            panMat.emissiveColor = new BABYLON.Color3(0.05, 0.15, 0.40);  // más brillo
            panMat.specularColor = new BABYLON.Color3(0.6, 0.7, 0.9);
            panMat.specularPower = 32;

            // Crear paneles — distribuidos en la mitad sur del tejado
            // Cada panel real: 1.7m x 1.0m, inclinación 30° orientado sur
            const PANEL_W = 5.1;
            const PANEL_D = 3.0;
            const PANEL_GAP = 0.4;
            const PANEL_H = 0.18;  // más grueso para verse
            const INCLINATION = 0.52;  // 30° en radianes — óptimo España

            // Calcular cuántos paneles caben según el área solicitada
            // rows siempre = 1 para evitar que una segunda fila flote sobre el tejado
            let totalPanelArea = 0;
            panelRooms.forEach(r => {{ totalPanelArea += (r.area_m2 || 10); }});
            const maxColsByWidth = Math.max(1, Math.floor(houseW / (PANEL_W + PANEL_GAP)));
            const numPanels = Math.min(
                Math.max(2, Math.round(totalPanelArea / (PANEL_W * PANEL_D))),
                maxColsByWidth
            );
            const cols = numPanels;
            const rows = 1;

            // Posición sobre faldón sur según tipo de tejado
            const houseD = maxZ - minZ;
            let panelBaseY, panelBaseZ;

            // Usa la MISMA fórmula que buildRoof(): roofH = houseW * 0.28
            const rH = houseW * 0.28;
            if (roofType.toLowerCase().includes('plana')) {{
                panelBaseY = WALL_H + 0.35;
                panelBaseZ = minZ + houseD * 0.25;
            }} else if (roofType.toLowerCase().includes('cuatro')) {{
                // 4 aguas: apex en centro. Panel al 18% desde sur.
                // Fracción de descenso desde apex = (0.5-0.18)/0.5 = 0.64 → altura = rH*(1-0.64)
                panelBaseY = WALL_H + rH * 0.36 + 0.12;
                panelBaseZ = minZ + houseD * 0.18;
            }} else {{
                // Dos aguas (default). Cumbrera en centro X.
                // Panel al 15% desde sur → altura = rH*(0.15/0.5) = rH*0.3
                panelBaseY = WALL_H + rH * 0.3 + 0.12;
                panelBaseZ = minZ + houseD * 0.15;
            }}

            const totalPanelW = cols * (PANEL_W + PANEL_GAP) - PANEL_GAP;
            const startX = houseCX - totalPanelW / 2;

            for (let row = 0; row < rows; row++) {{
                for (let col = 0; col < cols; col++) {{
                    if (row * cols + col >= numPanels) break;
                    const panel = BABYLON.MeshBuilder.CreateBox(
                        `solar_${{row}}_${{col}}`,
                        {{width: PANEL_W, height: PANEL_H, depth: PANEL_D}},
                        scene
                    );
                    panel.position.set(
                        startX + col * (PANEL_W + PANEL_GAP) + PANEL_W / 2,
                        panelBaseY + row * (PANEL_D * Math.cos(INCLINATION) + PANEL_GAP),
                        panelBaseZ + row * (PANEL_D * Math.sin(INCLINATION))
                    );
                    panel.rotation.x = -INCLINATION;  // inclinación sur 30°
                    panel.material = panMat;
                    panel.isPickable = false;
                    solarMeshes.push(panel);
                }}
            }}

            showToast(`☀️ ${{numPanels}} paneles solares — orientación Sur, 30°`);
        }}

        // ================================================
        // CAPTURA DE VISTAS 3D — 5 perspectivas
        // ================================================
        const capturedViews = {{}};

        function captureFromAngle(name, alpha, beta, radius, callback) {{
            const prevAlpha = camera.alpha;
            const prevBeta  = camera.beta;
            const prevRadius = camera.radius;

            camera.alpha  = alpha;
            camera.beta   = beta;
            camera.radius = radius;

            // Render a continuación; capturamos en el evento afterRender del motor
            scene.render();
            const once = () => {{
                scene.unregisterAfterRender(once);
                const canvas = engine.getRenderingCanvas();
                canvas.toBlob((blob) => {{
                    const reader = new FileReader();
                    reader.onloadend = () => {{
                        capturedViews[name] = reader.result;
                        camera.alpha  = prevAlpha;
                        camera.beta   = prevBeta;
                        camera.radius = prevRadius;
                        callback();
                    }};
                    reader.readAsDataURL(blob);
                }}, 'image/png');
            }};
            scene.registerAfterRender(once);
        }}

        // ZIP nativo sin dependencias externas
        // Versión simplificada para generar ZIP de imágenes PNG base64
        function crearZipImagenes(archivos, nombreZip) {{
            function b64ToBytes(b64) {{
                const bin = atob(b64);
                const out = new Uint8Array(bin.length);
                for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
                return out;
            }}
            function strToBytes(s) {{
                const out = new Uint8Array(s.length);
                for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i) & 0xff;
                return out;
            }}
            function u32(n) {{ return [n&0xff,(n>>8)&0xff,(n>>16)&0xff,(n>>24)&0xff]; }}
            function u16(n) {{ return [n&0xff,(n>>8)&0xff]; }}
            function concat(...arr) {{
                const tot = arr.reduce((s,a)=>s+a.length,0);
                const out = new Uint8Array(tot); let off=0;
                for (const a of arr) {{ out.set(a,off); off+=a.length; }}
                return out;
            }}
            function crc32(data) {{
                let c=0xFFFFFFFF, t=[];
                for(let i=0;i<256;i++){{let x=i;for(let j=0;j<8;j++)x=(x&1)?(0xEDB88320^(x>>>1)):(x>>>1);t[i]=x;}}
                for(let i=0;i<data.length;i++) c=t[(c^data[i])&0xff]^(c>>>8);
                return (c^0xFFFFFFFF)>>>0;
            }}
            const locals=[]; const central=[]; let offset=0;
            for (const [nombre, contenido, esBase64] of archivos) {{
                const nb = strToBytes(nombre);
                const data = esBase64 ? b64ToBytes(contenido) : strToBytes(contenido);
                const crc = crc32(data); const sz = data.length;
                const lh = new Uint8Array([
                    0x50,0x4B,0x03,0x04,0x14,0x00,0x00,0x00,0x00,0x00,
                    0x00,0x00,0x00,0x00,
                    ...u32(crc),...u32(sz),...u32(sz),
                    ...u16(nb.length),0x00,0x00,...nb
                ]);
                locals.push(concat(lh,data));
                const cd = new Uint8Array([
                    0x50,0x4B,0x01,0x02,0x3F,0x00,0x14,0x00,
                    0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
                    ...u32(crc),...u32(sz),...u32(sz),
                    ...u16(nb.length),
                    // extra len (2), comment len (2), disk start (2), internal attr (2), external attr (4)
                    0x00,0x00,  // extra
                    0x00,0x00,  // comment
                    0x00,0x00,  // disk start
                    0x00,0x00,  // internal attr
                    0x00,0x00,0x00,0x00, // external attr
                    ...u32(offset),...nb
                ]);
                central.push(cd);
                offset += lh.length + data.length;
            }}
            const cdb=concat(...central);
            const eocd=new Uint8Array([
                0x50,0x4B,0x05,0x06,0x00,0x00,0x00,0x00,
                ...u16(archivos.length),...u16(archivos.length),
                ...u32(cdb.length),...u32(offset),0x00,0x00
            ]);
            const blob=new Blob([concat(...locals,cdb,eocd)],{{type:'application/zip'}});
            const url=URL.createObjectURL(blob);
            const a=document.createElement('a');
            a.href=url; a.download=nombreZip;
            document.body.appendChild(a); a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }}
        function captureAllViews() {{
            showToast('📸 Capturando 5 vistas... espera');
            document.getElementById('btn-capture').disabled = true;

            const cx = totalWidth / 2;
            const cz = totalDepth / 2;
            camera.target = new BABYLON.Vector3(cx, 0, cz);
            const r = Math.max(totalWidth, totalDepth) * 2.2;

            const views = [
                {{ name: 'sur_fachada_principal', alpha: Math.PI,      beta: Math.PI/3.5 }},
                {{ name: 'norte',                 alpha: 0,            beta: Math.PI/3.5 }},
                {{ name: 'este',                  alpha: Math.PI/2,    beta: Math.PI/3.5 }},
                {{ name: 'oeste',                 alpha: -Math.PI/2,   beta: Math.PI/3.5 }},
                {{ name: 'planta_cenital',         alpha: Math.PI/4,   beta: 0.15 }},
            ];

            let idx = 0;
            function next() {{
                if (idx >= views.length) {{
                    // Todas capturadas — generar ZIP y descargar directamente
                    const nombres = {{
                        'sur_fachada_principal': 'Vistas_3D/01_Fachada_Principal_Sur.png',
                        'norte':                 'Vistas_3D/02_Vista_Norte.png',
                        'este':                  'Vistas_3D/03_Vista_Este.png',
                        'oeste':                 'Vistas_3D/04_Vista_Oeste.png',
                        'planta_cenital':        'Vistas_3D/05_Planta_Cenital.png',
                    }};
                    const total = Object.keys(capturedViews).length;
                    if (total === 0) {{
                        showToast('⚠️ No hay capturas generadas');
                        document.getElementById('btn-capture').disabled = false;
                        return;
                    }}
                    const archivos = [];
                    for (const [key, dataUrl] of Object.entries(capturedViews)) {{
                        const base64 = dataUrl.split(',')[1];
                        const filename = nombres[key] || 'Vistas_3D/' + key + '.png';
                        archivos.push([filename, base64, true]);
                    }}
                    archivos.push(['Vistas_3D/INSTRUCCIONES.txt',
                        'VISTAS 3D ArchiRapid MVP - 5 perspectivas: 01 Fachada Sur, 02 Norte, 03 Este, 04 Oeste, 05 Cenital. Adjuntalas al arquitecto. ArchiRapid MVP www.archirapid.es',
                        false
                    ]);
                    crearZipImagenes(archivos, 'Vistas_3D_ArchiRapid.zip');
                    document.getElementById('capture-status').style.display = 'block';
                    document.getElementById('btn-capture').disabled = false;
                    showToast('✅ ZIP con ' + total + ' vistas descargado — súbelo en Streamlit');
                    // Mostrar miniaturas en el toolbar
                    const thumbGrid = document.getElementById('thumb-grid');
                    thumbGrid.innerHTML = '';
                    const viewLabels = {{
                        'sur_fachada_principal': 'Sur',
                        'norte': 'Norte',
                        'este': 'Este',
                        'oeste': 'Oeste',
                        'planta_cenital': 'Planta'
                    }};
                    for (const [key, dataUrl] of Object.entries(capturedViews)) {{
                        const wrap = document.createElement('div');
                        wrap.style.cssText = 'text-align:center;';
                        const img = document.createElement('img');
                        img.src = dataUrl;
                        img.style.cssText = 'width:38px;height:38px;object-fit:cover;border-radius:4px;border:1px solid #9B59B6;cursor:pointer;';
                        img.title = viewLabels[key] || key;
                        const lbl = document.createElement('div');
                        lbl.textContent = viewLabels[key] || key;
                        lbl.style.cssText = 'font-size:9px;color:#9B59B6;';
                        wrap.appendChild(img);
                        wrap.appendChild(lbl);
                        thumbGrid.appendChild(wrap);
                    }}
                    document.getElementById('capture-thumbs').style.display = 'block';
                    return;
                }}
                const v = views[idx++];
                captureFromAngle(v.name, v.alpha, v.beta, r, next);
            }}
            next();
        }}

        // ================================================
        // ESTILOS DE FACHADA — cambio en tiempo real
        // ================================================
        const STYLE_COLORS = {{
            'Moderno':       [0.92, 0.92, 0.90],
            'Contemporáneo': [0.90, 0.90, 0.88],
            'Rural':         [0.75, 0.68, 0.55],
            'Montaña':       [0.62, 0.55, 0.45],
            'Ecológico':     [0.80, 0.72, 0.58],
            'Andaluz':       [0.96, 0.94, 0.88],
            'Clásico':       [0.93, 0.90, 0.83],
            'Playa':         [0.94, 0.91, 0.82],
        }};

        function applyStyle(styleName) {{
            _currentStyle = styleName;   // anclar: rebuildScene lo usará
            const c = STYLE_COLORS[styleName] || [0.92, 0.92, 0.90];
            const newColor = new BABYLON.Color3(c[0], c[1], c[2]);
            // Recorrer todos los materiales de pared existentes en la escena
            roomsData.forEach((room, i) => {{
                const zone = (room.zone || '').toLowerCase();
                if (zone === 'garden' || zone === 'exterior') return;
                const wMat = scene.getMaterialByName(`wMat_${{i}}`);
                if (wMat) wMat.diffuseColor = newColor;
            }});
            document.getElementById('style-applied').textContent = '✅ ' + styleName + ' aplicado';
            showToast('🎨 Estilo ' + styleName + ' aplicado');
            // Actualizar extras 3D (chimenea, piscina, árboles...) con el estilo recién elegido
            buildStyleExtras(styleName);
        }}

        function applyStyleUI(styleName) {{
            // Resaltar botón activo y desmarcar el resto
            const styleNames = ['Moderno','Rural','Andaluz','Montaña','Playa','Ecológico'];
            styleNames.forEach(s => {{
                const btn = document.getElementById('style-btn-' + s);
                if (btn) {{
                    btn.style.outline = '';
                    btn.style.fontWeight = 'normal';
                    btn.style.opacity = '0.85';
                }}
            }});
            const active = document.getElementById('style-btn-' + styleName);
            if (active) {{
                active.style.outline = '2px solid #C39BD3';
                active.style.fontWeight = 'bold';
                active.style.opacity = '1';
            }}
            applyStyle(styleName);
        }}

        function toggleStylePanel() {{
            const panel = document.getElementById('style-panel');
            const isVisible = panel.style.display !== 'none';
            panel.style.display = isVisible ? 'none' : 'block';
            document.getElementById('btn-style').classList.toggle('active', !isVisible);
        }}

        // ================================================
        // CIMIENTOS 3D
        // ================================================
        const foundationType = "{foundation_type}";
        let foundMeshes = [];
        let foundActive = false;

        function buildFoundation() {{
            // Limpiar previo
            foundMeshes.forEach(m => {{ m.material && m.material.dispose(); m.dispose(); }});
            foundMeshes = [];

            // FIX #3: detección robusta de pilotes (variantes en español)
            const ft = foundationType.toLowerCase();
            let type = 'losa';
            if (ft.includes('zapata')) type = 'zapatas';
            else if (ft.includes('pilote') || ft.includes('micropilote') ||
                     ft.startsWith('pil') || ft.includes('pilotaje')) type = 'pilotes';
            else if (ft.includes('losa') || ft.includes('placa')) type = 'losa';

            // Material hormigón
            const mat = new BABYLON.StandardMaterial('foundMat', scene);
            if (type === 'zapatas') {{
                mat.diffuseColor = new BABYLON.Color3(0.60, 0.58, 0.55);
            }} else if (type === 'pilotes') {{
                mat.diffuseColor = new BABYLON.Color3(0.40, 0.38, 0.36);
            }} else {{
                mat.diffuseColor = new BABYLON.Color3(0.70, 0.68, 0.65);
            }}

            if (type === 'losa') {{
                // Placa continua bajo toda la casa
                const houseRooms = roomsData.filter(r => {{
                    const z = (r.zone||'').toLowerCase();
                    return z !== 'garden' && z !== 'exterior';
                }});
                if (houseRooms.length === 0) return;
                const minX = Math.min(...houseRooms.map(r => r.x));
                const maxX = Math.max(...houseRooms.map(r => r.x + r.width));
                const minZ = Math.min(...houseRooms.map(r => r.z));
                const maxZ = Math.max(...houseRooms.map(r => r.z + r.depth));
                const losa = BABYLON.MeshBuilder.CreateBox('found_losa', {{
                    width: maxX - minX + 0.3,
                    height: 0.60,
                    depth: maxZ - minZ + 0.3
                }}, scene);
                losa.position.set((minX + maxX) / 2, -0.30, (minZ + maxZ) / 2);
                losa.material = mat;
                losa.isPickable = false;
                foundMeshes.push(losa);

            }} else if (type === 'zapatas') {{
                // Bloque bajo cada habitación habitable
                roomsData.forEach((room, i) => {{
                    const z = (room.zone||'').toLowerCase();
                    if (z === 'garden' || z === 'exterior') return;
                    const zap = BABYLON.MeshBuilder.CreateBox(`found_zap_${{i}}`, {{
                        width: room.width - 0.2,
                        height: 1.20,
                        depth: room.depth - 0.2
                    }}, scene);
                    zap.position.set(room.x + room.width/2, -0.60, room.z + room.depth/2);
                    zap.material = mat;
                    zap.isPickable = false;
                    foundMeshes.push(zap);
                }});

            }} else if (type === 'pilotes') {{
                // Cilindros en esquinas de cada habitación habitable
                roomsData.forEach((room, i) => {{
                    const z = (room.zone||'').toLowerCase();
                    if (z === 'garden' || z === 'exterior') return;
                    const corners = [
                        [room.x + 0.3, room.z + 0.3],
                        [room.x + room.width - 0.3, room.z + 0.3],
                        [room.x + 0.3, room.z + room.depth - 0.3],
                        [room.x + room.width - 0.3, room.z + room.depth - 0.3]
                    ];
                    corners.forEach((c, j) => {{
                        const pil = BABYLON.MeshBuilder.CreateCylinder(`found_pil_${{i}}_${{j}}`, {{
                            diameter: 0.50,
                            height: 2.50,
                            tessellation: 12
                        }}, scene);
                        pil.position.set(c[0], -1.25, c[1]);
                        pil.material = mat;
                        pil.isPickable = false;
                        foundMeshes.push(pil);
                    }});
                }});
            }}
        }}

        function toggleFoundation() {{
            const btn = document.getElementById('btn-found');
            const panel = document.getElementById('found-panel');
            if (foundActive) {{
                foundMeshes.forEach(m => {{ m.material && m.material.dispose(); m.dispose(); }});
                foundMeshes = [];
                foundActive = false;
                btn.textContent = '🏗️ Cimientos OFF';
                btn.classList.remove('active');
                panel.style.display = 'none';
                showToast('Cimientos ocultados');
            }} else {{
                buildFoundation();
                foundActive = true;
                btn.textContent = '🏗️ Cimientos ON';
                btn.classList.add('active');
                panel.style.display = 'block';
                // Mostrar tipo en panel
                document.getElementById('found-type-label').textContent =
                    foundationType.split('(')[0].trim();
                showToast('Cimientos: ' + foundationType.split('(')[0].trim());
            }}
        }}                                                                                                                              
        // ================================================
        // RENDER LOOP
        // ================================================
        engine.runRenderLoop(() => scene.render());
        window.addEventListener('resize', () => engine.resize());

        // ================================================
        // BRÚJULA — N siempre arriba, fija
        // ================================================
        (function() {{
            const canvas = document.getElementById('compass-canvas');
            if (!canvas) return;
            const ctx = canvas.getContext('2d');
            // Fondo círculo
            ctx.beginPath();
            ctx.arc(35, 35, 32, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(0,0,0,0.5)';
            ctx.fill();
            ctx.strokeStyle = 'rgba(255,215,0,0.5)';
            ctx.lineWidth = 1.5;
            ctx.stroke();
            // Letras N S E O
            ctx.fillStyle = '#FFD700';
            ctx.font = 'bold 9px Arial';
            ctx.textAlign = 'center';
            ctx.fillText('N', 35, 12);
            ctx.fillText('S', 35, 62);
            ctx.fillText('E', 62, 38);
            ctx.fillText('O', 10, 38);
            // Aguja Norte (rojo) apunta arriba
            const rad = (180 - 90) * Math.PI / 180;
            ctx.beginPath();
            ctx.moveTo(35, 35);
            ctx.lineTo(35 + 22 * Math.cos(rad), 35 + 22 * Math.sin(rad));
            ctx.strokeStyle = '#E74C3C';
            ctx.lineWidth = 2.5;
            ctx.stroke();
            // Aguja Sur (blanco)
            ctx.beginPath();
            ctx.moveTo(35, 35);
            ctx.lineTo(35 - 16 * Math.cos(rad), 35 - 16 * Math.sin(rad));
            ctx.strokeStyle = 'white';
            ctx.lineWidth = 2;
            ctx.stroke();
            // Centro
            ctx.beginPath();
            ctx.arc(35, 35, 3, 0, Math.PI * 2);
            ctx.fillStyle = '#FFD700';
            ctx.fill();
        }})();

        // ================================================
        // INICIALIZACIÓN — construir escena al cargar
        // ================================================
        // FIX #2: use Python-computed coordinates when available; only generate from scratch if missing
        const hasLayout = roomsData.length > 0 && typeof roomsData[0].x !== 'undefined'
                          && typeof roomsData[0].width !== 'undefined';
        const initialLayout = hasLayout ? roomsData : generateLayoutJS(roomsData);
        rebuildScene(initialLayout);
        // Aplicar automáticamente el estilo elegido en el Paso 1
        applyStyleUI(houseStyle);

        // FIX #5: slider range calculado desde bounding box real de la casa
        (function initPlotSliders() {{
            const houseRoomsS = roomsData.filter(r => (r.zone||'').toLowerCase() !== 'garden');
            const hMinX = houseRoomsS.length ? Math.min(...houseRoomsS.map(r => r.x)) : 0;
            const hMaxX = houseRoomsS.length ? Math.max(...houseRoomsS.map(r => r.x + r.width)) : totalWidth;
            const hMinZ = houseRoomsS.length ? Math.min(...houseRoomsS.map(r => r.z)) : 0;
            const hMaxZ = houseRoomsS.length ? Math.max(...houseRoomsS.map(r => r.z + r.depth)) : totalDepth;
            const hW = hMaxX - hMinX;
            const hD = hMaxZ - hMinZ;
            // Espacio disponible = plot - huella casa - 2*retranqueo (ambos lados)
            const availX = Math.max(0, plotW - hW - 2 * RETRANQUEO);
            const availZ = Math.max(0, plotD - hD - 2 * RETRANQUEO);
            const slX = document.getElementById('slider-offset-x');
            const slZ = document.getElementById('slider-offset-z');
            if (slX) {{
                slX.min   = '0';
                slX.max   = availX.toFixed(1);
                slX.value = '0';
                slX.disabled = availX <= 0;
            }}
            if (slZ) {{
                slZ.min   = '0';
                slZ.max   = availZ.toFixed(1);
                slZ.value = '0';
                slZ.disabled = availZ <= 0;
            }}
            // Guardar posiciones base al inicio
            _basePosData = roomsData.map(r => ({{ x: r.x, z: r.z }}));
        }})();

        setMode('select');
        console.log('ArchiRapid Editor 3D v3.0 —', roomsData.length, 'habitaciones cargadas');

        function toggleToolbar() {{
            const tb = document.getElementById('toolbar');
            const btn = document.getElementById('toggle-toolbar');
            tb.classList.toggle('collapsed');
            btn.textContent = tb.classList.contains('collapsed') ? '▶' : '◀';
        }}

    </script>
</body>
</html>"""

    return html