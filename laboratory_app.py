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
    header {visibility: hidden;}

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
        
        # 2. Escanear el texto buscando tablas Markdown
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
        
        # 3. Clasificar cada tabla encontrada
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
                            st.success("¡Sesión iniciada exitosamente!")
                            st.rerun()
                        else:
                            st.error("Contraseña incorrecta.")
                            
        with tab_register:
            nuevo_correo = st.text_input("Correo Electrónico", key="reg_correo")
            nombre_reg = st.text_input("Nombre Completo", key="reg_nombre")
            carrera_reg = st.selectbox("Carrera", ["Contaduría Pública", "Ingeniería Financiera", "Administración de Empresas", "Otra"], key="reg_carrera")
            institucion_reg = st.selectbox("Institución", ["UNICEN", "UNIVALLE", "Otra"], key="reg_inst")
            nuevo_password = st.text_input("Contraseña", type="password", key="reg_pass")
            
            if st.button("Crear Cuenta", type="primary", use_container_width=True):
                if not nuevo_correo or not nuevo_password or not nombre_reg:
                    st.error("Por favor llena todos los campos, incluyendo tu nombre.")
                elif db is None:
                    st.error("Base de datos no disponible.")
                else:
                    usuarios_ref = db.collection('usuarios')
                    query = usuarios_ref.where('correo', '==', nuevo_correo).limit(1).get()
                    if len(query) > 0:
                        st.error("Ese correo ya está registrado.")
                    else:
                        nuevo_usuario = {
                            "correo": nuevo_correo,
                            "nombre": nombre_reg,
                            "carrera": carrera_reg,
                            "institucion": institucion_reg,
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
                        st.session_state.user_institucion = institucion_reg
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

    # --- BARRA LATERAL ---
    with st.sidebar:
        st.header("Configuración")
        
        st.markdown("### 🏆 Tu Progreso")
        col_xp, col_streak = st.columns(2)
        with col_xp:
            st.metric(label="Experiencia", value=f"{st.session_state.user_xp} XP")
        with col_streak:
            st.metric(label="Racha 🔥", value=f"{st.session_state.user_streak}")
        st.divider()
        
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
                        1. Cambia radicalmente los montos monetarios.
                        2. Cambia los nombres de las empresas, bancos o personas.
                        3. Cambia la fecha.
                        4. Puedes agregar un pequeño detalle extra.
                        5. MANTÉN exactamente el mismo nivel de complejidad contable.
                        6. DEVUELVE ÚNICAMENTE EL TEXTO DEL NUEVO ENUNCIADO.
                        
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
                        {reglas_actuales}
                        TAREA: Resuelve el caso generando Libro Diario, explicación, Mayor en T, e impacto en EEFF con tablas Markdown perfectas."""
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
                st.session_state.messages.append({"role": "assistant", "content": f"⚔️ **¡Reto Aceptado!**\n\nCaso: *{st.session_state.current_active_case}*\n\nEscribe tu asiento contable propuesto. Actuaré como un Auditor estricto."})
                st.rerun()
                
        else:
            st.warning("⚠️ No se encontraron casos de laboratorio.")

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
                    st.session_state.messages.append({"role": "assistant", "content": f"☁️ **¡Proyecto Retomado!**\n\nHe recuperado **{len(transacciones_guardadas)} transacciones** de la nube."})
                else:
                    st.session_state.messages.append({"role": "assistant", "content": "🏢 **¡Modo Proyecto Iniciado!**\n\nEscribe tus transacciones una por una. Usa **'💾 Guardar Avance'** para no perder el progreso."})
                st.rerun()
        else:
            st.info(f"Transacciones registradas: {len(st.session_state.get('project_transactions', []))}")
            
            # --- NUEVO BOTÓN: GUARDAR AVANCE ---
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

    # --- Lógica para mostrar el Panel de Administración ---
    if st.session_state.get("show_admin_panel", False):
        st.markdown("---")
        st.header("🛠️ Panel de Administración y Analíticas")
        
        mi_institucion = st.session_state.get("user_institucion", "UNICEN")
        mi_rol = st.session_state.get("user_rol", "docente")
        
        if mi_rol == "admin":
            st.success("👑 MODO SUPER ADMIN: Viendo datos globales.")
            usuarios_ref = db.collection('usuarios').get()
        else:
            st.info(f"👨‍🏫 MODO DOCENTE: Viendo datos de {mi_institucion}.")
            usuarios_ref = db.collection('usuarios').where('rol', '==', 'estudiante').where('institucion', '==', mi_institucion).get()
            
        usuarios_lista = [u for u in usuarios_ref if u.to_dict().get('rol') != 'admin']

        tab_alumnos, tab_casos, tab_analiticas = st.tabs(["👥 Gestión de Estudiantes", "📚 Gestor de Casos", "🧠 Analíticas"])
        
        # ==========================================
        # PESTAÑA 1: ESTUDIANTES Y DOCENTES (CARGA MASIVA)
        # ==========================================
        with tab_alumnos:
            if mi_rol == "admin":
                with st.expander("📥 Carga Masiva de Usuarios (Excel/CSV)"):
                    st.markdown("Las columnas en la primera fila del Excel deben llamarse **EXACTAMENTE** así:")
                    st.code("NOMBRE | CARRERA | UNIVERSIDAD | CORREO | PASSWORD")
                    
                    archivo_masivo = st.file_uploader("Selecciona tu archivo Excel", type=['csv', 'xlsx'])
                    
                    if archivo_masivo is not None:
                        if st.button("🚀 Procesar y Subir Usuarios", type="primary"):
                            with st.spinner("Leyendo archivo y subiendo a la nube..."):
                                try:
                                    if archivo_masivo.name.endswith('.csv'):
                                        df_masivo = pd.read_csv(archivo_masivo)
                                    else:
                                        df_masivo = pd.read_excel(archivo_masivo)
                                    
                                    df_masivo.columns = df_masivo.columns.str.strip().str.upper()
                                    esperadas = ["NOMBRE", "CARRERA", "UNIVERSIDAD", "CORREO", "PASSWORD"]
                                    
                                    if not all(col in df_masivo.columns for col in esperadas):
                                        st.error("⚠️ Error: Faltan columnas. Revisa que diga: NOMBRE, CARRERA, UNIVERSIDAD, CORREO, PASSWORD.")
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
                                                "xp": 0, "racha": 0, "rol": "estudiante", "estado": "activo", "acceso_analiticas": False
                                            })
                                            correos_existentes.append(correo_nuevo)
                                            agregados += 1
                                        
                                        st.success(f"✅ Carga completada: {agregados} alumnos creados | {duplicados} omitidos.")
                                        time.sleep(3)
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Error al procesar el archivo: {e}")

            csv_data = "Nombre Completo;Rol;Carrera;Institucion;Correo Electronico;Experiencia (XP);Racha (Dias)\n"
            st.write(f"**Total de usuarios encontrados:** {len(usuarios_lista)}")
            
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
                nueva_categoria = st.text_input("Categoría (Ej. 'Ajustes Contables')")
                nivel_dificultad = st.selectbox("Nivel de Dificultad", ["[BÁSICO]", "[INTERMEDIO]", "[AVANZADO]"])
                nuevo_enunciado = st.text_area("Enunciado del Caso Práctico")
                
                if st.form_submit_button("💾 Guardar Caso", type="primary"):
                    if nueva_categoria and nuevo_enunciado:
                        nuevo_documento = {
                            "categoria": nueva_categoria,
                            "enunciado": f"{nivel_dificultad} {nuevo_enunciado}",
                            "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "institucion": mi_institucion
                        }
                        db.collection('casos_practicos').add(nuevo_documento)
                        st.success("¡Caso guardado!")
                        time.sleep(1.5)
                        st.rerun()
                        
            st.divider()
            st.markdown("### 📚 Casos Subidos en la Nube")
            try:
                if mi_rol == "admin":
                    casos_db = db.collection('casos_practicos').get()
                else:
                    casos_db = db.collection('casos_practicos').where('institucion', '==', mi_institucion).get()
                    
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
                st.warning("🔒 No tienes acceso al módulo de analíticas.")
            else:
                st.subheader(f"🧠 Inteligencia Académica - {mi_institucion if mi_rol != 'admin' else 'Global'}")
                
                estudiantes = [u.to_dict() for u in usuarios_lista if u.to_dict().get('rol') == 'estudiante']
                
                if len(estudiantes) == 0:
                    st.info("No hay suficientes datos de estudiantes.")
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
                    col_top, col_riesgo = st.columns(2)
                    with col_top:
                        st.markdown("### 🏆 Top 5 - Cuadro de Honor")
                        estudiantes_ordenados = sorted(estudiantes, key=lambda x: x.get('xp', 0), reverse=True)[:5]
                        datos_grafico = {e.get('nombre', 'Anónimo'): e.get('xp', 0) for e in estudiantes_ordenados if e.get('xp', 0) > 0}
                        if datos_grafico: st.bar_chart(datos_grafico)
                            
                    with col_riesgo:
                        st.markdown("### 🚨 Radar de Alerta Temprana")
                        alumnos_riesgo = [e for e in estudiantes if e.get('xp', 0) == 0]
                        if len(alumnos_riesgo) > 0:
                            for ar in alumnos_riesgo:
                                st.error(f"⚠️ **{ar.get('nombre')}** \n\n ✉️ {ar.get('correo')}")
                        else:
                            st.success("¡Excelente! Todos los alumnos tienen participación activa.")
                            
                    st.divider()
                    st.markdown("### 🤖 Comportamiento de Aprendizaje (Uso de IA)")
                    
                    total_tutor = sum(e.get('uso_tutor', 0) for e in estudiantes)
                    total_auditor = sum(e.get('uso_auditor', 0) for e in estudiantes)
                    
                    col_t1, col_t2 = st.columns(2)
                    with col_t1: st.info(f"🧑‍🏫 **Tutor Analista:** {total_tutor} consultas")
                    with col_t2: st.success(f"🕵️ **Reto Auditor:** {total_auditor} intentos")
                        
                    if total_tutor > 0 or total_auditor > 0:
                        st.bar_chart({"Tutor Analista": total_tutor, "Reto Auditor": total_auditor})
                        
                    st.divider()
                    st.markdown("### 🌡️ Termómetro de Rendimiento por Temas")
                    rendimiento_global = {}
                    for e in estudiantes:
                        for cat, xp_ganada in e.get('rendimiento_categorias', {}).items():
                            rendimiento_global[cat] = rendimiento_global.get(cat, 0) + xp_ganada
                    if rendimiento_global: st.bar_chart(rendimiento_global)

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
                </div>
                """, unsafe_allow_html=True
            )

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
            if message == st.session_state.messages[-1] and message["role"] == "assistant":
                if "last_lab_response" in st.session_state and st.session_state.last_lab_response in message["content"]:
                    pdf_bytes = generar_pdf(message["content"])
                    st.download_button(label="📄 Descargar PDF", data=pdf_bytes, file_name="Resolucion_Laboratorio.pdf", mime="application/pdf", key=f"pdf_{len(st.session_state.messages)}")
                elif "last_auditor_response" in st.session_state and st.session_state.last_auditor_response in message["content"]:
                    pdf_bytes = generar_pdf(message["content"])
                    st.download_button(label="📄 Descargar Evaluación PDF", data=pdf_bytes, file_name="Evaluacion_Auditor.pdf", mime="application/pdf", key=f"pdf_aud_{len(st.session_state.messages)}")
                elif "**👨‍🏫 Tutor UNICEN (Resolución Libre):**" in message["content"]:
                    pdf_bytes = generar_pdf(message["content"])
                    st.download_button(label="📄 Descargar Resolución PDF", data=pdf_bytes, file_name="Resolucion_Libre.pdf", mime="application/pdf", key=f"pdf_chat_hist_{len(st.session_state.messages)}")
                elif "# 📊 REPORTE DEL CICLO CONTABLE Y ESTADOS FINANCIEROS FINALES" in message["content"]:
                    pdf_bytes = generar_pdf(message["content"])
                    st.download_button(label="📄 Descargar Balance PDF", data=pdf_bytes, file_name="Proyecto_Ciclo.pdf", mime="application/pdf", key=f"pdf_chat_hist_{len(st.session_state.messages)}")
                    excel_bytes = generar_excel_ciclo(message["content"], st.session_state.get('project_transactions', []))
                    st.download_button(label="📥 Descargar Planilla Excel", data=excel_bytes, file_name=f"Planilla_Contable.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"xlsx_chat_hist_{len(st.session_state.messages)}")
    
    def should_run_deep_search(prompt, checkbox_state):
        keywords = ['en la web', 'en internet', 'según impuestos', 'en notebooklm', 'busca en todas']
        return checkbox_state or any(k in prompt.lower() for k in keywords)

    if prompt := st.chat_input("Escribe tu consulta o transacción aquí..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
            
        if st.session_state.get("user_id"):
            try:
                user_ref = db.collection('usuarios').document(st.session_state.user_id)
                user_data = user_ref.get().to_dict()
                if st.session_state.get("auditor_mode", False):
                    user_ref.update({"uso_auditor": user_data.get("uso_auditor", 0) + 1})
                else:
                    user_ref.update({"uso_tutor": user_data.get("uso_tutor", 0) + 1})
            except Exception: pass
        
        with st.chat_message("assistant"):
            response_container = st.empty()
            full_response = ""
            
            if st.session_state.get("project_mode", False) and not st.session_state.get("generate_project_balance", False):
                st.session_state.project_transactions.append(prompt)
                full_response = f"✅ Transacción #{len(st.session_state.project_transactions)} guardada. Escribe la siguiente o presiona **'Generar EEFF'**."
                response_container.markdown(full_response)
                st.session_state.messages.append({"role": "assistant", "content": full_response})
            
            elif st.session_state.get("auditor_mode", False):
                 with st.spinner("🧐 El Auditor está revisando..."):
                    try:
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel('gemini-flash-latest')
                        prompt_audit = f"""Eres un Auditor Contable. Evalúas al estudiante. Tono TÉCNICO. Caso: "{st.session_state.get('auditor_case')}". Respuesta alumno: "{prompt}". Califica sobre 100 y da formato Markdown."""
                        response = model.generate_content(prompt_audit)
                        full_response = response.text.strip()
                        
                        match = re.search(r'CALIFICACIÓN:\s*(\d+)/100', full_response, re.IGNORECASE)
                        if match:
                            score = int(match.group(1))
                            st.session_state.user_xp += score 
                            if score >= 80:
                                st.session_state.user_streak += 1
                                st.balloons() 
                                st.toast(f"¡Excelente! +{score} XP. Racha 🔥", icon="🔥")
                            else:
                                st.session_state.user_streak = 0
                                st.toast(f"+{score} XP. Racha a cero.", icon="🧊")
                                
                            if db is not None:
                                try:
                                    user_ref = db.collection('usuarios').document(st.session_state.user_id)
                                    cat = st.session_state.get("categoria", "General")
                                    user_data = user_ref.get().to_dict()
                                    rend = user_data.get("rendimiento_categorias", {})
                                    rend[cat] = rend.get(cat, 0) + score
                                    user_ref.update({"xp": st.session_state.user_xp, "racha": st.session_state.user_streak, "rendimiento_categorias": rend})
                                except: pass

                        st.session_state.auditor_mode = False 
                        st.session_state.last_auditor_response = full_response
                    except Exception as e:
                        full_response = f"Error del Auditor: {e}"
                        st.session_state.auditor_mode = False

            else:
                is_deep_search = should_run_deep_search(prompt, deep_search_active)
                
                if is_deep_search:
                    with st.spinner('Consultando todas las bases...'):
                        local_candidates = search_local(prompt, load_local_data())
                        local_text = "".join([f"\n--- EXTRACTO {idx+1} ---\n{c['snippet']}" for idx, c in enumerate(local_candidates)]) if local_candidates else "Sin resultados locales."
                        nlm_text = search_notebooklm(prompt) or "Sin resultados en NotebookLM."
                        web_text = search_web(prompt) or "Sin resultados en la Web."
                        
                        master_context = f"[LOCAL]:\n{local_text}\n[NOTEBOOKLM]:\n{nlm_text}\n[WEB]:\n{web_text}"
                        try:
                            genai.configure(api_key=api_key)
                            model = genai.GenerativeModel('gemini-flash-latest')
                            response = model.generate_content(f"Alumno preguntó: '{prompt}'. Contexto: {master_context}. TAREA: Integra teórica, legal y normativa oficial.")
                            full_response = response.text.strip()
                        except Exception as e:
                            full_response = f"Error IA: {e}"
                else:
                    local_candidates = search_local(prompt, load_local_data())
                    should_escalate = True
                    
                    if local_candidates:
                        combined_snippets = ""
                        with st.expander(f"📄 Documentos encontrados ({len(local_candidates)})"):
                            for idx, cand in enumerate(local_candidates):
                                st.markdown(f"**{idx+1}. {cand['topic']}** (Score: {cand['score']})")
                                combined_snippets += f"\n{cand['snippet']}"

                        with st.spinner("👩‍🏫 Analizando material..."):
                            try:
                                llm_verdict = evaluate_snippet_with_llm(prompt, combined_snippets, api_key)
                                if llm_verdict != "INSUFICIENTE":
                                    full_response = f"**Tutor UNICEN:**\n\n{llm_verdict}"
                                    should_escalate = False 
                            except Exception as e:
                                st.error(f"Error IA: {e}")
                                should_escalate = False 

                    if should_escalate:
                        with st.spinner("🤖 Consultando base extendida (NotebookLM)..."):
                            nlm_result = search_notebooklm(prompt)
                        if nlm_result:
                            full_response = f"**Respuesta NotebookLM:**\n\n{nlm_result}"
                        else:
                            with st.spinner("🌐 Buscando web..."):
                                web_result = search_web(prompt)
                            if web_result:
                                full_response = f"**Web (Bolivia):**\n\n{web_result}"
                            else:
                                with st.spinner("👨‍🏫 Resolviendo caso práctico libre..."):
                                    try:
                                        genai.configure(api_key=api_key)
                                        model = genai.GenerativeModel('gemini-flash-latest')
                                        response_libre = model.generate_content(f"Tutor UNICEN. Alumno plantea: '{prompt}'. Resuelve con tablas Markdown (Diario, Mayores, EEFF).")
                                        full_response = "**👨‍🏫 Tutor UNICEN (Resolución Libre):**\n\n" + response_libre.text.strip()
                                    except Exception as e:
                                        full_response = f"❌ Error IA: {e}"
            
            response_container.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})

            if st.session_state.get("last_auditor_response") == full_response:
                pdf_bytes = generar_pdf(full_response)
                st.download_button(label="📄 Descargar Evaluación PDF", data=pdf_bytes, file_name="Evaluacion.pdf", mime="application/pdf", key=f"pdf_aud_gen_{len(st.session_state.messages)}")
            elif "**👨‍🏫 Tutor UNICEN (Resolución Libre):**" in full_response:
                pdf_bytes = generar_pdf(full_response)
                st.download_button(label="📄 Descargar Resolución PDF", data=pdf_bytes, file_name="Resolucion_Libre.pdf", mime="application/pdf", key=f"pdf_chat_gen_{len(st.session_state.messages)}")

    if st.session_state.get("generate_project_balance", False):
        st.session_state.generate_project_balance = False 
        st.session_state.project_mode = False 
        
        with st.chat_message("assistant"):
            with st.spinner("📊 Analizando el ciclo completo y estructurando..."):
                try:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('gemini-flash-latest')
                    trans_text = "\n".join([f"{i+1}. {t}" for i, t in enumerate(st.session_state.project_transactions)])
                    prompt_proyecto = f"""Eres Tutor Contable Bolivia. Transacciones: {trans_text}.
                    Genera: 1. Libro Diario 2. Balance Comprobación 3. Estado Resultados 4. Balance General.
                    Todo en tablas Markdown perfectas. Título H1: # 📊 REPORTE DEL CICLO CONTABLE Y ESTADOS FINANCIEROS FINALES"""
                    
                    response = model.generate_content(prompt_proyecto)
                    full_response = response.text.strip()
                    st.markdown(full_response)
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
                    
                    pdf_bytes = generar_pdf(full_response)
                    st.download_button(label="📄 Descargar Balance PDF", data=pdf_bytes, file_name="Proyecto_Ciclo.pdf", mime="application/pdf", key=f"pdf_proyecto_{len(st.session_state.messages)}")
                    excel_bytes = generar_excel_ciclo(full_response, st.session_state.project_transactions)
                    st.download_button(label="📥 Descargar Planilla Excel", data=excel_bytes, file_name=f"Planilla_Contable.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"xlsx_proyecto_{len(st.session_state.messages)}")
                except Exception as e:
                    st.error(f"Error generando balance: {e}")

if __name__ == "__main__":
    main()
