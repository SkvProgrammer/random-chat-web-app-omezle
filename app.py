from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'

# Initialize Flask-Limiter
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"]
)

# Initialize Flask-SocketIO
socketio = SocketIO(app)

# Store connected users
users = {}  # Mapping: {socket_id: partner_socket_id or None}
last_partners = {}  # Mapping: {socket_id: previous_partner_socket_id}

@app.route('/')
@limiter.limit("10 per minute")  # Rate limit for accessing the homepage
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
@limiter.limit("5 per minute")  # Limit requests to find a partner
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
@limiter.limit("20 per minute")  # Limit the rate of sending messages
def send_message(data):
    partner = users.get(request.sid)
    if partner:
        emit('receive_message', data, room=partner)

@app.errorhandler(429)
def ratelimit_error(e):
    return {"error": "Rate limit exceeded. Please slow down."}, 429

@socketio.on_error_default
def handle_error(e):
    if isinstance(e, limiter.RateLimitExceeded):
        emit('rate_limit_exceeded', {'message': 'You are sending messages too quickly. Please slow down.'})

if __name__ == '__main__':
    socketio.run(app, debug=True)
