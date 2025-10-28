from flask import Flask, request, jsonify, render_template, send_from_directory
import secrets
# Importa o datetime para pegar o tempo exato
from datetime import datetime
# NOVO: Importa a biblioteca de fuso horário
import pytz
import base64
import os
from fpdf import FPDF

app = Flask(__name__)

# --- CONFIGURAÇÃO ---
PDF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'finalizados')
os.makedirs(PDF_DIR, exist_ok=True)
TEMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp')
os.makedirs(TEMP_DIR, exist_ok=True)

dados_pendentes = {}

@app.route('/')
def index():
    return "<h1>Servidor do AssinaGym está no ar!</h1>"

@app.route('/api/gerar-link', methods=['POST'])
def gerar_link():
    dados_cliente = request.get_json()
    token = secrets.token_urlsafe(16)
    dados_pendentes[token] = dados_cliente
    link_assinatura = f"https://assinagym.onrender.com/assinar/{token}"
    return jsonify({"link_assinatura": link_assinatura})

@app.route('/assinar/<token>')
def pagina_assinatura(token):
    dados_cliente = dados_pendentes.get(token)
    if not dados_cliente:
        return "<h1>Link de assinatura inválido ou expirado.</h1>", 404
    
    data_hoje = datetime.today().strftime('%d/%m/%Y')
    return render_template('assinatura.html', token=token, **dados_cliente, data_solicitacao=data_hoje)

@app.route('/assinar/<token>/finalizar', methods=['POST'])
def finalizar_assinatura(token):
    dados_cliente = dados_pendentes.get(token)
    if not dados_cliente:
        return jsonify({"sucesso": False, "mensagem": "Token inválido."}), 404

    dados_formulario = request.get_json()
    assinatura_base64 = dados_formulario.get('assinatura')
    
    # --- DADOS DE AUDITORIA CORRIGIDOS ---
    sao_paulo_tz = pytz.timezone('America/Sao_Paulo')
    timestamp_sp = datetime.now(sao_paulo_tz).strftime('%d/%m/%Y às %H:%M:%S (%Z)')
    
    ip_lista_completa = request.headers.get('X-Forwarded-For', request.remote_addr)
    ip_cliente = ip_lista_completa.split(',')[0].strip()
    
    user_agent_cliente = request.headers.get('User-Agent', 'Não informado')

    try:
        img_data = base64.b64decode(assinatura_base64.split(',')[1])
        caminho_assinatura = os.path.join(TEMP_DIR, f'assinatura_{token}.png')
        with open(caminho_assinatura, 'wb') as f: f.write(img_data)
    except Exception as e:
        return jsonify({"sucesso": False, "mensagem": "Erro ao processar a imagem da assinatura."}), 500

    try:
        pdf = FPDF()
        pdf.add_page()
        
        # --- LÓGICA DE GERAÇÃO DO PDF COMPLETA ---
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, "SOLICITAÇÃO DE NÃO RENOVAÇÃO DE CONTRATO", 0, 1, 'C')
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, "IRONBERG", 0, 1, 'C')
        pdf.ln(10)

        pdf.set_font("Arial", size=12)
        texto_principal = f"""EU, {dados_cliente['nome']}, CPF: {dados_cliente['cpf']}, MATRÍCULA: {dados_cliente['matricula']} SOLICITO A FINALIZAÇÃO DO MEU CONTRATO FIRMADO COM A EMPRESA IRONBERG ALPHAVILLE CNPJ 55.157.797.0001/06, NO DIA {dados_cliente['data_inicio_contrato']}, EFETUEI O PAGAMENTO NO VALOR DE R$ {dados_cliente['valor_multa']} REFERENTE A RESCISÃO ANTECIPADA DO MEU CONTRATO."""
        pdf.multi_cell(0, 5, texto_principal)
        pdf.ln(5)

        pdf.cell(0, 5, f"DATA DA SOLICITAÇÃO: {datetime.today().strftime('%d/%m/%Y')}", 0, 1)
        pdf.cell(0, 5, f"CONSULTOR(A) RESPONSÁVEL: {dados_cliente['consultor']}", 0, 1)
        pdf.ln(10)
        
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "MOTIVO:", 0, 1)
        pdf.set_font("Arial", size=11)
        
        motivos = {
            "atendimento_professores": "NÃO GOSTEI DO ATENDIMENTO DOS PROFESSORES",
            "atendimento_recepcao": "NÃO GOSTEI DO ATENDIMENTO DA RECEPÇÃO",
            "problemas_saude": "ESTOU COM PROBLEMAS DE SAÚDE",
            "dificuldade_financeira": "ESTOU COM DIFICULDADE FINANCEIRA",
            "mudei_endereco": "MUDEI DE ENDEREÇO",
            "outros": "OUTROS, DESCREVA:"
        }
        
        for chave, texto in motivos.items():
            marcador = "[X]" if chave == dados_formulario.get('motivo') else "[ ]"
            pdf.cell(0, 6, f"{marcador} {texto}", 0, 1)

        if dados_formulario.get('motivo') == 'outros' and dados_formulario.get('texto_outros'):
            pdf.set_left_margin(pdf.l_margin + 5)
            pdf.multi_cell(0, 5, f"      {dados_formulario.get('texto_outros')}", 0, 'L')
            pdf.set_left_margin(10)
        pdf.ln(10)

        pdf.cell(0, 10, "ASSINATURA:", 0, 1)
        pdf.image(caminho_assinatura, w=80)
        
        pdf.ln(10)
        pdf.set_font("Arial", 'B', 8)
        pdf.cell(0, 5, "Trilha de Auditoria do Documento", 0, 1, 'C')
        pdf.set_font("Arial", size=7)
        pdf.multi_cell(0, 4,
            f"Documento assinado eletronicamente por {dados_cliente['nome']} em {timestamp_sp}.\n"
            f"Endereço IP do signatário: {ip_cliente}.\n"
            f"Navegador / Sistema Operacional: {user_agent_cliente}",
            border=1, align='C'
        )

        nome_arquivo_pdf = f"Cancelamento_{dados_cliente['nome'].replace(' ', '_')}_{token}.pdf"
        caminho_pdf_final = os.path.join(PDF_DIR, nome_arquivo_pdf)
        pdf.output(caminho_pdf_final)
        
        os.remove(caminho_assinatura)
        if token in dados_pendentes: del dados_pendentes[token]

        return jsonify({"sucesso": True,"mensagem": "Documento assinado com sucesso!","url_pdf": f"/finalizados/{nome_arquivo_pdf}"})

    except Exception as e:
        print(f"ERRO CRÍTICO NA GERAÇÃO DO PDF: {e}")
        return jsonify({"sucesso": False, "mensagem": "Erro interno ao gerar o documento PDF."}), 500

@app.route('/finalizados/<nome_arquivo>')
def servir_pdf(nome_arquivo):
    return send_from_directory(PDF_DIR, nome_arquivo)

if __name__ == '__main__':
    app.run(debug=True)