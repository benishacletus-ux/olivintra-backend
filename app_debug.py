# app_debug.py
import traceback
import sys

try:
    from app import app
    print("App imported successfully!")
except Exception as e:
    print("ERROR IMPORTING APP:")
    print(traceback.format_exc())
    sys.exit(1)

if __name__ == '__main__':
    try:
        print("Starting server on http://127.0.0.1:5000")
        app.run(debug=True, host='127.0.0.1', port=5000)
    except Exception as e:
        print("ERROR RUNNING APP:")
        print(traceback.format_exc())