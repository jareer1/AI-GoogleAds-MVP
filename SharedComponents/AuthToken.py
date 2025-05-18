from functools import wraps
from flask import request, jsonify
import jwt
from ..SharedComponents.keys import loadPublicKey

def tokenRequired():
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # 1) Get the header
            auth_header = request.headers.get('Authorization', None)
            if not auth_header:
                return jsonify({'error': 'Token is missing'}), 401

            parts = auth_header.split()
            if parts[0].lower() != 'bearer' or len(parts) != 2:
                return jsonify({'error': 'Invalid authorization header format'}), 401

            token = parts[1]

            try:
                # 2) Load your PEM-encoded public key (bytes or str)
                public_key = loadPublicKey()

                # 3) Decode & verify. 
                #    You can also pass issuer='...', audience='...' as needed.
                decoded = jwt.decode(
                    token,
                    public_key,
                    algorithms=['RS256'],
                    options={
                        'require_exp': True,   # reject tokens without exp
                        'require_iat': True,   # reject tokens without iat
                    }
                )

                # 4) Attach user info to request
                #    Change 'sub' to match your claim, or use 'userId' if you prefer
                request.userId = decoded.get('sub') or decoded.get('userId')
                print("token Validated Successfully")
                return f(*args, **kwargs)

            except jwt.ExpiredSignatureError:
                return jsonify({'error': 'Token has expired'}), 401
            except jwt.InvalidTokenError as e:
                return jsonify({'error': f'Invalid token: {str(e)}'}), 401


        return decorated
    return decorator
