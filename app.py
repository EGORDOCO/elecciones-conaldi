# =============================================================================
#  SISTEMA DE VOTACIÓN ESCOLAR — CONALDI
#  Archivo: app.py (Backend principal Flask)
#
#  ╔══════════════════════════════════════════════════════════════════════════╗
#  ║  GUÍA DE MODIFICACIONES ANUALES — LEE ESTO PRIMERO                     ║
#  ╠══════════════════════════════════════════════════════════════════════════╣
#  ║  Cada año, antes de las elecciones, debes actualizar:                   ║
#  ║                                                                          ║
#  ║  1. AÑO DE ELECCIÓN  →  busca la etiqueta  # ✏️ AÑO                    ║
#  ║  2. CONTRASEÑA ADMIN →  busca la etiqueta  # ✏️ CLAVE_ADMIN             ║
#  ║  3. LLAVE SECRETA    →  busca la etiqueta  # ✏️ SECRET_KEY              ║
#  ║                                                                          ║
#  ║  Pasos para reiniciar el sistema cada año:                               ║
#  ║  a) Cambia los valores marcados con ✏️                                  ║
#  ║  b) Borra el archivo instance/elecciones.db                             ║
#  ║  c) Ejecuta: python app.py  (se crea la BD desde cero)                  ║
#  ║  d) Carga los estudiantes desde el panel admin                          ║
#  ║  e) Registra los nuevos candidatos                                      ║
#  ╚══════════════════════════════════════════════════════════════════════════╝
#
#  Desarrollado por: Enrique Gordo (Kikegc) — Docente Sistemas CONALDI
#  Versión: 1.0 | Junio 2026
# =============================================================================

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import pandas as pd
import os
from datetime import datetime
from functools import wraps

app = Flask(__name__)

# ✏️ SECRET_KEY — Cambia esta clave cada año por seguridad.
# Usa cualquier cadena larga y aleatoria. Ejemplo: 'conaldi-2027-xK9mAbC3'
app.secret_key = 'conaldi-elecciones-2026-secret-key-xK9mP2'

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///elecciones.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Máx 16 MB por foto

db = SQLAlchemy(app)
app.jinja_env.globals.update(enumerate=enumerate)


# =============================================================================
#  MODELOS DE BASE DE DATOS
#  No es necesario modificar esta sección cada año.
#  Solo edita si agregas nuevos campos o cargos.
# =============================================================================

class Estudiante(db.Model):
    """Tabla de estudiantes habilitados para votar."""
    id = db.Column(db.Integer, primary_key=True)
    documento = db.Column(db.String(20), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    grado = db.Column(db.String(20))
    password_hash = db.Column(db.String(200), nullable=False)
    ha_votado_personero = db.Column(db.Boolean, default=False)
    ha_votado_contralor = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Candidato(db.Model):
    """Tabla de candidatos. cargo puede ser 'personero' o 'contralor'."""
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    numero = db.Column(db.Integer, nullable=False)
    # ✏️ Si en el futuro se agrega un nuevo cargo (ej: 'tesorero'),
    # agrégalo también en los templates votar.html y admin_panel.html
    cargo = db.Column(db.String(20), nullable=False)  # 'personero' o 'contralor'
    eslogan = db.Column(db.String(200))
    foto = db.Column(db.String(200), default='default.jpg')
    votos = db.Column(db.Integer, default=0)
    activo = db.Column(db.Boolean, default=True)


class Eleccion(db.Model):
    """Tabla con la configuración general de la elección."""
    id = db.Column(db.Integer, primary_key=True)
    # ✏️ AÑO — Cambia el nombre de la elección aquí y en init_db() al final del archivo
    nombre = db.Column(db.String(100), default='Elecciones Escolares 2027')
    estado = db.Column(db.String(20), default='configuracion')
    # Estados posibles: 'configuracion' | 'activa' | 'cerrada'
    fecha_inicio = db.Column(db.DateTime)
    fecha_fin = db.Column(db.DateTime)
    votos_nulos_personero = db.Column(db.Integer, default=0)
    votos_nulos_contralor = db.Column(db.Integer, default=0)


class Voto(db.Model):
    """Registro individual de cada voto. No almacena qué candidato eligió quién (anónimo)."""
    id = db.Column(db.Integer, primary_key=True)
    estudiante_id = db.Column(db.Integer, db.ForeignKey('estudiante.id'))
    candidato_id = db.Column(db.Integer, db.ForeignKey('candidato.id'))
    cargo = db.Column(db.String(20))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


# =============================================================================
#  HELPERS / DECORADORES
# =============================================================================

def login_required(f):
    """Decorador que exige sesión de estudiante activa."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'estudiante_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    """Decorador que exige sesión de administrador activa."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

def get_eleccion():
    """Retorna el registro único de la elección actual."""
    return Eleccion.query.first()

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# =============================================================================
#  RUTAS PÚBLICAS (accesibles por estudiantes)
# =============================================================================

@app.route('/')
def index():
    eleccion = get_eleccion()
    return render_template('index.html', eleccion=eleccion)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        documento = request.form.get('documento', '').strip()
        password = request.form.get('password', '').strip()
        estudiante = Estudiante.query.filter_by(documento=documento).first()
        if estudiante and estudiante.check_password(password):
            session['estudiante_id'] = estudiante.id
            session['estudiante_nombre'] = estudiante.nombre
            return redirect(url_for('votar'))
        flash('Documento o contraseña incorrectos.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/votar')
@login_required
def votar():
    eleccion = get_eleccion()
    if not eleccion or eleccion.estado != 'activa':
        flash('Las votaciones no están activas en este momento.', 'info')
        return redirect(url_for('index'))
    estudiante = Estudiante.query.get(session['estudiante_id'])
    personeros = Candidato.query.filter_by(cargo='personero', activo=True).order_by(Candidato.numero).all()
    contralores = Candidato.query.filter_by(cargo='contralor', activo=True).order_by(Candidato.numero).all()
    return render_template('votar.html', estudiante=estudiante,
        personeros=personeros, contralores=contralores, eleccion=eleccion)

@app.route('/emitir_voto', methods=['POST'])
@login_required
def emitir_voto():
    eleccion = get_eleccion()
    if not eleccion or eleccion.estado != 'activa':
        return jsonify({'success': False, 'msg': 'Votaciones cerradas.'})
    estudiante = Estudiante.query.get(session['estudiante_id'])
    data = request.json
    cargo = data.get('cargo')
    candidato_id = data.get('candidato_id')
    es_nulo = data.get('nulo', False)

    if cargo == 'personero':
        if estudiante.ha_votado_personero:
            return jsonify({'success': False, 'msg': 'Ya votaste para Personero.'})
        if es_nulo:
            eleccion.votos_nulos_personero += 1
        else:
            candidato = Candidato.query.get(candidato_id)
            if not candidato:
                return jsonify({'success': False, 'msg': 'Candidato no encontrado.'})
            candidato.votos += 1
            db.session.add(Voto(estudiante_id=estudiante.id, candidato_id=candidato_id, cargo='personero'))
        estudiante.ha_votado_personero = True

    elif cargo == 'contralor':
        if estudiante.ha_votado_contralor:
            return jsonify({'success': False, 'msg': 'Ya votaste para Contralor.'})
        if es_nulo:
            eleccion.votos_nulos_contralor += 1
        else:
            candidato = Candidato.query.get(candidato_id)
            if not candidato:
                return jsonify({'success': False, 'msg': 'Candidato no encontrado.'})
            candidato.votos += 1
            db.session.add(Voto(estudiante_id=estudiante.id, candidato_id=candidato_id, cargo='contralor'))
        estudiante.ha_votado_contralor = True

    db.session.commit()
    return jsonify({'success': True})

@app.route('/confirmacion')
@login_required
def confirmacion():
    estudiante = Estudiante.query.get(session['estudiante_id'])
    return render_template('confirmacion.html', estudiante=estudiante)


# =============================================================================
#  RUTAS DE ADMINISTRACIÓN (solo admin)
# =============================================================================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        usuario = request.form.get('user')
        clave = request.form.get('password')
        # ✏️ CLAVE_ADMIN — Cambia 'admin' y 'conaldi2026' por credenciales seguras antes de cada elección.
        # Ejemplo: usuario='rector2027', clave='Cl4v3S3gur4!'
        if usuario == 'admin' and clave == 'conaldi2026':
            session['is_admin'] = True
            return redirect(url_for('admin_panel'))
        flash('Credenciales incorrectas.', 'error')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect(url_for('index'))

@app.route('/admin')
@admin_required
def admin_panel():
    eleccion = get_eleccion()
    total_estudiantes = Estudiante.query.count()
    votos_personero = Voto.query.filter_by(cargo='personero').count()
    votos_contralor = Voto.query.filter_by(cargo='contralor').count()
    if eleccion:
        votos_personero += eleccion.votos_nulos_personero
        votos_contralor += eleccion.votos_nulos_contralor
    candidatos_p = Candidato.query.filter_by(cargo='personero', activo=True).order_by(Candidato.numero).all()
    candidatos_c = Candidato.query.filter_by(cargo='contralor', activo=True).order_by(Candidato.numero).all()
    return render_template('admin_panel.html', eleccion=eleccion,
        total_estudiantes=total_estudiantes, votos_personero=votos_personero,
        votos_contralor=votos_contralor, candidatos_p=candidatos_p, candidatos_c=candidatos_c)

@app.route('/admin/eleccion/estado', methods=['POST'])
@admin_required
def cambiar_estado():
    eleccion = get_eleccion()
    nuevo_estado = request.form.get('estado')
    if eleccion:
        eleccion.estado = nuevo_estado
        if nuevo_estado == 'activa':
            eleccion.fecha_inicio = datetime.utcnow()
        elif nuevo_estado == 'cerrada':
            eleccion.fecha_fin = datetime.utcnow()
        db.session.commit()
        flash(f'Estado cambiado a: {nuevo_estado}', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/candidato/nuevo', methods=['POST'])
@admin_required
def nuevo_candidato():
    nombre = request.form.get('nombre')
    numero = request.form.get('numero')
    cargo = request.form.get('cargo')
    eslogan = request.form.get('eslogan')
    # ✏️ LÍMITE CANDIDATOS — Por reglamento son máx 6. Cambia el número si la norma cambia.
    count = Candidato.query.filter_by(cargo=cargo, activo=True).count()
    if count >= 6:
        flash(f'Ya hay 6 candidatos para {cargo}. Máximo permitido.', 'error')
        return redirect(url_for('admin_panel'))
    foto_nombre = 'default.jpg'
    if 'foto' in request.files:
        foto = request.files['foto']
        if foto and foto.filename and allowed_file(foto.filename):
            filename = secure_filename(f"{cargo}_{numero}_{foto.filename}")
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            foto.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            foto_nombre = filename
    candidato = Candidato(nombre=nombre, numero=int(numero), cargo=cargo, eslogan=eslogan, foto=foto_nombre)
    db.session.add(candidato)
    db.session.commit()
    flash('Candidato agregado exitosamente.', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/candidato/eliminar/<int:cid>', methods=['POST'])
@admin_required
def eliminar_candidato(cid):
    c = Candidato.query.get_or_404(cid)
    c.activo = False
    db.session.commit()
    flash('Candidato desactivado.', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/candidato/editar/<int:cid>', methods=['POST'])
@admin_required
def editar_candidato(cid):
    c = Candidato.query.get_or_404(cid)
    c.nombre = request.form.get('nombre', c.nombre)
    c.eslogan = request.form.get('eslogan', c.eslogan)
    c.numero = int(request.form.get('numero', c.numero))
    if 'foto' in request.files:
        foto = request.files['foto']
        if foto and foto.filename and allowed_file(foto.filename):
            filename = secure_filename(f"{c.cargo}_{c.numero}_{foto.filename}")
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            foto.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            c.foto = filename
    db.session.commit()
    flash('Candidato actualizado.', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/cargar_estudiantes', methods=['POST'])
@admin_required
def cargar_estudiantes():
    if 'archivo' not in request.files:
        flash('No se seleccionó archivo.', 'error')
        return redirect(url_for('admin_panel'))
    archivo = request.files['archivo']
    if not archivo.filename.endswith(('.xlsx', '.xls', '.csv')):
        flash('Solo se aceptan archivos Excel (.xlsx/.xls) o CSV.', 'error')
        return redirect(url_for('admin_panel'))
    try:
        if archivo.filename.endswith('.csv'):
            df = pd.read_csv(archivo)
        else:
            df = pd.read_excel(archivo)
        df.columns = df.columns.str.lower().str.strip()
        required = {'documento', 'nombre', 'password'}
        if not required.issubset(set(df.columns.tolist())):
            flash(f'Columnas requeridas: documento, nombre, password. Encontradas: {list(df.columns)}', 'error')
            return redirect(url_for('admin_panel'))
        agregados = actualizados = 0
        for _, row in df.iterrows():
            doc = str(row['documento']).strip()
            existente = Estudiante.query.filter_by(documento=doc).first()
            if existente:
                existente.nombre = str(row['nombre']).strip()
                existente.set_password(str(row['password']).strip())
                if 'grado' in df.columns:
                    existente.grado = str(row['grado']).strip()
                actualizados += 1
            else:
                est = Estudiante(
                    documento=doc,
                    nombre=str(row['nombre']).strip(),
                    grado=str(row['grado']).strip() if 'grado' in df.columns else ''
                )
                est.set_password(str(row['password']).strip())
                db.session.add(est)
                agregados += 1
        db.session.commit()
        flash(f'✅ {agregados} estudiantes agregados, {actualizados} actualizados.', 'success')
    except Exception as e:
        flash(f'Error al procesar archivo: {str(e)}', 'error')
    return redirect(url_for('admin_panel'))

@app.route('/admin/resultados')
@admin_required
def resultados():
    eleccion = get_eleccion()
    personeros = Candidato.query.filter_by(cargo='personero').order_by(Candidato.votos.desc()).all()
    contralores = Candidato.query.filter_by(cargo='contralor').order_by(Candidato.votos.desc()).all()
    total_p = sum(c.votos for c in personeros) + (eleccion.votos_nulos_personero if eleccion else 0)
    total_c = sum(c.votos for c in contralores) + (eleccion.votos_nulos_contralor if eleccion else 0)
    return render_template('resultados.html', personeros=personeros, contralores=contralores,
        eleccion=eleccion, total_p=total_p, total_c=total_c)

@app.route('/admin/reset_votos', methods=['POST'])
@admin_required
def reset_votos():
    """Reinicia TODOS los votos. Úsalo solo para pruebas antes del día oficial."""
    Voto.query.delete()
    db.session.query(Candidato).update({'votos': 0})
    db.session.query(Estudiante).update({'ha_votado_personero': False, 'ha_votado_contralor': False})
    eleccion = get_eleccion()
    if eleccion:
        eleccion.votos_nulos_personero = 0
        eleccion.votos_nulos_contralor = 0
        eleccion.estado = 'configuracion'
    db.session.commit()
    flash('🔄 Todos los votos han sido reiniciados.', 'success')
    return redirect(url_for('admin_panel'))


# =============================================================================
#  INICIALIZACIÓN DE LA BASE DE DATOS
#
#  ✏️ AÑO — Cambia '2026' por el año correspondiente en la línea de abajo.
#  También actualiza el año en los archivos:
#    - templates/base.html       (pie de página y título del navegador)
#    - templates/index.html      (texto del hero)
#    - templates/login.html      (subtítulo del formulario)
#    - templates/votar.html      (encabezado de la página de votación)
#    - templates/confirmacion.html (texto de confirmación)
#    - templates/admin_login.html  (subtítulo)
#    - templates/admin_panel.html  (título)
# =============================================================================

def init_db():
    os.makedirs('instance', exist_ok=True)
    os.makedirs(os.path.join('static', 'uploads'), exist_ok=True)
    with app.app_context():
        db.create_all()
        if not Eleccion.query.first():
            # ✏️ AÑO — Actualiza el año aquí cada año electoral
            db.session.add(Eleccion(nombre='Elecciones Escolares 2027'))
            db.session.commit()
            print("✅ Base de datos inicializada.")

if __name__ == '__main__':
    init_db()
    print("🚀 Servidor: http://localhost:5000")
    # ✏️ DEBUG — Cambia debug=True a debug=False cuando se use en producción/internet
    app.run(debug=True, host='0.0.0.0', port=5000)
