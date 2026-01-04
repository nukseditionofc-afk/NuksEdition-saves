from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from flask_mail import Mail, Message
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import json
import random
import uuid


load_dotenv()

app = Flask(__name__, template_folder='.', static_folder='Public')
app.secret_key = os.getenv('SECRET_KEY', 'uma-chave-secreta-muito-segura')

# --- Configuração do Flask-Mail ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME')
mail = Mail(app)

USERS_FILE = 'NuksEdition.json'

def load_users():
    if not os.path.exists(USERS_FILE): return {}
    try:
        with open(USERS_FILE, 'r') as f: return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError): return {}

def save_users(users):
    with open(USERS_FILE, 'w') as f: json.dump(users, f, indent=4)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        users = load_users()
        user_data = users.get(email)
        
        # LÓGICA DE ERRO ATUALIZADA
        if not user_data:
            # Caso 1: Email não existe no banco de dados
            return redirect(url_for('index', error='email_not_found'))
        elif not check_password_hash(user_data['password_hash'], senha):
            # Caso 2: Senha está incorreta
            return redirect(url_for('index', error='wrong_password'))
        else:
            # Caso 3: Sucesso no login
            session['logged_in'] = True
            session['usuario'] = user_data['username']
            return redirect(url_for('home'))
            
    return render_template('Public/login.html')

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        usuario = request.form['usuario']
        email = request.form['email']
        senha = request.form['senha']
        users = load_users()

        if email in users:
            return redirect(url_for('cadastro', error='email_exists'))

        codigo = str(random.randint(100000, 999999))
        
        try:
            msg = Message('Seu código de confirmação NuksEdition', recipients=[email])
            msg.body = f'Olá {usuario}, seu código de confirmação é: {codigo}'
            mail.send(msg)
        except Exception as e:
            print(f"Erro ao enviar e-mail: {e}")
            return "Ocorreu um erro ao enviar o e-mail de confirmação.", 500

        # A conta NÃO é salva aqui. Os dados ficam temporários na sessão.
        session['temp_user'] = {'usuario': usuario, 'email': email, 'senha': senha}
        session['codigo_confirmacao'] = codigo
        
        return redirect(url_for('confirmar'))

    return render_template('Public/cadastro.html')

@app.route('/confirmar.html')
def confirmar():
    return render_template('Public/confirmar.html')

@app.route('/verificar-codigo', methods=['POST'])
def verificar_codigo():
    codigo_digitado = request.form.get('codigo')
    codigo_sessao = session.get('codigo_confirmacao')

    if codigo_digitado == codigo_sessao:
        temp_user = session.get('temp_user')
        if not temp_user: return redirect(url_for('index'))

        users = load_users()
        
        # É SOMENTE AQUI que a conta é criada e salva no arquivo.
        user_id = str(uuid.uuid4())
        creation_date = datetime.now().strftime('%d/%m/%Y')
        hashed_password = generate_password_hash(temp_user['senha'], method='pbkdf2:sha256')

        users[temp_user['email']] = {
            'id': user_id,
            'username': temp_user['usuario'],
            'password_hash': hashed_password,
            'data_criacao': creation_date
        }
        save_users(users)

        session.clear()
        session['logged_in'] = True
        session['usuario'] = temp_user['usuario']
        
        return redirect(url_for('home', success=True))
    else:
        return redirect(url_for('confirmar', error=True))

# --- Rotas Protegidas ---
@app.route('/home')
def home():
    if not session.get('logged_in'): return redirect(url_for('index'))
    return render_template('protect/home.html', usuario=session.get('usuario'))

@app.route('/explorar')
def explorar():
    if not session.get('logged_in'): return redirect(url_for('index'))
    return render_template('protect/explorar.html', usuario=session.get('usuario'))

@app.route('/download/calculadora')
def download_calculadora():
    if not session.get('logged_in'): return redirect(url_for('index'))
    protect_directory = os.path.join(app.root_path, 'protect')
    return send_from_directory(directory=protect_directory, path='Calculadora.exe', as_attachment=True)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    # Substitui o app.run() pelo servidor de produção Waitress
    from waitress import serve
    print("Servidor de produção iniciado em http://localhost:5000")
    serve(app, host='0.0.0.0', port=5000)