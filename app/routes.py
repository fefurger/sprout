from llama_index.core.base.llms.types import ChatMessage, MessageRole
from llama_index.core.agent import ReActAgent
from flask import request, session, current_app
from flask import jsonify, render_template
from flask_httpauth import HTTPBasicAuth
from flask import Response

from datetime import datetime, timezone
from werkzeug.security import check_password_hash

import msgpack
import json
import re

auth = HTTPBasicAuth()

FIRST_MESSAGE = """
Hi, I am Sprout! I am powered by <i>gpt-4o-mini</i>, and I am here to demonstrate Félix's interest in the GenAI field.<br> \
You can ask me questions about Félix's background, and together we can explore why he \
is a good fit for the position you are looking to fill! Where should we start?
"""

FRESH_CONVERSATION = [
    {
        'role': MessageRole.ASSISTANT,
        'content': FIRST_MESSAGE,
        'additional_kwargs': {
        }
    }
]

SYSTEM_PROMPT = """
We are in September 2024. \
Your name is Sprout and you have been hired by Félix Furger to interact with recruiters on his behalf.\
If asked to, you should give details about who you are and how you were built (Sprout, powered by gpt-4o-mini from OpenAI and you are embedded in an app that was built by Félix Furger using LlamaIndex and Flask)\
While Félix doesn't have professional experience in GenAI, you are a living testimony of Félix's interest in the field. You are a proof that Félix is learning these emerging technologies.\
The person talking to you is a recruiter.\
If you are asked about something regarding Félix, you should always use the tool to browse the provided documents.\
If the recruiter's question doesn't make sense, you should ask for clarification.\
You should speak in a very enthusiastic way.\
You have access to information about Félix's studies and professional background, so that you can answer recruiters questions.\
For any question related to Félix background and skills, check the provided documents, even if you know the answer.\
You should show the recruiter why Félix should be hired.\
If they ask questions that have nothing to do with yourself or Félix, you should keep them on topic in a funny way.
"""

def register_routes(app):
    @app.route('/')
    def load_conversation():
        try:
            conversation = session.get('conversation', FRESH_CONVERSATION.copy())
            if len(conversation)==1:
                conversation[0]['additional_kwargs']['time'] = datetime.now(timezone.utc).isoformat()
            session['conversation'] = conversation

            return render_template('chatbox.html', messages=conversation)

        except Exception as e:
            print("Error loading conversation:", e)
            conversation = FRESH_CONVERSATION.copy()
            session['conversation'] = conversation

        return render_template('chatbox.html', messages=conversation)

    @app.route('/send-message', methods=['POST'])
    def send_message():
        try:
            user_message = request.json.get('message')

            conversation = session.get('conversation')

            now = datetime.now(timezone.utc).isoformat()
            agent = ReActAgent.from_tools([current_app.config['felix_tool']], llm=current_app.config['llm'], verbose=True, context=SYSTEM_PROMPT)
            agent.chat_history.extend([ChatMessage(**message) for message in conversation])
            agent.chat_history.append(ChatMessage(role=MessageRole.SYSTEM, content="You should remember to always use the tool when asked to provide information about Félix."))

            response = agent.chat(user_message)
            print(response)

            session['conversation'].append({
                'role': MessageRole.USER,
                'content': user_message,
                'additional_kwargs': {
                    'time': datetime.now(timezone.utc).isoformat()
                }
            })

            text = response.response.split('```')[0].replace('\n', '<br>')
            text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)
            text = re.sub(r"\*(.*?)\*", r"<i>\1</i>", text)

            now = datetime.now(timezone.utc).isoformat()

            session['conversation'].append({
                'role': MessageRole.ASSISTANT,
                'content': text,
                'additional_kwargs': {
                    'time': now
                }
            })

            return jsonify({
                'response': text,
                'time': now
            })
        
        except Exception as e:
            print(f"Error handling message: {e}")
            return jsonify({'error': 'An error occurred while processing the message'}), 500

    @app.route('/restart', methods=['POST'])
    def restart_conversation():
        conversation = session.get('conversation', [])

        if conversation:
            date = datetime.now(timezone.utc).isoformat()
            archive_key = f"archived_conversation:{date}:{session.sid}"
            current_app.config['SESSION_REDIS'].set(archive_key, json.dumps(conversation))

        session.clear()
        
        return jsonify({'status': 'success'})
    
### ADMIN RELATED FUNCTIONS ###

    @auth.verify_password
    def verify_password(username, password):
        if username in current_app.config['USERS'] and check_password_hash(current_app.config['USERS'].get(username), password):
            return username
        return None
    
    @app.route('/admin', methods=['GET'])
    @auth.login_required
    def view_conversations():
        try:
            conversation_keys = current_app.config['SESSION_REDIS'].keys('session:*')
            archived_keys = current_app.config['SESSION_REDIS'].keys('archived_conversation:*')

            conversations = {}

            for key in conversation_keys:
                conversation = current_app.config['SESSION_REDIS'].get(key)
                conversations[key.decode('utf-8')] = msgpack.unpackb(conversation, raw=False)

            for key in archived_keys:
                conversation = json.loads(current_app.config['SESSION_REDIS'].get(key))
                conversations[key.decode('utf-8')] = conversation

            json_data = json.dumps(conversations, indent=4)

            response = Response(
                json_data,
                mimetype='application/json',
                headers={'Content-Disposition': 'attachment;filename=conversations.json'}
            )

            return response

        except Exception as e:
            print(f"Error retrieving conversations: {e}")
            return jsonify({'error': 'An error occurred while retrieving the conversations'}), 500
