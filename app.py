from flask import Flask, request, jsonify
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from datetime import datetime
from collections import OrderedDict

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:_Arc3usadmin7410@fornecedores.cxic2sq6q4t5.us-east-1.rds.amazonaws.com/Fornecedores'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Função para calcular a similaridade por cosseno
def calcular_similaridade(vetor1, vetor2):
    return cosine_similarity([vetor1], [vetor2])[0][0]

# Função para normalizar os valores
def normalizar(valor, minimo, maximo):
    if maximo - minimo == 0:
        return 0
    return (valor - minimo) / (maximo - minimo)

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
        if isinstance(dtEntrega, str):
            dtEntrega_usuario = datetime.strptime(dtEntrega, '%Y-%m-%d').date()
        else:
            dtEntrega_usuario = dtEntrega

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

    # Calcular a similaridade de cada proposta com o vetor do usuário
    propostas_com_similaridade = []

    for proposta in propostas:
        vetor_proposta = []

        if 'valor' in parametros_usuario:
            vetor_proposta.append(float(proposta['valorTotal']))
        if 'dtEntrega' in parametros_usuario:
            dtEntrega_proposta = proposta['dtEntrega']
            diff = (dtEntrega_usuario - dtEntrega_proposta).days
            vetor_proposta.append(abs(diff))  # Valor absoluto da diferença
        if 'experiencia' in parametros_usuario:
            vetor_proposta.append(int(proposta['anosExperiencia']))
        if 'recorrente' in parametros_usuario:
            if 'recorrente' in proposta and proposta['recorrente'] is not None:
                vetor_proposta.append(int(proposta['recorrente']))
            else:
                vetor_proposta.append(0)

        # Normalização dos vetores
        vetor_usuario_normalizado = [normalizar(v, min(vetor_usuario), max(vetor_usuario)) for v in vetor_usuario]
        vetor_proposta_normalizado = [normalizar(v, min(vetor_proposta), max(vetor_proposta)) for v in vetor_proposta]

        # Calcular similaridade
        if vetor_usuario_normalizado and vetor_proposta_normalizado:
            similaridade = calcular_similaridade(vetor_usuario_normalizado, vetor_proposta_normalizado)
            proposta['similaridade'] = similaridade

            # Organize the keys in the desired order
            proposta_ordenada = {
                'idProposta': proposta['idProposta'],
                'empresa': proposta['empresa'],
                'telefone': proposta['telefone'],
                'email': proposta['email'],
                'valorTotal': proposta['valorTotal'],
                'dtEntrega': proposta['dtEntrega'],
                'recorrente': proposta['recorrente'],
                'anosExperiencia': proposta['anosExperiencia'],
                'similaridade': proposta['similaridade']
            }

            propostas_com_similaridade.append(proposta_ordenada)

    # Ordenar as propostas pela similaridade
    propostas_com_similaridade.sort(key=lambda x: x['similaridade'], reverse=True)

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
            'anosExperiencia': row[7],
            'similaridade': None  # Aqui adiciona-se a coluna similaridade
        })
        propostas.append(proposta)
    
    return propostas

if __name__ == '__main__':
    app.run(debug=True)
