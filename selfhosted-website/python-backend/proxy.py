from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import requests
import json
import logging

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Check if Ollama is responding
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            return jsonify({"status": "healthy", "ollama": "connected"}), 200
        else:
            return jsonify({"status": "unhealthy", "ollama": "disconnected"}), 503
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({"status": "unhealthy", "error": str(e)}), 503

@app.route('/api/ollama/api/tags', methods=['GET'])
def get_models():
    """Get available Ollama models"""
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=10)
        return Response(response.content, status=response.status_code, content_type=response.headers.get('content-type'))
    except Exception as e:
        logger.error(f"Failed to get models: {e}")
        return jsonify({"error": "Failed to connect to Ollama"}), 500

@app.route('/api/ollama/api/generate', methods=['POST'])
def generate():
    """Generate text using Ollama"""
    try:
        data = request.get_json()
        logger.info(f"Generate request for model: {data.get('model', 'unknown')}")
        
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=data,
            timeout=300,
            stream=True
        )
        
        def generate_response():
            for chunk in response.iter_lines():
                if chunk:
                    yield chunk + b'\n'
        
        return Response(generate_response(), content_type='application/json')
    except Exception as e:
        logger.error(f"Generate failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/ollama/api/chat', methods=['POST'])
def chat():
    """Chat with Ollama models"""
    try:
        data = request.get_json()
        logger.info(f"Chat request for model: {data.get('model', 'unknown')}")
        
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json=data,
            timeout=300,
            stream=True
        )
        
        def generate_response():
            for chunk in response.iter_lines():
                if chunk:
                    yield chunk + b'\n'
        
        return Response(generate_response(), content_type='application/json')
    except Exception as e:
        logger.error(f"Chat failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/ollama/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy_ollama(path):
    """Generic proxy for other Ollama endpoints"""
    try:
        url = f"{OLLAMA_BASE_URL}/api/{path}"
        
        if request.method == 'GET':
            response = requests.get(url, params=request.args, timeout=30)
        elif request.method == 'POST':
            response = requests.post(url, json=request.get_json(), timeout=300)
        elif request.method == 'PUT':
            response = requests.put(url, json=request.get_json(), timeout=300)
        elif request.method == 'DELETE':
            response = requests.delete(url, timeout=30)
        
        return Response(response.content, status=response.status_code, content_type=response.headers.get('content-type'))
    except Exception as e:
        logger.error(f"Proxy failed for {path}: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)