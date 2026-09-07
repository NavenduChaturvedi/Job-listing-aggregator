"""``python -m webapp`` - start the dashboard on http://127.0.0.1:5001"""

from webapp.app import app

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)
