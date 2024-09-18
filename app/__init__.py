from flask import Flask
from flask_session import Session
import redis
import os


from dotenv import load_dotenv

from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.llms.openai import OpenAI
from llama_index.core.tools import QueryEngineTool


def create_app():

    load_dotenv(override=True)

    app = Flask(__name__)

    app.secret_key = os.getenv('FLASK_SECRET_KEY')
    redis_host = os.getenv('REDIS_HOST')
    redis_port = os.getenv('REDIS_PORT')


    app.config['SESSION_TYPE'] = 'redis'
    app.config['SESSION_REDIS'] = redis.Redis(host=redis_host, port=redis_port)
    app.config['USERS'] = {'admin': os.getenv('ADMIN_HASH_PASS')}

    Session(app)

    llm = OpenAI(temperature=0.1, model="gpt-4o-mini", max_tokens=512, verbose=True)

    documents = SimpleDirectoryReader("data").load_data()
    index = VectorStoreIndex.from_documents(documents, llm=llm)
    query_engine = index.as_query_engine()

    felix_tool = QueryEngineTool.from_defaults(
        query_engine,
        name="tool",
        description="Gather knowledge about Félix",
    )

    app.config['felix_tool'] = felix_tool
    app.config['llm'] = llm

    from app.routes import register_routes
    register_routes(app)

    return app