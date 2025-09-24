from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit
from openai import OpenAI
from pymongo import MongoClient
import datetime
import uuid
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
socketio = SocketIO(app, cors_allowed_origins="*")

def get_db():
    try:
        mongo_uri = os.getenv("MONGO_URI")
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
        client.admin.command('ping')
        db_name = os.getenv("MONGO_DB", "genabap")
        return client[db_name]
    except Exception as e:
        print(f"Mongo connection failed: {e}")
        return None

def format_response(ai_msg):
    """Format AI response with proper ABAP code blocks and structure"""
    # Check if response contains ABAP code
    abap_keywords = ['DEFINE VIEW', 'SELECT', 'FROM', 'WHERE', 'GROUP BY', 'ORDER BY', 
                     '@ViewType', '@AccessControl', '@EndUserText', '@Analytics', 
                     'AS SELECT', 'UNION ALL', 'LEFT JOIN', 'INNER JOIN']
    
    has_abap_code = any(keyword in ai_msg.upper() for keyword in abap_keywords)
    
    if has_abap_code:
        # Split into explanation and code parts
        lines = ai_msg.split('\n')
        formatted_lines = []
        code_started = False
        
        for line in lines:
            line_upper = line.upper().strip()
            
            # Start code block when we hit ABAP annotations or DEFINE VIEW
            if (line_upper.startswith('@') or 
                line_upper.startswith('DEFINE VIEW') or
                'DEFINE VIEW' in line_upper):
                if not code_started:
                    formatted_lines.append("\n```abap")
                    code_started = True
                formatted_lines.append(line)
            
            # Continue code block for ABAP syntax
            elif code_started and (
                any(keyword in line_upper for keyword in ['SELECT', 'FROM', 'WHERE', 'AS', 'KEY', 'UNION', 'JOIN', '}', '{']) or
                line.strip().startswith('//') or  # Comments
                line.strip() == '' or  # Empty lines in code
                line.strip().endswith(',') or  # Continuation lines
                line.strip().endswith(';')  # End statements
            ):
                formatted_lines.append(line)
            
            # End code block
            elif code_started and line.strip() and not any(keyword in line_upper for keyword in abap_keywords):
                formatted_lines.append("```\n")
                formatted_lines.append(line)
                code_started = False
            
            # Regular text
            else:
                formatted_lines.append(line)
        
        # Close code block if still open
        if code_started:
            formatted_lines.append("```")
        
        return '\n'.join(formatted_lines)
    
    return ai_msg

def log_chat(session_id, user_msg, ai_msg, message_id=None):
    db = get_db()
    if db is not None:
        try:
            collection = db["interactions"]
            doc = {
                "session_id": session_id,
                "message_id": message_id or str(uuid.uuid4()),
                "user_message": user_msg,
                "ai_response": ai_msg,
                "timestamp": datetime.datetime.now(),
                "feedback": None
            }
            result = collection.insert_one(doc)
            print(f"Chat logged with message_id: {doc['message_id']}")
            return doc["message_id"]
        except Exception as e:
            print(f"Failed to log chat: {e}")
            return None
    return None

def log_feedback(message_id, feedback):
    db = get_db()
    if db is not None:
        try:
            collection = db["interactions"]
            result = collection.update_one(
                {"message_id": message_id},
                {"$set": {"feedback": feedback, "feedback_timestamp": datetime.datetime.now()}}
            )
            
            if result.modified_count > 0:
                print(f"Feedback '{feedback}' successfully saved for message_id: {message_id}")
                return True
            else:
                print(f"No document found or updated for message_id: {message_id}")
                return False
                
        except Exception as e:
            print(f"Database error while saving feedback: {e}")
            return False
    else:
        print("Database connection not available")
        return False

client = OpenAI(base_url=os.getenv("API_BASE_URL"), api_key="")

@app.route('/')
def index():
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
        session['messages'] = []
        session['message_ids'] = []
        session['feedbacks'] = {}
    return render_template('index.html')

@socketio.on('send_message')
def handle_message(data):
    user_message = data['message']
    session_id = session.get('session_id')
    
    # Add user message to session
    if 'messages' not in session:
        session['messages'] = []
    session['messages'].append({"role": "user", "content": user_message})
    
    # Emit user message to client
    emit('user_message', {'message': user_message})
    
    try:
        # Get AI response
        response = client.chat.completions.create(
            model=os.getenv("MODEL_PATH"),
            messages=session['messages'],
            max_tokens=2000
        )
        
        ai_msg = response.choices[0].message.content
        formatted_response = format_response(ai_msg)
        
        # Check if response contains ABAP code
        has_code = any(keyword in ai_msg.upper() for keyword in 
                      ['DEFINE VIEW', '@VIEWTYPE', '@ACCESSCONTROL', 'SELECT FROM'])
        
        # Add AI message to session
        session['messages'].append({"role": "assistant", "content": ai_msg})
        
        # Log chat and get message ID
        message_id = log_chat(session_id, user_message, ai_msg)
        if message_id:
            if 'message_ids' not in session:
                session['message_ids'] = []
            session['message_ids'].append(message_id)
        
        # Emit AI response to client
        emit('ai_response', {
            'message': ai_msg,
            'formatted_message': formatted_response,
            'has_code': has_code,
            'message_id': message_id
        })
        
    except Exception as e:
        emit('error', {'message': f"Error: {str(e)}"})

@app.route('/feedback', methods=['POST'])
def submit_feedback():
    data = request.json
    message_id = data.get('message_id')
    feedback = data.get('feedback')
    
    success = log_feedback(message_id, feedback)
    
    if success:
        if 'feedbacks' not in session:
            session['feedbacks'] = {}
        session['feedbacks'][message_id] = feedback
    
    return jsonify({'success': success})

if __name__ == '__main__':
    socketio.run(app, debug=True)