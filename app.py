from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'segredo_super_secreto'

# --- Funções auxiliares ---
def conectar_db():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def mascarar_email(email):
    parte1, parte2 = email.split("@")
    if len(parte1) <= 2:
        return "*" * len(parte1) + "@" + parte2
    return parte1[:2] + "*" * (len(parte1) - 2) + "@" + parte2

def registrar_log(usuario_id, nome, email, acao):
    conn = conectar_db()
    cursor = conn.cursor()
    data_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO logs (usuario_id, nome_usuario, email_usuario, acao_usuario, data_hora) VALUES (?, ?, ?, ?, ?)",
        (usuario_id, nome, email, acao, data_hora)
    )
    conn.commit()
    conn.close()

# --- Rotas ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        senha = request.form['senha']
        conn = conectar_db()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO usuarios (nome, email, senha) VALUES (?, ?, ?)", (nome, email, senha))
            conn.commit()
            cursor.execute("SELECT id, nome FROM usuarios WHERE email = ?", (email,))
            usuario = cursor.fetchone()
            registrar_log(usuario['id'], usuario['nome'], email, "Cadastro realizado")
            flash("Cadastro realizado com sucesso. Faça o login.", "sucesso")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("Este e-mail já está cadastrado.", "erro")
        finally:
            conn.close()
    return render_template('cadastro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE email = ? AND senha = ?", (email, senha))
        usuario = cursor.fetchone()
        conn.close()
        if usuario:
            session['usuario'] = dict(usuario)
            session['usuario_id'] = usuario['id']
            registrar_log(usuario['id'], usuario['nome'], usuario['email'], "Login realizado")
            return redirect(url_for('comprar'))
        else:
            flash("Email ou senha inválidos.", "erro")
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/comprar', methods=['GET', 'POST'])
def comprar():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    conn = conectar_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        ingresso_id = request.form['ingresso']
        quantidade = int(request.form.get('quantidade', 1))
        cursor.execute("SELECT nome_evento, preco, disponivel FROM ingressos WHERE id = ?", (ingresso_id,))
        ingresso = cursor.fetchone()
        if ingresso:
            if ingresso['disponivel'] >= quantidade:
                # Registrar a compra
                usuario_id = session['usuario_id']
                data_compra = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute(
                    "INSERT INTO compras (usuario_id, ingresso_id, quantidade, data_compra) VALUES (?, ?, ?, ?)",
                    (usuario_id, ingresso_id, quantidade, data_compra)
                )
                # Atualizar a disponibilidade do ingresso
                cursor.execute(
                    "UPDATE ingressos SET disponivel = disponivel - ? WHERE id = ?",
                    (quantidade, ingresso_id)
                )
                conn.commit()

                flash("Compra realizada com sucesso!", "sucesso")
                usuario = session['usuario']
                registrar_log(usuario['id'], usuario['nome'], usuario['email'], f"Compra do ingresso ID {ingresso_id}")
                return redirect(url_for('comprar'))
            else:
                flash("Quantidade indisponível.", "erro")

    cursor.execute("SELECT id, nome_evento, descricao, preco, data_evento, disponivel FROM ingressos WHERE disponivel > 0")
    ingressos_raw = cursor.fetchall()
    conn.close()

    ingressos = []
    for ingresso in ingressos_raw:
        ingresso_dict = dict(ingresso)
        ingresso_dict['preco'] = f"{ingresso_dict['preco']:.2f}".replace('.', ',')
        ingresso_dict['data_evento'] = datetime.strptime(ingresso_dict['data_evento'], "%Y-%m-%d").strftime("%d/%m/%Y")
        ingressos.append(ingresso_dict)

    return render_template('comprar.html', ingressos=ingressos)

# --- Nova rota: Meus ingressos ---
@app.route('/meus-ingressos')
def meus_ingressos():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    usuario_id = session['usuario_id']
    conn = conectar_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT c.id as compra_id, c.quantidade, c.data_compra,
               i.nome_evento, i.data_evento, i.preco
        FROM compras c
        JOIN ingressos i ON i.id = c.ingresso_id
        WHERE c.usuario_id = ?
        ORDER BY c.data_compra DESC
    """, (usuario_id,))
    rows = cursor.fetchall()
    conn.close()

    compras = []
    for r in rows:
        d = dict(r)
        d['preco'] = f"{d['preco']:.2f}".replace('.', ',')
        d['data_evento'] = datetime.strptime(d['data_evento'], "%Y-%m-%d").strftime("%d/%m/%Y")
        d['data_compra_br'] = datetime.strptime(d['data_compra'], "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y %H:%M")
        compras.append(d)

    return render_template('meus_ingressos.html', compras=compras)

@app.route('/logout')
def logout():
    if "usuario" in session:
        usuario = session['usuario']
        registrar_log(usuario['id'], usuario['nome'], usuario['email'], "Logout realizado")
        session.clear()
    return redirect(url_for('index'))

# --- Execução ---
if __name__ == '__main__':
    app.run(debug=True, port=5000)
