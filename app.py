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
# CONFIGURAÇÃO DA PÁGINA
# ==============================================================================
st.set_page_config(
    page_title="CurrículoBuilder AI — Criador de Currículos",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# GARANTIA DE INFRAESTRUTURA (Cria o template HTML base se não existir)
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
                body { font-family: 'Inter', sans-serif; color: #333; line-height: 1.5; margin: 0; padding: 20px; }
                .watermark { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%) rotate(-45deg); font-size: 80px; color: rgba(255,0,0,0.1); z-index: -1; white-space: nowrap; }
                h1 { color: #1e293b; border-bottom: 2px solid #cbd5e1; padding-bottom: 5px; margin-bottom: 5px; }
                .contact-info { font-size: 0.9em; color: #475569; margin-bottom: 20px; }
                h2 { color: #0f172a; font-size: 1.2em; margin-top: 20px; border-bottom: 1px solid #e2e8f0; padding-bottom: 3px; }
                .job-title { font-weight: 600; color: #1e293b; }
                ul { margin-top: 5px; padding-left: 20px; }
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
            <p>{{ professional_summary }}</p>
            {% endif %}
            
            {% if work_experience %}
            <h2>Experiência Profissional</h2>
            {% for exp in work_experience %}
                <div style="margin-bottom: 15px;">
                    <div class="job-title">{{ exp.get('role_company', 'Empresa/Cargo') }}</div>
                    <p style="margin: 5px 0;">{{ exp.get('description', '') }}</p>
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
# INICIALIZAÇÃO DO ESTADO DA SESSÃO (st.session_state)
# ==============================================================================
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
        "skills": {}
    }

if "step" not in st.session_state: st.session_state.step = "vaga_alvo"
if "vaga_alvo" not in st.session_state: st.session_state.vaga_alvo = ""
if "pdfs_gerados" not in st.session_state: st.session_state.pdfs_gerados = False
if "pdf_limpo_path" not in st.session_state: st.session_state.pdf_limpo_path = None
if "pdf_previsao_path" not in st.session_state: st.session_state.pdf_previsao_path = None

if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {
            "role": "assistant",
            "content": "Olá! Para qual vaga ou área você quer direcionar este currículo? (Ex: Vendedor, Motorista, Jovem Aprendiz, ou 'Qualquer uma')"
        }
    ]

# Segurança: Captura a API Key via st.secrets
API_KEY = st.secrets.get("OPENAI_API_KEY", "")

# ==============================================================================
# FASE 4: MOTOR DE GERAÇÃO ("O MILAGRE ATS")
# ==============================================================================
def polir_curriculo_com_ia(dados_brutos):
    if not OPENAI_INSTALLED or not API_KEY:
        raise Exception("API da OpenAI não configurada.")

    client = OpenAI(api_key=API_KEY)
    vaga_alvo = st.session_state.vaga_alvo if st.session_state.vaga_alvo else "qualquer área"
    
    system_prompt = (
        f"Você é um Headhunter sênior escrevendo um currículo ATS. O usuário busca a vaga: '{vaga_alvo}'. "
        "Ele tem um perfil avesso a escrever. Se as experiências profissionais dele tiverem descrições pobres ou vazias, "
        "sua obrigação é INFERIR e GERAR 2 a 3 bullet points profissionais baseados estritamente na função (Cargo) que ele ocupou, "
        "usando o método STAR (Situação, Tarefa, Ação, Resultado) e verbos de ação. "
        "Melhore a apresentação sem inventar cargos de chefia ou mentiras. Crie um Resumo Profissional focado na vaga alvo.\n"
        "Você DEVE retornar os dados polidos EXCLUSIVAMENTE em formato JSON, mantendo a estrutura exata do JSON recebido."
    )
    
    user_prompt = json.dumps(dados_brutos, ensure_ascii=False)
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content.strip())
    except Exception as e:
        return dados_brutos # Fallback seguro

# ==============================================================================
# MOTOR DE EXTRAÇÃO JSON (CUSTO QUASE ZERO)
# ==============================================================================
def extrair_dados_com_ia(texto):
    if not OPENAI_INSTALLED or not API_KEY:
        return {} 

    client = OpenAI(api_key=API_KEY)
    
    system_prompt = (
        "Você é um extrator de dados. Seu objetivo é ler o texto desestruturado do candidato e mapear "
        "os dados EXCLUSIVAMENTE para o seguinte esquema JSON. Se a informação não existir, omita a chave.\n"
        "{\n"
        '  "personal_info": {"full_name": "", "contact": {"email": "", "phone": ""}, "location": {"city": ""}},\n'
        '  "professional_summary": "",\n'
        '  "work_experience": [{"role_company": "Cargo e Empresa", "description": ""}],\n'
        '  "education": [{"degree_institution": ""}],\n'
        '  "skills": {"Habilidade": "Nível"}\n'
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
    except Exception as e:
        return {}

# ==============================================================================
# MOTOR DE GERAÇÃO DE PDF
# ==============================================================================
def gerar_pdfs(dados_resume):
    diretorio_atual = os.path.dirname(os.path.abspath(__file__))
    env = Environment(loader=FileSystemLoader(diretorio_atual))
    template = env.get_template("template_cv.html")
    
    html_limpo = template.render(**dados_resume, eh_previsao=False)
    html_previsao = template.render(**dados_resume, eh_previsao=True)
    
    temp_dir = tempfile.gettempdir()
    path_limpo = os.path.join(temp_dir, f"cv_limpo_{uuid.uuid4().hex[:8]}.pdf")
    path_previsao = os.path.join(temp_dir, f"cv_previsao_{uuid.uuid4().hex[:8]}.pdf")
    
    HTML(string=html_limpo).write_pdf(path_limpo)
    HTML(string=html_previsao).write_pdf(path_previsao)
    
    return path_limpo, path_previsao

# ==============================================================================
# ESTILIZAÇÃO PREMIUM CSS (NOVA PALETA LIMPA - OCEAN BLUE & SLATE)
# ==============================================================================
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"], .stApp {
        font-family: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Fundo da aplicação: Grafite escuro e profundo, sem tons roxos */
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #020617 100%);
        color: #f8fafc;
    }

    [data-testid="stSidebar"] {
        background-color: rgba(15, 23, 42, 0.95) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
        padding-top: 2rem;
    }

    /* Cards de Visualização */
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
        border-color: rgba(56, 189, 248, 0.4); /* Azul Claro no Hover */
        box-shadow: 0 4px 20px rgba(56, 189, 248, 0.1);
        transform: translateY(-2px);
    }

    /* Títulos dos Cards */
    .preview-header {
        font-weight: 600;
        font-size: 1.05rem;
        color: #38bdf8; /* Sky Blue Clean */
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

    /* Tags de Habilidades */
    .skill-badge {
        display: inline-block;
        background-color: rgba(56, 189, 248, 0.15); /* Fundo Azul Translúcido */
        color: #7dd3fc; /* Texto Azul Claro */
        border: 1px solid rgba(56, 189, 248, 0.3);
        border-radius: 6px;
        padding: 0.15rem 0.45rem;
        font-size: 0.8rem;
        margin-right: 0.3rem;
        margin-bottom: 0.3rem;
    }

    /* Balões do Chat */
    .stChatMessage {
        background-color: rgba(30, 41, 59, 0.5) !important;
        border: 1px solid rgba(255, 255, 255, 0.03) !important;
        border-radius: 12px !important;
        padding: 1rem !important;
        margin-bottom: 0.75rem !important;
        backdrop-filter: blur(5px);
    }
    
    /* Ícone do Robô Assistente */
    [data-testid="chatAvatarIcon-assistant"] {
        background-color: #2563eb !important; /* Azul Profissional */
    }

    /* Campo de Digitação */
    .stChatInputContainer {
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        background-color: rgba(15, 23, 42, 0.9) !important;
        border-radius: 12px !important;
        box-shadow: 0 -4px 30px rgba(0, 0, 0, 0.3) !important;
    }

    .stChatInputContainer:focus-within {
        border-color: #38bdf8 !important; /* Foco em Azul Claro */
    }

    /* Título Principal no Topo */
    .app-header {
        background: linear-gradient(90deg, #2563eb 0%, #38bdf8 100%); /* Gradiente Azul */
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

    /* Crachá de Status */
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
        background: linear-gradient(90deg, #2563eb, #38bdf8); /* Gradiente Azul */
        height: 100%;
        border-radius: 9999px;
        transition: width 0.5s ease-in-out;
    }
    
    /* Botões Principais */
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
# PROCESSAMENTO DO PROGRESSO
# ==============================================================================
progresso_map = {
    "vaga_alvo": 10,
    "coleta_basica": 30,
    "lapidacao": 70,
    "geracao": 100
}
progresso_percentual = progresso_map.get(st.session_state.step, 10)

# ==============================================================================
# LAYOUT SPA (Duas Colunas Principais)
# ==============================================================================
col_preview, col_chat = st.columns([1, 2], gap="large")

# ------------------------------------------------------------------------------
# COLUNA DA ESQUERDA: VISUALIZADOR DE CURRÍCULO (PREVIEW + JSON)
# ------------------------------------------------------------------------------
with col_preview:
    st.markdown('<div class="app-header">CurrículoBuilder</div>', unsafe_allow_html=True)
    st.markdown('<div class="app-subtitle">Criação Interativa e Inteligente</div>', unsafe_allow_html=True)
    
    st.markdown(f'<div class="status-badge">Progresso: {progresso_percentual}%</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="progress-bar-container">
            <div class="progress-bar-fill" style="width: {progresso_percentual}%;"></div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    st.write("---")
    
    tab_visual, tab_json = st.tabs(["📝 Rascunho Visual", "💾 JSON em Tempo Real"])
    
    with tab_visual:
        resume = st.session_state.resume
        
        full_name = resume["personal_info"].get("full_name")
        email = resume["personal_info"]["contact"].get("email")
        phone = resume["personal_info"]["contact"].get("phone")
        city = resume["personal_info"]["location"].get("city")
        
        has_info = any([full_name, email, phone, city])
        
        info_html = ""
        if full_name: info_html += f"<b>Nome:</b> {full_name}<br>"
        if email: info_html += f"<b>E-mail:</b> {email}<br>"
        if phone: info_html += f"<b>Telefone:</b> {phone}<br>"
        if city: info_html += f"<b>Localização:</b> {city}<br>"
            
        st.markdown(
            f"""
            <div class="preview-card">
                <div class="preview-header">👤 Informações Pessoais</div>
                {"<div class='preview-placeholder'>Aguardando dados...</div>" if not has_info else f"<div class='preview-value'>{info_html}</div>"}
            </div>
            """,
            unsafe_allow_html=True
        )
        
        summary = resume.get("professional_summary")
        st.markdown(
            f"""
            <div class="preview-card">
                <div class="preview-header">🎯 Resumo Profissional</div>
                {"<div class='preview-placeholder'>Aguardando dados...</div>" if not summary else f"<div class='preview-value'>{summary}</div>"}
            </div>
            """,
            unsafe_allow_html=True
        )
        
        skills = resume.get("skills", {})
        skills_html = "".join(f'<span class="skill-badge">{skill}</span>' for skill in skills.keys())
        st.markdown(
            f"""
            <div class="preview-card">
                <div class="preview-header">🛠️ Habilidades</div>
                {"<div class='preview-placeholder'>Aguardando dados...</div>" if not skills else f"<div>{skills_html}</div>"}
            </div>
            """,
            unsafe_allow_html=True
        )
        
        experiences = resume.get("work_experience", [])
        exp_html = ""
        for exp in experiences:
            exp_html += f"<div class='preview-value' style='margin-bottom:0.5rem;'>💼 <b>{exp.get('role_company')}</b></div>"
            
        st.markdown(
            f"""
            <div class="preview-card">
                <div class="preview-header">💼 Experiências Profissionais ({len(experiences)})</div>
                {"<div class='preview-placeholder'>Aguardando dados ou 'pular'...</div>" if not experiences else exp_html}
            </div>
            """,
            unsafe_allow_html=True
        )
        
        education = resume.get("education", [])
        edu_html = ""
        for edu in education:
            edu_html += f"<div class='preview-value' style='margin-bottom:0.5rem;'>🎓 <b>{edu.get('degree_institution')}</b></div>"
            
        st.markdown(
            f"""
            <div class="preview-card">
                <div class="preview-header">🎓 Formação Acadêmica ({len(education)})</div>
                {"<div class='preview-placeholder'>Aguardando dados ou 'pular'...</div>" if not education else edu_html}
            </div>
            """,
            unsafe_allow_html=True
        )
        
    with tab_json:
        st.markdown("<p style='color:#64748b; font-size:0.85rem; margin-bottom: 0.5rem;'>Representação exata de st.session_state.resume:</p>", unsafe_allow_html=True)
        st.json(st.session_state.resume)

# ------------------------------------------------------------------------------
# COLUNA DA DIREITA: CHAT INTERATIVO E PAINEL FINAL DE EXPORTAÇÃO
# ------------------------------------------------------------------------------
with col_chat:
    with st.expander("💡 Como conversar com a nossa IA (Clique para expandir)", expanded=False):
        st.markdown(
            "👋 Olá! Sou o seu **Assistente AI de Criação de Currículo (com Escuta Ativa e IA ATS)**.\n\n"
            "Eu sou capaz de entender várias informações ao mesmo tempo! Você pode se apresentar "
            "por completo (nome, e-mail, fone e cidade) ou responder às minhas perguntas passo a passo."
        )

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    
    # ==========================================================================
    # BLOCO CONDICIONAL LÓGICO: GERAÇÃO FINAL E DOWNLOADS
    # ==========================================================================
    if st.session_state.step == "geracao":
        st.markdown("<br>", unsafe_allow_html=True)
        
        if not WEASYPRINT_INSTALLED or not OPENAI_INSTALLED:
            st.warning("⚠️ Dependências ausentes no ambiente! Instale `weasyprint` e `openai`.")
            
        st.info("🏆 **Coleta Finalizada!** Clique abaixo para polir seu currículo com IA e gerar os seus arquivos em PDF.")
        
        if st.button("🚀 Gerar Currículos em PDF", use_container_width=True, disabled=not WEASYPRINT_INSTALLED or not OPENAI_INSTALLED):
            with st.spinner("Aguarde... Nossa IA Headhunter está polindo e otimizando o seu currículo para sistemas ATS!"):
                try:
                    dados_polidos = polir_curriculo_com_ia(st.session_state.resume)
                    path_limpo, path_previsao = gerar_pdfs(dados_polidos)
                    
                    st.session_state.pdf_limpo_path = path_limpo
                    st.session_state.pdf_previsao_path = path_previsao
                    st.session_state.pdfs_gerados = True
                except Exception as e:
                    st.error(f"Erro no processamento da IA ou do PDF: {str(e)}")
                    
        if st.session_state.pdfs_gerados:
            st.success("Currículo otimizado com sucesso!")
            col_d1, col_d2 = st.columns(2)
            
            with col_d1:
                if st.session_state.pdf_previsao_path and os.path.exists(st.session_state.pdf_previsao_path):
                    with open(st.session_state.pdf_previsao_path, "rb") as f:
                        pdf_previsao_bytes = f.read()
                    st.download_button(
                        label="👀 Baixar Previsão Grátis",
                        data=pdf_previsao_bytes,
                        file_name="curriculo_previsao.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
            
            with col_d2:
                st.link_button(
                    label="💳 Pagar R$ 1,99 para Liberar PDF Oficial",
                    url="COLOQUE_SEU_LINK_DO_MERCADO_PAGO_AQUI",
                    use_container_width=True
                )
                
            codigo_digitado = st.text_input("Já pagou? Digite seu código de liberação:")
            VALOR_TOKEN_SEGURO = st.secrets.get("TOKEN_LIBERACAO", "APROVADO-ATS-26")
            
            if codigo_digitado == VALOR_TOKEN_SEGURO:
                if st.session_state.pdf_limpo_path and os.path.exists(st.session_state.pdf_limpo_path):
                    with open(st.session_state.pdf_limpo_path, "rb") as f:
                        pdf_limpo_bytes = f.read()
                    st.download_button(
                        label="📄 Baixar Currículo Oficial",
                        data=pdf_limpo_bytes,
                        file_name="curriculo_limpo.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
            elif codigo_digitado != "":
                st.error("Código inválido.")

    # ==========================================================================
    # MÁQUINA DE ESTADOS DO CHAT (COLETA E LAPIDAÇÃO)
    # ==========================================================================
    else:
        user_input = st.chat_input("Digite sua resposta aqui...")
        
        if user_input:
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)
                
            # FASE 1: VAGA ALVO
            if st.session_state.step == "vaga_alvo":
                st.session_state.vaga_alvo = user_input.strip()
                st.session_state.step = "coleta_basica"
                next_msg = "Ótimo! Agora escreva do seu jeito um resumão sobre você: seu nome, sua cidade, e onde você já trabalhou ou estudou."
                st.session_state.chat_history.append({"role": "assistant", "content": next_msg})
                st.rerun()
                
            # FASE 2: VARREDURA INTELIGENTE (EXTRAÇÃO JSON)
            elif st.session_state.step == "coleta_basica":
                with st.spinner("Analisando suas informações..."):
                    dados_extraidos = extrair_dados_com_ia(user_input)
                    
                    # MERGE INTELIGENTE DEFENSIVO
                    if isinstance(dados_extraidos.get("personal_info"), dict):
                        info = dados_extraidos["personal_info"]
                        if info.get("full_name"): 
                            st.session_state.resume["personal_info"]["full_name"] = info["full_name"]
                        
                        contact = info.get("contact")
                        if isinstance(contact, dict):
                            if contact.get("email"): st.session_state.resume["personal_info"]["contact"]["email"] = contact["email"]
                            if contact.get("phone"): st.session_state.resume["personal_info"]["contact"]["phone"] = contact["phone"]
                            
                        location = info.get("location")
                        if isinstance(location, dict):
                            if location.get("city"): st.session_state.resume["personal_info"]["location"]["city"] = location["city"]
                            
                    if dados_extraidos.get("professional_summary"):
                        st.session_state.resume["professional_summary"] = dados_extraidos["professional_summary"]
                        
                    if isinstance(dados_extraidos.get("work_experience"), list) and len(dados_extraidos["work_experience"]) > 0:
                        st.session_state.resume["work_experience"] = dados_extraidos["work_experience"]
                        
                    if isinstance(dados_extraidos.get("education"), list) and len(dados_extraidos["education"]) > 0:
                        st.session_state.resume["education"] = dados_extraidos["education"]
                        
                    if isinstance(dados_extraidos.get("skills"), dict) and len(dados_extraidos["skills"]) > 0:
                        st.session_state.resume["skills"] = dados_extraidos["skills"]
                        
                # FASE 3: Lógica Qualitativa de Tiro Único (One-Shot)
                exp_list = st.session_state.resume.get("work_experience", [])
                precisa_lapidacao = False
                cargo_alvo = "seu emprego anterior"
                
                if exp_list:
                    primeira_exp = exp_list[0]
                    desc = primeira_exp.get("description", "")
                    if len(desc) < 20:
                        precisa_lapidacao = True
                        cargo_alvo = primeira_exp.get("role_company", cargo_alvo)
                
                if precisa_lapidacao:
                    st.session_state.step = "lapidacao"
                    next_msg = f"Vi que você trabalhou como **{cargo_alvo}**. Para seu currículo chamar a atenção, é legal colocar uma estimativa de ano ou o que você mais fazia lá. Consegue me dar algum detalhe?"
                    st.session_state.chat_history.append({"role": "assistant", "content": next_msg})
                else:
                    st.session_state.step = "geracao"
                    
                st.rerun()
                
            # FASE 3 -> FASE 4: LAPIDAÇÃO (Sem Loop)
            elif st.session_state.step == "lapidacao":
                exp_list = st.session_state.resume.get("work_experience", [])
                if exp_list:
                    desc_atual = str(exp_list[0].get("description", ""))
                    exp_list[0]["description"] = desc_atual + " | Adicionais: " + user_input.strip()
                    
                st.session_state.step = "geracao"
                st.rerun()