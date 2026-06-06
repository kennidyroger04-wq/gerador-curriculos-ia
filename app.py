import streamlit as st
import tempfile
import os
import uuid
import json
from jinja2 import Environment, FileSystemLoader

# ==============================================================================
# VERIFICAÇÃO DE DEPENDÊNCIAS
# ==============================================================================
try:
    from weasyprint import HTML
    WEASYPRINT_INSTALLED = True
except ImportError:
    WEASYPRINT_INSTALLED = False

try:
    from openai import OpenAI
    OPENAI_INSTALLED = True
except ImportError:
    OPENAI_INSTALLED = False


# ==============================================================================
# GARANTIA DE INFRAESTRUTURA (Template HTML Ajustado para Listas e Layout)
# ==============================================================================
def garantir_template_html():
    template_path = os.path.join(os.path.dirname(__file__), "template_cv.html")
    if not os.path.exists(template_path):
        html_base = """
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
                
                body { 
                    font-family: 'Inter', sans-serif; 
                    color: #333; 
                    line-height: 1.5; 
                    margin: 0; 
                    padding: 25px; 
                }
                
                .watermark { 
                    position: absolute; 
                    top: 50%; 
                    left: 50%; 
                    transform: translate(-50%, -50%) rotate(-45deg); 
                    font-size: 80px; 
                    color: rgba(255,0,0,0.1); 
                    z-index: -1; 
                    white-space: nowrap; 
                }
                
                h1 { 
                    color: #1e293b; 
                    border-bottom: 2px solid #cbd5e1; 
                    padding-bottom: 5px; 
                    margin-bottom: 5px; 
                    font-size: 24px; 
                    text-transform: uppercase;
                }
                
                .contact-info { 
                    font-size: 0.9em; 
                    color: #475569; 
                    margin-bottom: 20px; 
                }
                
                h2 { 
                    color: #0f172a; 
                    font-size: 1.1em; 
                    margin-top: 20px; 
                    border-bottom: 1px solid #e2e8f0; 
                    padding-bottom: 3px; 
                    text-transform: uppercase;
                }
                
                .job-header { 
                    display: flex; 
                    justify-content: space-between; 
                    align-items: baseline; 
                    margin-bottom: 2px; 
                }
                
                .job-title { 
                    font-weight: 700; 
                    color: #1e293b; 
                }
                
                .job-company { 
                    font-weight: 600; 
                    color: #475569; 
                }
                
                .job-date { 
                    font-size: 0.85em; 
                    color: #64748b; 
                    font-style: italic; 
                }
                
                .job-desc { 
                    margin-top: 5px; 
                    font-size: 0.95em; 
                    color: #334155; 
                }
                
                ul { 
                    margin-top: 5px; 
                    padding-left: 20px; 
                    margin-bottom: 15px; 
                }
                
                li { 
                    margin-bottom: 4px; 
                }
                
                .skills-container { 
                    display: flex; 
                    flex-wrap: wrap; 
                    gap: 5px; 
                    margin-top: 5px; 
                }
                
                .skill-tag { 
                    background-color: #f1f5f9; 
                    border: 1px solid #e2e8f0; 
                    padding: 2px 8px; 
                    border-radius: 4px; 
                    font-size: 0.85em; 
                    color: #475569;
                }
            </style>
        </head>
        <body>
            {% if eh_previsao %}
                <div class="watermark">PREVISÃO - PENDENTE PAGAMENTO</div>
            {% endif %}
            
            <h1>{{ personal_info.get('full_name', 'Nome não informado') }}</h1>
            <div class="contact-info">
                {{ personal_info.get('contact', {}).get('email', '') }} | 
                {{ personal_info.get('contact', {}).get('phone', '') }} | 
                {{ personal_info.get('location', {}).get('city', '') }}
            </div>
            
            {% if professional_summary %}
            <h2>Resumo Profissional</h2>
            <p style="font-size: 0.95em; color: #334155;">{{ professional_summary }}</p>
            {% endif %}
            
            {% if skills %}
            <h2>Principais Habilidades</h2>
            <div class="skills-container">
                {% for skill, level in skills.items() %}
                    <span class="skill-tag">{{ skill }}</span>
                {% endfor %}
            </div>
            {% endif %}
            
            {% if work_experience %}
            <h2>Experiência Profissional</h2>
            {% for exp in work_experience %}
                <div style="margin-bottom: 15px;">
                    <div class="job-header">
                        <div>
                            <span class="job-title">{{ exp.get('role', '') }}</span>
                            {% if exp.get('company') %} <span class="job-company">| {{ exp.get('company') }}</span> {% endif %}
                        </div>
                        {% if exp.get('period') %} <div class="job-date">{{ exp.get('period') }}</div> {% endif %}
                    </div>
                    <!-- Uso do | safe para permitir as tags HTML de lista (<ul><li>) -->
                    <div class="job-desc">{{ exp.get('description', '') | safe }}</div>
                </div>
            {% endfor %}
            {% endif %}
            
            {% if education %}
            <h2>Formação Acadêmica</h2>
            <ul>
            {% for edu in education %}
                <li>{{ edu.get('degree_institution', 'Curso/Instituição') }}</li>
            {% endfor %}
            </ul>
            {% endif %}
        </body>
        </html>
        """
        with open(template_path, "w", encoding="utf-8") as f:
            f.write(html_base)

garantir_template_html()

# ==============================================================================
# CONFIGURAÇÃO DA PÁGINA E ESTADOS
# ==============================================================================
st.set_page_config(
    page_title="CurrículoBuilder AI — Criador de Currículos",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded"
)

if "resume" not in st.session_state:
    st.session_state.resume = {
        "personal_info": {
            "full_name": "",
            "contact": {"email": "", "phone": ""},
            "location": {"city": ""}
        },
        "professional_summary": "",
        "work_experience": [],
        "education": [],
        "courses_certifications": [],
        "skills": {},
        "adicionais_usuario": ""
    }

if "step" not in st.session_state:
    st.session_state.step = "vaga_alvo"

if "vaga_alvo" not in st.session_state:
    st.session_state.vaga_alvo = ""

if "pdfs_gerados" not in st.session_state:
    st.session_state.pdfs_gerados = False

if "pdf_limpo_path" not in st.session_state:
    st.session_state.pdf_limpo_path = None

if "pdf_previsao_path" not in st.session_state:
    st.session_state.pdf_previsao_path = None

if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {
            "role": "assistant",
            "content": "Olá! Para qual vaga ou área você quer direcionar este currículo? (Ex: Vendedor, Motorista, Jovem Aprendiz, ou 'Qualquer uma')"
        }
    ]

API_KEY = st.secrets.get("OPENAI_API_KEY", "")

# ==============================================================================
# MOTORES DE INTELIGÊNCIA ARTIFICIAL (EXTRAÇÃO E POLIMENTO)
# ==============================================================================
def extrair_dados_com_ia(texto):
    if not OPENAI_INSTALLED or not API_KEY: 
        return {} 
        
    client = OpenAI(api_key=API_KEY)
    
    # NOVO SCHEMA: Separa role, company e period explicitamente para não causar bugs no PDF.
    system_prompt = (
        "Você é um extrator de dados. Seu objetivo é ler o texto desestruturado do candidato e mapear "
        "os dados EXCLUSIVAMENTE para o seguinte esquema JSON.\n"
        "Se a informação não existir no texto, simplesmente omita a chave.\n"
        "Ao ler o relato do usuário, você DEVE INFERIR pelo menos 4 a 6 Habilidades (Soft Skills e Hard Skills) pertinentes à história contada, mesmo que o usuário não as tenha listado explicitamente. Exemplo: Se ele trabalhou em caixa de mercado, adicione habilidades como 'Atendimento ao Público', 'Fechamento de Caixa' e 'Agilidade'.\n"
        "{\n"
        '  "personal_info": {"full_name": "", "contact": {"email": "", "phone": ""}, "location": {"city": ""}},\n'
        '  "professional_summary": "",\n'
        '  "work_experience": [\n'
        '    {"role": "Cargo", "company": "Empresa", "period": "Anos/Meses", "description": "Texto original"}\n'
        '  ],\n'
        '  "education": [{"degree_institution": "Curso e Local"}],\n'
        '  "courses_certifications": [{"name": "Nome do Curso/Certificação", "institution": "Instituição"}],\n'
        '  "skills": {"Habilidade 1": "Nível", "Habilidade 2": "Nível"}\n'
        "}"
    )
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt}, 
                {"role": "user", "content": texto}
            ],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content.strip())
    except Exception:
        return {}

def polir_curriculo_com_ia(dados_brutos):
    if not OPENAI_INSTALLED or not API_KEY: 
        raise Exception("API não configurada.")
        
    client = OpenAI(api_key=API_KEY)
    vaga_alvo = st.session_state.vaga_alvo if st.session_state.vaga_alvo else "a área profissional informada"
    
    system_prompt = (
        f"Você é um Headhunter de Elite construindo um currículo para a vaga de '{vaga_alvo}'. O usuário tem dificuldade de se expressar. Você recebeu os dados estruturados e notas adicionais dele.\n"
        "Sua missão:\n\n"
        f"Crie um Resumo Profissional altamente persuasivo conectando a história de vida/objetivos do usuário com a {vaga_alvo}.\n\n"
        "Nas experiências, use o Método STAR. Expanda as respostas curtas em 3 bullet points detalhados usando verbos de ação fortes, formatados obrigatoriamente como uma lista HTML (<ul><li>...</li></ul>).\n\n"
        "Para garantir que o documento caiba em 1 página, limite-se a detalhar no máximo as 3 experiências mais relevantes, focando em qualidade e não em quantidade.\n\n"
        "Seja criativo para valorizar o perfil, mas É PROIBIDO inventar empresas, cargos que ele não ocupou ou métricas numéricas falsas (como 'aumentou 15%'). Enriqueça a forma, mantenha a essência verdadeira."
    )
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt}, 
                {"role": "user", "content": json.dumps(dados_brutos, ensure_ascii=False)}
            ],
            temperature=0.2, # Baixa temperatura para reduzir a criatividade alucinatória
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content.strip())
    except Exception:
        return dados_brutos

# ==============================================================================
# MOTOR DE GERAÇÃO DE PDF (COM INTERCEPTAÇÃO DE LISTAS)
# ==============================================================================
def gerar_pdfs(dados_resume):
    # Processamento Crítico para evitar colchetes ['...'] no PDF e transformar em Bullet Points
    dados_processados = json.loads(json.dumps(dados_resume)) # Copia profunda para não alterar a UI
    
    for exp in dados_processados.get("work_experience", []):
        desc = exp.get("description", "")
        # Se a IA retornou uma lista de strings, formatamos como bullet points do HTML
        if isinstance(desc, list):
            html_bullets = "<ul>"
            for item in desc:
                html_bullets += f"<li>{item}</li>"
            html_bullets += "</ul>"
            exp["description"] = html_bullets
            
        # Se por acaso retornou string simples, convertemos quebras de linha normais
        elif isinstance(desc, str):
            exp["description"] = desc.replace("\n", "<br>")

    diretorio_atual = os.path.dirname(os.path.abspath(__file__))
    env = Environment(loader=FileSystemLoader(diretorio_atual))
    template = env.get_template("template_cv.html")
    
    html_limpo = template.render(**dados_processados, eh_previsao=False)
    html_previsao = template.render(**dados_processados, eh_previsao=True)
    
    temp_dir = tempfile.gettempdir()
    path_limpo = os.path.join(temp_dir, f"cv_limpo_{uuid.uuid4().hex[:8]}.pdf")
    path_previsao = os.path.join(temp_dir, f"cv_previsao_{uuid.uuid4().hex[:8]}.pdf")
    
    HTML(string=html_limpo).write_pdf(path_limpo)
    HTML(string=html_previsao).write_pdf(path_previsao)
    
    return path_limpo, path_previsao

# ==============================================================================
# ESTILIZAÇÃO PREMIUM CSS (CLEAN - OCEAN BLUE & SLATE - TOTALMENTE EXPANDIDO)
# ==============================================================================
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"], .stApp { 
        font-family: 'Outfit', sans-serif; 
    }
    
    #MainMenu, footer, header { 
        visibility: hidden; 
    }
    
    /* Fundo Slate Premium */
    .stApp { 
        background: linear-gradient(135deg, #0f172a 0%, #020617 100%); 
        color: #f8fafc; 
    }
    
    [data-testid="stSidebar"] { 
        background-color: rgba(15, 23, 42, 0.95) !important; 
        border-right: 1px solid rgba(255, 255, 255, 0.08) !important; 
        padding-top: 2rem; 
    }

    /* Cards da Interface Esquerda */
    .preview-card { 
        background: rgba(30, 41, 59, 0.7); 
        border: 1px solid rgba(255, 255, 255, 0.05); 
        border-radius: 12px; 
        padding: 1.1rem; 
        margin-bottom: 0.9rem; 
        backdrop-filter: blur(10px); 
        transition: all 0.3s ease; 
    }
    
    .preview-card:hover { 
        border-color: rgba(56, 189, 248, 0.4); 
        box-shadow: 0 4px 20px rgba(56, 189, 248, 0.1); 
        transform: translateY(-2px); 
    }
    
    .preview-header { 
        font-weight: 600; 
        font-size: 1.05rem; 
        color: #38bdf8; 
        margin-bottom: 0.4rem; 
        display: flex; 
        align-items: center; 
        gap: 0.5rem; 
    }
    
    .preview-placeholder { 
        font-style: italic; 
        color: #64748b; 
        font-size: 0.85rem; 
    }
    
    .preview-value { 
        color: #e2e8f0; 
        font-size: 0.9rem; 
        line-height: 1.4; 
    }

    /* Badges de Habilidades */
    .skill-badge { 
        display: inline-block; 
        background-color: rgba(56, 189, 248, 0.15); 
        color: #7dd3fc; 
        border: 1px solid rgba(56, 189, 248, 0.3); 
        border-radius: 6px; 
        padding: 0.15rem 0.45rem; 
        font-size: 0.8rem; 
        margin-right: 0.3rem; 
        margin-bottom: 0.3rem; 
    }

    /* Balões do ChatBot */
    .stChatMessage { 
        background-color: rgba(30, 41, 59, 0.5) !important; 
        border: 1px solid rgba(255, 255, 255, 0.03) !important; 
        border-radius: 12px !important; 
        padding: 1rem !important; 
        margin-bottom: 0.75rem !important; 
        backdrop-filter: blur(5px); 
    }
    
    [data-testid="chatAvatarIcon-assistant"] { 
        background-color: #2563eb !important; 
    }

    /* Input do Chat */
    .stChatInputContainer { 
        border: 1px solid rgba(255, 255, 255, 0.1) !important; 
        background-color: rgba(15, 23, 42, 0.9) !important; 
        border-radius: 12px !important; 
        box-shadow: 0 -4px 30px rgba(0, 0, 0, 0.3) !important; 
    }
    
    .stChatInputContainer:focus-within { 
        border-color: #38bdf8 !important; 
    }

    /* Topografia Geral */
    .app-header { 
        background: linear-gradient(90deg, #2563eb 0%, #38bdf8 100%); 
        -webkit-background-clip: text; 
        -webkit-text-fill-color: transparent; 
        font-weight: 800; 
        font-size: 2.2rem; 
        margin-bottom: 0.1rem; 
        letter-spacing: -0.025em; 
    }
    
    .app-subtitle { 
        color: #94a3b8; 
        font-size: 0.95rem; 
        margin-bottom: 1.5rem; 
    }
    
    .status-badge { 
        display: inline-block; 
        padding: 0.25rem 0.6rem; 
        border-radius: 9999px; 
        font-size: 0.75rem; 
        font-weight: 600; 
        background-color: rgba(56, 189, 248, 0.15); 
        color: #7dd3fc; 
        border: 1px solid rgba(56, 189, 248, 0.3); 
    }

    /* Barra de Progresso */
    .progress-bar-container { 
        margin: 1rem 0; 
        background: rgba(255, 255, 255, 0.05); 
        border-radius: 9999px; 
        height: 6px; 
        overflow: hidden; 
    }
    
    .progress-bar-fill { 
        background: linear-gradient(90deg, #2563eb, #38bdf8); 
        height: 100%; 
        border-radius: 9999px; 
        transition: width 0.5s ease-in-out; 
    }
    
    /* Botões Padrão Ocean Blue */
    .stButton>button { 
        background: linear-gradient(90deg, #2563eb 0%, #38bdf8 100%) !important; 
        color: white !important; 
        border: none !important; 
        font-weight: 600 !important; 
        border-radius: 10px !important; 
        padding: 0.6rem 1.5rem !important; 
        transition: transform 0.2s ease, box-shadow 0.2s ease !important; 
    }
    
    .stButton>button:hover { 
        transform: translateY(-1px) !important; 
        box-shadow: 0 4px 15px rgba(56, 189, 248, 0.4) !important; 
    }
    </style>
    """, 
    unsafe_allow_html=True
)

# ==============================================================================
# LAYOUT SPA E MÁQUINA DE ESTADOS
# ==============================================================================
progresso_map = {
    "vaga_alvo": 10, 
    "coleta_basica": 40, 
    "confirmacao_adicional": 70,
    "geracao": 100
}
progresso_percentual = progresso_map.get(st.session_state.step, 10)

col_preview, col_chat = st.columns([1, 2], gap="large")

with col_preview:
    st.markdown('<div class="app-header">CurrículoBuilder</div>', unsafe_allow_html=True)
    st.markdown('<div class="app-subtitle">Criação Interativa e Inteligente</div>', unsafe_allow_html=True)
    
    st.markdown(f'<div class="status-badge">Progresso: {progresso_percentual}%</div>', unsafe_allow_html=True)
    
    progress_html = f"""
    <div class="progress-bar-container">
        <div class="progress-bar-fill" style="width: {progresso_percentual}%;"></div>
    </div>
    """
    st.markdown(progress_html, unsafe_allow_html=True)
    
    st.write("---")
    
    tab_visual, tab_json = st.tabs(["📝 Rascunho Visual", "💾 JSON em Tempo Real"])
    
    with tab_visual:
        resume = st.session_state.resume
        
        # Renderização Lógica Expandida: Dados Pessoais
        has_info = False
        if resume["personal_info"].get("full_name"):
            has_info = True
        if resume["personal_info"]["contact"].get("email"):
            has_info = True
        if resume["personal_info"]["contact"].get("phone"):
            has_info = True
        if resume["personal_info"]["location"].get("city"):
            has_info = True

        info_html = ""
        if resume["personal_info"].get("full_name"): 
            info_html += f"<b>Nome:</b> {resume['personal_info']['full_name']}<br>"
        
        if resume["personal_info"]["contact"].get("email"): 
            info_html += f"<b>E-mail:</b> {resume['personal_info']['contact']['email']}<br>"
        
        if resume["personal_info"]["contact"].get("phone"): 
            info_html += f"<b>Telefone:</b> {resume['personal_info']['contact']['phone']}<br>"
        
        if resume["personal_info"]["location"].get("city"): 
            info_html += f"<b>Localização:</b> {resume['personal_info']['location']['city']}<br>"
            
        if not has_info:
            content = "<div class='preview-placeholder'>Aguardando dados...</div>"
        else:
            content = f"<div class='preview-value'>{info_html}</div>"
            
        st.markdown(f"""
            <div class="preview-card">
                <div class="preview-header">👤 Informações Pessoais</div>
                {content}
            </div>
            """, unsafe_allow_html=True)
        
        # Renderização Lógica Expandida: Resumo Profissional
        summary = resume.get("professional_summary")
        if not summary:
            content = "<div class='preview-placeholder'>Aguardando dados...</div>"
        else:
            content = f"<div class='preview-value'>{summary}</div>"
            
        st.markdown(f"""
            <div class="preview-card">
                <div class="preview-header">🎯 Resumo Profissional</div>
                {content}
            </div>
            """, unsafe_allow_html=True)
        
        # Renderização Lógica Expandida: Habilidades
        skills = resume.get("skills", {})
        skills_html = ""
        for skill in skills.keys():
            skills_html += f'<span class="skill-badge">{skill}</span>'
            
        if not skills:
            content = "<div class='preview-placeholder'>Aguardando dados...</div>"
        else:
            content = f"<div>{skills_html}</div>"
            
        st.markdown(f"""
            <div class="preview-card">
                <div class="preview-header">🛠️ Habilidades</div>
                {content}
            </div>
            """, unsafe_allow_html=True)
        
        # Renderização Lógica Expandida: Experiências
        experiences = resume.get("work_experience", [])
        exp_html = ""
        for exp in experiences:
            # Adequado ao novo schema da API (separando role e company perfeitamente)
            cargo = exp.get('role', '')
            
            if exp.get('company'):
                empresa = f" | {exp.get('company')}"
            else:
                empresa = ""
                
            if exp.get('period'):
                data = f" ({exp.get('period')})"
            else:
                data = ""
                
            exp_html += f"<div class='preview-value' style='margin-bottom:0.5rem;'>💼 <b>{cargo}{empresa}</b>{data}</div>"
            
        if not experiences:
            content = "<div class='preview-placeholder'>Aguardando dados ou 'pular'...</div>"
        else:
            content = exp_html
            
        st.markdown(f"""
            <div class="preview-card">
                <div class="preview-header">💼 Experiências Profissionais ({len(experiences)})</div>
                {content}
            </div>
            """, unsafe_allow_html=True)
        
        # Renderização Lógica Expandida: Formação
        education = resume.get("education", [])
        edu_html = ""
        for edu in education:
            edu_html += f"<div class='preview-value' style='margin-bottom:0.5rem;'>🎓 <b>{edu.get('degree_institution')}</b></div>"
            
        if not education:
            content = "<div class='preview-placeholder'>Aguardando dados ou 'pular'...</div>"
        else:
            content = edu_html
            
        st.markdown(f"""
            <div class="preview-card">
                <div class="preview-header">🎓 Formação Acadêmica ({len(education)})</div>
                {content}
            </div>
            """, unsafe_allow_html=True)
            
        # Renderização Lógica Expandida: Cursos Complementares
        courses = resume.get("courses_certifications", [])
        crs_html = ""
        for crs in courses:
            inst = f" - <em>{crs.get('institution')}</em>" if crs.get("institution") else ""
            crs_html += f"<div class='preview-value' style='margin-bottom:0.5rem;'>🔖 <b>{crs.get('name', 'Curso')}</b>{inst}</div>"
            
        if not courses:
            content = "<div class='preview-placeholder'>Nenhum curso extra adicionado.</div>"
        else:
            content = crs_html
            
        st.markdown(f"""
            <div class="preview-card">
                <div class="preview-header">🔖 Cursos e Certificações ({len(courses)})</div>
                {content}
            </div>
            """, unsafe_allow_html=True)
        
    with tab_json:
        st.markdown("<p style='color:#64748b; font-size:0.85rem; margin-bottom: 0.5rem;'>Representação exata de st.session_state.resume:</p>", unsafe_allow_html=True)
        st.json(st.session_state.resume)

with col_chat:
    with st.expander("💡 Como conversar com a nossa IA", expanded=False):
        st.markdown("👋 Olá! Sou capaz de entender várias informações ao mesmo tempo! Você pode se apresentar por completo ou responder passo a passo.")

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]): 
            st.markdown(msg["content"])
    
    # --------------------------------------------------------------------------
    # BLOCO CONDICIONAL LÓGICO: GERAÇÃO FINAL (FASE 4)
    # --------------------------------------------------------------------------
    if st.session_state.step == "geracao":
        st.markdown("<br>", unsafe_allow_html=True)
        
        if not WEASYPRINT_INSTALLED or not OPENAI_INSTALLED: 
            st.warning("⚠️ Dependências ausentes no ambiente! Instale `weasyprint` e `openai`.")
            
        st.info("🏆 **Coleta Finalizada!** Clique abaixo para nossa IA Headhunter polir seu currículo.")
        
        if st.button("🚀 Gerar Currículos em PDF", use_container_width=True, disabled=not WEASYPRINT_INSTALLED or not OPENAI_INSTALLED):
            with st.spinner("Aguarde... Nossa IA Headhunter está polindo e otimizando o seu currículo de forma realista!"):
                try:
                    dados_polidos = polir_curriculo_com_ia(st.session_state.resume)
                    path_limpo, path_previsao = gerar_pdfs(dados_polidos)
                    st.session_state.pdf_limpo_path = path_limpo
                    st.session_state.pdf_previsao_path = path_previsao
                    st.session_state.pdfs_gerados = True
                except Exception as e:
                    st.error(f"Erro no processamento: {str(e)}")
                    
        if st.session_state.pdfs_gerados:
            st.success("Currículo otimizado com sucesso!")
            col_d1, col_d2 = st.columns(2)
            
            with col_d1:
                with open(st.session_state.pdf_previsao_path, "rb") as f:
                    st.download_button("👀 Baixar Previsão Grátis", f.read(), "previsao.pdf", "application/pdf", use_container_width=True)
                    
            with col_d2:
                st.link_button("💳 Pagar R$ 1,99 para Liberar Oficial", "SUA_URL_AQUI", use_container_width=True)
                
            codigo_digitado = st.text_input("Já pagou? Digite seu código de liberação:")
            if codigo_digitado == st.secrets.get("TOKEN_LIBERACAO", "APROVADO-ATS-26"):
                with open(st.session_state.pdf_limpo_path, "rb") as f:
                    st.download_button("📄 Baixar Currículo Oficial", f.read(), "curriculo_limpo.pdf", "application/pdf", use_container_width=True)
            elif codigo_digitado != "":
                st.error("Código inválido.")

    # --------------------------------------------------------------------------
    # MÁQUINA DE ESTADOS DO CHAT (PYTHON HARDCODED - FASE 1 A 3)
    # --------------------------------------------------------------------------
    else:
        user_input = st.chat_input("Digite sua resposta aqui...")
        
        if user_input:
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            with st.chat_message("user"): 
                st.markdown(user_input)
                
            # FASE 1: Coleta da Vaga Alvo
            if st.session_state.step == "vaga_alvo":
                st.session_state.vaga_alvo = user_input.strip()
                st.session_state.step = "coleta_basica"
                
                msg_assistant = "Ótimo! Agora escreva do seu jeito um resumão sobre você: seu nome, sua cidade, e onde você já trabalhou ou estudou."
                st.session_state.chat_history.append({"role": "assistant", "content": msg_assistant})
                st.rerun()
                
            # FASE 2: Varredura de Texto (Extração Segura e Expandida)
            elif st.session_state.step == "coleta_basica":
                with st.spinner("Analisando suas informações..."):
                    dados_extraidos = extrair_dados_com_ia(user_input)
                    
                    if isinstance(dados_extraidos.get("personal_info"), dict):
                        info = dados_extraidos["personal_info"]
                        
                        if info.get("full_name"): 
                            st.session_state.resume["personal_info"]["full_name"] = info["full_name"]
                            
                        if isinstance(info.get("contact"), dict): 
                            st.session_state.resume["personal_info"]["contact"].update(info["contact"])
                            
                        if isinstance(info.get("location"), dict): 
                            st.session_state.resume["personal_info"]["location"].update(info["location"])
                            
                    if dados_extraidos.get("professional_summary"): 
                        st.session_state.resume["professional_summary"] = dados_extraidos["professional_summary"]
                        
                    if isinstance(dados_extraidos.get("work_experience"), list) and len(dados_extraidos["work_experience"]) > 0: 
                        if info.get("full_name"): st.session_state.resume["personal_info"]["full_name"] = info["full_name"]
                        if isinstance(info.get("contact"), dict): st.session_state.resume["personal_info"]["contact"].update(info["contact"])
                        if isinstance(info.get("location"), dict): st.session_state.resume["personal_info"]["location"].update(info["location"])
                        
                    if dados_extraidos.get("professional_summary"): st.session_state.resume["professional_summary"] = dados_extraidos["professional_summary"]
                    if isinstance(dados_extraidos.get("work_experience"), list) and len(dados_extraidos["work_experience"]) > 0: st.session_state.resume["work_experience"] = dados_extraidos["work_experience"]
                    if isinstance(dados_extraidos.get("education"), list) and len(dados_extraidos["education"]) > 0: st.session_state.resume["education"] = dados_extraidos["education"]
                    if isinstance(dados_extraidos.get("skills"), dict) and len(dados_extraidos["skills"]) > 0: st.session_state.resume["skills"] = dados_extraidos["skills"]
                        
                # FASE 2 -> 3: Transição para Confirmação
                st.session_state.step = "confirmacao_adicional"
                msg = "Legal! Já estruturei essa base. Você quer adicionar mais alguma coisa? (Ex: cursos complementares como CAD ou de idiomas, mais locais onde trabalhou, ou habilidades que esqueceu). Se já estiver tudo certo, é só digitar 'Finalizar' ou 'Pode gerar'."
                st.session_state.chat_history.append({"role": "assistant", "content": msg})
                st.rerun()
                
            # FASE 3: Loop de Confirmação Humano no Controle
            elif st.session_state.step == "confirmacao_adicional":
                user_lower = user_input.lower()
                fuga = ["finalizar", "pode gerar", "já está bom", "não", "pular"]
                
                # Gatilho de Saída
                if any(palavra in user_lower for palavra in fuga):
                    st.session_state.step = "geracao"
                    st.rerun()
                    
                # Captura de Novos Dados via IA
                with st.spinner("Integrando novas informações..."):
                    novos_dados = extrair_dados_com_ia(user_input)
                    
                    if isinstance(novos_dados.get("personal_info"), dict):
                        info = novos_dados["personal_info"]
                        if info.get("full_name"): st.session_state.resume["personal_info"]["full_name"] = info["full_name"]
                        if isinstance(info.get("contact"), dict): st.session_state.resume["personal_info"]["contact"].update(info["contact"])
                        if isinstance(info.get("location"), dict): st.session_state.resume["personal_info"]["location"].update(info["location"])
                        
                    if novos_dados.get("professional_summary"):
                        if st.session_state.resume.get("professional_summary"):
                            st.session_state.resume["professional_summary"] += "\n" + novos_dados["professional_summary"]
                        else:
                            st.session_state.resume["professional_summary"] = novos_dados["professional_summary"]
                            
                    if isinstance(novos_dados.get("work_experience"), list): st.session_state.resume["work_experience"].extend(novos_dados["work_experience"])
                    if isinstance(novos_dados.get("education"), list): st.session_state.resume["education"].extend(novos_dados["education"])
                    if isinstance(novos_dados.get("courses_certifications"), list): st.session_state.resume.setdefault("courses_certifications", []).extend(novos_dados["courses_certifications"])
                    if isinstance(novos_dados.get("skills"), dict): st.session_state.resume["skills"].update(novos_dados["skills"])
                
                msg_loop = "Adicionado com sucesso! Tem mais alguma coisa para incluir ou podemos Finalizar?"
                st.session_state.chat_history.append({"role": "assistant", "content": msg_loop})
                st.rerun()