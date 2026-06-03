import streamlit as st
import tempfile
import os
import uuid
import re
import json
from jinja2 import Environment, FileSystemLoader

# Tenta importar o WeasyPrint e o OpenAI. Caso não estejam presentes, exibe instruções amigáveis na UI.
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
# INICIALIZAÇÃO DO ESTADO DA SESSÃO (st.session_state)
# ==============================================================================
if "resume" not in st.session_state:
    st.session_state.resume = {
        "personal_info": {
            "full_name": "",
            "contact": {
                "email": "",
                "phone": ""
            },
            "location": {
                "city": ""
            }
        },
        "professional_summary": "",
        "work_experience": [],
        "education": [],
        "skills": {}
    }

if "experience_done" not in st.session_state:
    st.session_state.experience_done = False

if "education_done" not in st.session_state:
    st.session_state.education_done = False

if "pdfs_gerados" not in st.session_state:
    st.session_state.pdfs_gerados = False

if "pdf_limpo_path" not in st.session_state:
    st.session_state.pdf_limpo_path = None

if "pdf_previsao_path" not in st.session_state:
    st.session_state.pdf_previsao_path = None

# ==============================================================================
# FUNÇÃO DE POLIMENTO COM INTELIGÊNCIA ARTIFICIAL (OPENAI)
# ==============================================================================
def polir_curriculo_com_ia(dados_brutos):
    """
    Envia o dicionário do currículo bruto para o gpt-4o-mini da OpenAI,
    solicitando reescrita otimizada para ATS seguindo a System Message exata,
    e retorna o JSON resultante decodificado como dicionário Python.
    """
    if not OPENAI_INSTALLED:
        raise ImportError("A biblioteca oficial 'openai' não está instalada no ambiente.")
        
    if "OPENAI_API_KEY" not in st.secrets:
        raise KeyError("Chave 'OPENAI_API_KEY' não encontrada nas configurações do Streamlit (st.secrets).")

    # Inicializar o cliente com a chave vinda dos segredos seguros
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    
    # System Message Exata Exigida
    system_prompt = (
        "Você é um Headhunter Sênior e Especialista em Otimização de Currículos para sistemas ATS. "
        "Sua missão é receber informações brutas de um candidato e transformá-las em um perfil profissional de alto impacto, "
        "retornando os dados reescritos EXCLUSIVAMENTE em formato JSON. "
        "REGRAS: 1. ZERO ALUCINAÇÃO: Proibido inventar empresas, cargos ou métricas não relatadas. "
        "2. POLIMENTO: Use verbos de ação na primeira pessoa do passado (ex: Otimizei, Liderei). "
        "3. GATILHOS: Adapte o resumo e experiências às vagas pretendidas. "
        "REGRAS DE SAÍDA: 1. Apenas JSON válido. 2. NÃO adicione saudações. 3. NÃO utilize blocos markdown como: "
    )
    
    # Mensagem do Usuário envia json serializado dos dados brutos
    user_prompt = json.dumps(dados_brutos, ensure_ascii=False)
    
    # Chamada ao modelo gpt-4o-mini com temperatura baixa para formatação rigorosa
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.2
    )
    
    # Recebimento da resposta crua
    response_text = response.choices[0].message.content.strip()
    
    # Processamento da Resposta: Limpeza de tags markdown caso a IA desobedeça
    if response_text.startswith("```"):
        lines = response_text.splitlines()
        # Remove a linha que abre o bloco (ex: ```json ou ```)
        if lines[0].startswith("```"):
            lines = lines[1:]
        # Remove a linha que fecha o bloco (ex: ```)
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        response_text = "\n".join(lines).strip()
        
    # Converter para dicionário Python limpo usando json.loads
    try:
        dados_polidos = json.loads(response_text)
        return dados_polidos
    except Exception as e:
        # Fallback de Resiliência: em caso de qualquer anomalia de parsing,
        # retorna os dados brutos originais para manter o fluxo operacional
        return dados_brutos

# ==============================================================================
# MOTOR DE EXTRAÇÃO SIMULADO (NER POR REGEX)
# ==============================================================================
def extrair_entidades(texto):
    """
    Simula uma extração NER (Um analisador de entidades) utilizando expressões
    regulares robustas e heurísticas de palavras-chave.
    Capaz de extrair nome, e-mail, telefone e cidade a partir de um único parágrafo.
    """
    entidades = {}
    
    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', texto)
    if email_match:
        entidades["email"] = email_match.group(0).strip()
        
    phone_match = re.search(r'(?:\+?55\s?)?(?:\(?\d{2}\)?\s?)?\d{4,5}[-\s]?\d{4}', texto)
    if phone_match:
        entidades["phone"] = phone_match.group(0).strip()
        
    city_match = re.search(
        r'(?:moro em|moro na|resido em|cidade de|sou de|localizado em)\s+([A-Za-zÀ-ÖØ-öø-ÿ\s\'\/-]+?)(?:\.|,| e |$)', 
        texto, 
        re.IGNORECASE
    )
    if city_match:
        entidades["city"] = city_match.group(1).strip()
        
    name_match = re.search(
        r'(?:meu nome é|meu nome e|sou o|sou a)\s+([A-Za-zÀ-ÖØ-öø-ÿ\s\'-]+?)(?:\.|,| e |$)', 
        texto, 
        re.IGNORECASE
    )
    if name_match:
        entidades["full_name"] = name_match.group(1).strip()
    else:
        words = texto.strip().split()
        if 2 <= len(words) <= 4:
            if all(w[0].isupper() for w in words if w and w[0].isalpha()) and not entidades.get("email") and not entidades.get("phone"):
                entidades["full_name"] = texto.strip()
                
    resumo_keywords = ["experiência", "trabalho", "atuo", "atuei", "carreira", "resumo", "objetivo", "profissional", "desenvolvedor", "gerente", "analista", "formado", "graduado"]
    if len(texto) > 40 and any(keyword in texto.lower() for keyword in resumo_keywords):
        entidades["professional_summary"] = texto.strip()
        
    return entidades

# ==============================================================================
# MOTOR DE GERAÇÃO DE PDF (JINJA2 + WEASYPRINT)
# ==============================================================================
def gerar_pdfs(dados_resume):
    diretorio_atual = os.path.dirname(os.path.abspath(__file__))
    env = Environment(loader=FileSystemLoader(diretorio_atual))
    template = env.get_template("template_cv.html")
    
    html_limpo = template.render(
        personal_info=dados_resume.get("personal_info", {}),
        professional_summary=dados_resume.get("professional_summary", ""),
        skills=dados_resume.get("skills", {}),
        work_experience=dados_resume.get("work_experience", []),
        education=dados_resume.get("education", []),
        preview_mode=False
    )
    
    html_previsao = template.render(
        personal_info=dados_resume.get("personal_info", {}),
        professional_summary=dados_resume.get("professional_summary", ""),
        skills=dados_resume.get("skills", {}),
        work_experience=dados_resume.get("work_experience", []),
        education=dados_resume.get("education", []),
        preview_mode=True
    )
    
    temp_dir = tempfile.gettempdir()
    path_limpo = os.path.join(temp_dir, f"curriculo_limpo_{uuid.uuid4().hex[:8]}.pdf")
    path_previsao = os.path.join(temp_dir, f"curriculo_previsao_{uuid.uuid4().hex[:8]}.pdf")
    
    HTML(string=html_limpo).write_pdf(path_limpo)
    HTML(string=html_previsao).write_pdf(path_previsao)
    
    return path_limpo, path_previsao

# ==============================================================================
# MÁQUINA DE GAPS & ROTEAMENTO DINÂMICO (LOOKAHEAD)
# ==============================================================================
def determinar_proxima_pergunta():
    resume = st.session_state.resume
    
    gaps_contato = []
    if not resume["personal_info"].get("full_name"):
        gaps_contato.append("nome completo")
    if not resume["personal_info"]["contact"].get("email"):
        gaps_contato.append("e-mail de contato")
    if not resume["personal_info"]["contact"].get("phone"):
        gaps_contato.append("telefone com DDD")
    if not resume["personal_info"]["location"].get("city"):
        gaps_contato.append("cidade e estado")
        
    if gaps_contato:
        if len(gaps_contato) == 4:
            return "dados_contato", "Para começarmos, qual é o seu **nome completo, e-mail, telefone com DDD** e a **cidade e estado** onde reside?"
        else:
            if len(gaps_contato) > 1:
                itens_str = ", ".join(gaps_contato[:-1]) + " e " + gaps_contato[-1]
            else:
                itens_str = gaps_contato[0]
            return "dados_contato", f"Entendido! Para completarmos suas informações de cadastro, poderia me informar o seu **{itens_str}**?"
            
    if not resume.get("professional_summary"):
        return "professional_summary", "Excelente! Seus dados pessoais foram salvos com sucesso. Agora, por favor, escreva um **breve resumo profissional** destacando suas competências e objetivos."
        
    if not resume.get("skills"):
        return "skills", "Muito bom! Quais são as suas **principais habilidades ou competências**? (Digite-as separadas por vírgula, ex: Python, Excel, Scrum)"
        
    if not st.session_state.experience_done:
        if not resume.get("work_experience"):
            return "work_experience", "Deseja adicionar uma **experiência profissional**? Digite o **Cargo e Empresa** (ou digite **'pular'** para ir para a Formação Acadêmica)."
        else:
            return "work_experience", "Deseja adicionar **outra** experiência profissional? Digite o **Cargo e Empresa** (ou digite **'pular'** para avançar)."
            
    if not st.session_state.education_done:
        if not resume.get("education"):
            return "education", "Deseja adicionar uma **formação acadêmica**? Digite o **Curso e Instituição** (ou digite **'pular'** para finalizar)."
        else:
            return "education", "Deseja adicionar **outra** formação acadêmica? Digite o **Curso e Instituição** (ou digite **'pular'** para finalizar)."
            
    return "completed", "Parabéns! Todos os dados básicos do seu currículo foram coletados com sucesso. Veja o rascunho estruturado à esquerda! 🎉"

# Inicializar histórico do chat
if "chat_history" not in st.session_state:
    _, primeira_pergunta = determinar_proxima_pergunta()
    st.session_state.chat_history = [
        {
            "role": "assistant",
            "content": primeira_pergunta
        }
    ]

# ==============================================================================
# ESTILIZAÇÃO PREMIUM (CSS Customizado)
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

    [data-testid="stSidebar"] {
        background-color: rgba(15, 23, 42, 0.95) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
        padding-top: 2rem;
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

    .stChatInputContainer {
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        background-color: rgba(15, 23, 42, 0.9) !important;
        border-radius: 12px !important;
        box-shadow: 0 -4px 30px rgba(0, 0, 0, 0.3) !important;
    }

    .stChatInputContainer:focus-within {
        border-color: #6366f1 !important;
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
# PROCESSAMENTO DO PROGRESSO E MAPEAMENTO DO ESTADO DA SESSÃO
# ==============================================================================
passo_atual, _ = determinar_proxima_pergunta()
st.session_state.etapa_atual = passo_atual

progresso_map = {
    "dados_contato": 25,
    "professional_summary": 60,
    "skills": 75,
    "work_experience": 85,
    "education": 95,
    "completed": 100
}
progresso_percentual = progresso_map.get(st.session_state.etapa_atual, 10)

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
        if full_name:
            info_html += f"<b>Nome:</b> {full_name}<br>"
        if email:
            info_html += f"<b>E-mail:</b> {email}<br>"
        if phone:
            info_html += f"<b>Telefone:</b> {phone}<br>"
        if city:
            info_html += f"<b>Localização:</b> {city}<br>"
            
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
# COLUNA DA DIREITA: CHAT INTERATIVO / PAINEL FINAL DE EXPORTAÇÃO
# ------------------------------------------------------------------------------
with col_chat:
    with st.expander("💡 Como conversar com a nossa IA (Clique para expandir)", expanded=False):
        st.markdown(
            "👋 Olá! Sou o seu **Assistente AI de Criação de Currículo (com Escuta Ativa e IA ATS)**.\n\n"
            "Eu sou capaz de entender várias informações ao mesmo tempo! Você pode se apresentar "
            "por completo (nome, e-mail, fone e cidade) ou responder às minhas perguntas passo a passo."
        )

    st.markdown(
        """
        <div style="background-color: rgba(30, 41, 59, 0.3); padding: 1.5rem; border-radius: 16px; border: 1px solid rgba(255, 255, 255, 0.05); min-height: 520px; display: flex; flex-direction: column;">
            <h4 style="margin-top: 0; color: #818cf8; display: flex; align-items: center; gap: 8px;">
                💬 Chat com o Assistente
            </h4>
        """, 
        unsafe_allow_html=True
    )

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
    st.markdown("</div>", unsafe_allow_html=True)
    
    # --------------------------------------------------------------------------
    # BLOCO CONDICIONAL: FINALIZADO (st.session_state.etapa_atual == "completed")
    # --------------------------------------------------------------------------
    if st.session_state.etapa_atual == "completed":
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Alerta se WeasyPrint ou OpenAI não estiverem instalados
        if not WEASYPRINT_INSTALLED or not OPENAI_INSTALLED:
            st.warning(
                "⚠️ Dependências ausentes no ambiente! "
                "Para testar perfeitamente, por favor execute: `pip install weasyprint openai` no terminal."
            )
            
        st.info("🏆 **Coleta Finalizada!** Clique abaixo para polir seu currículo com IA e gerar os seus arquivos em PDF.")
        
        # O botão principal executa a interceptação com IA e renderização do PDF
        if st.button("🚀 Gerar Currículos em PDF", use_container_width=True, disabled=not WEASYPRINT_INSTALLED or not OPENAI_INSTALLED):
            # 1. Altera a mensagem do st.spinner exatamente como exigido
            with st.spinner("Aguarde... Nossa IA Headhunter está polindo e otimizando o seu currículo para sistemas ATS!"):
                try:
                    # 2. Intercepta os dados brutos e chama o polimento com IA
                    dados_polidos = polir_curriculo_com_ia(st.session_state.resume)
                    
                    # 3. Passa os dados polidos para a geração física dos PDFs
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
                    label="💳 Pagar R$ 19,90 para Liberar PDF Oficial",
                    url="COLOQUE_SEU_LINK_DO_MERCADO_PAGO_AQUI",
                    use_container_width=True
                )
                
            # Campo de liberação de Token abaixo das colunas
            codigo_digitado = st.text_input("Já pagou? Digite seu código de liberação:")
            if codigo_digitado == "APROVADO-ATS-26":
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
                    
    # --------------------------------------------------------------------------
    # BLOCO CONDICIONAL: CHAT ATIVO (Esconde o input quando finalizado)
    # --------------------------------------------------------------------------
    else:
        user_input = st.chat_input("Digite sua resposta aqui...")
        
        if user_input:
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)
                
            etapa_pendente, _ = determinar_proxima_pergunta()
            
            # Executar a EXTRAÇÃO INTELIGENTE (NER)
            entidades_extraidas = extrair_entidades(user_input)
            atualizou_por_ner = False
            
            if "full_name" in entidades_extraidas:
                st.session_state.resume["personal_info"]["full_name"] = entidades_extraidas["full_name"]
                atualizou_por_ner = True
            if "email" in entidades_extraidas:
                st.session_state.resume["personal_info"]["contact"]["email"] = entidades_extraidas["email"]
                atualizou_por_ner = True
            if "phone" in entidades_extraidas:
                st.session_state.resume["personal_info"]["contact"]["phone"] = entidades_extraidas["phone"]
                atualizou_por_ner = True
            if "city" in entidades_extraidas:
                st.session_state.resume["personal_info"]["location"]["city"] = entidades_extraidas["city"]
                atualizou_por_ner = True
            if "professional_summary" in entidades_extraidas:
                st.session_state.resume["professional_summary"] = entidades_extraidas["professional_summary"]
                atualizou_por_ner = True
                
            # Fallback clássico para respostas estruturadas ou diretas simples
            if not atualizou_por_ner:
                if etapa_pendente == "dados_contato":
                    resume_dict = st.session_state.resume
                    if not resume_dict["personal_info"].get("full_name"):
                        resume_dict["personal_info"]["full_name"] = user_input.strip()
                    elif not resume_dict["personal_info"]["contact"].get("email"):
                        resume_dict["personal_info"]["contact"]["email"] = user_input.strip()
                    elif not resume_dict["personal_info"]["contact"].get("phone"):
                        resume_dict["personal_info"]["contact"]["phone"] = user_input.strip()
                    elif not resume_dict["personal_info"]["location"].get("city"):
                        resume_dict["personal_info"]["location"]["city"] = user_input.strip()
                        
                elif etapa_pendente == "professional_summary":
                    st.session_state.resume["professional_summary"] = user_input.strip()
                    
                elif etapa_pendente == "skills":
                    skills_list = [s.strip() for s in user_input.replace("e", ",").split(",") if s.strip()]
                    st.session_state.resume["skills"] = {skill: True for skill in skills_list}
                    
                elif etapa_pendente == "work_experience":
                    if user_input.strip().lower() == "pular":
                        st.session_state.experience_done = True
                    else:
                        st.session_state.resume["work_experience"].append({
                            "role_company": user_input.strip()
                        })
                        
                elif etapa_pendente == "education":
                    if user_input.strip().lower() == "pular":
                        st.session_state.education_done = True
                    else:
                        st.session_state.resume["education"].append({
                            "degree_institution": user_input.strip()
                        })
            else:
                # Se atualizou algo via NER, mas o usuário estava em etapas de listas ou habilidades,
                # garantimos que respostas diretas a essas etapas específicas não sejam ignoradas
                if etapa_pendente == "skills" and not entidades_extraidas:
                    skills_list = [s.strip() for s in user_input.replace("e", ",").split(",") if s.strip()]
                    st.session_state.resume["skills"] = {skill: True for skill in skills_list}
                elif etapa_pendente == "work_experience":
                    if user_input.strip().lower() == "pular":
                        st.session_state.experience_done = True
                    else:
                        st.session_state.resume["work_experience"].append({
                            "role_company": user_input.strip()
                        })
                elif etapa_pendente == "education":
                    if user_input.strip().lower() == "pular":
                        st.session_state.education_done = True
                    else:
                        st.session_state.resume["education"].append({
                            "degree_institution": user_input.strip()
                        })
            
            proximo_passo, proxima_pergunta = determinar_proxima_pergunta()
            st.session_state.chat_history.append({"role": "assistant", "content": proxima_pergunta})
            
            st.rerun()
