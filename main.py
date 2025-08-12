
import os
from app import app

# Ensure PORT is set for all platforms
if not os.environ.get('PORT'):
    os.environ['PORT'] = '5000'

# Entry point for different hosting platforms
# Replit: Uses workflow with gunicorn
# Railway: gunicorn main:app --bind 0.0.0.0:$PORT
# Heroku: gunicorn main:app --bind 0.0.0.0:$PORT
# Render: gunicorn main:app --bind 0.0.0.0:$PORT
# Vercel: Uses serverless functions (see vercel.json)

if __name__ == '__main__':
    # For local development only
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
