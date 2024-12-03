from flask import Flask, request, jsonify
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from datetime import datetime, timedelta
from collections import OrderedDict
from sklearn.preprocessing import MinMaxScaler

app = Flask(__name__)

# Configurações do banco de dados
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:_Arc3usadmin7410@fornecedores.cxic2sq6q4t5.us-east-1.rds.amazonaws.com/Fornecedores'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

def calcular_similaridade(vetor1, vetor2):
    """Calcula a similaridade por cosseno entre dois vetores."""
    # Garantir que os vetores não contenham valores inválidos (None ou NaN)
    vetor1 = np.nan_to_num(vetor1, nan=0.0)
    vetor2 = np.nan_to_num(vetor2, nan=0.0)
    
    # Garantir que os vetores estejam no intervalo [0, 1]
    vetor1 = np.clip(vetor1, 0, 1)
    vetor2 = np.clip(vetor2, 0, 1)
    
    # Calcular a similaridade por cosseno, se os vetores não forem vazios
    if vetor1.size > 0 and vetor2.size > 0:
        return cosine_similarity([vetor1], [vetor2])[0][0]
    return 0  # Retorna 0 se não for possível calcular a similaridade

def classificar_experiencia(anos):
    """Classifica a experiência com base no número de anos."""
    if anos <= 5:
        return 'Iniciante'
    elif anos <= 15:
        return 'Intermediário'
    else:
        return 'Experiente'

@app.route('/atualizar_proposta', methods=['GET', 'POST'])
def atualizar_proposta():
    print('cheguei aqui')
    """Rota para atualizar a proposta e a solicitação."""
    proposta_id = request.args.get('idProposta')  # Recebe o valor de 'idProposta' da query string

    status_solicitacao = 'A AVALIAR'  # Novo status para a solicitação

    if not proposta_id:
        return jsonify({'error': 'ID da proposta é necessário.'}), 400

    try:
        # Ajustar a data e hora para 3 horas atrás
        dt_escolha = datetime.today() - timedelta(hours=3)
        
        # Atualizar a tabela Proposta
        proposta = db.session.execute(
            text(""" 
                UPDATE Proposta 
                SET escolhido = 1, dtEscolha = :dt_escolha
                WHERE idProposta = :proposta_id
            """), {'dt_escolha': dt_escolha, 'proposta_id': proposta_id}
        )
        
        # Atualizar a tabela Solicitacao
        solicitacao = db.session.execute(
            text(""" 
                UPDATE Solicitacao 
                SET status = :status 
                WHERE idSolicitacao = (
                    SELECT fkSolicitacao
                    FROM Proposta
                    WHERE idProposta = :proposta_id
                )
            """), {'status': status_solicitacao, 'proposta_id': proposta_id}
        )

        # Commit das alterações no banco de dados
        db.session.commit()

        return jsonify({'message': 'Proposta e Solicitação atualizadas com sucesso.'}), 200

    except Exception as e:
        # Em caso de erro, desfazer as alterações no banco
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/propostas', methods=['GET'])
def get_propostas():
    """Rota para buscar e calcular a similaridade das propostas."""
    solicitacao = request.args.get('solicitacao')
    dtEntrega = request.args.get('dtEntrega')
    valor = request.args.get('valor')
    recorrente = request.args.get('recorrente')
    experiencia = request.args.get('experiencia')

    vetor_usuario = []
    parametros_usuario = []

    # Construir vetor do usuário
    if valor:
        vetor_usuario.append(float(valor))
        parametros_usuario.append('valor')
    if dtEntrega:
        dtEntrega_usuario = datetime.strptime(dtEntrega, '%Y-%m-%d').date()
        diff_dtEntrega_usuario = (dtEntrega_usuario - datetime.today().date()).days
        vetor_usuario.append(diff_dtEntrega_usuario)
        parametros_usuario.append('dtEntrega')
    if experiencia:
        vetor_usuario.append(int(experiencia))
        parametros_usuario.append('experiencia')
    if recorrente:
        vetor_usuario.append(int(recorrente))
        parametros_usuario.append('recorrente')

    # Buscar propostas no banco de dados
    propostas = buscar_propostas(solicitacao)
    if not propostas:
        return jsonify([])

    # Normalizar os dados das propostas
    valores = np.array([proposta['valorTotal'] for proposta in propostas]).reshape(-1, 1)
    entregas = np.array([(proposta['dtEntrega'] - datetime.today().date()).days for proposta in propostas]).reshape(-1, 1)
    experiencias = np.array([proposta['anosExperiencia'] for proposta in propostas]).reshape(-1, 1)

    scaler_valor = MinMaxScaler()
    scaler_entrega = MinMaxScaler()
    scaler_experiencia = MinMaxScaler()

    valores_normalizados = scaler_valor.fit_transform(valores)
    entregas_normalizadas = scaler_entrega.fit_transform(entregas)
    experiencias_normalizadas = scaler_experiencia.fit_transform(experiencias)

    # Normalizar o vetor do usuário
    vetor_usuario_normalizado = []
    if 'valor' in parametros_usuario:
        vetor_usuario_normalizado.append(scaler_valor.transform([[vetor_usuario[parametros_usuario.index('valor')]]])[0][0])
    if 'dtEntrega' in parametros_usuario:
        vetor_usuario_normalizado.append(scaler_entrega.transform([[vetor_usuario[parametros_usuario.index('dtEntrega')]]])[0][0])
    if 'experiencia' in parametros_usuario:
        vetor_usuario_normalizado.append(scaler_experiencia.transform([[vetor_usuario[parametros_usuario.index('experiencia')]]])[0][0])
    if 'recorrente' in parametros_usuario:
        vetor_usuario_normalizado.append(vetor_usuario[parametros_usuario.index('recorrente')])

    vetor_usuario_normalizado = np.array(vetor_usuario_normalizado)

    # Calcular similaridade e preparar a resposta
    propostas_com_similaridade = []
    for i, proposta in enumerate(propostas):
        vetor_proposta = []
        if 'valor' in parametros_usuario:
            vetor_proposta.append(valores_normalizados[i][0])
        if 'dtEntrega' in parametros_usuario:
            vetor_proposta.append(entregas_normalizadas[i][0])
        if 'experiencia' in parametros_usuario:
            vetor_proposta.append(experiencias_normalizadas[i][0])
        if 'recorrente' in parametros_usuario:
            vetor_proposta.append(proposta.get('recorrente', 0))

        vetor_proposta_normalizado = np.array(vetor_proposta)

        if vetor_usuario_normalizado.size > 0 and vetor_proposta_normalizado.size > 0:
            similaridade = calcular_similaridade(vetor_usuario_normalizado, vetor_proposta_normalizado)
            proposta['similaridade'] = f"{similaridade * 100:.2f}%"
            proposta['anosExperiencia'] = classificar_experiencia(proposta['anosExperiencia'])
            proposta['recorrente'] = 'Sim' if proposta['recorrente'] == 1 else 'Não'
            proposta['dtEntrega'] = proposta['dtEntrega'].strftime('%Y-%m-%d')
            propostas_com_similaridade.append(proposta)

    # Ordenar por similaridade em ordem decrescente
    propostas_com_similaridade.sort(key=lambda x: float(x['similaridade'].replace('%', '')), reverse=True)
    return jsonify(propostas_com_similaridade)

def buscar_propostas(solicitacao):
    """Busca as propostas no banco de dados para a solicitação especificada."""
    sql = text(""" 
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
            p.fkSolicitacao = :solicitacao;
    """)
    result = db.session.execute(sql, {'solicitacao': solicitacao}).fetchall()

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
