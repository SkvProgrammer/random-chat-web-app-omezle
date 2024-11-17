from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS



app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
CORS(app, resources={r"/*": {"origins": "*"}})


# Initialize Flask-SocketIO
socketio = SocketIO(app)

# Store connected users
users = {}  # Mapping: {socket_id: partner_socket_id or None}
last_partners = {}  # Mapping: {socket_id: previous_partner_socket_id}

@app.route('/')
def home():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    users[request.sid] = None  # Add user with no partner
    print(f'User {request.sid} connected')

@socketio.on('disconnect')
def handle_disconnect():
    # Clean up user and notify partner
    partner = users.pop(request.sid, None)
    last_partners.pop(request.sid, None)  # Remove from last partners tracking
    if partner:
        users[partner] = None  # Reset the partner
        emit('partner_disconnected', room=partner)
    print(f'User {request.sid} disconnected')

def find_new_partner(sid):
    previous_partner = last_partners.get(sid)

    for other_sid, partner in users.items():
        # Ensure the potential partner is not already connected, not the same user, and not the previous partner
        if partner is None and other_sid != sid and other_sid != previous_partner:
            users[sid] = other_sid
            users[other_sid] = sid
            last_partners[sid] = other_sid  # Track last partner
            last_partners[other_sid] = sid  # Track last partner
            emit('partner_found', room=sid)
            emit('partner_found', room=other_sid)
            return

    # No available partner, notify the user
    emit('waiting_for_partner', room=sid)

@socketio.on('find_partner')
def find_partner():
    # Disconnect the current partner first
    current_partner = users.get(request.sid)
    if current_partner:
        users[current_partner] = None
        emit('partner_disconnected', room=current_partner)

    # Reset user's partner
    users[request.sid] = None

    # Find a new partner
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
    socketio.run(app, debug=True, host="0.0.0.0", port=5000, server_options={"use_eventlet": True})
