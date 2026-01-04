from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, jsonify
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
            session['email'] = email
            return redirect(url_for('home'))
            
    session.pop('temp_user', None)
    session.pop('codigo_confirmacao', None)
    error = request.args.get('error')
    return render_template('Public/login.html', error=error)

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        usuario = request.form['usuario']
        email = request.form['email']
        senha = request.form['senha']
        users = load_users()

        if len(senha) < 6:
            return redirect(url_for('cadastro', error='password_too_short'))

        if email in users:
            return redirect(url_for('cadastro', error='email_exists'))

        codigo = str(random.randint(100000, 999999))
        
        try:
            msg = Message('Seu código de confirmação NuksEdition', recipients=[email])
            msg.body = f'Olá {usuario}, seu código de confirmação é: {codigo}'
            mail.send(msg)
        except Exception as e:
            return "Ocorreu um erro ao enviar o e-mail de confirmação.", 500

        # A conta NÃO é salva aqui. Os dados ficam temporários na sessão.
        session['temp_user'] = {'usuario': usuario, 'email': email, 'senha': senha}
        session['codigo_confirmacao'] = codigo
        
        return redirect(url_for('confirmar'))

    error = request.args.get('error')
    return render_template('Public/cadastro.html', error=error)

@app.route('/confirmar')
def confirmar():
    if 'temp_user' not in session:
        return redirect(url_for('cadastro'))
    temp_user = session.get('temp_user', {})
    email = temp_user.get('email')
    return render_template('Public/confirmar.html', email=email)

@app.route('/verificar-codigo', methods=['POST'])
def verificar_codigo():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'Invalid request'})
    codigo_digitado = data.get('codigo')
    codigo_sessao = session.get('codigo_confirmacao')

    if codigo_digitado == codigo_sessao:
        temp_user = session.get('temp_user')
        if not temp_user:
            return jsonify({'success': False, 'error': 'session_expired'})

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
        session['email'] = temp_user['email']
        
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Código incorreto'})

@app.route('/reenviar-codigo', methods=['POST'])
def reenviar_codigo():
    if 'temp_user' in session:
        temp_user = session.get('temp_user')
        email = temp_user.get('email')
        usuario = temp_user.get('usuario')

        # Gerar novo código
        novo_codigo = str(random.randint(100000, 999999))
        session['codigo_confirmacao'] = novo_codigo
        
        # Enviar e-mail com o novo código
        try:
            msg = Message('Seu novo código de confirmação NuksEdition', recipients=[email])
            msg.body = f'Olá {usuario}, seu novo código de confirmação é: {novo_codigo}'
            mail.send(msg)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': 'Failed to send email'})
    
    return jsonify({'success': False, 'error': 'Session expired'})

@app.route('/Imagens/<path:filename>')
def send_image(filename):
    return send_from_directory('Imagens', filename)

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

@app.route('/download_snake_game')
def download_snake_game():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    # O executável deve estar na pasta 'game' para ser baixado
    game_directory = os.path.join(app.root_path, 'snake', 'game')
    return send_from_directory(directory=game_directory, path='NuksEdition_Snake.exe', as_attachment=True)

@app.route('/user')
def user():
    if not session.get('logged_in'):
        return redirect(url_for('index'))

    users = load_users()
    user_data = users.get(session.get('email'))

    if not user_data:
        return redirect(url_for('index'))

    user_data['email'] = session.get('email')
    return render_template('protect/user.html', usuario=user_data)

@app.route('/config')
def config():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    return render_template('protect/config.html')

@app.route('/send_delete_code')
def send_delete_code():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'})

    codigo = str(random.randint(100000, 999999))
    session['delete_confirmation_code'] = codigo
    email = session.get('email')
    
    try:
        msg = Message('Seu código de confirmação para exclusão de conta NuksEdition', recipients=[email])
        msg.body = f'Seu código de confirmação para exclusão de conta é: {codigo}'
        mail.send(msg)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': 'Failed to send email'})

@app.route('/verify_delete_code', methods=['POST'])
def verify_delete_code():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'})

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'Invalid request'})
    codigo_digitado = data.get('code')
    codigo_sessao = session.get('delete_confirmation_code')

    if codigo_digitado == codigo_sessao:
        users = load_users()
        email = session.get('email')
        if email in users:
            del users[email]
            save_users(users)
        session.clear()
        return jsonify({'success': True})
    else:
        return jsonify({'success': False})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/send_change_email_code')
def send_change_email_code():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'})

    codigo = str(random.randint(100000, 999999))
    session['change_email_code'] = codigo
    email = session.get('email')
    
    try:
        msg = Message('Seu código de confirmação para alteração de e-mail NuksEdition', recipients=[email])
        msg.body = f'Seu código de confirmação para alteração de e-mail é: {codigo}'
        mail.send(msg)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': 'Failed to send email'})

@app.route('/verify_change_email_code', methods=['POST'])
def verify_change_email_code():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'})

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'Invalid request'})
    codigo_digitado = data.get('code')
    codigo_sessao = session.get('change_email_code')

    if codigo_digitado == codigo_sessao:
        return jsonify({'success': True})
    else:
        return jsonify({'success': False})

@app.route('/send_new_email_code', methods=['POST'])
def send_new_email_code():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'})

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'Invalid request'})
    new_email = data.get('new_email')

    users = load_users()
    if new_email in users:
        return jsonify({'success': False, 'error': 'email_exists'})

    session['new_email'] = new_email

    codigo = str(random.randint(100000, 999999))
    session['new_email_code'] = codigo
    
    try:
        msg = Message('Seu código de confirmação para o novo e-mail NuksEdition', recipients=[new_email])
        msg.body = f'Seu código de confirmação para o novo e-mail é: {codigo}'
        mail.send(msg)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': 'Failed to send email'})

@app.route('/verify_new_email_code', methods=['POST'])
def verify_new_email_code():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'})

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'Invalid request'})
    codigo_digitado = data.get('code')
    codigo_sessao = session.get('new_email_code')

    if codigo_digitado == codigo_sessao:
        users = load_users()
        old_email = session.get('email')
        new_email = session.get('new_email')

        if old_email in users:
            users[new_email] = users.pop(old_email)
            save_users(users)
            session['email'] = new_email

        return jsonify({'success': True})
    else:
        return jsonify({'success': False})

@app.route('/send_change_password_code')
def send_change_password_code():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'})

    codigo = str(random.randint(100000, 999999))
    session['change_password_code'] = codigo
    email = session.get('email')
    
    try:
        msg = Message('Seu código de confirmação para alteração de senha NuksEdition', recipients=[email])
        msg.body = f'Seu código de confirmação para alteração de senha é: {codigo}'
        mail.send(msg)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': 'Failed to send email'})

@app.route('/verify_change_password_code', methods=['POST'])
def verify_change_password_code():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'})

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'Invalid request'})
    codigo_digitado = data.get('code')
    codigo_sessao = session.get('change_password_code')

    if codigo_digitado == codigo_sessao:
        return jsonify({'success': True})
    else:
        return jsonify({'success': False})

@app.route('/update_password', methods=['POST'])
def update_password():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'})

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'Invalid request'})
    new_password = data.get('new_password')

    if len(new_password) < 6:
        return jsonify({'success': False, 'error': 'Password too short'})

    users = load_users()
    email = session.get('email')

    if email in users:
        users[email]['password_hash'] = generate_password_hash(new_password, method='pbkdf2:sha256')
        save_users(users)
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'User not found'})

if __name__ == '__main__':
    app.run(debug=True)