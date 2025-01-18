from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['PREFERRED_URL_SCHEME'] = 'https'

# Initialize Flask-SocketIO with correct configuration for Render
socketio = SocketIO(app, 
    cors_allowed_origins="*",  # Enable CORS for all origins
    async_mode='eventlet',     # Use eventlet as async mode
    ping_timeout=30,           # Increase ping timeout
    ping_interval=15,          # Adjust ping interval
    logger=True,              # Enable logging for debugging
    engineio_logger=True      # Enable Engine.IO logging
)

# Store connected users
users = {}  # Mapping: {socket_id: partner_socket_id or None}
last_partners = {}  # Mapping: {socket_id: previous_partner_socket_id}

@app.route('/')
def home():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    users[request.sid] = None
    print(f'User {request.sid} connected')

@socketio.on('disconnect')
def handle_disconnect():
    partner = users.pop(request.sid, None)
    last_partners.pop(request.sid, None)
    if partner:
        users[partner] = None
        emit('partner_disconnected', room=partner)
    print(f'User {request.sid} disconnected')

def find_new_partner(sid):
    previous_partner = last_partners.get(sid)
    for other_sid, partner in users.items():
        if partner is None and other_sid != sid and other_sid != previous_partner:
            users[sid] = other_sid
            users[other_sid] = sid
            last_partners[sid] = other_sid
            last_partners[other_sid] = sid
            emit('partner_found', room=sid)
            emit('partner_found', room=other_sid)
            return
    emit('waiting_for_partner', room=sid)

@socketio.on('find_partner')
def find_partner():
    current_partner = users.get(request.sid)
    if current_partner:
        users[current_partner] = None
        emit('partner_disconnected', room=current_partner)
    users[request.sid] = None
    find_new_partner(request.sid)

@socketio.on('send_message')
def send_message(data):
    partner = users.get(request.sid)
    if partner:
        emit('receive_message', data, room=partner)

@socketio.on_error_default
def handle_error(e):
    print(f"An error occurred: {e}")

if __name__ == '__main__':
    # Get port from environment variable (Render sets this)
    port = int(os.environ.get('PORT', 5000))
    
    # Run with correct host and port configuration
    socketio.run(app,host='0.0.0.0',port=port,debug=False,use_reloader=False)