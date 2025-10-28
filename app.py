from flask import Flask, request, jsonify, render_template, send_from_directory
import secrets
from datetime import date
import base64
import os
from fpdf import FPDF

app = Flask(__name__)

# --- CONFIGURAÇÃO ---
# Cria uma pasta para salvar os PDFs finalizados, se ela não existir
PDF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'finalizados')
os.makedirs(PDF_DIR, exist_ok=True)

# Cria uma pasta para salvar as imagens de assinatura temporariamente
TEMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp')
os.makedirs(TEMP_DIR, exist_ok=True)
# --------------------


# Um dicionário simples para armazenar os dados de cada cancelamento
dados_pendentes = {}

# --- DADOS DE EXEMPLO PARA TESTE ---
token_teste = "token-do-gabriel"
dados_pendentes[token_teste] = {
    "nome": "GABRIEL PEREIRA",
    "cpf": "357.711.428-24",
    "matricula": "235658",
    "valor_multa": "107.70",
    "data_inicio_contrato": "23/03/2025",
    "consultor": "GABRIEL GOUVEA"
}
# -----------------------------------


@app.route('/')
def index():
    return "<h1>Servidor do AssinaGym está no ar!</h1>"


@app.route('/api/gerar-link', methods=['POST'])
def gerar_link():
    dados_cliente = request.get_json()
    token = secrets.token_urlsafe(16)
    dados_pendentes[token] = dados_cliente
    link_assinatura = f"http://127.0.0.1:5000/assinar/{token}"
    return jsonify({"link_assinatura": link_assinatura})


@app.route('/assinar/<token>')
def pagina_assinatura(token):
    dados_cliente = dados_pendentes.get(token)
    if not dados_cliente:
        return "<h1>Link de assinatura inválido ou expirado.</h1>", 404
    
    data_hoje = date.today().strftime('%d/%m/%Y')
    
    return render_template(
        'assinatura.html',
        token=token, # Passa o token para o template
        nome=dados_cliente.get('nome'),
        cpf=dados_cliente.get('cpf'),
        matricula=dados_cliente.get('matricula'),
        valor_multa=dados_cliente.get('valor_multa'),
        data_inicio_contrato=dados_cliente.get('data_inicio_contrato'),
        consultor=dados_cliente.get('consultor'),
        data_solicitacao=data_hoje
    )

# --- NOVA ROTA PARA RECEBER A ASSINATURA E GERAR O PDF ---
@app.route('/assinar/<token>/finalizar', methods=['POST'])
def finalizar_assinatura(token):
    # 1. Verifica se o token é válido
    dados_cliente = dados_pendentes.get(token)
    if not dados_cliente:
        return jsonify({"sucesso": False, "mensagem": "Token inválido."}), 404

    # 2. Pega os dados enviados pelo JavaScript
    dados_formulario = request.get_json()
    motivo_selecionado = dados_formulario.get('motivo')
    texto_outros = dados_formulario.get('texto_outros', '')
    assinatura_base64 = dados_formulario.get('assinatura')

    # 3. Decodifica a imagem da assinatura e salva temporariamente
    try:
        # Remove o cabeçalho "data:image/png;base64,"
        img_data = base64.b64decode(assinatura_base64.split(',')[1])
        caminho_assinatura = os.path.join(TEMP_DIR, f'assinatura_{token}.png')
        with open(caminho_assinatura, 'wb') as f:
            f.write(img_data)
    except Exception as e:
        print(f"Erro ao decodificar a assinatura: {e}")
        return jsonify({"sucesso": False, "mensagem": "Erro ao processar a imagem da assinatura."}), 500

    # 4. Gera o PDF com FPDF2
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    
    # Título
    pdf.set_font("Helvetica", 'B', 16)
    pdf.cell(0, 10, "SOLICITAÇÃO DE NÃO RENOVAÇÃO DE CONTRATO", 0, 1, 'C')
    pdf.set_font("Helvetica", 'B', 14)
    pdf.cell(0, 10, "IRONBERG", 0, 1, 'C')
    pdf.ln(10)

    # Corpo do texto
    pdf.set_font("Helvetica", size=12)
    texto_principal = f"""
    EU, {dados_cliente['nome']}, CPF: {dados_cliente['cpf']}, MATRÍCULA: {dados_cliente['matricula']} SOLICITO A FINALIZAÇÃO DO MEU CONTRATO FIRMADO COM A EMPRESA IRONBERG ALPHAVILLE CNPJ 55.157.979.0001/06, NO DIA {dados_cliente['data_inicio_contrato']}, EFETUEI O PAGAMENTO NO VALOR DE R$ {dados_cliente['valor_multa']} REFERENTE A RESCISÃO ANTECIPADA DO MEU CONTRATO.

    Estou ciente de que, caso exista alguma mensalidade com vencimento nos próximos 30 dias, ela será debitada no cartão de crédito, salvo se eu realizar o pagamento antecipado. Também estou ciente de que o plano contratado só será cancelado após a efetivação desse débito.
    """
    pdf.multi_cell(0, 5, texto_principal)
    pdf.ln(5)

    pdf.cell(0, 5, f"DATA: {date.today().strftime('%d/%m/%Y')}", 0, 1)
    pdf.cell(0, 5, f"CONSULTOR(A) RESPONSÁVEL: {dados_cliente['consultor']}", 0, 1)
    pdf.ln(10)
    
    # Motivos do cancelamento
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(0, 10, "MOTIVO:", 0, 1)
    pdf.set_font("Helvetica", size=11)
    
    motivos = {
        "atendimento_professores": "NÃO GOSTEI DO ATENDIMENTO DOS PROFESSORES",
        "atendimento_recepcao": "NÃO GOSTEI DO ATENDIMENTO DA RECEPÇÃO",
        "problemas_saude": "ESTOU COM PROBLEMAS DE SAÚDE",
        "dificuldade_financeira": "ESTOU COM DIFICULDADE FINANCEIRA",
        "mudei_endereco": "MUDEI DE ENDEREÇO",
        "outros": "OUTROS, DESCREVA:"
    }
    
    for chave, texto in motivos.items():
        marcador = "[X]" if chave == motivo_selecionado else "[ ]"
        pdf.cell(0, 6, f"{marcador} {texto}", 0, 1)

    if motivo_selecionado == 'outros' and texto_outros:
        pdf.set_left_margin(pdf.l_margin + 5) # Indenta o texto
        pdf.multi_cell(0, 5, f"      {texto_outros}", 0, 'L')
        pdf.set_left_margin(10) # Reseta a margem
    pdf.ln(10)

    # Assinatura
    pdf.cell(0, 10, "ASSINATURA:", 0, 1)
    pdf.image(caminho_assinatura, w=80) # Adiciona a imagem da assinatura
    
    # Salva o PDF
    nome_arquivo_pdf = f"Cancelamento_{dados_cliente['nome'].replace(' ', '_')}_{token}.pdf"
    caminho_pdf_final = os.path.join(PDF_DIR, nome_arquivo_pdf)
    pdf.output(caminho_pdf_final)
    
    # Limpa o arquivo de assinatura temporário
    os.remove(caminho_assinatura)

    # Remove os dados da lista de pendentes para que o link não possa ser usado novamente
    del dados_pendentes[token]

    # 5. Retorna uma resposta de sucesso para o navegador
    return jsonify({
        "sucesso": True,
        "mensagem": "Documento assinado com sucesso!",
        "url_pdf": f"/finalizados/{nome_arquivo_pdf}"
    })


# Rota para permitir o download do PDF finalizado
@app.route('/finalizados/<nome_arquivo>')
def servir_pdf(nome_arquivo):
    return send_from_directory(PDF_DIR, nome_arquivo)


if __name__ == '__main__':
    app.run(debug=True)