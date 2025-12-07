import os
import logging
import requests
from flask import g

logger = logging.getLogger(__name__)

BRAIN_INTERNAL_URL = os.environ.get('BRAIN_INTERNAL_URL', 'http://localhost:3000')


def call_brain(endpoint: str, params: dict = None, method: str = 'GET', json_data: dict = None):
    params = params or {}
    
    if hasattr(g, 'tenant_id') and g.tenant_id:
        params['tenant_id'] = str(g.tenant_id)
    
    url = f"{BRAIN_INTERNAL_URL}{endpoint}"
    
    try:
        if method.upper() == 'GET':
            response = requests.get(url, params=params, timeout=30)
        elif method.upper() == 'POST':
            response = requests.post(url, params=params, json=json_data, timeout=60)
        else:
            response = requests.request(method.upper(), url, params=params, json=json_data, timeout=30)
        
        return response.json(), response.status_code
        
    except requests.exceptions.ConnectionError:
        logger.error(f"Brain service unavailable at {url}")
        return {'error': 'Brain service unavailable'}, 503
    except requests.exceptions.Timeout:
        logger.error(f"Brain service timeout at {url}")
        return {'error': 'Brain service timeout'}, 504
    except Exception as e:
        logger.error(f"Brain call error: {e}")
        return {'error': str(e)}, 500
