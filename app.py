from flask import Flask, render_template, request, jsonify, send_file, url_for
import os
from markitdown import MarkItDown
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename
import uuid
from datetime import datetime
from threading import Lock

from local_ocr import (
    IMAGE_EXTENSIONS,
    LocalOcrImageConverter,
    OCR_ENGINES,
    get_ocr_capabilities,
)

# Check if running on Vercel
is_vercel = os.environ.get('VERCEL') == '1'

app = Flask(__name__, 
           template_folder='templates',
           static_folder='static')

def positive_int_env(name, default):
    try:
        value = int(os.environ.get(name, default))
        return value if value > 0 else default
    except (TypeError, ValueError):
        return default


# The file-size limit is configurable for the local Mac mini service. Flask's
# request limit is slightly larger because multipart/form-data adds metadata.
MAX_FILE_SIZE_MB = positive_int_env('MAX_FILE_SIZE_MB', 500)
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
MULTIPART_OVERHEAD_BYTES = 2 * 1024 * 1024
CLEANUP_AGE_HOURS = positive_int_env('CLEANUP_AGE_HOURS', 1)

app.config['MAX_FILE_SIZE_BYTES'] = MAX_FILE_SIZE_BYTES
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE_BYTES + MULTIPART_OVERHEAD_BYTES

# A single local conversion at a time prevents multiple large documents from
# exhausting the Mac mini's memory.
conversion_lock = Lock()

# For Vercel, use /tmp directory; for local, use uploads
if is_vercel:
    app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
else:
    app.config['UPLOAD_FOLDER'] = 'uploads'

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Allowed file extensions
ALLOWED_EXTENSIONS = {
    'pdf', 'docx', 'doc', 'pptx', 'ppt', 'xlsx', 'xls',
    'html', 'htm', 'csv', 'json', 'xml', 'txt', 'md',
    *IMAGE_EXTENSIONS,
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_type(filename):
    # Simple file type detection based on extension
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    type_map = {
        'pdf': 'application/pdf',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'doc': 'application/msword',
        'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'ppt': 'application/vnd.ms-powerpoint',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'xls': 'application/vnd.ms-excel',
        'html': 'text/html',
        'htm': 'text/html',
        'csv': 'text/csv',
        'json': 'application/json',
        'xml': 'application/xml',
        'txt': 'text/plain',
        'md': 'text/markdown',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'webp': 'image/webp',
        'bmp': 'image/bmp',
        'tif': 'image/tiff',
        'tiff': 'image/tiff',
    }
    return type_map.get(ext, 'application/octet-stream')

@app.route('/')
def index():
    return render_template(
        'index.html',
        max_file_size_mb=MAX_FILE_SIZE_MB,
        max_file_size_bytes=MAX_FILE_SIZE_BYTES,
        ocr_capabilities=get_ocr_capabilities(),
    )


@app.route('/api/ocr-capabilities')
def ocr_capabilities():
    return jsonify(get_ocr_capabilities())


@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(_error):
    return jsonify({
        'error': f'File is too large. Maximum size is {MAX_FILE_SIZE_MB} MB.'
    }), 413

@app.route('/convert', methods=['POST'])
def convert_file():
    if not conversion_lock.acquire(blocking=False):
        return jsonify({
            'error': 'Another document is being converted. Please try again shortly.'
        }), 429

    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        print(f"Received file: {file.filename}")
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'File type not supported'}), 400

        extension = file.filename.rsplit('.', 1)[1].lower()
        is_image = extension in IMAGE_EXTENSIONS
        ocr_engine = request.form.get('ocr_engine', 'auto').lower()
        if ocr_engine not in OCR_ENGINES:
            return jsonify({'error': 'Invalid OCR engine'}), 400
        if is_image and not get_ocr_capabilities()['available']:
            return jsonify({
                'error': (
                    'Local OCR is not installed on this server. On an Apple '
                    'Silicon Mac, run ./install.sh to install MLX OCR support.'
                )
            }), 503
        
        # Generate unique filename
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)

        if os.path.getsize(file_path) > app.config['MAX_FILE_SIZE_BYTES']:
            os.remove(file_path)
            return jsonify({
                'error': f'File is too large. Maximum size is {MAX_FILE_SIZE_MB} MB.'
            }), 413
        
        print(f"File saved to: {file_path}")
        
        # Initialize MarkItDown
        try:
            # Force import of PDF dependencies
            import pdfminer
            md = MarkItDown(enable_plugins=False)
            ocr_converter = None
            if is_image:
                ocr_converter = LocalOcrImageConverter(engine=ocr_engine)
                md.register_converter(ocr_converter, priority=-1.0)
            print(f"MarkItDown initialized successfully")
            
            # Check available converters
            converters = [type(c).__name__ for c in md._converters]
            print(f"Available converters: {converters}")
            
        except Exception as e:
            print(f"Failed to initialize MarkItDown: {e}")
            raise
        
        # Convert file
        try:
            print(f"Converting file: {file_path}")
            result = md.convert(file_path)
            print(f"Conversion successful")
        except Exception as e:
            print(f"Conversion failed: {e}")
            import traceback
            traceback.print_exc()
            raise
        
        # Generate output filename
        base_name = os.path.splitext(filename)[0]
        output_filename = f"{uuid.uuid4()}_{base_name}_converted.md"
        download_name = f"{base_name}_converted.md"
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
        
        # Save converted content
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result.text_content)
        
        # Clean up input file
        os.remove(file_path)
        
        return jsonify({
            'success': True,
            'output_filename': output_filename,
            'download_url': url_for(
                'download_file', filename=output_filename, name=download_name
            ),
            'content_preview': result.text_content[:500] + '...' if len(result.text_content) > 500 else result.text_content,
            'file_type': get_file_type(unique_filename),
            'ocr_engine': ocr_converter.last_engine if ocr_converter else None,
        })
        
    except RequestEntityTooLarge:
        return jsonify({
            'error': f'File is too large. Maximum size is {MAX_FILE_SIZE_MB} MB.'
        }), 413
    except Exception as e:
        # Clean up on error
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        error_msg = f'Conversion failed: {str(e)}'
        print(error_msg)
        import traceback
        traceback.print_exc()
        return jsonify({'error': error_msg}), 500
    finally:
        conversion_lock.release()

@app.route('/download/<filename>')
def download_file(filename):
    try:
        if secure_filename(filename) != filename:
            return jsonify({'error': 'File not found'}), 404

        download_name = secure_filename(request.args.get('name', filename)) or 'converted.md'
        return send_file(
            os.path.join(app.config['UPLOAD_FOLDER'], filename),
            as_attachment=True,
            download_name=download_name
        )
    except Exception as e:
        return jsonify({'error': 'File not found'}), 404

@app.route('/cleanup', methods=['POST'])
def cleanup_files():
    try:
        # Clean up files older than 1 hour
        current_time = datetime.now()
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.isfile(file_path):
                file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                if (current_time - file_time).total_seconds() > CLEANUP_AGE_HOURS * 3600:
                    os.remove(file_path)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': f'Cleanup failed: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
