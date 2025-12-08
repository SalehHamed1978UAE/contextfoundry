from flask import Flask, request
import os

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return '''<!DOCTYPE html>
<html>
<head>
    <title>Upload Test</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body style="font-family: sans-serif; padding: 20px;">
    <h1>Minimal Upload Test</h1>
    <form action="/upload" method="POST" enctype="multipart/form-data">
        <input type="file" name="file" required>
        <button type="submit">Upload</button>
    </form>
</body>
</html>'''

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return 'No file selected', 400
    
    file = request.files['file']
    if file.filename == '':
        return 'No file selected', 400
    
    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(filepath)
    
    return f'<h1>File saved: {file.filename}</h1><p>Path: {filepath}</p><a href="/">Upload another</a>'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
