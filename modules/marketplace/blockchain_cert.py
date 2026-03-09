# modules/marketplace/blockchain_cert.py
"""
Certificación criptográfica de documentos ArchiRapid
────────────────────────────────────────────────────
Fase 1 (activa):  SHA-256 del ZIP → almacenado en DB + badge visual
Fase 2 (opcional): registrar el hash en Polygon PoS via BLOCKCHAIN_PRIVATE_KEY
                  (sin dependencias extra — usa requests + eth_account si disponible)

No rompe nada: se llama DESPUÉS de generar el ZIP, no modifica la generación.
"""
import hashlib
import datetime
import sqlite3
import os

try:
    import streamlit as st
    _STREAMLIT = True
except ImportError:
    _STREAMLIT = False


# ── DB: tabla de certificados ──────────────────────────────────────────────────

def _ensure_table(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS document_certs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_hash    TEXT NOT NULL,
            doc_name    TEXT,
            user_email  TEXT,
            plot_id     TEXT,
            certified_at TEXT NOT NULL,
            polygon_tx  TEXT DEFAULT NULL,
            polygon_net TEXT DEFAULT NULL
        )
    """)
    conn.commit()


# ── Fase 1: hash + DB ─────────────────────────────────────────────────────────

def certify(zip_bytes: bytes, doc_name: str = "", user_email: str = "", plot_id: str = "") -> dict:
    """
    Certifica un ZIP:
      - Calcula SHA-256
      - Guarda en DB
      - (Opcional) registra en Polygon si hay BLOCKCHAIN_PRIVATE_KEY
    Devuelve dict con: hash, certified_at, cert_id, polygon_tx, polygon_net
    """
    doc_hash = hashlib.sha256(zip_bytes).hexdigest()
    now = datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"

    # Guardar en DB
    cert_id = None
    try:
        from modules.marketplace.utils import DB_PATH
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        _ensure_table(conn)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO document_certs (doc_hash, doc_name, user_email, plot_id, certified_at) VALUES (?,?,?,?,?)",
            (doc_hash, doc_name, user_email, plot_id, now)
        )
        conn.commit()
        cert_id = cur.lastrowid
        conn.close()
    except Exception:
        pass

    result = {
        "hash": doc_hash,
        "certified_at": now,
        "cert_id": cert_id,
        "polygon_tx": None,
        "polygon_net": None,
    }

    # Fase 2 (opcional): Polygon PoS — solo si hay clave configurada
    _polygon_key = _get_secret("BLOCKCHAIN_PRIVATE_KEY")
    if _polygon_key:
        tx = _register_on_polygon(doc_hash, _polygon_key)
        if tx:
            result["polygon_tx"] = tx["hash"]
            result["polygon_net"] = tx["net"]
            # Actualizar DB con tx
            try:
                from modules.marketplace.utils import DB_PATH
                conn2 = sqlite3.connect(str(DB_PATH), timeout=10)
                conn2.execute(
                    "UPDATE document_certs SET polygon_tx=?, polygon_net=? WHERE id=?",
                    (tx["hash"], tx["net"], cert_id)
                )
                conn2.commit()
                conn2.close()
            except Exception:
                pass

    return result


# ── Fase 2: registrar hash en Polygon ────────────────────────────────────────
# Usa eth_account (sub-dependencia ligera) si está instalado.
# Sin él, esta fase queda silenciosamente desactivada.

def _register_on_polygon(doc_hash: str, private_key: str) -> dict | None:
    """Envía una TX 0-valor a Polygon con el hash como data. Sin smart contract."""
    try:
        from eth_account import Account
        from eth_account.signers.local import LocalAccount
        import requests as _req, json as _json

        _use_testnet = _get_secret("BLOCKCHAIN_TESTNET", "true").lower() != "false"
        if _use_testnet:
            rpc_url = "https://rpc-mumbai.maticvigil.com"
            chain_id = 80001
            net_name = "polygon-mumbai"
            explorer = "https://mumbai.polygonscan.com/tx/"
        else:
            rpc_url = "https://polygon-rpc.com"
            chain_id = 137
            net_name = "polygon-mainnet"
            explorer = "https://polygonscan.com/tx/"

        account: LocalAccount = Account.from_key(private_key)
        address = account.address

        # Obtener nonce
        nonce_resp = _req.post(rpc_url, json={
            "jsonrpc": "2.0", "method": "eth_getTransactionCount",
            "params": [address, "latest"], "id": 1
        }, timeout=10)
        nonce = int(nonce_resp.json()["result"], 16)

        # Gas price
        gp_resp = _req.post(rpc_url, json={
            "jsonrpc": "2.0", "method": "eth_gasPrice", "params": [], "id": 2
        }, timeout=10)
        gas_price = int(gp_resp.json()["result"], 16)

        # Construir TX: 0 MATIC, data = "archirapid:" + hash
        data_hex = "0x" + ("archirapid:" + doc_hash).encode().hex()

        tx = {
            "to":       address,  # self-send, economiza gas
            "value":    0,
            "gas":      30000,
            "gasPrice": gas_price,
            "nonce":    nonce,
            "chainId":  chain_id,
            "data":     data_hex,
        }
        signed = account.sign_transaction(tx)
        raw_tx = "0x" + signed.rawTransaction.hex()

        send_resp = _req.post(rpc_url, json={
            "jsonrpc": "2.0", "method": "eth_sendRawTransaction",
            "params": [raw_tx], "id": 3
        }, timeout=15)
        tx_hash = send_resp.json().get("result")

        if tx_hash and tx_hash.startswith("0x"):
            return {"hash": tx_hash, "net": net_name, "explorer": explorer + tx_hash}

    except ImportError:
        pass  # eth_account no instalado — Fase 2 desactivada silenciosamente
    except Exception:
        pass
    return None


def _get_secret(key: str, default: str = "") -> str:
    if _STREAMLIT:
        try:
            v = st.secrets.get(key, "")
            if v:
                return str(v).strip()
        except Exception:
            pass
    return os.getenv(key, default).strip()


# ── Badge HTML para mostrar en Streamlit ──────────────────────────────────────

def cert_badge_html(cert: dict) -> str:
    """Devuelve HTML con el sello de certificación para st.markdown(unsafe_allow_html=True)."""
    short_hash = cert["hash"][:16] + "…" + cert["hash"][-8:]
    ts = cert["certified_at"].replace("T", " ").replace("Z", " UTC")

    if cert.get("polygon_tx"):
        net = cert["polygon_net"] or "polygon"
        tx = cert["polygon_tx"]
        explorer_base = "https://mumbai.polygonscan.com/tx/" if "mumbai" in net else "https://polygonscan.com/tx/"
        chain_badge = f'<a href="{explorer_base}{tx}" target="_blank" style="color:#8B5CF6;font-size:11px;">ver en Polygon ↗</a>'
        border_color = "#8B5CF6"
        icon = "⛓️"
        label = "Certificado Blockchain (Polygon)"
    else:
        chain_badge = '<span style="color:#64748B;font-size:11px;">on-chain pendiente de configuración</span>'
        border_color = "#10B981"
        icon = "🔐"
        label = "Certificación Criptográfica"

    return f"""
<div style="background:rgba(16,185,129,0.07);border:1px solid {border_color};
            border-radius:10px;padding:12px 16px;margin:12px 0;
            font-family:-apple-system,sans-serif;">
  <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
    <span style="font-size:1.4em;">{icon}</span>
    <div>
      <div style="font-weight:700;color:#F8FAFC;font-size:13px;">{label}</div>
      <div style="color:#94A3B8;font-size:11px;margin-top:2px;">
        SHA-256: <code style="color:#10B981;font-size:11px;">{short_hash}</code>
        &nbsp;·&nbsp; {ts}
      </div>
      <div style="margin-top:4px;">{chain_badge}</div>
    </div>
    <div style="margin-left:auto;">
      <span style="background:rgba(16,185,129,0.15);border:1px solid #10B981;
                   border-radius:6px;padding:3px 10px;color:#10B981;font-size:11px;font-weight:600;">
        ✓ Verificable
      </span>
    </div>
  </div>
</div>
"""
