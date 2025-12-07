#!/usr/bin/env python3
import os
import sys

os.environ.setdefault('BRAIN_INTERNAL_URL', 'http://localhost:5001')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import web_app

web_app.init_scheduler = lambda: None

from platform_service.routes.knowledge import knowledge_bp
web_app.app.register_blueprint(knowledge_bp)


@web_app.app.route('/api/brain/health')
def brain_health():
    from platform_service.brain_client import call_brain
    from flask import jsonify
    data, status = call_brain('/internal/v1/health')
    return jsonify(data), status


if __name__ == '__main__':
    port = int(os.environ.get('PLATFORM_PORT', 5000))
    print(f"[Platform] Starting on port {port}")
    web_app.app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
