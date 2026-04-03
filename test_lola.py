"""
TEST: Verificar que <input> funciona dentro de iframe Streamlit
Ejecutar: streamlit run test_lola.py
Esperado: boton abajo-derecha, click abre panel, escribir y enviar funciona
"""
import streamlit as st

st.set_page_config(page_title="Test Lola iframe", layout="wide")
st.title("Test Lola - Input en iframe")
st.write("Si ves el boton abajo-derecha, puedes abrir el chat, escribir y enviar, el test pasa.")

test_html = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { width: 100%; height: 100%; background: transparent; overflow: hidden;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
#btn {
    position: absolute; bottom: 0; right: 0;
    padding: 12px 20px; background: #2563EB; color: white;
    border: none; border-radius: 25px; cursor: pointer;
    font-size: 15px; font-weight: 700;
    box-shadow: 0 4px 24px rgba(37,99,235,0.55);
}
#panel {
    display: none; position: absolute; top: 0; left: 0;
    width: 100%; height: 100%;
    background: #1E293B; border-radius: 16px;
    border: 1px solid rgba(245,158,11,.3);
    flex-direction: column; overflow: hidden;
}
#panel.open { display: flex; }
.header { padding: 14px; background: #0D2A4A; color: white; font-weight: 700; flex-shrink: 0; }
.header button { float: right; background: none; border: none; color: #94A3B8; cursor: pointer; font-size: 18px; }
.msgs { flex: 1; padding: 14px; overflow-y: auto; }
.msgs .msg { background: rgba(30,58,95,.85); color: #E2E8F0; padding: 10px 13px; border-radius: 12px; margin-bottom: 8px; font-size: 13px; }
.input-area { padding: 10px; display: flex; gap: 8px; background: rgba(0,0,0,.2); flex-shrink: 0; }
.input-area input {
    flex: 1; background: rgba(255,255,255,.08); border: 1px solid rgba(255,255,255,.15);
    color: white; border-radius: 20px; padding: 10px 14px; font-size: 13px;
}
.input-area input:focus { outline: none; border-color: #2563EB; background: rgba(255,255,255,.12); }
.input-area input::placeholder { color: #64748B; }
.input-area button { background: #2563EB; border: none; color: white; width: 36px; height: 36px; border-radius: 50%; cursor: pointer; font-size: 16px; }
</style>
</head>
<body>
<button id="btn" onclick="toggle()">&#x1F4AC; Test Lola &#x1F7E2;</button>
<div id="panel">
    <div class="header">Test Chat <button onclick="toggle()">&#x2715;</button></div>
    <div class="msgs" id="msgs"><div class="msg">Test OK. Escribe algo y pulsa enviar o Enter.</div></div>
    <div class="input-area">
        <input type="text" id="inp" placeholder="Escribe aqui..." autocomplete="off" />
        <button onclick="send()">&#x2934;</button>
    </div>
</div>
<script>
console.log('[TestLola] Script ejecutando...');

// AUTO-POSICIONAR iframe desde dentro
(function() {
    try {
        var me = window.frameElement;
        if (!me) { console.log('[TestLola] No frameElement - no en iframe'); return; }

        // Posicionar el iframe fixed
        me.style.position = 'fixed';
        me.style.bottom = '20px';
        me.style.right = '20px';
        me.style.width = '160px';
        me.style.height = '55px';
        me.style.zIndex = '2147483647';
        me.style.border = 'none';
        me.style.background = 'transparent';

        // Desbloquear overflow en ancestros
        var p = me.parentElement;
        if (p) { p.style.overflow = 'visible'; p.style.height = 'auto'; }
        if (p && p.parentElement) { p.parentElement.style.overflow = 'visible'; }

        console.log('[TestLola] iframe posicionado OK');
    } catch(e) { console.warn('[TestLola] Error posicionando:', e); }
})();

function toggle() {
    var panel = document.getElementById('panel');
    var btn = document.getElementById('btn');
    var isOpen = !panel.classList.contains('open');
    panel.classList.toggle('open');
    btn.style.display = isOpen ? 'none' : 'block';

    try {
        var me = window.frameElement;
        if (me) {
            me.style.width = isOpen ? '350px' : '160px';
            me.style.height = isOpen ? '500px' : '55px';
        }
    } catch(e) {}

    if (isOpen) {
        setTimeout(function() { document.getElementById('inp').focus(); }, 200);
    }
    console.log('[TestLola] toggle:', isOpen ? 'ABIERTO' : 'CERRADO');
}

function send() {
    var inp = document.getElementById('inp');
    var text = (inp.value || '').trim();
    if (!text) return;

    var div = document.createElement('div');
    div.className = 'msg';
    div.style.background = 'linear-gradient(135deg, #2563EB, #1D4ED8)';
    div.style.color = 'white';
    div.textContent = text;
    document.getElementById('msgs').appendChild(div);
    inp.value = '';

    setTimeout(function() {
        var r = document.createElement('div');
        r.className = 'msg';
        r.textContent = 'Recibido: "' + text + '". Input FUNCIONA!';
        document.getElementById('msgs').appendChild(r);
        document.getElementById('msgs').scrollTop = document.getElementById('msgs').scrollHeight;
    }, 300);

    inp.focus();
    console.log('[TestLola] mensaje enviado:', text);
}

document.getElementById('inp').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') { e.preventDefault(); send(); }
});

console.log('[TestLola] listeners registrados OK');
</script>
</body>
</html>
"""

st.components.v1.html(test_html, height=55, scrolling=False)
