import streamlit as st
import json
import os
import subprocess
import time
import io
from datetime import datetime
import unicodedata
import random
import base64
import streamlit.components.v1 as components
import firebase_admin
from firebase_admin import credentials, firestore
import google.generativeai as genai
from fpdf import FPDF
import markdown
import re
import pandas as pd

# --- Configurar Firebase ---
@st.cache_resource
def get_db():
    if not firebase_admin._apps:
        try:
            cred_info = st.secrets["firebase"]["info"]
            cred_dict = json.loads(cred_info)
            
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
        except Exception as e:
            st.error(f"Error al inicializar Firebase: {e}")
            return None
    return firestore.client()

db = get_db()

def reproducir_sonido(file_path):
    try:
        with open(file_path, "rb") as f:
            data = f.read()
            b64 = base64.b64encode(data).decode()
        
        js_code = f"""
            <script>
                var audio = new Audio("data:audio/mp3;base64,{b64}");
                audio.play().catch(function(error) {{
                    console.log("Autoplay bloqueado por el navegador: ", error);
                }});
            </script>
        """
        components.html(js_code, height=0, width=0)
        
    except FileNotFoundError:
        st.error(f"⚠️ Error de Sonido: No se encontró el archivo '{file_path}'. Verifica que la carpeta 'audio' exista.")

# --- Configuration ---
st.set_page_config(
    page_title="Laboratorio Contable - IA",
    page_icon="🤖",
    layout="wide"
)

# --- CSS Styling Avanzado ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .stApp {
        background-color: #f8f9fa;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    /* ELIMINAMOS header {visibility: hidden;} PARA QUE LA FLECHA DEL PANEL NUNCA DESAPAREZCA */

    .stChatMessage {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        transition: transform 0.2s ease-in-out;
    }
    .stChatMessage:hover {
        transform: translateY(-2px);
    }
    
    [data-testid="chatAvatarIcon-user"] {
        background-color: #003366 !important;
    }
    [data-testid="chatAvatarIcon-assistant"] {
        background-color: #198754 !important;
    }

    .stButton > button {
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
        border: none;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        transform: translateY(-1px);
    }
    
    [data-testid="baseButton-primary"] {
        background-color: #003366 !important;
        color: white !important;
    }
    [data-testid="baseButton-primary"]:hover {
        background-color: #002244 !important;
    }

    [data-testid="stMetricValue"] {
        font-size: 2rem !important;
        font-weight: 800 !important;
        color: #003366;
    }
    [data-testid="stMetricLabel"] {
        font-size: 1rem !important;
        font-weight: 600 !important;
        color: #6c757d;
    }
</style>
""", unsafe_allow_html=True)

# --- Helper Functions for Premium Features ---
def get_difficulty_badge(text):
    if "[BÁSICO]" in text:
        return f'<span style="background-color: #d4edda; color: #155724; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 0.8em;">BÁSICO</span>'
    elif "[INTERMEDIO]" in text:
        return f'<span style="background-color: #fff3cd; color: #856404; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 0.8em;">INTERMEDIO</span>'
    elif "[AVANZADO]" in text:
        return f'<span style="background-color: #f8d7da; color: #721c24; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 0.8em;">AVANZADO</span>'
    return ""

def clean_case_title(text):
    return text.replace("[BÁSICO]", "").replace("[INTERMEDIO]", "").replace("[AVANZADO]", "").strip()

def generar_pdf(markdown_content):
    markdown_content = markdown_content.replace('•', '-').replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'").replace('–', '-').replace('—', '-')
    markdown_content = markdown_content.encode('latin-1', 'ignore').decode('latin-1')

    class PDF(FPDF):
        def header(self):
            try:
                self.image('img/Logo.png', 10, 4, 22)
            except Exception:
                pass 
            
            nombre_uni = st.secrets["general"].get("NOMBRE_INSTITUCION", "Institución Educativa")
            
            self.set_font('helvetica', 'B', 15)
            self.cell(25)
            self.cell(0, 8, nombre_uni, border=0, ln=1, align='C')
            
            self.set_font('helvetica', 'I', 10)
            self.cell(25)
            self.cell(0, 8, 'Laboratorio Contable - Reporte de Práctica IA', border=0, ln=1, align='C')
            
            self.set_draw_color(0, 51, 102)
            self.line(10, 28, 200, 28)
            self.ln(15)
            
        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'R')

    pdf = PDF()
    pdf.add_page()
    
    html_text = markdown.markdown(markdown_content, extensions=['tables'])
    html_text = html_text.replace('</p>', '</p><br>')
    html_text = html_text.replace('</li>', '</li><br>')
    html_text = re.sub(r'<table[^>]*>', '<br><table border="1" width="100%">', html_text)
    html_text = html_text.replace('</table>', '</table><br>')

    html_text = re.sub(r'<h1[^>]*>(.*?)</h1>', r'<h1><font color="#990000">\1</font></h1>', html_text, flags=re.IGNORECASE)
    html_text = re.sub(r'<h2[^>]*>(.*?)</h2>', r'<h2><font color="#990000">\1</font></h2>', html_text, flags=re.IGNORECASE)
    html_text = re.sub(r'\[CALIFICACIÓN:\s*([^\]]+)\]', r'<h1><font color="#990000">1. CALIFICACIÓN: \1</font></h1>', html_text, flags=re.IGNORECASE)

    html_text = html_text.replace('style="text-align: right;"', 'align="right"')
    html_text = html_text.replace('style="text-align: left;"', 'align="left"')
    html_text = html_text.replace('style="text-align: center;"', 'align="center"')

    pdf.set_font("helvetica", size=10)

    try:
        pdf.write_html(html_text)
    except Exception as e:
        pdf.set_text_color(255, 0, 0)
        pdf.multi_cell(0, 10, f"Error rendering HTML: {e}\n\nFallback Content:\n{markdown_content}")
        pdf.set_text_color(0, 0, 0)

    return bytes(pdf.output())
    
# --- NUEVA FUNCIÓN: EXPORTAR A EXCEL (LECTURA INTELIGENTE DE TABLAS) ---
def generar_excel_ciclo(markdown_text, transacciones):
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # 1. Hoja de Enunciados
        df_enunciados = pd.DataFrame({"N°": range(1, len(transacciones)+1), "Transacción": transacciones})
        df_enunciados.to_excel(writer, sheet_name='Enunciados', index=False)
        
        # 2. Escanear el texto de la IA
        lineas = markdown_text.split('\n')
        tablas = []
        tabla_actual = []
        
        for linea in lineas:
            if linea.strip().startswith('|'):
                tabla_actual.append(linea.strip())
            else:
                if tabla_actual:
                    tablas.append(tabla_actual)
                    tabla_actual = []
        if tabla_actual:
            tablas.append(tabla_actual)
        
        diario_filas = []
        diario_headers = ["Fecha", "Detalle / Cuenta", "Debe (Bs.)", "Haber (Bs.)"]
        
        # 3. Clasificar cada tabla
        for tabla in tablas:
            if len(tabla) < 3: continue
            
            encabezados = [c.strip() for c in tabla[0].split('|')[1:-1]]
            str_headers = " ".join(encabezados).upper()
            
            datos = []
            for fila in tabla[2:]:
                celdas = [c.strip() for c in fila.split('|')[1:-1]]
                while len(celdas) < len(encabezados): celdas.append("")
                datos.append(celdas[:len(encabezados)])
                
            if "FECHA" in str_headers and "DEBE" in str_headers:
                diario_filas.extend(datos)
                diario_filas.append(["", "---", "", ""]) 
            elif "SUMAS DEBE" in str_headers or "SALDO DEUDOR" in str_headers:
                pd.DataFrame(datos, columns=encabezados).to_excel(writer, sheet_name='Balance Comprobación', index=False)
            elif "CONCEPTO" in str_headers and "MONTO" in str_headers:
                pd.DataFrame(datos, columns=encabezados).to_excel(writer, sheet_name='Estado Resultados', index=False)
            elif "ACTIVO" in str_headers and "PASIVO" in str_headers:
                pd.DataFrame(datos, columns=encabezados).to_excel(writer, sheet_name='Balance General', index=False)
        
        # Guardar Libro Diario consolidado
        if diario_filas:
            df_diario = pd.DataFrame(diario_filas, columns=diario_headers)
            df_diario.to_excel(writer, sheet_name='Libro Diario', index=False)
        else:
            pd.DataFrame(columns=diario_headers).to_excel(writer, sheet_name='Libro Diario', index=False)
        
        for sheet in writer.sheets.values():
            sheet.set_column('A:Z', 22)

    return output.getvalue()

# --- Level 1: Local Search (Strict) ---
@st.cache_data
def load_tax_rules():
    try:
        base_path = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(base_path, 'data', 'reglas_tributarias.txt')
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "Aplica la normativa tributaria vigente en Bolivia."

@st.cache_data
def load_local_data():
    try:
        with open('data/topics_content.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("Error: data/topics_content.json no encontrado.")
        return []

def load_laboratory_cases():
    cases = {}
    try:
        base_path = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(base_path, 'data', 'laboratory_cases.json')
        with open(file_path, 'r', encoding='utf-8') as f:
            cases = json.load(f)
    except Exception:
        pass
        
    if db is not None:
        try:
            mi_institucion = st.session_state.get("user_institucion", "UNICEN")
            mi_rol = st.session_state.get("user_rol", "estudiante")
            
            if mi_rol == "admin":
                casos_nube = db.collection('casos_practicos').get()
            else:
                casos_nube = db.collection('casos_practicos').where('institucion', '==', mi_institucion).get()
                
            for doc in casos_nube:
                data = doc.to_dict()
                cat = data.get('categoria', 'Categoría Personalizada')
                
                if mi_rol == "admin":
                    inst_tag = data.get('institucion', 'Global')
                    cat = f"[{inst_tag}] {cat}"
                    
                enunciado = data.get('enunciado', '')
                if cat not in cases:
                    cases[cat] = []
                cases[cat].append(enunciado)
        except Exception:
            pass
            
    return cases

def normalize_text(text):
    if not isinstance(text, str): return ""
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn').lower()

def search_local(query, topics):
    query_clean = normalize_text(query).replace('¿', '').replace('?', '').strip()
    stopwords = ["que", "es", "el", "la", "los", "las", "un", "una", "de", "en", "para", "con", "como"]
    palabras_clave = [w for w in query_clean.split() if w not in stopwords and len(w) > 2]
    
    results = []
    
    for topic in topics:
        title = topic.get('title', '')
        content = topic.get('content', '')
        
        if isinstance(content, str):
            text_content = content
        elif isinstance(content, dict):
             text_content = content.get('summary', '') + " " + " ".join([sec.get('content', '') for sec in content.get('detailed_sections', [])])
        else:
            text_content = ""
            
        text_norm = normalize_text(text_content)
        title_norm = normalize_text(title)

        score = 0
        
        if len(palabras_clave) > 1 and query_clean in text_norm:
            score += 50
        
        for palabra in palabras_clave:
            if palabra in title_norm:
                score += 10
            if palabra in text_norm:
                score += 3
                
        if score >= 3:
            idx = -1
            if len(palabras_clave) > 1 and query_clean in text_norm:
                idx = text_norm.find(query_clean)
            else:
                idx = text_norm.find(palabras_clave[0]) if palabras_clave else 0

            start_idx = max(0, idx - 100)
            end_idx = min(len(text_content), idx + 800)
            
            snippet = text_content[start_idx:end_idx]
            if start_idx > 0: snippet = "..." + snippet
            if end_idx < len(text_content): snippet += "..."

            results.append({
                'topic': title,
                'snippet': snippet,
                'score': score
            })
    
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:3] if results else []

# --- Level 1.5: The Smart Judge (LLM) ---
def evaluate_snippet_with_llm(user_query, snippet, api_key):
    if not api_key:
        return "INSUFICIENTE" 

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-flash-latest')
        
        system_prompt = f"""Eres un Tutor Senior de Contabilidad. 
El alumno preguntó: "{user_query}". 
Aquí tienes los extractos más relevantes de varios temas del curso: "{snippet}". 

TAREA: Lee TODOS los extractos. 
Combina la información histórica y técnica para dar la mejor respuesta pedagógica posible. 
Si ninguno de los extractos responde realmente a la pregunta, responde estrictamente la palabra INSUFICIENTE."""
        
        response = model.generate_content(system_prompt)
        text_response = response.text.strip()
        
        if "INSUFICIENTE" in text_response.upper() and len(text_response) < 20:
             return "INSUFICIENTE"
             
        return text_response
    except Exception as e:
        raise e

# --- Level 2: NotebookLM ---
def search_notebooklm(query):
    notebooks = {
        "CURSO CONTABILIDAD BASICA": "af525325-ca19-4f82-975f-349f01c6a099",
        "Compendio Normativo y Guía del Sistema Tributario Boliviano": "ead8f2c0-19e9-42dc-8040-c4659126b7e9"
    }
    
    combined_results = []
    
    for title, notebook_id in notebooks.items():
        try:
            command = ['python', 'scripts/nlm_query_id.py', notebook_id, query]
            result = subprocess.run(command, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0 and result.stdout.strip():
                output = result.stdout.strip()
                if "Error:" not in output[:20]: 
                    combined_results.append(f"**Fuente: {title}**\n{output}")
                else:
                    print(f"NotebookLM Script Error ({title}): {output}")
            else:
                if result.stderr:
                    print(f"NotebookLM Stderr ({title}): {result.stderr}")

        except Exception as e:
            print(f"NotebookLM Error ({title}): {e}")
            continue

    if combined_results:
        return "\n\n---\n\n".join(combined_results)
    return None

# --- Level 3: Web Search ---
def search_web(query):
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            search_query = f"{query} site:gob.bo OR site:auditoresbolivia.com OR site:boliviaimpuestos.com"
            results = list(ddgs.text(search_query, max_results=3))
            
            if results:
                summary = "He encontrado información relevante en la normativa boliviana:\n\n"
                for r in results:
                    summary += f"- **{r['title']}**: {r['body']} ([Enlace]({r['href']}))\n"
                return summary
            return None
    except Exception as e:
        return f"Error en búsqueda web: {e}"

def mostrar_login():
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            "<div style='text-align: center; padding: 1rem;'><h2 style='color: #003366;'>Bienvenido a CONTA-EASY 🚀</h2><p style='color: #6c757d;'>Inicia sesión o regístrate para continuar.</p></div>",
            unsafe_allow_html=True
        )
        
        tab_login, tab_register = st.tabs(["🔑 Iniciar Sesión", "📝 Registrarse"])
        
        with tab_login:
            correo = st.text_input("Correo Electrónico", key="login_correo")
            password = st.text_input("Contraseña", type="password", key="login_pass")
            if st.button("Ingresar", type="primary", use_container_width=True):
                if not correo or not password:
                    st.error("Por favor llena todos los campos.")
                elif db is None:
                    st.error("Base de datos no disponible.")
                else:
                    usuarios_ref = db.collection('usuarios')
                    query = usuarios_ref.where('correo', '==', correo).limit(1).get()
                    if len(query) == 0:
                        st.error("Usuario no encontrado.")
                    else:
                        user_doc = query[0]
                        user_data = user_doc.to_dict()
                        
                        if user_data.get("estado") == "bloqueado":
                            st.error("🚫 Tu cuenta ha sido suspendida. Comunícate con Coordinación.")
                        elif user_data.get("password") == password:
                            st.session_state.user_id = user_doc.id
                            st.session_state.user_xp = user_data.get("xp", 0)
                            st.session_state.user_streak = user_data.get("racha", 0)
                            st.session_state.user_rol = user_data.get("rol", "estudiante")
                            st.session_state.user_institucion = user_data.get("institucion", "UNICEN") 
                            
                            # --- NUEVO: RECUPERAR EL CÓDIGO DE CLASE AL ENTRAR ---
                            st.session_state.user_codigo_clase = user_data.get("codigo_clase", "GENERAL")
                            
                            st.success("¡Sesión iniciada exitosamente!")
                            st.rerun()
                        else:
                            st.error("Contraseña incorrecta.")
                            
        with tab_register:
            nuevo_correo = st.text_input("Correo Electrónico", key="reg_correo")
            nombre_reg = st.text_input("Nombre Completo", key="reg_nombre")
            carrera_reg = st.selectbox("Carrera", ["Contaduría Pública", "Ingeniería Financiera", "Administración de Empresas", "Otra"], key="reg_carrera")
            
            # --- MODIFICACIÓN SAAS: Institución Fija y Bloqueada ---
            try:
                institucion_fija = st.secrets["general"]["NOMBRE_INSTITUCION"]
            except:
                institucion_fija = "UNICEN" # Valor por defecto
                
            institucion_reg = st.text_input("Institución (Asignada automáticamente)", value=institucion_fija, disabled=True, key="reg_inst")
            
            # --- NUEVO: CAMPO DE CÓDIGO DE CLASE ---
            codigo_clase_reg = st.text_input("Código de Clase (Pídeselo a tu docente)", help="Ejemplo: VERTIZ-101. Si eres docente independiente, inventa uno.", key="reg_codigo")
            
            nuevo_password = st.text_input("Contraseña", type="password", key="reg_pass")
            
            if st.button("Crear Cuenta", type="primary", use_container_width=True):
                if not nuevo_correo or not nuevo_password or not nombre_reg or not codigo_clase_reg:
                    st.error("Por favor llena todos los campos, incluyendo tu Código de Clase.")
                elif db is None:
                    st.error("Base de datos no disponible.")
                else:
                    usuarios_ref = db.collection('usuarios')
                    query = usuarios_ref.where('correo', '==', nuevo_correo).limit(1).get()
                    if len(query) > 0:
                        st.error("Ese correo ya está registrado.")
                    else:
                        codigo_limpio = codigo_clase_reg.strip().upper() # Lo forzamos a mayúsculas para evitar errores
                        nuevo_usuario = {
                            "correo": nuevo_correo,
                            "nombre": nombre_reg,
                            "carrera": carrera_reg,
                            "institucion": institucion_fija,
                            "codigo_clase": codigo_limpio, # <-- GUARDAMOS EL CÓDIGO EN FIREBASE
                            "password": nuevo_password,
                            "xp": 0,
                            "racha": 0,
                            "rol": "estudiante",
                            "estado": "activo"
                        }
                        _, doc_ref = usuarios_ref.add(nuevo_usuario)
                        st.session_state.user_id = doc_ref.id
                        st.session_state.user_xp = 0
                        st.session_state.user_streak = 0
                        st.session_state.user_rol = "estudiante"
                        st.session_state.user_institucion = institucion_fija
                        st.session_state.user_codigo_clase = codigo_limpio # <-- LO GUARDAMOS EN LA SESIÓN
                        st.success("Cuenta creada exitosamente. ¡Bienvenido!")
                        st.rerun()

def main():
    if "user_id" not in st.session_state:
        mostrar_login()
        return

    st.title("📚 Laboratorio de Contabilidad (IA)")
    st.markdown("Asistente inteligente con Búsqueda en Cascada (Local -> NotebookLM -> Web)")

    if "pending_sound" in st.session_state:
        reproducir_sonido(st.session_state.pending_sound)
        del st.session_state.pending_sound

    with st.sidebar:
        st.header("Configuración")
        
        st.markdown("### 🏆 Tu Progreso")
        col_xp, col_streak = st.columns(2)
        with col_xp:
            st.metric(label="Experiencia", value=f"{st.session_state.user_xp} XP")
        with col_streak:
            st.metric(label="Racha 🔥", value=f"{st.session_state.user_streak}")
        st.divider()
        
        # --- RANKING PÚBLICO (LEADERBOARD) ---
        with st.sidebar.expander("🏆 Ranking de mi Universidad", expanded=False):
            if db is not None:
                try:
                    mi_institucion_r = st.session_state.get("user_institucion", "UNICEN")
                    estudiantes_ref = db.collection('usuarios').where('rol', '==', 'estudiante').where('institucion', '==', mi_institucion_r).get()
                    
                    lista_estudiantes = []
                    for est in estudiantes_ref:
                        data_est = est.to_dict()
                        if data_est.get('xp', 0) > 0: 
                            lista_estudiantes.append({
                                "nombre": data_est.get("nombre", "Anónimo").split()[0],
                                "xp": data_est.get("xp", 0)
                            })
                    
                    top_5 = sorted(lista_estudiantes, key=lambda x: x["xp"], reverse=True)[:5]
                    
                    if len(top_5) == 0:
                        st.info("Aún no hay alumnos con puntos. ¡Sé el primero en liderar la tabla!")
                    else:
                        for i, alumno in enumerate(top_5):
                            medalla = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "🏅"
                            st.markdown(f"**{i+1}. {medalla} {alumno['nombre']}** - {alumno['xp']} XP")
                except Exception as e:
                    st.caption("No se pudo cargar el ranking en este momento.")
        st.sidebar.divider()
        
        # --- PANEL DE CONTROL (SOLO PARA ADMIN Y DOCENTES) ---
        user_ref = db.collection('usuarios').document(st.session_state.user_id).get()
        if user_ref.exists and user_ref.to_dict().get("rol") in ["admin", "docente"]:
            st.markdown("### 🛠️ Administración")
            if st.button("📊 Panel de Control", type="secondary"):
                st.session_state.show_admin_panel = True
            st.divider()

        try:
            api_key = st.secrets["general"]["GEMINI_API_KEY"]
        except Exception:
            st.error("⚠️ Error Crítico: No se encontró la API Key en los secretos del servidor.")
            api_key = ""

        st.divider()
        st.header("🔍 Motor de Búsqueda")
        deep_search_active = st.checkbox("Activar Búsqueda Profunda", value=False, key="deep_search", help="Consultar las 3 fuentes simultáneamente")
        st.caption("Niveles Activos: 1. Local (IA) | 2. NotebookLM | 3. Web Oficial")
        
        if st.button("🗑️ Limpiar Historial de Chat"):
            st.session_state.messages = []
            if "auditor_mode" in st.session_state: del st.session_state.auditor_mode
            if "auditor_case" in st.session_state: del st.session_state.auditor_case
            st.rerun()
            
        st.divider()
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            for key in ["user_id", "user_xp", "user_streak", "messages", "project_mode", "auditor_mode"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

        st.divider()
        st.header("📝 Laboratorio de Casos")
        
        lab_cases = load_laboratory_cases()
        
        if lab_cases:
            categories = list(lab_cases.keys())
            selected_category = st.selectbox("Categoría", categories, key="categoria")
            
            cases = lab_cases.get(selected_category, [])
            selected_case = st.selectbox("Ejercicio Práctico", cases)
            
            badge_html = get_difficulty_badge(selected_case)
            if badge_html:
                st.markdown(f"{badge_html}", unsafe_allow_html=True)
            
            caso_limpio = clean_case_title(selected_case)
            
            if "selected_case_tracker" not in st.session_state or st.session_state.selected_case_tracker != caso_limpio:
                st.session_state.selected_case_tracker = caso_limpio
                st.session_state.current_active_case = caso_limpio
            
            st.markdown(f"**📝 Caso Activo:** {st.session_state.current_active_case}")
            
            if st.button("🎲 Generar Variante Anti-Copia (Aleatorio)", help="Crea una versión única de este ejercicio para evitar copias."):
                reproducir_sonido("audio/dice.mp3") 
                with st.spinner("Creando variante única..."):
                    try:
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel('gemini-flash-latest')
                        prompt_mutacion = f"""Eres un Docente de Contabilidad Universitario. 
                        Toma el siguiente caso práctico base y crea una variante ÚNICA para un examen anti-copia.
                        REGLAS:
                        1. Cambia radicalmente los montos monetarios (hazlos realistas).
                        2. Cambia los nombres de las empresas, bancos o personas involucradas.
                        3. Cambia la fecha (usa fechas del año 2026).
                        4. Puedes agregar un pequeño detalle extra (ej. 'se incluye un descuento del 2%' o 'se paga con cheque del Banco Nacional').
                        5. MANTÉN exactamente el mismo nivel de complejidad contable y las cuentas principales que se evaluarían.
                        6. DEVUELVE ÚNICAMENTE EL TEXTO DEL NUEVO ENUNCIADO. No lo resuelvas, no uses introducciones, no uses markdown extra.
                        
                        Caso Base: "{caso_limpio}"
                        """
                        response = model.generate_content(prompt_mutacion)
                        st.session_state.current_active_case = response.text.strip()
                        st.rerun() 
                    except Exception as e:
                        st.error(f"Error al generar variante: {e}")
            
            col1, col2 = st.columns(2)
            
            if col1.button("👨‍🏫 Analizar con Tutor"):
                reproducir_sonido("audio/click.mp3") 
                st.session_state.messages.append({"role": "user", "content": st.session_state.current_active_case})
                st.session_state.auditor_mode = False 
                
                with st.spinner("👨‍🏫 El Tutor está analizando el caso..."):
                    try:
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel('gemini-flash-latest')
                        
                        nombre_uni = st.secrets["general"].get("NOMBRE_INSTITUCION", "Institución Educativa")
            
                        reglas_actuales = load_tax_rules()
                        prompt_lab = f"""Eres un Tutor de Contabilidad Senior de la {nombre_uni}. El alumno necesita resolver este caso práctico: "{st.session_state.current_active_case}". 
PROHIBIDO usar formato LaTeX, signos de dólar ($) o etiquetas como \\mathbf para fórmulas matemáticas. Escribe los cálculos en texto plano normal.
DEBES dejar obligatoriamente una línea en blanco (un Enter) justo ANTES de empezar la tabla del asiento contable.

{reglas_actuales}
REGLA DE ORO TRIBUTARIA: Aplica las normativas de impuestos SOLO si la transacción lo requiere explícitamente. ESTÁ ESTRICTAMENTE PROHIBIDO añadir "Notas", consejos o recordatorios al final de tu respuesta sobre retenciones (como el D.S. 4850) si el ejercicio no trata sobre pagos de servicios sin factura. Limítate a resolver el caso.
TAREA: 
1. Crea el asiento contable usando ESTRICTAMENTE esta estructura Markdown. NO fusiones columnas. Usa este modelo exacto para garantizar la alineación:
| Código | Detalle / Cuenta | Debe (Bs.) | Haber (Bs.) |
| :--- | :--- | ---: | ---: |
| 1.1.1 | Caja | 1.000,00 | |
| 2.1.1 | Cuentas por Pagar | | 1.000,00 |
REGLA DE ORO: ESCRIBE LA GLOSA COMPLETAMENTE AFUERA Y DEBAJO DE LA TABLA como texto normal. NUNCA incluyas la glosa como una fila o celda dentro de la tabla.
2. Explica breve y pedagógicamente por qué se debita o acredita cada cuenta basándote en la ley de movimiento de cuentas. 
3. Menciona qué documento de respaldo (factura, recibo, etc.) se necesitaría.

Después de la explicación del asiento, DEBES agregar dos secciones nuevas obligatorias:
4. LIBRO MAYOR (CUENTAS T): Genera el mayor de cada cuenta importante que intervino en el asiento usando ESTRICTAMENTE tablas individuales de Markdown. Suma las columnas y muestra el saldo final (Deudor o Acreedor). ¡NUNCA omitas la fila separadora | ---: | ---: | debajo de los encabezados! Usa EXACTAMENTE este formato para cada cuenta:

#### Cuenta: [Nombre de la Cuenta]
| DEBE (Bs.) | HABER (Bs.) |
| ---: | ---: |
| 1.000,00 | |
| | 500,00 |
| **Total: 1.000,00** | **Total: 500,00** |
| **Saldo Deudor:** | **500,00** |

DEBES dejar una línea en blanco entre la cuenta T de una cuenta y la siguiente.

5. IMPACTO EN ESTADOS FINANCIEROS: Crea una pequeña tabla con las columnas | Cuenta | Grupo | Estado Financiero |. Indica exactamente a dónde va cada cuenta (Ej. Activo Corriente -> Balance General; Gasto Operativo -> Estado de Resultados).
| Cuenta | Grupo | Estado Financiero |
| :--- | :--- | :--- |

REGLA DE ORO DE FORMATO: TODAS las filas de TODAS las tablas DEBEN empezar obligatoriamente con el símbolo | y terminar con el símbolo |. ¡Cero excepciones! El separador de las Cuentas T debe ser SIEMPRE EXACTAMENTE | ---: | ---: |."""

                        response = model.generate_content(prompt_lab)
                        lab_response = response.text.strip()
                        
                        st.session_state.messages.append({"role": "assistant", "content": lab_response})
                        st.session_state.last_lab_response = lab_response 
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Error: {e}")

            if col2.button("⚔️ Reto Auditor"):
                st.session_state.pending_sound = "audio/swords.mp3" 
                st.session_state.auditor_mode = True
                st.session_state.auditor_case = st.session_state.current_active_case
                st.session_state.messages.append({"role": "assistant", "content": f"⚔️ **¡Reto Aceptado!**\n\nCaso: *{st.session_state.current_active_case}*\n\nEscribe en el chat tu asiento contable propuesto (Cuentas y Montos). Yo actuaré como un Auditor estricto y calificaré tu respuesta."})
                st.rerun()
                
        else:
            st.warning("⚠️ No se encontraron casos de laboratorio. Verifica data/laboratory_cases.json")

            
        st.divider()
        st.header("🏢 Proyecto: Ciclo Contable")
        
        if not st.session_state.get("project_mode", False):
            if st.button("🚀 Iniciar / Retomar Proyecto"):
                st.session_state.pending_sound = "audio/rocket.mp3" 
                st.session_state.project_mode = True
                
                # --- MAGIA: RECUPERAR DE FIREBASE ---
                transacciones_guardadas = []
                if db is not None:
                    try:
                        user_data = db.collection('usuarios').document(st.session_state.user_id).get().to_dict()
                        transacciones_guardadas = user_data.get("proyecto_en_curso", [])
                    except Exception:
                        pass
                
                st.session_state.project_transactions = transacciones_guardadas
                
                if len(transacciones_guardadas) > 0:
                    st.session_state.messages.append({"role": "assistant", "content": f"☁️ **¡Proyecto Retomado!**\n\nHe recuperado **{len(transacciones_guardadas)} transacciones** de la nube. Puedes continuar ingresando la siguiente."})
                else:
                    st.session_state.messages.append({"role": "assistant", "content": "🏢 **¡Modo Proyecto Iniciado!**\n\nVamos a simular un ciclo contable libre. Escribe tus transacciones una por una en el chat."})
                st.rerun()
        else:
            st.info(f"Transacciones registradas: {len(st.session_state.get('project_transactions', []))}")
            
            if st.button("💾 Guardar Avance"):
                if db is not None:
                    try:
                        db.collection('usuarios').document(st.session_state.user_id).update({
                            "proyecto_en_curso": st.session_state.project_transactions
                        })
                        st.toast("✅ Avance guardado en la nube exitosamente", icon="☁️")
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")
                        
            if st.button("📊 Generar EEFF", type="primary"):
                if len(st.session_state.project_transactions) > 0:
                    st.session_state.generate_project_balance = True
                    if db is not None:
                        try:
                            db.collection('usuarios').document(st.session_state.user_id).update({"proyecto_en_curso": []})
                        except: pass
                else:
                    st.warning("Debes ingresar al menos una transacción.")
            
            if st.button("❌ Cancelar Proyecto"):
                st.session_state.project_mode = False
                st.session_state.project_transactions = []
                if db is not None:
                    try:
                        db.collection('usuarios').document(st.session_state.user_id).update({"proyecto_en_curso": []})
                    except: pass
                st.session_state.messages.append({"role": "assistant", "content": "Proyecto cancelado y borrado de la nube."})
                st.rerun()

        # ==========================================
        # NUEVO MÓDULO: EVALUACIÓN (EXÁMENES)
        # ==========================================
        st.divider()
        st.header("🎓 Módulo de Evaluación")
        
        if not st.session_state.get("exam_mode", False):
            with st.expander("📝 Cargar Examen / Plantilla"):
                examenes_disponibles = {}
                if db is not None:
                    try:
                        mi_institucion = st.session_state.get("user_institucion", "UNICEN")
                        mi_rol = st.session_state.get("user_rol", "estudiante")
                        
                        if mi_rol == "admin":
                            casos_ref = db.collection('casos_practicos').get()
                        else:
                            casos_ref = db.collection('casos_practicos').where('institucion', '==', mi_institucion).get()
                            
                        for doc in casos_ref:
                            data = doc.to_dict()
                            cat = data.get('categoria', 'Examen')
                            enunciado = data.get('enunciado', '')
                            anticopia = data.get('usa_anticopia', True) # Leemos la configuración secreta del docente
                            
                            if cat not in examenes_disponibles:
                                examenes_disponibles[cat] = []
                            # Guardamos texto y configuración
                            examenes_disponibles[cat].append({"texto": enunciado, "anticopia": anticopia})
                    except Exception:
                        pass

                if examenes_disponibles:
                    opciones_examenes = ["-- Selecciona un Examen --"]
                    mapa_examenes = {}
                    
                    for cat, casos in examenes_disponibles.items():
                        for c in casos:
                            titulo_limpio = clean_case_title(c["texto"])
                            titulo_corto = titulo_limpio[:50] + "..." if len(titulo_limpio) > 50 else titulo_limpio
                            etiqueta = f"[{cat}] {titulo_corto}"
                            opciones_examenes.append(etiqueta)
                            mapa_examenes[etiqueta] = c  # Mapeamos el diccionario completo
                            
                    examen_seleccionado = st.selectbox("Exámenes disponibles:", opciones_examenes, label_visibility="collapsed")
                    
                    if examen_seleccionado != "-- Selecciona un Examen --":
                        # ¡Desaparece el checkbox para el alumno! El sistema lee la orden silenciosa
                        if st.button("⏱️ Iniciar Examen", type="primary"):
                            st.session_state.pending_sound = "audio/swords.mp3" 
                            st.session_state.exam_mode = True
                            st.session_state.exam_title = examen_seleccionado
                            st.session_state.exam_answers = []
                            
                            datos_examen = mapa_examenes[examen_seleccionado]
                            texto_original = datos_examen["texto"]
                            
                            if datos_examen["anticopia"]:
                                with st.spinner("🎲 La IA está generando tu examen único (Anti-Copia)..."):
                                    try:
                                        genai.configure(api_key=api_key)
                                        model = genai.GenerativeModel('gemini-flash-latest')
                                        prompt_mutacion = f"""Eres un Docente Universitario de Contabilidad. Toma este examen base y crea una variante ÚNICA para evitar copias entre los alumnos.
                                        REGLAS DE ORO:
                                        1. Cambia radicalmente los montos monetarios (mantenlos realistas). Mantén la lógica matemática.
                                        2. Cambia los nombres de las empresas, clientes, proveedores y bancos.
                                        3. Cambia las fechas (año 2026).
                                        4. MANTÉN la misma cantidad de transacciones y dificultad contable.
                                        5. DEVUELVE ÚNICAMENTE el nuevo texto del examen, con saltos de línea por transacción. Nada de introducciones.
                                        
                                        Examen Base:
                                        {texto_original}
                                        """
                                        response = model.generate_content(prompt_mutacion)
                                        st.session_state.exam_questions = response.text.strip()
                                    except Exception as e:
                                        st.session_state.exam_questions = texto_original
                            else:
                                st.session_state.exam_questions = texto_original
                                
                            preguntas_formateadas = "* " + st.session_state.exam_questions.replace('\n', '\n\n* ')
                            
                            st.session_state.messages.append({
                                "role": "assistant", 
                                "content": f"🎓 **¡EXAMEN INICIADO!**\n\n**ENUNCIADO:**\n{preguntas_formateadas}\n\n---\n**INSTRUCCIONES:**\nEscribe en la barra de chat tus respuestas. Cuando termines de registrar TODO, presiona **'✅ Calificar Examen'** en la barra lateral."
                            })
                            st.rerun()
                else:
                    st.caption("No hay exámenes o plantillas subidas por el docente en la nube.")
        else:
            st.warning("⏱️ Examen en curso...")
            st.info(f"Asientos / Respuestas enviadas: {len(st.session_state.get('exam_answers', []))}")
            
            if st.button("✅ Calificar Examen", type="primary"):
                if len(st.session_state.exam_answers) > 0:
                    st.session_state.grade_exam_now = True
                    st.rerun()
                else:
                    st.error("Debes enviar al menos una respuesta en el chat antes de calificar.")
                    
            if st.button("❌ Abandonar Examen"):
                st.session_state.exam_mode = False
                st.session_state.exam_answers = []
                st.session_state.messages.append({"role": "assistant", "content": "Examen abandonado. Se ha borrado tu progreso."})
                st.rerun()

    # --- Lógica para mostrar el Panel de Administración ---
    if st.session_state.get("show_admin_panel", False):
        st.markdown("---")
        st.header("🛠️ Panel de Administración y Analíticas")
        
        mi_institucion = st.session_state.get("user_institucion", "UNICEN")
        mi_rol = st.session_state.get("user_rol", "docente")
        
        if mi_rol == "admin":
            st.success("👑 MODO SUPER ADMIN: Viendo datos globales de TODAS las instituciones.")
            usuarios_ref = db.collection('usuarios').get()
        else:
            st.info(f"👨‍🏫 MODO DOCENTE: Viendo datos exclusivos de {mi_institucion}.")
            usuarios_ref = db.collection('usuarios').where('rol', '==', 'estudiante').where('institucion', '==', mi_institucion).get()
            
        usuarios_lista = [u for u in usuarios_ref if u.to_dict().get('rol') != 'admin']

        tab_alumnos, tab_casos, tab_analiticas, tab_notas = st.tabs(["👥 Gestión de Estudiantes", "📚 Gestor de Casos Prácticos", "🧠 Analíticas", "📊 Libro de Notas"])
        
        # ==========================================
        # PESTAÑA 1: ESTUDIANTES Y DOCENTES (CON CARGA MASIVA)
        # ==========================================
        with tab_alumnos:
            # --- NUEVA FUNCIÓN: CARGA MASIVA (SOLO SUPER ADMIN) ---
            if mi_rol == "admin":
                with st.expander("📥 Carga Masiva de Usuarios (Excel/CSV)"):
                    st.markdown("Sube un archivo con los datos de tus estudiantes. Las columnas en la primera fila del Excel deben llamarse **EXACTAMENTE** así:")
                    st.code("NOMBRE | CARRERA | UNIVERSIDAD | CORREO | PASSWORD | CODIGO_CLASE")
                    
                    archivo_masivo = st.file_uploader("Selecciona tu archivo Excel o CSV", type=['csv', 'xlsx'])
                    
                    if archivo_masivo is not None:
                        if st.button("🚀 Procesar y Subir Usuarios", type="primary"):
                            with st.spinner("Leyendo archivo y subiendo a la nube..."):
                                try:
                                    if archivo_masivo.name.endswith('.csv'):
                                        df_masivo = pd.read_csv(archivo_masivo)
                                    else:
                                        df_masivo = pd.read_excel(archivo_masivo)
                                    
                                    # Normalizar nombres de columnas
                                    df_masivo.columns = df_masivo.columns.str.strip().str.upper()
                                    esperadas = ["NOMBRE", "CARRERA", "UNIVERSIDAD", "CORREO", "PASSWORD", "CODIGO_CLASE"]
                                    
                                    if not all(col in df_masivo.columns for col in esperadas):
                                        st.error("⚠️ Error: Faltan columnas. Deben ser exactamente: NOMBRE, CARRERA, UNIVERSIDAD, CORREO, PASSWORD, CODIGO_CLASE.")
                                    else:
                                        agregados = 0
                                        duplicados = 0
                                        usuarios_actuales = db.collection('usuarios').get()
                                        correos_existentes = [doc.to_dict().get('correo', '') for doc in usuarios_actuales]
                                        
                                        for index, row in df_masivo.iterrows():
                                            correo_nuevo = str(row['CORREO']).strip()
                                            if pd.isna(row['CORREO']) or correo_nuevo == "" or correo_nuevo == "nan": continue
                                            
                                            if correo_nuevo in correos_existentes:
                                                duplicados += 1
                                                continue
                                                
                                            db.collection('usuarios').add({
                                                "nombre": str(row['NOMBRE']).strip(),
                                                "carrera": str(row['CARRERA']).strip(),
                                                "institucion": str(row['UNIVERSIDAD']).strip(),
                                                "correo": correo_nuevo,
                                                "password": str(row['PASSWORD']).strip(),
                                                "codigo_clase": str(row['CODIGO_CLASE']).strip().upper(),
                                                "xp": 0, "racha": 0, "rol": "estudiante", "estado": "activo", "acceso_analiticas": False
                                            })
                                            correos_existentes.append(correo_nuevo)
                                            agregados += 1
                                        
                                        st.success(f"✅ Carga masiva completada: {agregados} alumnos creados | {duplicados} omitidos.")
                                        time.sleep(3)
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Error al procesar el archivo: {e}")

            # --- LISTA DE ESTUDIANTES ---
            csv_data = "Nombre Completo;Rol;Carrera;Institucion;Correo Electronico;Experiencia (XP);Racha (Dias)\n"
            
            with st.expander(f"📋 Ver Lista de Usuarios Registrados ({len(usuarios_lista)})"):
                for u in usuarios_lista:
                    data = u.to_dict()
                    user_doc_id = u.id
                    rol_usuario = data.get('rol', 'estudiante')
                    correo = data.get('correo', 'Desconocido')
                    nombre = data.get('nombre', 'Sin Nombre Registrado')
                    carrera = data.get('carrera', 'Sin Carrera')
                    inst_alumno = data.get('institucion', 'Desconocida')
                    xp = data.get('xp', 0)
                    racha = data.get('racha', 0)
                    estado = data.get('estado', 'activo')
                    acceso_ana = data.get('acceso_analiticas', False)
                    
                    with st.container():
                        col_info, col_btn1, col_btn2, col_btn3 = st.columns([3, 1, 1, 1])
                        with col_info:
                            estado_icono = "🔴 BLOQUEADO" if estado == "bloqueado" else "🟢 ACTIVO"
                            if mi_rol == "admin":
                                etiqueta_rol = "👨‍🏫 DOCENTE" if rol_usuario == "docente" else "🧑‍🎓 ESTUDIANTE"
                                st.info(f"👤 **{nombre}** | 🏛️ {inst_alumno} | {etiqueta_rol} | {estado_icono}")
                            else:
                                st.info(f"👤 **{nombre}** | {carrera} | XP: {xp} | {estado_icono}")
                                
                        with col_btn1:
                            if st.button("🔑 Reset", key=f"pass_{user_doc_id}", use_container_width=True):
                                db.collection('usuarios').document(user_doc_id).update({"password": "123456"})
                                st.toast("✅ Contraseña cambiada a 123456")
                                time.sleep(1)
                                st.rerun()
                        with col_btn2:
                            if mi_rol == "admin" and rol_usuario == "docente":
                                if acceso_ana:
                                    if st.button("🚫 Ocultar Analíticas", key=f"ana_{user_doc_id}", use_container_width=True):
                                        db.collection('usuarios').document(user_doc_id).update({"acceso_analiticas": False})
                                        st.rerun()
                                else:
                                    if st.button("📊 Dar Analíticas", key=f"ana_{user_doc_id}", use_container_width=True):
                                        db.collection('usuarios').document(user_doc_id).update({"acceso_analiticas": True})
                                        st.rerun()
                            else:
                                if st.button("🔄 XP", key=f"xp_{user_doc_id}", use_container_width=True):
                                    db.collection('usuarios').document(user_doc_id).update({"xp": 0, "racha": 0})
                                    st.toast("✅ Progreso reiniciado")
                                    time.sleep(1)
                                    st.rerun()
                                    
                        with col_btn3:
                            if estado == "bloqueado":
                                if st.button("✅ Activar", key=f"unblock_{user_doc_id}", use_container_width=True):
                                    db.collection('usuarios').document(user_doc_id).update({"estado": "activo"})
                                    st.rerun()
                            else:
                                if st.button("🚫 Bloquear", key=f"block_{user_doc_id}", use_container_width=True):
                                    db.collection('usuarios').document(user_doc_id).update({"estado": "bloqueado"})
                                    st.rerun()

                    csv_data += f"{nombre};{rol_usuario};{carrera};{inst_alumno};{correo};{xp};{racha}\n"
                
            col1, col2 = st.columns(2)
            with col1:
                if st.button("❌ Cerrar Panel", use_container_width=True):
                    st.session_state.show_admin_panel = False
                    st.rerun()
            with col2:
                st.download_button("📥 Descargar Reporte (Excel)", data=csv_data.encode('utf-8-sig'), file_name=f"Reporte_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv", use_container_width=True)

        # ==========================================
        # PESTAÑA 2: SUBIR CASOS (CRUD)
        # ==========================================
        with tab_casos:
            st.subheader("Subir Nuevo Ejercicio a la Nube")
            with st.form("form_nuevo_caso", clear_on_submit=True):
                nueva_categoria = st.text_input("Categoría (Ej. 'Ajustes Contables', 'Pasivos', etc.)")
                nivel_dificultad = st.selectbox("Nivel de Dificultad", ["[BÁSICO]", "[INTERMEDIO]", "[AVANZADO]"])
                nuevo_enunciado = st.text_area("Enunciado del Caso Práctico")
                
                # --- NUEVA OPCIÓN: EL DOCENTE DECIDE SI ES ANTI-COPIA ---
                activar_anticopia = st.checkbox("🛡️ Activar Escudo Anti-Copia para este ejercicio", value=True, help="La IA generará valores distintos para cada alumno.")
                
                if st.form_submit_button("💾 Guardar Caso", type="primary"):
                    if nueva_categoria and nuevo_enunciado:
                        nuevo_documento = {
                            "categoria": nueva_categoria,
                            "enunciado": f"{nivel_dificultad} {nuevo_enunciado}",
                            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "institucion": mi_institucion,
                            "codigo_clase": st.session_state.get("user_codigo_clase", "GENERAL") # <-- NUEVO
                        }
                        db.collection('casos_practicos').add(nuevo_documento)
                        st.success("¡Caso guardado!")
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.error("Por favor completa la categoría y el enunciado.")
            st.markdown("### 📚 Casos Subidos en la Nube")
            try:
                if mi_rol == "admin":
                            casos_ref = db.collection('casos_practicos').get()
                        else:
                            # EL ALUMNO SOLO VE LOS EXÁMENES DE SU CLASE
                            mi_codigo = st.session_state.get("user_codigo_clase", "GENERAL")
                            casos_ref = db.collection('casos_practicos').where('institucion', '==', mi_institucion).where('codigo_clase', '==', mi_codigo).get()
                    
                if len(casos_db) == 0:
                    st.info("Aún no hay casos personalizados en la nube.")
                else:
                    for c in casos_db:
                        c_data = c.to_dict()
                        c_id = c.id
                        inst_caso = c_data.get('institucion', 'Global')
                        
                        col_texto, col_borrar = st.columns([5, 1])
                        with col_texto:
                            etiqueta = f"🏛️ {inst_caso} | " if mi_rol == "admin" else ""
                            st.info(f"{etiqueta}📁 **{c_data.get('categoria')}**: {c_data.get('enunciado')}")
                        with col_borrar:
                            if st.button("🗑️ Eliminar", key=f"del_caso_{c_id}", use_container_width=True):
                                db.collection('casos_practicos').document(c_id).delete()
                                st.rerun()
            except Exception as e:
                pass

        # ==========================================
        # PESTAÑA 3: ANALÍTICAS E INTELIGENCIA
        # ==========================================
        with tab_analiticas:
            mi_usuario_db = db.collection('usuarios').document(st.session_state.user_id).get().to_dict()
            tiene_permiso = (mi_rol == "admin") or (mi_rol == "docente" and mi_usuario_db.get("acceso_analiticas", False) == True)
            
            if not tiene_permiso:
                st.warning("🔒 No tienes acceso al módulo de analíticas. Solicita la habilitación al Administrador General.")
            else:
                st.subheader(f"🧠 Inteligencia Académica - {mi_institucion if mi_rol != 'admin' else 'Global'}")
                
                estudiantes = [u.to_dict() for u in usuarios_lista if u.to_dict().get('rol') == 'estudiante']
                
                if len(estudiantes) == 0:
                    st.info("No hay suficientes datos de estudiantes para generar analíticas.")
                else:
                    total_estudiantes = len(estudiantes)
                    xp_total = sum(e.get('xp', 0) for e in estudiantes)
                    xp_promedio = int(xp_total / total_estudiantes) if total_estudiantes > 0 else 0
                    alumnos_en_racha = sum(1 for e in estudiantes if e.get('racha', 0) > 0)
                    
                    c1, c2, c3 = st.columns(3)
                    c1.metric("👥 Estudiantes Activos", total_estudiantes)
                    c2.metric("⭐ XP Promedio", xp_promedio)
                    c3.metric("🔥 Alumnos en Racha", alumnos_en_racha)
                    
                    st.divider()
                    
                    # --- FILA 1: TOP 5 Y RIESGO ---
                    col_top, col_riesgo = st.columns(2)
                    
                    with col_top:
                        st.markdown("### 🏆 Top 5 - Cuadro de Honor")
                        estudiantes_ordenados = sorted(estudiantes, key=lambda x: x.get('xp', 0), reverse=True)[:5]
                        datos_grafico = {e.get('nombre', 'Anónimo'): e.get('xp', 0) for e in estudiantes_ordenados if e.get('xp', 0) > 0}
                        if datos_grafico:
                            st.bar_chart(datos_grafico)
                        else:
                            st.caption("Aún no hay alumnos con Experiencia (XP) para mostrar.")
                            
                    with col_riesgo:
                        st.markdown("### 🚨 Radar de Alerta Temprana")
                        st.caption("Alumnos inactivos (0 XP). Intervención sugerida.")
                        alumnos_riesgo = [e for e in estudiantes if e.get('xp', 0) == 0]
                        if len(alumnos_riesgo) > 0:
                            for ar in alumnos_riesgo:
                                nombre_ar = ar.get('nombre', 'Sin Nombre')
                                correo_ar = ar.get('correo', 'Sin Correo')
                                st.error(f"⚠️ **{nombre_ar}** \n\n ✉️ {correo_ar}")
                        else:
                            st.success("¡Excelente! Todos los alumnos tienen participación activa.")
                            
                    # --- FILA 2: NUEVO COMPORTAMIENTO IA ---
                    st.divider()
                    st.markdown("### 🤖 Comportamiento de Aprendizaje (Uso de IA)")
                    st.caption("Mide la confianza del grupo: ¿Buscan ayuda o se ponen a prueba?")
                    
                    total_tutor = sum(e.get('uso_tutor', 0) for e in estudiantes)
                    total_auditor = sum(e.get('uso_auditor', 0) for e in estudiantes)
                    
                    col_t1, col_t2 = st.columns(2)
                    with col_t1:
                        st.info(f"🧑‍🏫 **Tutor Analista (Fase Aprendizaje):** {total_tutor} consultas")
                    with col_t2:
                        st.success(f"🕵️ **Reto Auditor (Fase Evaluación):** {total_auditor} intentos")
                        
                    if total_tutor > 0 or total_auditor > 0:
                        datos_ia = {"Tutor Analista": total_tutor, "Reto Auditor": total_auditor}
                        st.bar_chart(datos_ia)
                    else:
                        st.caption("Aún no hay suficientes datos de interacción con la IA para graficar.")
                        
                    # --- FILA 3: TERMÓMETRO POR CATEGORÍA ---
                    st.divider()
                    st.markdown("### 🌡️ Termómetro de Rendimiento por Temas")
                    st.caption("Mide el dominio del curso en cada categoría contable según la Experiencia (XP) ganada.")
                    
                    rendimiento_global = {}
                    for e in estudiantes:
                        rendimiento_usuario = e.get('rendimiento_categorias', {})
                        for cat, xp_ganada in rendimiento_usuario.items():
                            rendimiento_global[cat] = rendimiento_global.get(cat, 0) + xp_ganada
                            
                    if rendimiento_global:
                        st.bar_chart(rendimiento_global)
                    else:
                        st.info("Aún no hay datos de rendimiento. Los alumnos deben ganar XP resolviendo casos para que el termómetro se active.")
          
        # ==========================================
        # PESTAÑA 4: LIBRO DE NOTAS
        # ==========================================
        with tab_notas:
            st.subheader("📊 Registro Oficial de Calificaciones")
            if db is not None:
                try:
                    if mi_rol == "admin":
                        notas_ref = db.collection('calificaciones').order_by('fecha', direction=firestore.Query.DESCENDING).get()
                    else:
                        mi_codigo = st.session_state.get("user_codigo_clase", "GENERAL")
                        notas_ref = db.collection('calificaciones').where('institucion', '==', mi_institucion).where('codigo_clase', '==', mi_codigo).get()
                        
                    lista_notas = [n.to_dict() for n in notas_ref]
                    
                    if not lista_notas:
                        st.info("Aún no hay exámenes calificados en tu institución.")
                    else:
                        df_notas = pd.DataFrame(lista_notas)
                        if "fecha" in df_notas.columns:
                            df_notas = df_notas[["fecha", "nombre_alumno", "examen_titulo", "nota"]]
                            df_notas.columns = ["Fecha y Hora", "Estudiante", "Examen Evaluado", "Calificación (/100)"]
                            
                        st.dataframe(df_notas, use_container_width=True)
                        
                        csv_notas = df_notas.to_csv(index=False).encode('utf-8-sig')
                        st.download_button("📥 Descargar Libro de Notas (Excel/CSV)", data=csv_notas, file_name=f"Notas_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv", use_container_width=True)
                except Exception as e:
                    st.error(f"Error al cargar las calificaciones: {e}") 
                        
    # --- Inicializar memoria del chat ---
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if not st.session_state.messages:
        st.markdown("<br><br>", unsafe_allow_html=True)
        col_a, col_b, col_c = st.columns([1, 4, 1])
        with col_b:
            st.markdown(
                """
                <div style='text-align: center; padding: 2rem; background-color: white; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);'>
                    <h2 style='color: #003366; margin-bottom: 0;'>¡Bienvenido a CONTA-EASY! 🚀</h2>
                    <p style='color: #6c757d; font-size: 1.1rem; margin-top: 10px;'>Tu simulador de auditoría y laboratorio contable inteligente.</p>
                    <hr style='opacity: 0.2;'>
                    <div style='text-align: left; color: #495057;'>
                        <p><b>¿Cómo empezar?</b></p>
                        <ul>
                            <li><b>📝 Laboratorio:</b> Selecciona un caso en el menú izquierdo y reta al Auditor.</li>
                            <li><b>🏢 Proyecto:</b> Inicia un ciclo contable completo y genera tus Estados Financieros.</li>
                            <li><b>💬 Consultas:</b> Pregunta sobre normativas tributarias en la barra inferior.</li>
                        </ul>
                    </div>
                </div>
                """, 
                unsafe_allow_html=True
            )
        st.markdown("<br><br>", unsafe_allow_html=True)

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
            if message == st.session_state.messages[-1] and message["role"] == "assistant":
                if "last_lab_response" in st.session_state and st.session_state.last_lab_response in message["content"]:
                    pdf_bytes = generar_pdf(message["content"])
                    st.download_button(label="📄 Descargar PDF", data=pdf_bytes, file_name="Resolucion_Laboratorio.pdf", mime="application/pdf", key=f"pdf_{len(st.session_state.messages)}")
                elif "last_auditor_response" in st.session_state and st.session_state.last_auditor_response in message["content"]:
                    pdf_bytes = generar_pdf(message["content"])
                    st.download_button(label="📄 Descargar Evaluación en PDF", data=pdf_bytes, file_name="Evaluacion_Auditor_UNICEN.pdf", mime="application/pdf", key=f"pdf_aud_{len(st.session_state.messages)}")
                elif "**👨‍🏫 Tutor UNICEN (Resolución Libre):**" in message["content"]:
                    pdf_bytes = generar_pdf(message["content"])
                    st.download_button(
                        label="📄 Descargar Resolución en PDF", 
                        data=pdf_bytes, 
                        file_name="Resolucion_Caso_Libre.pdf", 
                        mime="application/pdf", 
                        key=f"pdf_chat_hist_{len(st.session_state.messages)}"
                    )
                elif "# 📊 REPORTE DEL CICLO CONTABLE Y ESTADOS FINANCIEROS FINALES" in message["content"]:
                    pdf_bytes = generar_pdf(message["content"])
                    st.download_button(label="📄 Descargar Balance y EDFF en PDF", data=pdf_bytes, file_name="Proyecto_Ciclo_Contable.pdf", mime="application/pdf", key=f"pdf_chat_hist_{len(st.session_state.messages)}")
                    
                    # --- MANTENER EL BOTÓN DE EXCEL EN MEMORIA ---
                    excel_bytes = generar_excel_ciclo(message["content"], st.session_state.get('project_transactions', []))
                    st.download_button(
                        label="📥 Descargar Planilla de Trabajo (Excel)",
                        data=excel_bytes,
                        file_name=f"Planilla_Contable_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"xlsx_proyecto_final_{len(st.session_state.messages)}"
                    )
    
    def should_run_deep_search(prompt, checkbox_state):
        keywords = ['en la web', 'en internet', 'según impuestos', 'en notebooklm', 'busca en todas']
        return checkbox_state or any(k in prompt.lower() for k in keywords)

    # Input
    if prompt := st.chat_input("Escribe tu consulta o transacción aquí..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
            
        # --- RASTREADOR DE IA PARA ANALÍTICAS ---
        if st.session_state.get("user_id"):
            try:
                user_ref = db.collection('usuarios').document(st.session_state.user_id)
                user_data = user_ref.get().to_dict()
                
                es_auditor = st.session_state.get("auditor_mode", False) 
                
                if es_auditor:
                    user_ref.update({"uso_auditor": user_data.get("uso_auditor", 0) + 1})
                else:
                    user_ref.update({"uso_tutor": user_data.get("uso_tutor", 0) + 1})
            except Exception as e:
                pass
        # ----------------------------------------
        
        with st.chat_message("assistant"):
            response_container = st.empty()
            full_response = ""
            
            # --- 1. PROJECT MODE INTERCEPTION ---
            if st.session_state.get("project_mode", False) and not st.session_state.get("generate_project_balance", False):
                st.session_state.project_transactions.append(prompt)
                full_response = f"✅ Transacción #{len(st.session_state.project_transactions)} guardada. Escribe la siguiente o presiona **'Generar EEFF'** en la barra lateral."
                response_container.markdown(full_response)
                st.session_state.messages.append({"role": "assistant", "content": full_response})
            
            # --- 2. EXAM MODE INTERCEPTION (SILENCIOSO) ---
            elif st.session_state.get("exam_mode", False) and not st.session_state.get("grade_exam_now", False):
                st.session_state.exam_answers.append(prompt)
                full_response = f"✅ Asiento registrado (Respuesta #{len(st.session_state.exam_answers)}). Ingresa el siguiente asiento, o si ya terminaste presiona **'✅ Calificar Examen'** en la barra lateral."
                response_container.markdown(full_response)
                st.session_state.messages.append({"role": "assistant", "content": full_response})

            # 3. --- CHALLENGE MODE INTERCEPTION (RETO AUDITOR) ---
            elif st.session_state.get("auditor_mode", False):
                 with st.spinner("🧐 El Auditor está revisando tu asiento..."):
                    try:
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel('gemini-flash-latest')
                        
                        reglas_actuales = load_tax_rules()
                        case_ref = st.session_state.get("auditor_case", "Caso desconocido")
                        
                        prompt_audit = f"""Eres un Auditor Contable y Docente Universitario. Evalúas a un estudiante. Tu tono es ESTRICTAMENTE PROFESIONAL, OBJETIVO y TÉCNICO.
                        {reglas_actuales}
                        Genera este título exacto: # 1. CALIFICACIÓN: X/100
                        Luego detalla observaciones y errores. Luego muestra la solución correcta en tabla Markdown.
                        El caso es: "{case_ref}". Su respuesta fue: "{prompt}"."""
                        
                        response = model.generate_content(prompt_audit)
                        full_response = response.text.strip()
                        
                        match = re.search(r'CALIFICACIÓN:\s*(\d+)/100', full_response, re.IGNORECASE)
                        if match:
                            score = int(match.group(1))
                            st.session_state.user_xp += score 
                            if db is not None:
                                try:
                                    db.collection('usuarios').document(st.session_state.user_id).update({"xp": st.session_state.user_xp})
                                except: pass

                        st.session_state.auditor_mode = False 
                        st.session_state.last_auditor_response = full_response
                        st.success("Evaluación Completada.")
                    except Exception as e:
                        full_response = f"Error del Auditor: {e}"
                        st.session_state.auditor_mode = False

            # 4. --- TUTOR IA / BÚSQUEDA (MODO NORMAL) ---
            else:
                is_deep_search = should_run_deep_search(prompt, deep_search_active)
                
                if is_deep_search:
                    with st.spinner('Consultando bases de datos...'):
                        nlm_text = search_notebooklm(prompt) or "Sin resultados."
                        try:
                            genai.configure(api_key=api_key)
                            model = genai.GenerativeModel('gemini-flash-latest')
                            response = model.generate_content(f"Alumno pregunta: '{prompt}'. Usa esto: {nlm_text}.")
                            full_response = response.text.strip()
                        except Exception as e:
                            full_response = f"Error: {e}"
                else:
                    with st.spinner("👨‍🏫 Resolviendo o buscando..."):
                        try:
                            genai.configure(api_key=api_key)
                            model = genai.GenerativeModel('gemini-flash-latest')
                            reglas_actuales = load_tax_rules() if 'load_tax_rules' in globals() else ""
                            response_libre = model.generate_content(f"Eres Tutor de UNICEN. Alumno pregunta: '{prompt}'. Aplica norma boliviana. {reglas_actuales}. Crea asiento en tabla Markdown si corresponde.")
                            full_response = "**👨‍🏫 Tutor UNICEN (Resolución Libre):**\n\n" + response_libre.text.strip()
                        except Exception as e:
                            full_response = f"❌ Error: {e}"
            
            # --- IMPRIMIR LA RESPUESTA DE CUALQUIERA DE LOS 4 MODOS ---
            response_container.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})

            # --- BOTONES DE DESCARGA PDF SI CORRESPONDE ---
            if st.session_state.get("last_auditor_response") == full_response:
                pdf_bytes = generar_pdf(full_response)
                st.download_button(label="📄 Descargar Evaluación", data=pdf_bytes, file_name="Evaluacion.pdf", mime="application/pdf", key=f"pdf_aud_gen_{len(st.session_state.messages)}")
            elif "**👨‍🏫 Tutor UNICEN (Resolución Libre):**" in full_response:
                pdf_bytes = generar_pdf(full_response)
                st.download_button(
                    label="📄 Descargar Resolución en PDF",
                    data=pdf_bytes,
                    file_name="Resolucion_Caso_Libre.pdf",
                    mime="application/pdf",
                    key=f"pdf_chat_gen_{len(st.session_state.messages)}"
                )

# =======================================================
    # --- PROCESS EXAM GRADING (EL CALIFICADOR FINAL) ---
    # =======================================================
    if st.session_state.get("grade_exam_now", False):
        st.session_state.grade_exam_now = False 
        st.session_state.exam_mode = False 
        
        with st.chat_message("assistant"):
            with st.spinner("👩‍🏫 El Evaluador IA está revisando tu examen minuciosamente..."):
                try:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('gemini-flash-latest')
                    
                    enunciado_examen = st.session_state.get("exam_questions", "")
                    respuestas_alumno = "\n".join([f"Asiento/Respuesta {i+1}: {r}" for i, r in enumerate(st.session_state.exam_answers)])
                    
                    reglas_actuales = load_tax_rules() if 'load_tax_rules' in globals() else "Aplica normativa boliviana."
                    
                    prompt_calificacion = f"""Eres un Evaluador Contable Estricto Universitario de la UNICEN.
                    El estudiante acaba de terminar su examen práctico.
                    
                    {reglas_actuales}
                    
                    ENUNCIADO ORIGINAL DEL DOCENTE:
                    "{enunciado_examen}"
                    
                    LO QUE EL ALUMNO RESPONDIÓ (Sus asientos):
                    "{respuestas_alumno}"
                    
                    TAREA:
                    1. Analiza cada respuesta del alumno contrastándola con el enunciado. Revisa los cálculos matemáticos (Ej: 87% y 13% del IVA, 3% del IT) y las cuentas usadas.
                    2. Otorga una calificación final estricta sobre 100 puntos. Si hay errores, descuenta puntos.
                    3. Genera un reporte detallado para el alumno:
                       - Qué hizo bien.
                       - Qué hizo mal (errores de cuenta, de monto, de concepto).
                       - Cuál era la solución correcta (Muestra los asientos correctos usando ESTRICTAMENTE tablas Markdown).
                    
                    FORMATO ESTRICTO DE RESPUESTA:
                    Empieza obligatoriamente con este título exacto:
                    # 🎓 RESULTADO DEL EXAMEN
                    **CALIFICACIÓN FINAL:** [Tu nota]/100
                    
                    (Luego continúa con tu retroalimentación).
                    """
                    
                    response = model.generate_content(prompt_calificacion)
                    full_response = response.text.strip()
                    
                    # Actualizar puntos XP y registrar nota oficial en la base de datos
                    match = re.search(r'CALIFICACIÓN FINAL:\*\*?\s*(\d+)/100', full_response, re.IGNORECASE)
                    if match:
                        nota_final = int(match.group(1))
                        st.session_state.user_xp += nota_final
                        if db is not None:
                            try:
                                # 1. Actualizar XP del alumno
                                usuario_ref = db.collection('usuarios').document(st.session_state.user_id)
                                usuario_ref.update({"xp": st.session_state.user_xp})
                                
                                # 2. Enviar la calificación al Libro de Notas
                                user_data = usuario_ref.get().to_dict()
                                registro_nota = {
                                    "alumno_id": st.session_state.user_id,
                                    "nombre_alumno": user_data.get("nombre", "Desconocido"),
                                    "institucion": user_data.get("institucion", "Desconocida"),
                                    "examen_titulo": st.session_state.get("exam_title", "Examen Genérico"),
                                    "nota": nota_final,
                                    "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                }
                                db.collection('calificaciones').add(registro_nota)
                            except: pass
                    
                    st.markdown(full_response)
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
                    
                    pdf_bytes = generar_pdf(full_response)
                    st.download_button(
                        label="📄 Descargar Certificado de Examen (PDF)",
                        data=pdf_bytes,
                        file_name="Reporte_Examen.pdf",
                        mime="application/pdf",
                        key=f"pdf_exam_{len(st.session_state.messages)}"
                    )
                except Exception as e:
                    st.error(f"Error al calificar el examen: {e}")

    # --- PROCESS PROJECT BALANCE ---
    if st.session_state.get("generate_project_balance", False):
        st.session_state.generate_project_balance = False 
        st.session_state.project_mode = False 
        
        with st.chat_message("assistant"):
            with st.spinner("📊 Analizando el ciclo completo y estructurando el Balance de Comprobación..."):
                try:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('gemini-flash-latest')
                    
                    reglas_actuales = load_tax_rules() if 'load_tax_rules' in globals() else "Aplica normativa contable boliviana vigente."
                    transacciones_texto = "\n".join([f"{i+1}. {t}" for i, t in enumerate(st.session_state.project_transactions)])
                    
                    prompt_proyecto = f"""Eres un Tutor Senior de Contabilidad en Bolivia.
                    {reglas_actuales}
                    REGLA DE ORO TRIBUTARIA: Aplica las normativas de impuestos SOLO si la transacción lo requiere explícitamente. ESTÁ ESTRICTAMENTE PROHIBIDO añadir "Notas", consejos o recordatorios al final de tu respuesta sobre retenciones (como el D.S. 4850) si el ejercicio no trata sobre pagos de servicios sin factura. Limítate a resolver el caso.
                    El estudiante ha registrado este ciclo de transacciones:
                    {transacciones_texto}
                    
                    TAREA OBLIGATORIA:
                    1. Genera el LIBRO DIARIO. Es VITAL que crees una tabla Markdown SEPARADA para cada asiento contable.
                    - OBLIGATORIO: Escribe la Glosa justo debajo de CADA tabla como texto en cursiva.
                    - Deja una línea en blanco entre la glosa y el siguiente asiento.
                    - PROHIBIDO agrupar todos los asientos en una sola tabla.
                    
                    Usa EXACTAMENTE esta estructura para CADA transacción individual:
                    
                    | Fecha | Detalle / Cuenta | Debe (Bs.) | Haber (Bs.) |
                    | :--- | :--- | ---: | ---: |
                    | 01/01/2026 | **Asiento N° X** | | |
                    | | Cuenta 1 | 100.000,00 | |
                    | | Cuenta 2 | | 100.000,00 |
                    
                    *Glosa: Escribe aquí la explicación de la transacción.*
                    
                    2. Genera un BALANCE DE COMPROBACIÓN DE SUMAS Y SALDOS usando EXACTAMENTE esta estructura:
                    | N° | Cuenta | Sumas Debe | Sumas Haber | Saldo Deudor | Saldo Acreedor |
                    | :--- | :--- | ---: | ---: | ---: | ---: |
                    
                    3. Genera el ESTADO DE RESULTADOS usando esta estructura:
                    | Concepto | Monto (Bs.) |
                    | :--- | ---: |
                    | **INGRESOS OPERATIVOS** | |
                    | Ventas (Neto de IT y devoluciones) | 0.00 |
                    | **COSTO DE VENTAS** | |
                    | Costo de Mercadería Vendida | (0.00) |
                    | **UTILIDAD BRUTA EN VENTAS** | **0.00** |
                    | **GASTOS OPERATIVOS** | |
                    | (Desglosar gastos) | (0.00) |
                    | **UTILIDAD (O PÉRDIDA) DE LA GESTIÓN** | **0.00** |
                    
                    4. Genera el BALANCE GENERAL usando esta estructura:
                    | ACTIVO | Monto (Bs.) | PASIVO Y PATRIMONIO | Monto (Bs.) |
                    | :--- | ---: | :--- | ---: |
                    | **ACTIVO CORRIENTE** | | **PASIVO CORRIENTE** | |
                    | (Desglosar) | 0.00 | (Desglosar) | 0.00 |
                    | **ACTIVO NO CORRIENTE** | | **PATRIMONIO** | |
                    | (Desglosar) | 0.00 | Capital Social | 0.00 |
                    | | | Utilidad (o Pérdida) de la Gestión | 0.00 |
                    | **TOTAL ACTIVO** | **0.00** | **TOTAL PASIVO Y PATRIMONIO** | **0.00** |
                    
                    REGLAS DE ORO ABSOLUTAS: 
                    - ¡PROHIBIDO omitir símbolos "|" en celdas vacías! Todas las filas de todas las tablas DEBEN empezar y terminar con "|".
                    - La Utilidad/Pérdida del Estado de Resultados DEBE trasladarse exactamente al Patrimonio en el Balance General.
                    - El Balance General DEBE cuadrar perfectamente (Total Activo = Total Pasivo + Patrimonio).
                    
                    Inicia tu respuesta con este título H1 exacto:
                    # 📊 REPORTE DEL CICLO CONTABLE Y ESTADOS FINANCIEROS FINALES
                    """
                    
                    response = model.generate_content(prompt_proyecto)
                    full_response = response.text.strip()
                    
                    st.markdown(full_response)
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
                    
                    pdf_bytes = generar_pdf(full_response)
                    st.download_button(
                        label="📄 Descargar Balance en PDF",
                        data=pdf_bytes,
                        file_name="Proyecto_Ciclo_Contable.pdf",
                        mime="application/pdf",
                        key=f"pdf_proyecto_inmediato_{len(st.session_state.messages)}"
                    )
                    # --- BOTÓN DE EXCEL CON ICONO PROFESIONAL ---
                    excel_bytes = generar_excel_ciclo(full_response, st.session_state.project_transactions)
                    st.download_button(
                        label="📥 Descargar Planilla de Trabajo (Excel)",
                        data=excel_bytes,
                        file_name=f"Planilla_Contable_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"xlsx_proyecto_final_{len(st.session_state.messages)}"
                    )
                except Exception as e:
                    st.error(f"Error al generar el balance: {e}")

if __name__ == "__main__":
    main()

















