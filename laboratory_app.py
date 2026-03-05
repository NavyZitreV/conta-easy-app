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
        pass

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

# --- Helper Functions ---
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
    html_text = html_text.replace('style="text-align: right;"', 'align="right"').replace('style="text-align: left;"', 'align="left"').replace('style="text-align: center;"', 'align="center"')

    pdf.set_font("helvetica", size=10)
    try:
        pdf.write_html(html_text)
    except Exception as e:
        pdf.set_text_color(255, 0, 0)
        pdf.multi_cell(0, 10, f"Error rendering HTML: {e}\n\nFallback Content:\n{markdown_content}")
    return bytes(pdf.output())
    
def generar_excel_ciclo(markdown_text, transacciones):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_enunciados = pd.DataFrame({"N°": range(1, len(transacciones)+1), "Transacción": transacciones})
        df_enunciados.to_excel(writer, sheet_name='Enunciados', index=False)
        
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
        
        if diario_filas:
            df_diario = pd.DataFrame(diario_filas, columns=diario_headers)
            df_diario.to_excel(writer, sheet_name='Libro Diario', index=False)
        else:
            pd.DataFrame(columns=diario_headers).to_excel(writer, sheet_name='Libro Diario', index=False)
        
        for sheet in writer.sheets.values():
            sheet.set_column('A:Z', 22)
    return output.getvalue()

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
        return []

def load_laboratory_cases():
    cases = {}
    try:
        base_path = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(base_path, 'data', 'laboratory_cases.json')
        with open(file_path, 'r', encoding='utf-8') as f:
            cases = json.load(f)
    except Exception: pass
        
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
        except Exception: pass
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
        text_content = content if isinstance(content, str) else content.get('summary', '')
        text_norm = normalize_text(text_content)
        title_norm = normalize_text(title)
        score = 0
        if len(palabras_clave) > 1 and query_clean in text_norm: score += 50
        for palabra in palabras_clave:
            if palabra in title_norm: score += 10
            if palabra in text_norm: score += 3
        if score >= 3:
            idx = text_norm.find(query_clean) if len(palabras_clave) > 1 and query_clean in text_norm else (text_norm.find(palabras_clave[0]) if palabras_clave else 0)
            start_idx = max(0, idx - 100)
            end_idx = min(len(text_content), idx + 800)
            snippet = ("..." if start_idx > 0 else "") + text_content[start_idx:end_idx] + ("..." if end_idx < len(text_content) else "")
            results.append({'topic': title, 'snippet': snippet, 'score': score})
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:3] if results else []

def evaluate_snippet_with_llm(user_query, snippet, api_key):
    if not api_key: return "INSUFICIENTE" 
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-flash-latest')
        sys_p = f'Eres Tutor Contabilidad. Pregunta: "{user_query}". Extractos: "{snippet}". TAREA: Combina info. Si no responde, di INSUFICIENTE.'
        res = model.generate_content(sys_p).text.strip()
        return "INSUFICIENTE" if "INSUFICIENTE" in res.upper() and len(res) < 20 else res
    except Exception as e: raise e

def search_notebooklm(query):
    notebooks = {"CURSO CONTABILIDAD BASICA": "af525325-ca19-4f82-975f-349f01c6a099", "Compendio Tributario": "ead8f2c0-19e9-42dc-8040-c4659126b7e9"}
    combined_results = []
    for title, n_id in notebooks.items():
        try:
            res = subprocess.run(['python', 'scripts/nlm_query_id.py', n_id, query], capture_output=True, text=True, timeout=60)
            if res.returncode == 0 and res.stdout.strip() and "Error:" not in res.stdout.strip()[:20]:
                combined_results.append(f"**Fuente: {title}**\n{res.stdout.strip()}")
        except Exception: continue
    return "\n\n---\n\n".join(combined_results) if combined_results else None

def search_web(query):
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(f"{query} site:gob.bo OR site:auditoresbolivia.com OR site:boliviaimpuestos.com", max_results=3))
            if results:
                summary = "Hallazgos en la web:\n\n"
                for r in results: summary += f"- **{r['title']}**: {r['body']} ([Enlace]({r['href']}))\n"
                return summary
            return None
    except Exception as e: return f"Error web: {e}"

def mostrar_login():
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<div style='text-align: center; padding: 1rem;'><h2 style='color: #003366;'>Bienvenido a CONTA-EASY 🚀</h2><p style='color: #6c757d;'>Inicia sesión o regístrate.</p></div>", unsafe_allow_html=True)
        tab_login, tab_register = st.tabs(["🔑 Iniciar Sesión", "📝 Registrarse"])
        with tab_login:
            correo = st.text_input("Correo Electrónico", key="log_c")
            password = st.text_input("Contraseña", type="password", key="log_p")
            if st.button("Ingresar", type="primary", use_container_width=True):
                if not correo or not password: st.error("Llena todos los campos.")
                elif db is None: st.error("Sin BD.")
                else:
                    query = db.collection('usuarios').where('correo', '==', correo).limit(1).get()
                    if not query: st.error("Usuario no encontrado.")
                    else:
                        u_doc = query[0]
                        u_data = u_doc.to_dict()
                        if u_data.get("estado") == "bloqueado": st.error("Cuenta suspendida.")
                        elif u_data.get("password") == password:
                            st.session_state.user_id = u_doc.id
                            st.session_state.user_xp = u_data.get("xp", 0)
                            st.session_state.user_streak = u_data.get("racha", 0)
                            st.session_state.user_rol = u_data.get("rol", "estudiante")
                            st.session_state.user_institucion = u_data.get("institucion", "UNICEN") 
                            st.rerun()
                        else: st.error("Contraseña incorrecta.")
        with tab_register:
            n_c = st.text_input("Correo", key="reg_c")
            n_n = st.text_input("Nombre", key="reg_n")
            n_car = st.selectbox("Carrera", ["Contaduría Pública", "Ingeniería Financiera", "Administración de Empresas", "Otra"], key="reg_car")
            n_i = st.selectbox("Institución", ["UNICEN", "UNIVALLE", "Otra"], key="reg_i")
            n_p = st.text_input("Contraseña", type="password", key="reg_p")
            if st.button("Crear Cuenta", type="primary", use_container_width=True):
                if not n_c or not n_p or not n_n: st.error("Llena todos los campos.")
                elif db is None: st.error("Sin BD.")
                else:
                    q = db.collection('usuarios').where('correo', '==', n_c).limit(1).get()
                    if q: st.error("Correo ya registrado.")
                    else:
                        _, doc_ref = db.collection('usuarios').add({"correo": n_c, "nombre": n_n, "carrera": n_car, "institucion": n_i, "password": n_p, "xp": 0, "racha": 0, "rol": "estudiante", "estado": "activo"})
                        st.session_state.user_id = doc_ref.id
                        st.session_state.update({"user_xp": 0, "user_streak": 0, "user_rol": "estudiante", "user_institucion": n_i})
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
        col_xp.metric("Experiencia", f"{st.session_state.user_xp} XP")
        col_streak.metric("Racha 🔥", f"{st.session_state.user_streak}")
        st.divider()
        
        with st.sidebar.expander("🏆 Ranking de mi Universidad", expanded=False):
            if db is not None:
                try:
                    ests = db.collection('usuarios').where('rol', '==', 'estudiante').where('institucion', '==', st.session_state.get("user_institucion", "UNICEN")).get()
                    l_ests = [{"nombre": e.to_dict().get("nombre", "A").split()[0], "xp": e.to_dict().get("xp", 0)} for e in ests if e.to_dict().get('xp', 0) > 0]
                    t_5 = sorted(l_ests, key=lambda x: x["xp"], reverse=True)[:5]
                    if not t_5: st.info("Aún no hay alumnos con puntos.")
                    else:
                        for i, a in enumerate(t_5):
                            m = ["🥇", "🥈", "🥉", "🏅", "🏅"][i] if i < 5 else "🏅"
                            st.markdown(f"**{i+1}. {m} {a['nombre']}** - {a['xp']} XP")
                except Exception: pass
        st.sidebar.divider()
        
        u_ref = db.collection('usuarios').document(st.session_state.user_id).get()
        if u_ref.exists and u_ref.to_dict().get("rol") in ["admin", "docente"]:
            st.markdown("### 🛠️ Administración")
            if st.button("📊 Panel de Control", type="secondary"): st.session_state.show_admin_panel = True
            st.divider()

        try: api_key = st.secrets["general"]["GEMINI_API_KEY"]
        except Exception: api_key = ""

        st.header("🔍 Motor de Búsqueda")
        deep_search_active = st.checkbox("Activar Búsqueda Profunda", value=False)
        if st.button("🗑️ Limpiar Chat"):
            st.session_state.messages = []
            for k in ["auditor_mode", "auditor_case", "exam_mode", "exam_answers", "project_mode", "project_transactions"]:
                if k in st.session_state: del st.session_state[k]
            st.rerun()
            
        st.divider()
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            for key in list(st.session_state.keys()): del st.session_state[key]
            st.rerun()

        st.divider()
        st.header("📝 Laboratorio de Casos")
        lab_cases = load_laboratory_cases()
        if lab_cases:
            cat_lab = st.selectbox("Categoría", list(lab_cases.keys()))
            sel_case = st.selectbox("Ejercicio Práctico", lab_cases.get(cat_lab, []))
            st.markdown(get_difficulty_badge(sel_case), unsafe_allow_html=True)
            c_limpio = clean_case_title(sel_case)
            st.session_state.current_active_case = c_limpio
            st.markdown(f"**📝 Caso:** {c_limpio}")
            
            c1, c2 = st.columns(2)
            if c1.button("👨‍🏫 Analizar"):
                st.session_state.messages.append({"role": "user", "content": c_limpio})
                st.session_state.auditor_mode = False 
                with st.spinner("👨‍🏫 Analizando..."):
                    try:
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel('gemini-flash-latest')
                        p_lab = f"""Eres Tutor Contabilidad. Resuelve este caso: "{c_limpio}". {load_tax_rules()} 
                        Usa tablas Markdown estrictas para Diario y Mayores T."""
                        res = model.generate_content(p_lab).text.strip()
                        st.session_state.messages.append({"role": "assistant", "content": res})
                        st.session_state.last_lab_response = res 
                        st.rerun()
                    except Exception as e: st.error(e)
            if c2.button("⚔️ Reto Auditor"):
                st.session_state.pending_sound = "audio/swords.mp3" 
                st.session_state.auditor_mode = True
                st.session_state.auditor_case = c_limpio
                st.session_state.messages.append({"role": "assistant", "content": f"⚔️ **Reto:** *{c_limpio}*\nEscribe tu asiento."})
                st.rerun()

        st.divider()
        st.header("🏢 Proyecto: Ciclo Contable")
        if not st.session_state.get("project_mode", False):
            if st.button("🚀 Iniciar Proyecto Libre"):
                st.session_state.project_mode = True
                t_g = db.collection('usuarios').document(st.session_state.user_id).get().to_dict().get("proyecto_en_curso", []) if db else []
                st.session_state.project_transactions = t_g
                msg = f"☁️ Retomado: {len(t_g)} transacciones." if t_g else "🏢 Escribe transacciones libres en el chat."
                st.session_state.messages.append({"role": "assistant", "content": msg})
                st.rerun()
        else:
            st.info(f"Transacciones: {len(st.session_state.get('project_transactions', []))}")
            if st.button("💾 Guardar Avance"):
                if db: db.collection('usuarios').document(st.session_state.user_id).update({"proyecto_en_curso": st.session_state.project_transactions})
                st.toast("✅ Guardado")
            if st.button("📊 Generar EEFF", type="primary"):
                if st.session_state.project_transactions: st.session_state.generate_project_balance = True
                else: st.warning("Ingresa transacciones.")
            if st.button("❌ Cancelar Proyecto"):
                st.session_state.project_mode = False
                st.session_state.project_transactions = []
                if db: db.collection('usuarios').document(st.session_state.user_id).update({"proyecto_en_curso": []})
                st.rerun()

        # ==========================================
        # NUEVO MÓDULO: EVALUACIÓN (EXÁMENES)
        # ==========================================
        st.divider()
        st.header("🎓 Módulo de Evaluación")
        
        if not st.session_state.get("exam_mode", False):
            with st.expander("📝 Cargar Examen / Plantilla"):
                # --- MAGIA: SOLO LEER DE LA NUBE (FIREBASE) ---
                examenes_disponibles = {}
                if db is not None:
                    try:
                        mi_i = st.session_state.get("user_institucion", "UNICEN")
                        m_r = st.session_state.get("user_rol", "estudiante")
                        c_ref = db.collection('casos_practicos').get() if m_r == "admin" else db.collection('casos_practicos').where('institucion', '==', mi_i).get()
                        for doc in c_ref:
                            cat = doc.to_dict().get('categoria', '')
                            # Filtramos cualquier cosa que no venga del sistema local base
                            if cat: 
                                if cat not in examenes_disponibles: examenes_disponibles[cat] = []
                                examenes_disponibles[cat].append(doc.to_dict().get('enunciado', ''))
                    except Exception: pass

                if examenes_disponibles:
                    ops_ex = ["-- Selecciona un Examen --"]
                    map_ex = {}
                    for cat, casos in examenes_disponibles.items():
                        for c in casos:
                            t_l = clean_case_title(c)
                            etiq = f"[{cat}] {t_l[:40]}..."
                            ops_ex.append(etiq)
                            map_ex[etiq] = t_l
                            
                    ex_sel = st.selectbox("Exámenes:", ops_ex, label_visibility="collapsed")
                    if ex_sel != "-- Selecciona un Examen --":
                        if st.button("⏱️ Iniciar Examen", type="primary"):
                            st.session_state.exam_mode = True
                            st.session_state.exam_questions = map_ex[ex_sel]
                            st.session_state.exam_answers = []
                            # Forzar viñetas visuales
                            p_formt = "* " + st.session_state.exam_questions.replace('\n', '\n\n* ')
                            st.session_state.messages.append({
                                "role": "assistant", 
                                "content": f"🎓 **¡EXAMEN INICIADO!**\n\n**ENUNCIADO:**\n{p_formt}\n\n---\n**INSTRUCCIONES:**\nEscribe abajo tus asientos. Al terminar TODOS, presiona **'✅ Calificar Examen'**."
                            })
                            st.rerun()
                else:
                    st.caption("No hay exámenes en la nube.")
        else:
            st.warning("⏱️ Examen en curso...")
            st.info(f"Respuestas enviadas: {len(st.session_state.get('exam_answers', []))}")
            if st.button("✅ Calificar Examen", type="primary"):
                if st.session_state.exam_answers: st.session_state.grade_exam_now = True; st.rerun()
                else: st.error("Envía al menos una respuesta.")
            if st.button("❌ Abandonar Examen"):
                st.session_state.exam_mode = False
                st.session_state.exam_answers = []
                st.rerun()

    # --- Panel de Administración ---
    if st.session_state.get("show_admin_panel", False):
        st.markdown("---")
        st.header("🛠️ Panel de Administración")
        m_i = st.session_state.get("user_institucion", "UNICEN")
        m_r = st.session_state.get("user_rol", "docente")
        u_ref = db.collection('usuarios').get() if m_r == "admin" else db.collection('usuarios').where('rol', '==', 'estudiante').where('institucion', '==', m_i).get()
        u_list = [u for u in u_ref if u.to_dict().get('rol') != 'admin']

        t_al, t_ca, t_an = st.tabs(["👥 Estudiantes", "📚 Casos", "🧠 Analíticas"])
        with t_al:
            if m_r == "admin":
                with st.expander("📥 Carga Masiva (Excel/CSV)"):
                    a_mas = st.file_uploader("Selecciona archivo", type=['csv', 'xlsx'])
                    if a_mas and st.button("🚀 Subir Usuarios", type="primary"):
                        try:
                            df_m = pd.read_csv(a_mas) if a_mas.name.endswith('.csv') else pd.read_excel(a_mas)
                            df_m.columns = df_m.columns.str.strip().str.upper()
                            req = ["NOMBRE", "CARRERA", "UNIVERSIDAD", "CORREO", "PASSWORD"]
                            if not all(c in df_m.columns for c in req): st.error("Faltan columnas.")
                            else:
                                ext = [d.to_dict().get('correo', '') for d in db.collection('usuarios').get()]
                                a = 0
                                for _, r in df_m.iterrows():
                                    c_n = str(r['CORREO']).strip()
                                    if pd.isna(r['CORREO']) or c_n == "" or c_n in ext: continue
                                    db.collection('usuarios').add({"nombre": str(r['NOMBRE']), "carrera": str(r['CARRERA']), "institucion": str(r['UNIVERSIDAD']), "correo": c_n, "password": str(r['PASSWORD']), "xp": 0, "racha": 0, "rol": "estudiante", "estado": "activo", "acceso_analiticas": False})
                                    ext.append(c_n); a += 1
                                st.success(f"✅ {a} creados.")
                                time.sleep(2); st.rerun()
                        except Exception as e: st.error(e)

            csv_d = "Nombre;Rol;Carrera;Institucion;Correo;XP;Racha\n"
            with st.expander(f"📋 Ver Lista de Usuarios ({len(u_list)})"):
                for u in u_list:
                    d = u.to_dict(); i = u.id
                    c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
                    est = "🔴" if d.get('estado') == "bloqueado" else "🟢"
                    c1.info(f"👤 **{d.get('nombre')}** | XP: {d.get('xp',0)} | {est}")
                    if c2.button("🔑", key=f"p_{i}"): db.collection('usuarios').document(i).update({"password": "123456"}); st.rerun()
                    if c3.button("🔄", key=f"x_{i}"): db.collection('usuarios').document(i).update({"xp": 0, "racha": 0}); st.rerun()
                    if c4.button("🚫/✅", key=f"b_{i}"): db.collection('usuarios').document(i).update({"estado": "activo" if d.get('estado')=="bloqueado" else "bloqueado"}); st.rerun()
                    csv_d += f"{d.get('nombre')};{d.get('rol')};{d.get('carrera')};{d.get('institucion')};{d.get('correo')};{d.get('xp')};{d.get('racha')}\n"
            c1, c2 = st.columns(2)
            if c1.button("❌ Cerrar Panel", use_container_width=True): st.session_state.show_admin_panel = False; st.rerun()
            c2.download_button("📥 Descargar Reporte", data=csv_d.encode('utf-8-sig'), file_name="Reporte.csv", mime="text/csv", use_container_width=True)

        with t_ca:
            with st.form("fc"):
                n_c = st.text_input("Categoría (Ej. 'Examen Final')")
                n_d = st.selectbox("Dificultad", ["[BÁSICO]", "[INTERMEDIO]", "[AVANZADO]"])
                n_e = st.text_area("Enunciado (Usa Enter para separar transacciones)")
                if st.form_submit_button("💾 Guardar") and n_c and n_e:
                    db.collection('casos_practicos').add({"categoria": n_c, "enunciado": f"{n_d} {n_e}", "institucion": m_i})
                    st.success("Guardado!"); time.sleep(1); st.rerun()
            
            c_db = db.collection('casos_practicos').get() if m_r == "admin" else db.collection('casos_practicos').where('institucion', '==', m_i).get()
            for c in c_db:
                c1, c2 = st.columns([5, 1])
                c1.info(f"📁 **{c.to_dict().get('categoria')}**: {c.to_dict().get('enunciado')}")
                if c2.button("🗑️", key=f"d_{c.id}"): db.collection('casos_practicos').document(c.id).delete(); st.rerun()
        
        with t_an:
            st.info("Módulo Analítico Activo.")

    # --- CHAT UI ---
    if "messages" not in st.session_state: st.session_state.messages = []
    if not st.session_state.messages:
        st.markdown("<br><br><div style='text-align: center; padding: 2rem; background-color: white; border-radius: 12px;'><h2 style='color: #003366;'>¡Bienvenido a CONTA-EASY! 🚀</h2><p style='color: #6c757d;'>Tu simulador contable IA.</p></div><br>", unsafe_allow_html=True)

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg == st.session_state.messages[-1] and msg["role"] == "assistant":
                if "last_lab_response" in st.session_state and st.session_state.last_lab_response in msg["content"]:
                    st.download_button("📄 PDF", generar_pdf(msg["content"]), "Lab.pdf", "application/pdf", key=f"p1_{len(st.session_state.messages)}")
                elif "last_auditor_response" in st.session_state and st.session_state.last_auditor_response in msg["content"]:
                    st.download_button("📄 PDF Eval", generar_pdf(msg["content"]), "Eval.pdf", "application/pdf", key=f"p2_{len(st.session_state.messages)}")
                elif "**👨‍🏫 Tutor UNICEN" in msg["content"]:
                    st.download_button("📄 PDF Tutor", generar_pdf(msg["content"]), "Tutor.pdf", "application/pdf", key=f"p3_{len(st.session_state.messages)}")
                elif "# 📊 REPORTE DEL CICLO" in msg["content"]:
                    st.download_button("📄 PDF Balance", generar_pdf(msg["content"]), "Balance.pdf", "application/pdf", key=f"p4_{len(st.session_state.messages)}")
                    st.download_button("📥 Excel", generar_excel_ciclo(msg["content"], st.session_state.get('project_transactions', [])), "Planilla.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"x1_{len(st.session_state.messages)}")

    # ==========================================
    # EL CEREBRO DEL CHAT (EL SEMÁFORO CORRECTO)
    # ==========================================
    if prompt := st.chat_input("Escribe tu consulta o asiento aquí..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        
        with st.chat_message("assistant"):
            resp_box = st.empty()
            f_resp = ""
            
            # 1. MODO PROYECTO LIBRE
            if st.session_state.get("project_mode", False):
                st.session_state.project_transactions.append(prompt)
                f_resp = f"✅ Transacción #{len(st.session_state.project_transactions)} guardada. Sigue escribiendo o presiona **Generar EEFF**."
            
            # 2. MODO EXAMEN (SILENCIOSO)
            elif st.session_state.get("exam_mode", False):
                st.session_state.exam_answers.append(prompt)
                f_resp = f"✅ Asiento registrado (Respuesta #{len(st.session_state.exam_answers)}). Ingresa el siguiente asiento, o si ya terminaste presiona **'✅ Calificar Examen'**."
            
            # 3. MODO AUDITORÍA (UN SOLO ASIENTO)
            elif st.session_state.get("auditor_mode", False):
                 with st.spinner("🧐 Auditando..."):
                    try:
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel('gemini-flash-latest')
                        p_aud = f"""Eres Auditor Contable. Tono ESTRICTO. {load_tax_rules()} 
                        Título obligatorio: # 1. CALIFICACIÓN: X/100. 
                        Caso: "{st.session_state.get("auditor_case")}". Respuesta: "{prompt}"."""
                        f_resp = model.generate_content(p_aud).text.strip()
                        st.session_state.auditor_mode = False 
                        st.session_state.last_auditor_response = f_resp
                        
                        m = re.search(r'CALIFICACIÓN:\s*(\d+)', f_resp, re.IGNORECASE)
                        if m and db:
                            st.session_state.user_xp += int(m.group(1))
                            db.collection('usuarios').document(st.session_state.user_id).update({"xp": st.session_state.user_xp})
                    except Exception as e: f_resp = f"Error: {e}"; st.session_state.auditor_mode = False

            # 4. MODO TUTOR LIBRE (POR DEFECTO)
            else:
                with st.spinner("👨‍🏫 Resolviendo..."):
                    try:
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel('gemini-flash-latest')
                        f_resp = "**👨‍🏫 Tutor UNICEN:**\n\n" + model.generate_content(f"Tutor UNICEN. Resuelve: '{prompt}'. {load_tax_rules()} Usa Markdown.").text.strip()
                    except Exception as e: f_resp = f"Error: {e}"
            
            resp_box.markdown(f_resp)
            st.session_state.messages.append({"role": "assistant", "content": f_resp})
            if "last_auditor_response" in st.session_state and st.session_state.last_auditor_response == f_resp:
                st.download_button("📄 PDF Eval", generar_pdf(f_resp), "Eval.pdf", "application/pdf", key=f"pd_{len(st.session_state.messages)}")
            elif "**👨‍🏫 Tutor UNICEN" in f_resp:
                st.download_button("📄 PDF Tutor", generar_pdf(f_resp), "Tutor.pdf", "application/pdf", key=f"pd2_{len(st.session_state.messages)}")

    # ==========================================
    # GENERADORES FINALES (BOTONES DE LA BARRA LATERAL)
    # ==========================================
    
    # --- CALIFICADOR DE EXÁMENES ---
    if st.session_state.get("grade_exam_now", False):
        st.session_state.grade_exam_now = False 
        st.session_state.exam_mode = False 
        with st.chat_message("assistant"):
            with st.spinner("👩‍🏫 Calificando examen..."):
                try:
                    genai.configure(api_key=api_key)
                    m = genai.GenerativeModel('gemini-flash-latest')
                    en_ex = st.session_state.get("exam_questions", "")
                    re_al = "\n".join([f"Asiento {i+1}: {r}" for i, r in enumerate(st.session_state.exam_answers)])
                    p_calif = f"""Evaluador Estricto UNICEN. {load_tax_rules()}
                    ENUNCIADO: "{en_ex}"
                    RESPUESTAS ALUMNO: "{re_al}"
                    Analiza, da nota sobre 100 y corrige en tablas Markdown.
                    Título exacto OBLIGATORIO: # 🎓 RESULTADO DEL EXAMEN\n**CALIFICACIÓN FINAL:** [Nota]/100"""
                    
                    res_f = m.generate_content(p_calif).text.strip()
                    st.markdown(res_f)
                    st.session_state.messages.append({"role": "assistant", "content": res_f})
                    
                    mt = re.search(r'CALIFICACIÓN FINAL:\*\*?\s*(\d+)', res_f, re.IGNORECASE)
                    if mt and db:
                        st.session_state.user_xp += int(mt.group(1))
                        db.collection('usuarios').document(st.session_state.user_id).update({"xp": st.session_state.user_xp})
                        
                    st.download_button("📄 Certificado", generar_pdf(res_f), "Cert.pdf", "application/pdf", key=f"cx_{len(st.session_state.messages)}")
                except Exception as e: st.error(e)

    # --- GENERADOR DE PROYECTO (BALANCES) ---
    if st.session_state.get("generate_project_balance", False):
        st.session_state.generate_project_balance = False 
        st.session_state.project_mode = False 
        with st.chat_message("assistant"):
            with st.spinner("📊 Generando EEFF..."):
                try:
                    genai.configure(api_key=api_key)
                    m = genai.GenerativeModel('gemini-flash-latest')
                    tr_txt = "\n".join([f"{i+1}. {t}" for i, t in enumerate(st.session_state.project_transactions)])
                    p_proy = f"""Tutor Senior Bolivia. {load_tax_rules()}
                    Transacciones: {tr_txt}
                    Genera 1. Diario 2. Balance Comprobación 3. Resultados 4. Balance General en Tablas Markdown perfectas.
                    Título exacto: # 📊 REPORTE DEL CICLO CONTABLE Y ESTADOS FINANCIEROS FINALES"""
                    res_p = m.generate_content(p_proy).text.strip()
                    
                    st.markdown(res_p)
                    st.session_state.messages.append({"role": "assistant", "content": res_p})
                    st.download_button("📄 PDF EEFF", generar_pdf(res_p), "EEFF.pdf", "application/pdf", key=f"e1_{len(st.session_state.messages)}")
                    st.download_button("📥 Excel", generar_excel_ciclo(res_p, st.session_state.project_transactions), "Planilla.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"e2_{len(st.session_state.messages)}")
                except Exception as e: st.error(e)

if __name__ == "__main__":
    main()
