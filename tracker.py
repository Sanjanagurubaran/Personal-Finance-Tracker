from flask import Flask, render_template, request, redirect, url_for,session,flash
from werkzeug.security import generate_password_hash,check_password_hash
from functools import wraps
import mysql.connector
from collections import defaultdict
from datetime import datetime
from calendar import monthrange

app = Flask(__name__)
app.secret_key="Gvss972010@"

def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password=#password,
        database=#database
    )

@app.route('/')
def home():
    return redirect(url_for('login'))


#----------AUNTHETICATION PAGE--------

# ---- Add this function to protect pages ----
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

# ---- User Register Route ----
@app.route('/register', methods=['GET', 'POST'])
def register():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Check if username already exists
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            flash("Username already exists!", "warning")
            return redirect(url_for('register'))

        # Store hashed password
        hashed_pw = generate_password_hash(password)
        cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_pw))
        conn.commit()
        flash("Registration successful! Please login.", "success")
        return redirect(url_for('login'))

    return render_template("register.html")


# ---- User Login Route ----
@app.route('/login', methods=['GET', 'POST'])
def login():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash("Login successful!", "success")
            return redirect(url_for('setup'))  # or any page you want after login
        else:
            flash("Invalid username or password", "danger")

    return render_template("login.html")


# ---- Logout Route ----
@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully!", "info")
    return redirect(url_for('login'))

#---------- FORGOT PASSWORD ROUTE ----------

@app.route('/forgot-password', methods=['GET', 'POST']) 
def forgot_password(): 
    conn = get_db() 
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        username = request.form['username']
        new_password = request.form['new_password']

        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()

        if user:
            hashed_pw = generate_password_hash(new_password)
            cursor.execute("UPDATE users SET password = %s WHERE username = %s", (hashed_pw, username))
            conn.commit()
            flash("Password reset successful! Please login.", "success")
            return redirect(url_for('login'))
        else:
            flash("Username not found.", "danger")
    return render_template("forgot_password.html")

#---------- CHANGE PASSWORD ROUTE ----------

@app.route('/change-password', methods=['GET', 'POST'])
@login_required 
def change_password(): 
    conn = get_db() 
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        old_password = request.form['old_password']
        new_password = request.form['new_password']

        user_id = session['user_id']
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()

        if user and check_password_hash(user['password'], old_password):
            hashed_pw = generate_password_hash(new_password)
            cursor.execute("UPDATE users SET password = %s WHERE id = %s", (hashed_pw, user_id))
            conn.commit()
            flash("Password changed successfully!", "success")
            return redirect(url_for('setup'))
        else:
            flash("Incorrect old password.", "danger")

    return render_template("change_password.html")




# --------- SETUP PAGE ---------
@app.route('/setup', methods=['GET', 'POST'])
@login_required
def setup():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Handle delete
    delete_id = request.args.get('delete_id')
    if delete_id:
        cursor.execute("DELETE FROM setup WHERE id = %s", (delete_id,))
        db.commit()
        return redirect(url_for('setup'))

    # Add income setup
    if request.method == 'POST':
        form_type = request.form.get('form_type')
        category = request.form['category']
        subcategory = request.form['subcategory']
        if form_type == 'income':
            cursor.execute(
                "INSERT INTO setup (category, subcategory, type) VALUES (%s, %s, 'income')",
                (category, subcategory)
            )
        elif form_type == 'expense':
            cursor.execute(
                "INSERT INTO setup (category, subcategory, type) VALUES (%s, %s, 'expense')",
                (category, subcategory)
            )
        db.commit()
        return redirect(url_for('setup'))

    cursor.execute("SELECT * FROM setup WHERE type='income' ORDER BY category, subcategory")
    income_setup = cursor.fetchall()

    cursor.execute("SELECT * FROM setup WHERE type='expense' ORDER BY category, subcategory")
    expense_setup = cursor.fetchall()

    db.close()
    return render_template("setup.html", income_setup=income_setup, expense_setup=expense_setup)

# --------- INCOME PAGE --------
@app.route("/income", methods=["GET", "POST"])
@login_required
def income():
    conn=get_db()
    cursor = conn.cursor(dictionary=True)

    # Fetch setup data for Income
    cursor.execute("SELECT category, subcategory FROM setup WHERE type = 'Income'")
    setup_data = cursor.fetchall()

    if request.method == "POST":
        entry_date = request.form.get("entry_date")
        entry_time=request.form.get("entry_time")
        entry_datetime=f"{entry_date}{entry_time}"
        categories = request.form.getlist("category")
        subcategories = request.form.getlist("subcategory")
        amounts = request.form.getlist("amount")

        for cat, sub, amt in zip(categories, subcategories, amounts):
            if amt.strip():
                cursor.execute("""
                    INSERT INTO entries (type, category, subcategory, amount, entry_date)
                    VALUES (%s, %s, %s, %s, %s)
                """, ("Income", cat, sub, amt, entry_date))
        conn.commit()

    # Fetch and group all income entries by (month, year)
    cursor.execute("""
        SELECT category, subcategory, amount, entry_date
        FROM entries
        WHERE type = 'Income'
        ORDER BY entry_date DESC
    """)
    all_entries = cursor.fetchall()

    grouped_entries = defaultdict(list)
    for row in all_entries:
        date_obj = row["entry_date"]
        key = date_obj.strftime("%B %Y")  # e.g., "July 2025"
        grouped_entries[key].append(row)

    return render_template("income.html", setup_data=setup_data, grouped_entries=grouped_entries)
# Assuming you have this function to connect
@app.route("/expense", methods=["GET", "POST"])
@login_required
def expense():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # Get setup data for expense
    cursor.execute("SELECT category, subcategory FROM setup WHERE type = 'Expense'")
    setup_data = cursor.fetchall()

    # Save new entries
    if request.method == "POST":
        entry_date = request.form.get("entry_date")
        categories = request.form.getlist("category")
        subcategories = request.form.getlist("subcategory")
        amounts = request.form.getlist("amount")

        for cat, sub, amt in zip(categories, subcategories, amounts):
            if amt.strip():
                cursor.execute("""
                    INSERT INTO entries (type, category, subcategory, amount, entry_date)
                    VALUES (%s, %s, %s, %s, %s)
                """, ("Expense", cat, sub, amt, entry_date))
        conn.commit()

    # Fetch and group previous entries month-wise
    cursor.execute("""
        SELECT category, subcategory, amount, entry_date
        FROM entries
        WHERE type = 'Expense'
        ORDER BY entry_date DESC
    """)
    all_entries = cursor.fetchall()

    from collections import defaultdict
    grouped_entries = defaultdict(list)
    for row in all_entries:
        key = row["entry_date"].strftime("%B %Y")  # e.g., "July 2025"
        grouped_entries[key].append(row)

    cursor.close()
    conn.close()

    return render_template("expense.html", setup_data=setup_data, grouped_entries=grouped_entries)
#------------REPORT PAGE-----------------
@app.route('/report', methods=['GET', 'POST'])
@login_required
def report():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    income_data = []
    expense_data = []

    income_labels = []
    income_values = []

    expense_labels = []
    expense_values = []

    if request.method == 'POST':
        from_date = request.form.get('from_date')
        to_date = request.form.get('to_date')
        month_year = request.form.get('month_year')  # New field for month selection

        # If month_year is selected, override from_date and to_date
        if month_year:
            # Example: month_year = '2025-07'
            year, month = map(int, month_year.split('-'))
            first_day = datetime(year, month, 1)
            last_day = datetime(year, month, monthrange(year, month)[1])
            from_date = first_day.strftime('%Y-%m-%d')
            to_date = last_day.strftime('%Y-%m-%d')

        # Fetch income data grouped by category
        cursor.execute("""
            SELECT category, SUM(amount) AS total
            FROM entries
            WHERE type='Income' AND entry_date BETWEEN %s AND %s
            GROUP BY category
        """, (from_date, to_date))
        income_data = cursor.fetchall()
        income_labels = [row['category'] for row in income_data]
        income_values = [float(row['total']) for row in income_data]

        # Fetch expense data grouped by category
        cursor.execute("""
            SELECT category, SUM(amount) AS total
            FROM entries
            WHERE type='Expense' AND entry_date BETWEEN %s AND %s
            GROUP BY category
        """, (from_date, to_date))
        expense_data = cursor.fetchall()
        expense_labels = [row['category'] for row in expense_data]
        expense_values = [float(row['total']) for row in expense_data]

    cursor.close()
    conn.close()

    return render_template("report.html",
                           income_data=income_data,
                           expense_data=expense_data,
                           income_labels=income_labels,
                           income_values=income_values,
                           expense_labels=expense_labels,
                           expense_values=expense_values)
if __name__=='__main__':
    app.run(port=8000)
