# modules/marketplace/privacidad.py
"""
Política de Privacidad — ArchiRapid
Ruta pública: ?page=privacidad
"""
import streamlit as st


def render():
    st.markdown("""
<div style="max-width:800px;margin:0 auto;padding:0 8px;">
""", unsafe_allow_html=True)

    st.markdown("# Política de Privacidad")
    st.markdown("*Última actualización: marzo de 2026*")
    st.markdown("---")

    st.markdown("""
**ARCHIRAPID** (en adelante, "ArchiRapid", "nosotros" o "la plataforma") trata tus datos
personales con total respeto a tu privacidad y en cumplimiento del
**Reglamento General de Protección de Datos (RGPD) UE 2016/679** y la
**Ley Orgánica 3/2018 (LOPDGDD)**.

---

## 1. Responsable del tratamiento

| | |
|---|---|
| **Nombre** | ArchiRapid |
| **Email de contacto** | hola@archirapid.com |
| **Dominio** | archirapid.com |

---

## 2. Datos que recogemos

Recogemos únicamente los datos que tú nos proporcionas al usar la plataforma:

- **Datos de registro:** nombre, email, contraseña (almacenada cifrada, nunca en texto plano).
- **Datos de perfil:** provincia, teléfono, empresa (solo constructores/profesionales).
- **Datos de uso:** proyectos diseñados, ofertas enviadas, fincas consultadas.
- **Datos de contacto:** mensajes enviados a través del asistente virtual o formularios.

No recogemos datos de menores de 14 años. No vendemos ni cedemos tus datos a terceros.

---

## 3. Finalidad del tratamiento

| Finalidad | Base legal |
|---|---|
| Gestionar tu cuenta y acceso | Ejecución de contrato (Art. 6.1.b RGPD) |
| Enviarte notificaciones de proyectos o alertas | Consentimiento (Art. 6.1.a RGPD) |
| Comunicaciones de servicio (emails transaccionales) | Interés legítimo (Art. 6.1.f RGPD) |
| Cumplimiento legal | Obligación legal (Art. 6.1.c RGPD) |

---

## 4. Conservación de datos

Tus datos se conservan mientras mantengas una cuenta activa en ArchiRapid.
Puedes solicitar la eliminación en cualquier momento escribiendo a **hola@archirapid.com**.
Tras la solicitud, eliminamos tus datos en un plazo máximo de 30 días.

---

## 5. Tus derechos

Tienes derecho a:

- **Acceder** a los datos que tenemos sobre ti.
- **Rectificarlos** si son incorrectos.
- **Suprimirlos** ("derecho al olvido").
- **Oponerte** al tratamiento o **limitarlo**.
- **Portabilidad**: recibir tus datos en formato estructurado.

Para ejercer cualquiera de estos derechos, escribe a **hola@archirapid.com**
indicando tu nombre, email y el derecho que deseas ejercer.
Responderemos en un plazo máximo de **30 días**.

Si consideras que el tratamiento no es conforme al RGPD, puedes presentar
una reclamación ante la **Agencia Española de Protección de Datos (AEPD)**
en [aepd.es](https://www.aepd.es).

---

## 6. Seguridad

ArchiRapid implementa medidas técnicas y organizativas adecuadas para proteger
tus datos: contraseñas cifradas con hash seguro (bcrypt), conexiones HTTPS,
acceso restringido a bases de datos.

---

## 7. Cookies

La plataforma utiliza únicamente cookies de sesión estrictamente necesarias
para el funcionamiento del servicio (Streamlit). No utilizamos cookies de
rastreo ni publicidad de terceros.

---

## 8. Servicios de terceros

ArchiRapid utiliza los siguientes servicios externos:

| Servicio | Finalidad | Política |
|---|---|---|
| **Resend** | Envío de emails transaccionales | resend.com/privacy |
| **Streamlit Cloud** | Alojamiento de la aplicación | streamlit.io/privacy |
| **Google Gemini API** | Análisis de imágenes con IA | ai.google.dev |
| **Groq API** | Asistente de IA conversacional | groq.com/privacy |

---

## 9. Cambios en esta política

Nos reservamos el derecho de actualizar esta política. Te notificaremos
por email si los cambios son significativos.

---

*Para cualquier consulta: **hola@archirapid.com***
""")

    st.markdown("---")
    if st.button("← Volver al inicio", use_container_width=False):
        st.query_params["page"] = "home"
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)
