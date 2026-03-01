import streamlit as st
import json
import os
import subprocess
import time
from datetime import datetime
import unicodedata
import random
import base64
import streamlit.components.v1 as components

def reproducir_sonido(file_path):
    try:
        with open(file_path, "rb") as f:
            data = f.read()
            b64 = base64.b64encode(data).decode()
        
        # Inyección de JavaScript para forzar la reproducción
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
    /* Importar fuente moderna */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* Fondo principal y ocultar elementos de Streamlit */
    .stApp {
        background-color: #f8f9fa;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    /* Estilos para los mensajes del chat */
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
    
    /* Diferenciar Avatar del Usuario vs IA */
    [data-testid="chatAvatarIcon-user"] {
        background-color: #003366 !important; /* Azul Corporativo */
    }
    [data-testid="chatAvatarIcon-assistant"] {
        background-color: #198754 !important; /* Verde Éxito */
    }

    /* Estilizar los botones de la barra lateral */
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
    
    /* Botón primario (Generar EEFF) */
    [data-testid="baseButton-primary"] {
        background-color: #003366 !important;
        color: white !important;
    }
    [data-testid="baseButton-primary"]:hover {
        background-color: #002244 !important;
    }

    /* Estilo de las métricas (Gamificación) */
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

import google.generativeai as genai
from fpdf import FPDF
import markdown

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
    # 1. ESCUDO ABSOLUTO ANTI-EMOJIS Y CARACTERES NO SOPORTADOS
    markdown_content = markdown_content.replace('•', '-').replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'").replace('–', '-').replace('—', '-')
    # Forzar codificación estricta a latin-1 eliminando lo que la fuente Helvetica no soporte
    markdown_content = markdown_content.encode('latin-1', 'ignore').decode('latin-1')

    class PDF(FPDF):
        def header(self):
            # Insertar Logo (Manejar excepción por si no encuentra la ruta)
            try:
                # Assuming logo.png is in img/ folder relative to script
                self.image('img/Logo.png', 10, 4, 22) # x, y, ancho en mm
            except Exception:
                pass 
            
            self.set_font('helvetica', 'B', 15)
            self.cell(25) # Espacio para que el texto no pise el logo
            self.cell(0, 8, 'UNIVERSIDAD CENTRAL - UNICEN', border=0, ln=1, align='C')
            
            self.set_font('helvetica', 'I', 10)
            self.cell(25)
            self.cell(0, 8, 'Laboratorio Contable - Reporte de Práctica IA', border=0, ln=1, align='C')
            
            self.set_draw_color(0, 51, 102) # Línea azul oscuro
            self.line(10, 28, 200, 28)
            self.ln(15)
            
        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'R')

    pdf = PDF()
    pdf.add_page()
    
    import re
    
    # 2. CONVERSIÓN SIMPLE A HTML
    html_text = markdown.markdown(markdown_content, extensions=['tables'])

    # 3. INTERLINEADO Y BORDES DE TABLAS
    html_text = html_text.replace('</p>', '</p><br>')
    html_text = html_text.replace('</li>', '</li><br>')
    html_text = re.sub(r'<table[^>]*>', '<br><table border="1" width="100%">', html_text)
    html_text = html_text.replace('</table>', '</table><br>')

    # Dar formato de "Corrector de Examen" a los títulos principales (H1 y H2)
    # Forzar títulos grandes (H1 y H2) a color rojo oscuro (#990000)
    html_text = re.sub(r'<h1[^>]*>(.*?)</h1>', r'<h1><font color="#990000">\1</font></h1>', html_text, flags=re.IGNORECASE)
    html_text = re.sub(r'<h2[^>]*>(.*?)</h2>', r'<h2><font color="#990000">\1</font></h2>', html_text, flags=re.IGNORECASE)
    
    # Limpieza de seguridad: Si el LLM escribe la calificación entre corchetes sin H1, la convertimos a H1 Rojo
    html_text = re.sub(r'\[CALIFICACIÓN:\s*([^\]]+)\]', r'<h1><font color="#990000">1. CALIFICACIÓN: \1</font></h1>', html_text, flags=re.IGNORECASE)

    # 4. TRADUCCIÓN DE ALINEACIÓN PARA FPDF2
    html_text = html_text.replace('style="text-align: right;"', 'align="right"')
    html_text = html_text.replace('style="text-align: left;"', 'align="left"')
    html_text = html_text.replace('style="text-align: center;"', 'align="center"')

    # 5. CREACIÓN DEL DOCUMENTO
    pdf.set_font("helvetica", size=10)

    try:
        pdf.write_html(html_text)
    except Exception as e:
        # Fallback simple en caso de emergencia extrema
        pdf.set_text_color(255, 0, 0)
        pdf.multi_cell(0, 10, f"Error rendering HTML: {e}\n\nFallback Content:\n{markdown_content}")
        pdf.set_text_color(0, 0, 0)

    return bytes(pdf.output())

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

@st.cache_data
def load_laboratory_cases():
    try:
        base_path = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(base_path, 'data', 'laboratory_cases.json')
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error(f"Error: No se encontró el archivo en {file_path}")
        return {}
    except json.JSONDecodeError as e:
        st.error(f"Error descifrando JSON: {e}")
        return {}

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
        
        # 1. Exact Phrase Match (High Priority)
        if len(palabras_clave) > 1 and query_clean in text_norm:
            score += 50
        
        # 2. Keyword Matching
        for palabra in palabras_clave:
            if palabra in title_norm:
                score += 10
            if palabra in text_norm:
                score += 3
                
        # UMBRAL RELAJADO (User Request): Score >= 3 (antes 12)
        if score >= 3:
            # Try to center snippet on the exact phrase first, then keywords
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
        return "INSUFICIENTE" # Fallback if no key

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
        
        # Clean up potential extra wording from LLM if it tries to be chatty around the keyword
        if "INSUFICIENTE" in text_response.upper() and len(text_response) < 20:
             return "INSUFICIENTE"
             
        return text_response
    except Exception as e:
        # Re-raise explicit errors for the UI to handle
        raise e

# --- Level 2: NotebookLM ---
# --- Level 2: NotebookLM ---
def search_notebooklm(query):
    # Dictionary of Notebooks: Title -> ID
    notebooks = {
        "CURSO CONTABILIDAD BASICA": "af525325-ca19-4f82-975f-349f01c6a099",
        "Compendio Normativo y Guía del Sistema Tributario Boliviano": "ead8f2c0-19e9-42dc-8040-c4659126b7e9"
    }
    
    combined_results = []
    
    for title, notebook_id in notebooks.items():
        try:
            # Use our custom python wrapper that talks to MCP server via ID
            # This avoids issues with special characters in names
            command = ['python', 'scripts/nlm_query_id.py', notebook_id, query]
            
            # Timeout increased to 60s as MCP might take time
            result = subprocess.run(command, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0 and result.stdout.strip():
                # Filter out "Error:" lines if any mixed in stdout
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

# --- Main App Logic ---
def main():
    st.title("📚 Laboratorio de Contabilidad (IA)")
    st.markdown("Asistente inteligente con Búsqueda en Cascada (Local -> NotebookLM -> Web)")

    # --- Gamification State ---
    if "user_xp" not in st.session_state:
        st.session_state.user_xp = 0
    if "user_streak" not in st.session_state:
        st.session_state.user_streak = 0

    # --- Gestor de Sonidos ---
    if "pending_sound" in st.session_state:
        reproducir_sonido(st.session_state.pending_sound)
        del st.session_state.pending_sound

    # Sidebar
    with st.sidebar:
        st.header("Configuración")
        
        # --- Perfil y Progreso ---
        st.markdown("### 🏆 Tu Progreso")
        col_xp, col_streak = st.columns(2)
        with col_xp:
            st.metric(label="Experiencia", value=f"{st.session_state.user_xp} XP")
        with col_streak:
            st.metric(label="Racha 🔥", value=f"{st.session_state.user_streak}")
        st.divider()
        
        # --- Carga Segura de API Key (Invisible para el usuario) ---
        try:
            api_key = st.secrets["general"]["GEMINI_API_KEY"]
        except Exception:
            st.error("⚠️ Error Crítico: No se encontró la API Key en los secretos del servidor.")
            api_key = ""

        # --- Módulo: Motor de Búsqueda ---
        st.divider()
        st.header("🔍 Motor de Búsqueda")
        deep_search_active = st.checkbox("Activar Búsqueda Profunda", value=False, key="deep_search", help="Consultar las 3 fuentes simultáneamente")
        st.caption("Niveles Activos: 1. Local (IA) | 2. NotebookLM | 3. Web Oficial")
        
        if st.button("🗑️ Limpiar Historial de Chat"):
            st.session_state.messages = []
            if "auditor_mode" in st.session_state: del st.session_state.auditor_mode
            if "auditor_case" in st.session_state: del st.session_state.auditor_case
            st.rerun()


        # --- Laboratorio de Casos (Sidebar) ---
        st.divider()
        st.header("📝 Laboratorio de Casos")
        
        lab_cases = load_laboratory_cases()
        
        if lab_cases:
            # 1. Select Category
            categories = list(lab_cases.keys())
            selected_category = st.selectbox("Categoría", categories)
            
            # 2. Select Case
            cases = lab_cases.get(selected_category, [])
            selected_case = st.selectbox("Ejercicio Práctico", cases)
            
            # Visual Badge
            badge_html = get_difficulty_badge(selected_case)
            if badge_html:
                st.markdown(f"{badge_html}", unsafe_allow_html=True)
            
            # --- CONTROL DE CASO ACTIVO (SISTEMA ANTI-COPIA) ---
            caso_limpio = clean_case_title(selected_case)
            
            # Si el usuario cambia de caso en el selectbox, reseteamos al caso original
            if "selected_case_tracker" not in st.session_state or st.session_state.selected_case_tracker != caso_limpio:
                st.session_state.selected_case_tracker = caso_limpio
                st.session_state.current_active_case = caso_limpio
            
            st.markdown(f"**📝 Caso Activo:** {st.session_state.current_active_case}")
            
            if st.button("🎲 Generar Variante Anti-Copia (Aleatorio)", help="Crea una versión única de este ejercicio para evitar copias."):
                reproducir_sonido("audio/dice.mp3") # Sonido de dados
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
                        st.rerun() # Recargar la interfaz para mostrar el nuevo caso
                    except Exception as e:
                        st.error(f"Error al generar variante: {e}")
            
            col1, col2 = st.columns(2)
            
            # Button 1: Tutor Mode
            if col1.button("👨‍🏫 Analizar con Tutor"):
                reproducir_sonido("audio/click.mp3") # Sonido de interfaz
                st.session_state.messages.append({"role": "user", "content": st.session_state.current_active_case})
                st.session_state.auditor_mode = False # Reset challenge
                
                with st.spinner("👨‍🏫 El Tutor está analizando el caso..."):
                    try:
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel('gemini-flash-latest')
                        
                        reglas_actuales = load_tax_rules()
                        prompt_lab = f"""Eres un Tutor de Contabilidad Senior de la UNICEN. El alumno necesita resolver este caso práctico: "{st.session_state.current_active_case}". 
PROHIBIDO usar formato LaTeX, signos de dólar ($) o etiquetas como \\mathbf para fórmulas matemáticas. Escribe los cálculos en texto plano normal.
DEBES dejar obligatoriamente una línea en blanco (un Enter) justo ANTES de empezar la tabla del asiento contable.

{reglas_actuales}

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
                        st.session_state.last_lab_response = lab_response # Store for PDF
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Error: {e}")

            # Button 2: Auditor Challenge
            if col2.button("⚔️ Reto Auditor"):
                st.session_state.pending_sound = "audio/swords.mp3" # Sonido de espadas chocar
                st.session_state.auditor_mode = True
                st.session_state.auditor_case = st.session_state.current_active_case
                st.session_state.messages.append({"role": "assistant", "content": f"⚔️ **¡Reto Aceptado!**\n\nCaso: *{st.session_state.current_active_case}*\n\nEscribe en el chat tu asiento contable propuesto (Cuentas y Montos). Yo actuaré como un Auditor estricto y calificaré tu respuesta."})
                st.rerun()
                
        else:
            st.warning("⚠️ No se encontraron casos de laboratorio. Verifica data/laboratory_cases.json")

        # --- Simulador de Ciclo Completo (Sidebar) ---
        st.divider()
        st.header("🏢 Proyecto: Ciclo Contable")
        
        if not st.session_state.get("project_mode", False):
            if st.button("🚀 Iniciar Nuevo Proyecto"):
                st.session_state.pending_sound = "audio/rocket.mp3" # Sonido de despegue
                st.session_state.project_mode = True
                st.session_state.project_transactions = []
                st.session_state.messages.append({"role": "assistant", "content": "🏢 **¡Modo Proyecto Iniciado!**\n\nVamos a simular un ciclo contable. Escribe tus transacciones una por una en el chat (ej. 'Transacción 1: Inicio de actividades con 50.000 Bs en caja...').\n\nEl sistema las guardará. Cuando termines todas, presiona el botón **'Generar EEFF'** en la barra lateral."})
                st.rerun()
        else:
            st.info(f"Transacciones registradas: {len(st.session_state.get('project_transactions', []))}")
            
            if st.button("📊 Generar EEFF", type="primary"):
                if len(st.session_state.project_transactions) > 0:
                    st.session_state.generate_project_balance = True
                else:
                    st.warning("Debes ingresar al menos una transacción en el chat.")
            
            if st.button("❌ Cancelar Proyecto"):
                st.session_state.project_mode = False
                st.session_state.project_transactions = []
                st.session_state.messages.append({"role": "assistant", "content": "Proyecto cancelado. Volviendo al modo normal."})
                st.rerun()

    # Chat History
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # --- Pantalla de Bienvenida (Solo si no hay mensajes) ---
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
            
            # Show download button if this message is the last one and from assistant
            if message == st.session_state.messages[-1] and message["role"] == "assistant":
                # Check if we have content to download (heuristic or explicit state)
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
                # NUEVO BLOQUE: Historial del Proyecto
                elif "# 📊 REPORTE DEL CICLO CONTABLE Y ESTADOS FINANCIEROS FINALES" in message["content"]:
                    pdf_bytes = generar_pdf(message["content"])
                    st.download_button(label="📄 Descargar Balance y EDFF en PDF", data=pdf_bytes, file_name="Proyecto_Ciclo_Contable.pdf", mime="application/pdf", key=f"pdf_chat_hist_{len(st.session_state.messages)}")
    
    # Helper for intent detection
    def should_run_deep_search(prompt, checkbox_state):
        keywords = ['en la web', 'en internet', 'según impuestos', 'en notebooklm', 'busca en todas']
        return checkbox_state or any(k in prompt.lower() for k in keywords)

    # Input
    if prompt := st.chat_input("Escribe tu consulta o transacción aquí..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            response_container = st.empty()
            full_response = ""
            
            # --- PROJECT MODE INTERCEPTION ---
            if st.session_state.get("project_mode", False) and not st.session_state.get("generate_project_balance", False):
                st.session_state.project_transactions.append(prompt)
                full_response = f"✅ Transacción #{len(st.session_state.project_transactions)} guardada. Escribe la siguiente o presiona **'Generar EEFF'** en la barra lateral."
                response_container.markdown(full_response)
                st.session_state.messages.append({"role": "assistant", "content": full_response})
            
            # --- CHALLENGE MODE INTERCEPTION ---
            elif st.session_state.get("auditor_mode", False):
                 with st.spinner("🧐 El Auditor está revisando tu asiento..."):
                    try:
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel('gemini-flash-latest')
                        
                        reglas_actuales = load_tax_rules()
                        case_ref = st.session_state.get("auditor_case", "Caso desconocido")
                        
                        # --- REPERTORIO DEL AUDITOR ---
                        frases_auditor = [
                            "SEÑOR ESTUDIANTE, recuerde que la contabilidad es el lenguaje de los negocios y una ciencia exacta, no un simple juego de sumas y restas.",
                            "FUTURO COLEGA, la precisión contable es innegociable. Un asiento mal registrado altera el destino financiero y tributario de toda una empresa.",
                            "ESTIMADO UNIVERSITARIO, el auditor no asume, verifica. Evaluemos con rigor técnico si su análisis cumple con la normativa vigente.",
                            "LA CONTABILIDAD exige criterio profesional, no adivinanzas. Procederé a auditar su registro bajo la lupa estricta de la normativa boliviana.",
                            "COLEGA EN FORMACIÓN, detrás de cada cuenta hay una gran responsabilidad legal y penal. Revisemos su propuesta contable paso a paso."
                        ]
                        frase_apertura = random.choice(frases_auditor)
                        
                        prompt_audit = f"""Eres un Auditor Contable y Docente Universitario en Bolivia. Evalúas a un estudiante. Tu tono es ESTRICTAMENTE PROFESIONAL, OBJETIVO y TÉCNICO.
                        
                        {reglas_actuales}
                    REGLA 1 (APERTURA OBLIGATORIA): Inicia tu respuesta EXACTAMENTE con este párrafo, sin agregar nada antes:
                    "{frase_apertura}"
                    
                    REGLA 2 (ESTRUCTURA VISUAL): Usa OBLIGATORIAMENTE un solo numeral (#) seguido de un espacio para crear títulos grandes. Debes generar exactamente estos títulos:
                    # 1. CALIFICACIÓN: X/100
                    # 2. OBSERVACIONES Y ERRORES DETECTADOS:
                    (Aquí tu lista numerada de puntos citando Código de Comercio, Ley 843, PCGA, etc.)
                    # 3. SOLUCIÓN CORRECTA:
                    (Aquí la tabla)
                    
                    REGLA 3 (GLOSA AFUERA): Genera la tabla Markdown del asiento. DEBES cerrar la tabla después de la fila de TOTALES. La GLOSA debe ir AFUERA de la tabla, abajo, como un párrafo de texto normal.
                    
                    REGLA 4: Cierra con una frase de aliento profesional.
                    
                    El caso es: "{case_ref}". Su respuesta fue: "{prompt}"."""
                        
                        response = model.generate_content(prompt_audit)
                        full_response = response.text.strip()
                        
                        import re
                        # Buscar el patrón de calificación generado por la IA
                        match = re.search(r'CALIFICACIÓN:\s*(\d+)/100', full_response, re.IGNORECASE)
                        if match:
                            score = int(match.group(1))
                            st.session_state.user_xp += score # Sumar XP
                            
                            if score >= 80:
                                st.session_state.user_streak += 1
                                st.balloons() # Efecto visual de celebración
                                reproducir_sonido("audio/success.mp3") # NUEVO: Efecto de sonido
                                st.toast(f"¡Excelente! Ganaste {score} XP. Racha aumentada a {st.session_state.user_streak} 🔥", icon="🔥")
                            else:
                                st.session_state.user_streak = 0
                                reproducir_sonido("audio/error.mp3") # NUEVO: Efecto de sonido de fallo
                                st.toast(f"Obtuviste {score} XP. La racha ha vuelto a cero. ¡Revisa la norma y recupera tu fuego!", icon="🧊")
                        
                        st.session_state.auditor_mode = False # End challenge after advice
                        st.session_state.last_auditor_response = full_response
                        st.success("Evaluación Completada.")
                        
                    except Exception as e:
                        full_response = f"Error del Auditor: {e}"
            # ...
            else:
                is_deep_search = should_run_deep_search(prompt, deep_search_active)
                
                if is_deep_search:
                    # --- DEEP SEARCH MODE (Parallel Execution) ---
                    with st.spinner('Consultando todas las bases de datos (Local, NLM, Web)...'):
                        # 1. Local Search
                        topics_data = load_local_data()
                        local_candidates = search_local(prompt, topics_data)
                        local_text = ""
                        if local_candidates:
                            for idx, cand in enumerate(local_candidates):
                                local_text += f"\n--- EXTRACTO LOCAL {idx+1} ({cand['topic']}) ---\n{cand['snippet']}"
                        else:
                            local_text = "Sin resultados locales relevantes."

                        # 2. NotebookLM
                        nlm_text = search_notebooklm(prompt) or "Sin resultados en NotebookLM."
                        
                        # 3. Web Search
                        web_text = search_web(prompt) or "Sin resultados en la Web."
                        
                        # Synthesize with LLM
                        master_context = f"""
                        [RESULTADOS LOCALES]:
                        {local_text}
                        
                        [RESULTADOS NOTEBOOKLM]:
                        {nlm_text}
                        
                        [RESULTADOS WEB]:
                        {web_text}
                        """
                        
                        try:
                            genai.configure(api_key=api_key)
                            model = genai.GenerativeModel('gemini-flash-latest')
                            
                            system_prompt = f"""El alumno preguntó: "{prompt}". 
                            Aquí tienes información de 3 fuentes distintas: {master_context}. 
                            TAREA: Redacta una respuesta exhaustiva integrando los apuntes teóricos, la base legal (NLM) y la normativa web oficial. 
                            Cita de qué fuente sacas cada dato."""
                            
                            response = model.generate_content(system_prompt)
                            full_response = response.text.strip()
                            
                            st.success("✅ Respuesta Generada en Modo Profundo (3 Fuentes).")
                            
                        except Exception as e:
                            full_response = f"Error al sintetizar respuesta profunda: {e}\n\nDetalles de fuentes:\n{master_context}"
                
                else:
                    # --- NORMAL MODE (Waterfall) ---
                    # Level 1: Local Search
                    topics_data = load_local_data()
                    local_candidates = search_local(prompt, topics_data)
                    
                    should_escalate = True
                    
                    if local_candidates:
                        # DEBUG VISIBILITY: Show what we found locally (Top 3)
                        combined_snippets = ""
                        
                        with st.expander(f"📄 Documentos encontrados ({len(local_candidates)})"):
                            for idx, cand in enumerate(local_candidates):
                                st.markdown(f"**{idx+1}. {cand['topic']}** (Score: {cand['score']})")
                                st.caption(cand['snippet'])
                                combined_snippets += f"\n\n--- EXTRACTO {idx+1} ({cand['topic']}) ---\n{cand['snippet']}"

                        with st.spinner("👩‍🏫 Analizando material del curso (El Juez)..."):
                            try:
                                llm_verdict = evaluate_snippet_with_llm(prompt, combined_snippets, api_key)
                                
                                if llm_verdict != "INSUFICIENTE":
                                    full_response = f"**Tutor UNICEN:**\n\n{llm_verdict}"
                                    st.success("✅ Respuesta validada por Juez IA (Contexto Combinado).")
                                    should_escalate = False # We have a good answer
                                    
                            except Exception as e:
                                st.error(f"Error de API (El Juez): {e}")
                                # Don't escalate effectively if API fails, just stop or let user know
                                should_escalate = False 
                                full_response = "⚠️ Ocurrió un error al contactar con la IA para validar la respuesta local. Por favor verifica tu API Key."
                    else:
                         # No local candidates found
                         pass # Logic falls through to should_escalate=True

                    if should_escalate:
                        # Level 2: NotebookLM
                        with st.spinner("🤖 Consultando base de conocimiento extendida (NotebookLM)..."):
                            if not local_candidates:
                                 st.info("Búsqueda local sin coincidencias fuertes (Score < 3). Escalando...")
                            else:
                                 st.warning("El Juez IA determinó que la info local era insuficiente. Escalando...")
                                 
                            nlm_result = search_notebooklm(prompt)
                        
                        if nlm_result:
                            full_response = f"**Respuesta de NotebookLM:**\n\n{nlm_result}"
                            st.success("✅ Respuesta recuperada de NotebookLM.")
                        else:
                            # Level 3: Web
                            with st.spinner("🌐 Buscando normativa oficial en la web (Nivel 3)..."):
                                st.warning("NotebookLM no tiene datos. Escalando a Nivel 3...")
                                web_result = search_web(prompt)
                            
                            if web_result:
                                full_response = f"**Búsqueda Web (Normativa Bolivia):**\n\n{web_result}"
                            else:
                                # FALLBACK: Si no hay info teórica, asumimos que es un ejercicio práctico libre.
                                with st.spinner("👨‍🏫 Parece un caso práctico. Generando resolución estructurada..."):
                                    try:
                                        genai.configure(api_key=api_key)
                                        model = genai.GenerativeModel('gemini-flash-latest')
                                        
                                        reglas_actuales = load_tax_rules()
                                        prompt_resolucion_libre = f"""Eres un Tutor de Contabilidad Senior de la UNICEN. El alumno te ha planteado el siguiente caso o ejercicio práctico de forma libre: "{prompt}".
                                        PROHIBIDO usar formato LaTeX o etiquetas matemáticas. Escribe en texto plano normal.
                                        
                                        {reglas_actuales}
                                        
                                        TAREA: 
                                        1. Crea el asiento contable usando ESTRICTAMENTE esta estructura Markdown:
                                        | Código | Detalle / Cuenta | Debe (Bs.) | Haber (Bs.) |
                                        | :--- | :--- | ---: | ---: |
                                        REGLA: La GLOSA debe ir COMPLETAMENTE AFUERA y debajo de la tabla.
                                        
                                        2. Explica pedagógicamente la ley de movimiento de cuentas aplicada y el documento de respaldo necesario.
                                        
                                        3. LIBRO MAYOR (CUENTAS T): Genera el mayor usando ESTRICTAMENTE tablas individuales. ¡NUNCA omitas la fila separadora | ---: | ---: |!
                                        #### Cuenta: [Nombre]
                                        | DEBE (Bs.) | HABER (Bs.) |
                                        | ---: | ---: |
                                        
                                        4. IMPACTO EN ESTADOS FINANCIEROS:
                                        | Cuenta | Grupo | Estado Financiero |
                                        | :--- | :--- | :--- |
                                        
                                        REGLA DE ORO: TODAS las tablas DEBEN empezar y terminar con |.
                                        """
                                        
                                        response_libre = model.generate_content(prompt_resolucion_libre)
                                        full_response = "**👨‍🏫 Tutor UNICEN (Resolución Libre):**\n\n" + response_libre.text.strip()
                                        
                                        st.success("✅ Caso resuelto exitosamente.")
                                        
                                    except Exception as e:
                                        full_response = f"❌ Error al intentar resolver el caso: {e}"
            
            response_container.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})

            # Show download button immediately for Auditor (before next rerun)
            if st.session_state.get("last_auditor_response") == full_response:
                pdf_bytes = generar_pdf(full_response)
                st.download_button(
                    label="📄 Descargar Evaluación en PDF",
                    data=pdf_bytes,
                    file_name="Evaluacion_Auditor_UNICEN.pdf",
                    mime="application/pdf",
                    key=f"pdf_aud_gen_{len(st.session_state.messages)}"
                )
            elif "**👨‍🏫 Tutor UNICEN (Resolución Libre):**" in full_response:
                pdf_bytes = generar_pdf(full_response)
                st.download_button(
                    label="📄 Descargar Resolución en PDF",
                    data=pdf_bytes,
                    file_name="Resolucion_Caso_Libre.pdf",
                    mime="application/pdf",
                    key=f"pdf_chat_gen_{len(st.session_state.messages)}"
                )

    # --- PROCESS PROJECT BALANCE ---
    if st.session_state.get("generate_project_balance", False):
        st.session_state.generate_project_balance = False # Reset flag
        st.session_state.project_mode = False # End mode
        
        with st.chat_message("assistant"):
            with st.spinner("📊 Analizando el ciclo completo y estructurando el Balance de Comprobación..."):
                try:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('gemini-flash-latest')
                    
                    reglas_actuales = load_tax_rules() if 'load_tax_rules' in globals() else "Aplica normativa contable boliviana vigente."
                    transacciones_texto = "\n".join([f"{i+1}. {t}" for i, t in enumerate(st.session_state.project_transactions)])
                    
                    prompt_proyecto = f"""Eres un Tutor Senior de Contabilidad en Bolivia.
                    {reglas_actuales}
                    
                    El estudiante ha registrado este ciclo de transacciones:
                    {transacciones_texto}
                    
                    TAREA OBLIGATORIA:
                    1. Genera un LIBRO DIARIO consolidado usando EXACTAMENTE esta estructura de tabla Markdown. TODAS las filas DEBEN tener exactamente 4 columnas y empezar/terminar con el símbolo "|":
                    | Fecha | Detalle / Cuenta | Debe (Bs.) | Haber (Bs.) |
                    | :--- | :--- | ---: | ---: |
                    | 01/01/2026 | **Asiento N° 1** | | |
                    | | Caja M/N | 100.000,00 | |
                    | | Capital Social | | 100.000,00 |
                    REGLA: La glosa va AFUERA de la tabla.
                    
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
                    
                    # NUEVO: Generar PDF y mostrar botón inmediatamente en la pantalla
                    pdf_bytes = generar_pdf(full_response)
                    st.download_button(
                        label="📄 Descargar Balance en PDF",
                        data=pdf_bytes,
                        file_name="Proyecto_Ciclo_Contable.pdf",
                        mime="application/pdf",
                        key=f"pdf_proyecto_inmediato_{len(st.session_state.messages)}"
                    )
                    
                except Exception as e:
                    st.error(f"Error al generar el balance: {e}")

if __name__ == "__main__":
    main()

