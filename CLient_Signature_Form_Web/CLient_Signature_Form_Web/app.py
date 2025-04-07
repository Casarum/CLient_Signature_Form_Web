from pickle import TRUE
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import pyodbc
from PIL import Image
import io
import os
import base64
from dotenv import load_dotenv  # For loading environment variables

load_dotenv()
app = Flask(__name__)
# Load sensitive credentials from .env
app.secret_key = os.getenv("FLASK_SECRET_KEY")  # Required for session management

# Database connection details from .env
server = os.getenv("DB_SERVER")
database = os.getenv("DB_NAME")
username = os.getenv("DB_USERNAME")
password = os.getenv("DB_PASSWORD")

# Connection string for SQL Server
connection_string = f"""
    DRIVER={{ODBC Driver 17 for SQL Server}};
    SERVER={server};
    DATABASE={database};
    UID={username};
    PWD={password};
"""
def get_db_connection():
    """Establish a connection to the database."""
    try:
        conn = pyodbc.connect(connection_string)
        return conn
    except Exception as e:
        print("Database connection error:", str(e))  # Log the error
        return None
# Initialize Flask-Limiter
limiter = Limiter(
    app=app,  # Pass the Flask app object
    key_func=get_remote_address,  # Use the client's IP address for rate limiting
    default_limits=["200 per day", "50 per hour"]  # Global rate limits
)

def get_db_connection():
    """Establish a connection to the database."""
    try:
        return pyodbc.connect(connection_string)
    except Exception as e:
        flash("Failed to connect to the database.", "error")
        return None


@app.route("/", methods=["GET", "POST"])
@limiter.limit("15 per minute")  # Rate limit for the login route
def login():
    if request.method == "POST":
        input_username = request.form.get("username")
        input_password = request.form.get("password")

        if not input_username or not input_password:
            flash("Please enter both username and password.", "error")
            return redirect(url_for("login"))

        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT username, roli FROM perdoruesit WHERE username = ? AND password = ?", (input_username, input_password))
                user = cursor.fetchone()
                if user:
                    session["logged_in"] = True
                    session["username"] = user.username
                    session["roli"] = user.roli  # Store the user's roli in the session
                    flash("Login successful!", "success")
                    return redirect(url_for("index"))
                else:
                    flash("Invalid username or password.", "error")
            except Exception as e:
                flash("An error occurred during login.", "error")
            finally:
                conn.close()

    return render_template("login.html")


@app.route("/index", methods=["GET", "POST"])
def index():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    if request.method == "POST":
        # Handle logout
        if request.form.get("action") == "logout":
            session.clear()
            flash("You have been logged out.", "success")
            return redirect(url_for("login"))

    return render_template("index.html")


@app.route("/search_client", methods=["POST"])
@limiter.limit("15 per minute")  # Rate limit for the search route
def search_client():
    search_text = request.form.get("search_text")

    if not search_text:
        return jsonify({"error": "Please enter a search term."})

    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT emri, kodi FROM klient_furnitor WHERE emri LIKE ? and Klient_Furnitor='1' and pasiv='0'", (f"%{search_text}%",))
            clients = [{"emri": row.emri, "kodi": row.kodi} for row in cursor.fetchall()]
            return jsonify({"clients": clients})
        except Exception as e:
            return jsonify({"error": "An error occurred during search."})
        finally:
            conn.close()
    return jsonify({"error": "Failed to connect to the database."})


@app.route("/get_signature", methods=["POST"])
@limiter.limit("15 per minute")  # Rate limit for the get signature route
def get_signature():
    emri = request.form.get("emri")

    if not emri:
        return jsonify({"error": "Please select a client."})

    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT signature FROM klient_furnitor WHERE emri = ?", (emri,))
            result = cursor.fetchone()
            if result and result[0]:
                # Convert binary data to base64
                signature_data = base64.b64encode(result[0]).decode("utf-8")
                return jsonify({"signature": signature_data})
            else:
                return jsonify({"signature": None})
        except Exception as e:
            return jsonify({"error": "An error occurred while fetching the signature."})
        finally:
            conn.close()
    return jsonify({"error": "Failed to connect to the database."})


#@app.route("/save_signature", methods=["POST"])
#@limiter.limit("15 per minute")  # Rate limit for the save signature route
#def save_signature():
#    emri = request.form.get("emri")
#    signature_data = request.form.get("signature")

#    if not emri or not signature_data:
#        return jsonify({"error": "Please select a client and provide a signature."})

#    try:
#        # Ensure the signature data is in the correct format
#        if not signature_data.startswith("data:image/png;base64,"):
#            return jsonify({"error": "Invalid signature format."})

#        # Check if a signature already exists for this client
#        conn = get_db_connection()
#        if conn:
#            try:
#                cursor = conn.cursor()
#                cursor.execute("SELECT signature FROM klient_furnitor WHERE emri = ?", (emri,))
#                result = cursor.fetchone()
#                if result and result[0]:  # If a signature already exists
#                    return jsonify({"error": "A signature already exists for this client. Delete the existing signature before saving a new one."})

#                # Extract the base64 part of the data
#                base64_data = signature_data.split(",")[1]

#                # Convert base64 signature to an image
#                signature_image = Image.open(io.BytesIO(base64.b64decode(base64_data)))

#                # Resize the signature to a fixed size (e.g., 300x100)
#                signature_image = signature_image.resize((300, 100), Image.Resampling.LANCZOS)

#                # Save the resized signature
#                signature_filename = f"signature_{emri}.png"
#                signature_image.save(signature_filename)

#                # Save the signature to the database
#                with open(signature_filename, "rb") as file:
#                    signature_data = file.read()
#                cursor.execute("UPDATE klient_furnitor SET signature = ? WHERE emri = ?", (signature_data, emri))
#                conn.commit()
#                return jsonify({"success": "Signature saved successfully."})
#            except Exception as e:
#                print("Error saving signature to database:", str(e))  # Log database errors
#                return jsonify({"error": "An error occurred while saving the signature."})
#            finally:
#                conn.close()
#                if os.path.exists(signature_filename):
#                    os.remove(signature_filename)
#    except Exception as e:
#        print("Error processing signature:", str(e))  # Log processing errors
#        return jsonify({"error": "Failed to process the signature."})

@app.route("/save_signature", methods=["POST"])
@limiter.limit("15 per minute")
def save_signature():
    emri = request.form.get("emri")
    signature_data = request.form.get("signature")

    if not emri or not signature_data:
        return jsonify({"error": "Please select a client and provide a signature."})

    try:
        # Ensure the signature data is in the correct format
        if not signature_data.startswith("data:image/png;base64,"):
            return jsonify({"error": "Invalid signature format."})

        # Extract the base64 part of the data
        base64_data = signature_data.split(",")[1]

        # Decode the base64 data to binary and check its size
        binary_data = base64.b64decode(base64_data)
        signature_size_kb = len(binary_data) / 1024  # Size in KB

        # Enforce a 20 KB limit
        if signature_size_kb > 20:
            return jsonify({"error": "Signature size exceeds the 20 KB limit."})

        # Check if a signature already exists for this client
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT signature FROM klient_furnitor WHERE emri = ?", (emri,))
                result = cursor.fetchone()
                if result and result[0]:  # If a signature already exists
                    return jsonify({"error": "A signature already exists for this client. Delete the existing signature before saving a new one."})

                # Convert base64 signature to an image
                signature_image = Image.open(io.BytesIO(binary_data))

                # Resize the signature to a fixed size (200x70)
                signature_image = signature_image.resize((200, 70), Image.Resampling.LANCZOS)

                # Save the resized signature temporarily
                signature_filename = f"signature_{emri}.png"
                signature_image.save(signature_filename)

                # Read the resized image and check its size again (optional)
                with open(signature_filename, "rb") as file:
                    resized_data = file.read()
                resized_size_kb = len(resized_data) / 1024

                # Save to the database
                cursor.execute(
                    "UPDATE klient_furnitor SET signature = ? WHERE emri = ?",
                    (resized_data, emri),
                )
                conn.commit()

                return jsonify({"success": "Signature saved successfully."})
            except Exception as e:
                print("Error saving signature to database:", str(e))
                return jsonify({"error": "An error occurred while saving the signature."})
            finally:
                conn.close()
                if os.path.exists(signature_filename):
                    os.remove(signature_filename)
    except Exception as e:
        print("Error processing signature:", str(e))
        return jsonify({"error": "Failed to process the signature."})

@app.route("/delete_signature", methods=["POST"])
@limiter.limit("15 per minute")  # Rate limit for the delete signature route
def delete_signature():
    if not session.get("logged_in"):
        return jsonify({"error": "You must be logged in to delete a signature."})

    # Check if the user is an admin
    if session.get("roli") != "Administrator":
        return jsonify({"error": "Only admin users can delete signatures."})

    emri = request.form.get("emri")

    if not emri:
        return jsonify({"error": "Please select a client."})

    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE klient_furnitor SET signature = NULL WHERE emri = ?", (emri,))
            conn.commit()
            return jsonify({"success": "Signature cleared successfully."})
        except Exception as e:
            return jsonify({"error": "An error occurred while clearing the signature."})
        finally:
            conn.close()
    return jsonify({"error": "Failed to connect to the database."})


if __name__ == "__main__":
    app.run(debug=TRUE)  # Disable debug mode in production