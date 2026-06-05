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
        "personal_info": {"full_name": "", "contact": {"email": "", "phone": ""}, "location": {"city": ""}},
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
    
    # PROMPT AGRESSIVO (Exatamente como definido no seu planejamento)
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
# ESTILIZAÇÃO PREMIUM CSS (RESTAURADA E COMPLETA)
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
    
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
        color: #f8fafc;
    }

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
        border-color: rgba(99, 102, 241, 0.4);
        box-shadow: 0 4px 20px rgba(99, 102, 241, 0.1);
        transform: translateY(-2px);
    }

    .preview-header {
        font-weight: 600;
        font-size: 1.05rem;
        color: #818cf8;
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
        color: #cbd5e1;
        font-size: 0.9rem;
        line-height: 1.4;
    }

    .skill-badge {
        display: inline-block;
        background-color: rgba(99, 102, 241, 0.15);
        color: #a5b4fc;
        border: 1px solid rgba(99, 102, 241, 0.3);
        border-radius: 6px;
        padding: 0.15rem 0.45rem;
        font-size: 0.8rem;
        margin-right: 0.3rem;
        margin-bottom: 0.3rem;
    }

    .stChatMessage {
        background-color: rgba(30, 41, 59, 0.5) !important;
        border: 1px solid rgba(255, 255, 255, 0.03) !important;
        border-radius: 12px !important;
        padding: 1rem !important;
        margin-bottom: 0.75rem !important;
        backdrop-filter: blur(5px);
    }
    
    [data-testid="chatAvatarIcon-assistant"] {
        background-color: #6366f1 !important;
    }

    .app-header {
        background: linear-gradient(90deg, #6366f1 0%, #a855f7 100%);
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
        background-color: rgba(99, 102, 241, 0.15);
        color: #a5b4fc;
        border: 1px solid rgba(99, 102, 241, 0.3);
    }

    .progress-bar-container {
        margin: 1rem 0;
        background: rgba(255, 255, 255, 0.05);
        border-radius: 9999px;
        height: 6px;
        overflow: hidden;
    }

    .progress-bar-fill {
        background: linear-gradient(90deg, #6366f1, #a855f7);
        height: 100%;
        border-radius: 9999px;
        transition: width 0.5s ease-in-out;
    }
    
    .stButton>button {
        background: linear-gradient(90deg, #6366f1 0%, #a855f7 100%) !important;
        color: white !important;
        border: none !important;
        font-weight: 600 !important;
        border-radius: 10px !important;
        padding: 0.6rem 1.5rem !important;
        transition: transform 0.2s ease, box-shadow 0.2s ease !important;
    }
    
    .stButton>button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 15px rgba(99, 102, 241, 0.4) !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ==============================================================================
# LAYOUT SPA (COLUNAS) E VISUALIZAÇÃO RICA
# ==============================================================================
progresso_map = {"vaga_alvo": 10, "coleta_basica": 30, "lapidacao": 70, "geracao": 100}
progresso_percentual = progresso_map.get(st.session_state.step, 10)

col_preview, col_chat = st.columns([1, 2], gap="large")

with col_preview:
    st.markdown('<div class="app-header">CurrículoBuilder</div>', unsafe_allow_html=True)
    st.markdown('<div class="app-subtitle">Criação Interativa e Inteligente</div>', unsafe_allow_html=True)
    
    st.markdown(f'<div class="status-badge">Progresso: {progresso_percentual}%</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="progress-bar-container"><div class="progress-bar-fill" style="width: {progresso_percentual}%;"></div></div>', unsafe_allow_html=True)
    
    st.write("---")
    
    tab_visual, tab_json = st.tabs(["📝 Rascunho Visual", "💾 JSON Interno"])
    
    with tab_visual:
        resume = st.session_state.resume
        
        # 1. Informações Pessoais
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
        
        # 2. Resumo Profissional
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
        
        # 3. Habilidades (Badges)
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
        
        # 4. Experiências
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
        
        # 5. Educação
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
    # FINALIZAÇÃO (BOTÃO E PAGAMENTO)
    # ==========================================================================
    if st.session_state.step == "geracao":
        st.info("🏆 **Coleta Finalizada!** Clique abaixo para nossa IA criar a mágica.")
        
        if st.button("🚀 Gerar Currículos em PDF", use_container_width=True):
            with st.spinner("Headhunter IA escrevendo seu currículo (Método STAR)..."):
                dados_polidos = polir_curriculo_com_ia(st.session_state.resume)
                path_limpo, path_previsao = gerar_pdfs(dados_polidos)
                st.session_state.pdf_limpo_path = path_limpo
                st.session_state.pdf_previsao_path = path_previsao
                st.session_state.pdfs_gerados = True
                    
        if st.session_state.pdfs_gerados:
            st.success("Pronto! Veja a previsão gratuita.")
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                with open(st.session_state.pdf_previsao_path, "rb") as f:
                    st.download_button("👀 Baixar Previsão Grátis", f.read(), "previsao.pdf", "application/pdf", use_container_width=True)
            with col_d2:
                st.link_button("💳 Pagar R$ 1,99 para Liberar Oficial", "COLOQUE_SEU_LINK", use_container_width=True)
                
            codigo_digitado = st.text_input("Código de liberação:")
            if codigo_digitado == st.secrets.get("TOKEN_LIBERACAO", "APROVADO-ATS-26"):
                with open(st.session_state.pdf_limpo_path, "rb") as f:
                    st.download_button("📄 Baixar Oficial", f.read(), "curriculo_oficial.pdf", "application/pdf", use_container_width=True)

    # ==========================================================================
    # MÁQUINA DE ESTADOS REATORA (PYTHON HARDCODED - CUSTO ZERO)
    # ==========================================================================
    else:
        user_input = st.chat_input("Escreva aqui...")
        if user_input:
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)
                
            # FASE 1 -> FASE 2
            if st.session_state.step == "vaga_alvo":
                st.session_state.vaga_alvo = user_input.strip()
                st.session_state.step = "coleta_basica"
                # Exatamente a string solicitada no plano:
                next_msg = "Ótimo! Agora escreva do seu jeito um resumão sobre você: seu nome, sua cidade, e onde você já trabalhou ou estudou."
                st.session_state.chat_history.append({"role": "assistant", "content": next_msg})
                st.rerun()
                
            # FASE 2 -> FASE 3 (Varredura de baixo custo)
            elif st.session_state.step == "coleta_basica":
                with st.spinner("Analisando..."):
                    dados_extraidos = extrair_dados_com_ia(user_input)
                    
                    # Merge Seguro
                    if isinstance(dados_extraidos.get("personal_info"), dict):
                        info = dados_extraidos["personal_info"]
                        if info.get("full_name"): st.session_state.resume["personal_info"]["full_name"] = info["full_name"]
                        if isinstance(info.get("contact"), dict):
                            st.session_state.resume["personal_info"]["contact"].update(info["contact"])
                        if isinstance(info.get("location"), dict):
                            st.session_state.resume["personal_info"]["location"].update(info["location"])

                    if dados_extraidos.get("professional_summary"):
                        st.session_state.resume["professional_summary"] = dados_extraidos["professional_summary"]
                        
                    # Prevenção de loop: Atribuição direta se houver dados
                    if isinstance(dados_extraidos.get("work_experience"), list) and len(dados_extraidos["work_experience"]) > 0:
                        st.session_state.resume["work_experience"] = dados_extraidos["work_experience"]
                    if isinstance(dados_extraidos.get("education"), list) and len(dados_extraidos["education"]) > 0:
                        st.session_state.resume["education"] = dados_extraidos["education"]
                    if isinstance(dados_extraidos.get("skills"), dict) and len(dados_extraidos["skills"]) > 0:
                        st.session_state.resume["skills"] = dados_extraidos["skills"]
                        
                # LÓGICA QUALITATIVA "ONE-SHOT"
                exp_list = st.session_state.resume.get("work_experience", [])
                if exp_list and len(exp_list[0].get("description", "")) < 20:
                    st.session_state.step = "lapidacao"
                    cargo = exp_list[0].get("role_company", "seu emprego anterior")
                    # Exatamente a string solicitada no plano:
                    next_msg = f"Vi que você trabalhou como {cargo}. Para seu currículo chamar a atenção, é legal colocar o ano ou o que você fazia lá. Lembra de algum detalhe?"
                    st.session_state.chat_history.append({"role": "assistant", "content": next_msg})
                else:
                    st.session_state.step = "geracao"
                    
                st.rerun()
                
            # FASE 3 -> FASE 4 (Sem loop de "Quer adicionar mais?")
            elif st.session_state.step == "lapidacao":
                exp_list = st.session_state.resume.get("work_experience", [])
                if exp_list:
                    desc_atual = str(exp_list[0].get("description", ""))
                    # Junta o que o cliente respondeu (mesmo se for "não lembro") e manda pro milagre final.
                    exp_list[0]["description"] = desc_atual + " | Detalhes extra: " + user_input.strip()
                    
                st.session_state.step = "geracao"
                st.rerun()