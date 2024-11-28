from flask import Flask, request, jsonify
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from datetime import datetime
from collections import OrderedDict
from sklearn.preprocessing import MinMaxScaler

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:_Arc3usadmin7410@fornecedores.cxic2sq6q4t5.us-east-1.rds.amazonaws.com/Fornecedores'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Função para calcular a similaridade por cosseno
def calcular_similaridade(vetor1, vetor2):
    return cosine_similarity([vetor1], [vetor2])[0][0]

# Função para classificar os anos de experiência
def classificar_experiencia(anos):
    if anos <= 5:
        return 'Iniciante'
    elif anos <= 15:
        return 'Intermediário'
    else:
        return 'Experiente'

@app.route('/propostas', methods=['GET'])
def get_propostas():
    # Pegando os parâmetros da query string
    solicitacao = request.args.get('solicitacao')
    dtEntrega = request.args.get('dtEntrega')
    valor = request.args.get('valor')
    recorrente = request.args.get('recorrente')
    experiencia = request.args.get('experiencia')

    # Inicializa uma lista para os parâmetros válidos
    vetor_usuario = []
    parametros_usuario = []

    # Adiciona o valor ao vetor se não for vazio
    if valor:
        vetor_usuario.append(float(valor))
        parametros_usuario.append('valor')

    # Adiciona a data de entrega ao vetor se não for vazia
    if dtEntrega:
        dtEntrega_usuario = datetime.strptime(dtEntrega, '%Y-%m-%d').date()
        diff_dtEntrega_usuario = (dtEntrega_usuario - datetime.today().date()).days
        vetor_usuario.append(diff_dtEntrega_usuario)
        parametros_usuario.append('dtEntrega')

    # Adiciona a experiência ao vetor se não for vazia
    if experiencia:
        vetor_usuario.append(int(experiencia))
        parametros_usuario.append('experiencia')

    # Adiciona o recorrente ao vetor se não for vazio
    if recorrente:
        vetor_usuario.append(int(recorrente))
        parametros_usuario.append('recorrente')

    # Buscar as propostas no banco de dados
    propostas = buscar_propostas(solicitacao)
    if not propostas:
        return jsonify([])

    # Preparar dados para normalização
    valores = np.array([proposta['valorTotal'] for proposta in propostas]).reshape(-1, 1)
    entregas = np.array([(datetime.strptime(proposta['dtEntrega'], '%Y-%m-%d').date() - datetime.today().date()).days for proposta in propostas]).reshape(-1, 1)

    # Configurar os escalonadores
    scaler_valor = MinMaxScaler()
    scaler_entrega = MinMaxScaler()

    # Normalizar os dados das propostas
    valores_normalizados = scaler_valor.fit_transform(valores)
    entregas_normalizadas = scaler_entrega.fit_transform(entregas)

    # Normalizar vetor do usuário
    vetor_usuario_array = np.array(vetor_usuario).reshape(-1, 1)
    scaler_usuario = MinMaxScaler()
    vetor_usuario_normalizado = scaler_usuario.fit_transform(vetor_usuario_array).flatten()

    # Calcular a similaridade de cada proposta com o vetor do usuário
    propostas_com_similaridade = []

    for i, proposta in enumerate(propostas):
        vetor_proposta = []

        if 'valor' in parametros_usuario:
            vetor_proposta.append(valores_normalizados[i][0])
        if 'dtEntrega' in parametros_usuario:
            vetor_proposta.append(entregas_normalizadas[i][0])
        if 'experiencia' in parametros_usuario:
            vetor_proposta.append(proposta['anosExperiencia'] / 30.0)  # Normalizar anos de experiência (escala aproximada)
        if 'recorrente' in parametros_usuario:
            vetor_proposta.append(proposta.get('recorrente', 0))

        # Calcular similaridade
        if vetor_usuario_normalizado and vetor_proposta:
            similaridade = calcular_similaridade(vetor_usuario_normalizado, vetor_proposta)
            proposta['similaridade'] = f"{similaridade * 100:.2f}%"

            # Ajustar campos
            proposta['anosExperiencia'] = classificar_experiencia(proposta['anosExperiencia'])
            proposta['recorrente'] = 'Sim' if proposta['recorrente'] == 1 else 'Não'

            propostas_com_similaridade.append(proposta)

    # Ordenar pela similaridade
    propostas_com_similaridade.sort(key=lambda x: float(x['similaridade'].replace('%', '')), reverse=True)

    return jsonify(propostas_com_similaridade)

def buscar_propostas(solicitacao):
    sql = text(f"""
        SELECT 
            p.idProposta,
            f.empresa,
            f.telefone,
            f.email,
            p.valorTotal,
            p.dtEntrega,
            f.recorrente,
            f.anosExperiencia
        FROM 
            Proposta p
        INNER JOIN 
            Fornecedor f
        ON 
            p.fkFornecedor = f.idFornecedor
        WHERE 
            p.fkSolicitacao = {solicitacao};
    """)

    result = db.session.execute(sql).fetchall()

    propostas = []

    for row in result:
        proposta = OrderedDict({
            'idProposta': row[0],
            'empresa': row[1],
            'telefone': row[2],
            'email': row[3],
            'valorTotal': row[4],
            'dtEntrega': row[5],
            'recorrente': row[6],
            'anosExperiencia': row[7]
        })
        propostas.append(proposta)

    return propostas

if __name__ == '__main__':
    app.run(debug=True)
