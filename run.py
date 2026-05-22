from app import create_app
import webbrowser
import threading

app = create_app()

# Function to open the browser after the server starts
def open_browser():
    webbrowser.open_new("http://127.0.0.1:5000")

if __name__ == "__main__":
    # Start a thread that will open the browser
    threading.Timer(1, open_browser).start()
    app.run(debug=True, use_reloader=False)
    