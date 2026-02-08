import os
from flask import Flask, render_template, request, jsonify
import requests
from dotenv import load_dotenv

# Load .env if it exists (for local development)
if os.path.exists("EnvironmentVariables.env"):
    load_dotenv("EnvironmentVariables.env")

app = Flask(__name__)

# Fallback for Vercel environment variables
API_KEY = os.getenv("TEXTSTUDIO_API_KEY")
TEXTSTUDIO_URL = "https://api.textstudio.com/generate"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    text = data.get('text')
    style_id = data.get('styleId')

    if not text or not style_id:
        return jsonify({"success": False, "error": "Missing text or styleId"}), 400

    params = {
        'text': text,
        'styleId': style_id,
        'background': 'transparent',
        'format': 'png',
        'quality': 'lite',
        'output': 'dataUrl',
        'padding': 5,
        'aspectRatio': 'fit'
    }

    headers = {
        'Authorization': f'Bearer {API_KEY}'
    }

    try:
        response = requests.get(TEXTSTUDIO_URL, params=params, headers=headers)
        response.raise_for_status()
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        print(f"Error calling TextStudio API: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    from waitress import serve
    print("Starting production server on http://0.0.0.0:5000")
    serve(app, host='0.0.0.0', port=5000)
