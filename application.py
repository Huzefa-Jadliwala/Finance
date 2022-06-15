import os
import time

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    sum_amount = 0
    rows = db.execute("SELECT * FROM usershares WHERE id = ?", session.get("user_id"))
    balance = int(db.execute('SELECT cash FROM users WHERE id = ?', session.get("user_id"))[0]['cash'])
    for i in range(len(rows)):
        data = lookup(rows[i]['company_name'])
        rows[i]['name'] = data['name']
        sum_amount += (rows[i]['share_holding'] * rows[i]['shares_price'])
        rows[i]['price_of_share_holding'] = (rows[i]['share_holding'] * rows[i]['shares_price'])
        rows[i]['shares_price'] = usd(data['price'])
        rows[i]['price_of_share_holding'] = usd(rows[i]['price_of_share_holding'])

    return render_template('index.html', rows=rows, cash=usd(balance-sum_amount), balance=usd(balance))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide Symbol", 400)

        # Ensure shares amount was submitted
        elif not request.form.get("shares"):
            return apology("must provide Shares", 400)

        try:
            shares = int(request.form.get("shares"))
        except ValueError:
            return apology("shares must be a posative integer", 400)

        if shares <= 0:
            return apology("shares must be a posative integer", 400)
        # Ensure company's symbol exist in reality
        data = lookup(request.form.get("symbol"))
        if data == None:
            return apology("Invalid company's symbol provide", 400)

        # Ensure that user has sufficient balance in acount
        share_amount_price = 0
        no_shares_buying = float(request.form.get("shares"))
        TOTAL_SHARE_HOLDING = db.execute('SELECT (share_holding) FROM usershares WHERE id=?', session.get("user_id"))
        TOTAL_SHARE_PRICE = db.execute('SELECT (shares_price) FROM usershares WHERE id=?', session.get("user_id"))
        for i in range(len(TOTAL_SHARE_HOLDING)):
            share_amount_price += TOTAL_SHARE_HOLDING[i]['share_holding']*TOTAL_SHARE_PRICE[i]['shares_price']
        CURRENT_BUY_SHARE_PRICE = data['price']*no_shares_buying
        share_amount_price += CURRENT_BUY_SHARE_PRICE
        if share_amount_price > 10000:
            return apology("Insufficient account balance ", 400)

        # Updating the database with the new purchased shares
        rows = db.execute("SELECT * FROM usershares WHERE id = ? AND company_name = ?",
                          session.get("user_id"), request.form.get("symbol").upper())
        if len(rows) > 0:
            db.execute('UPDATE usershares SET share_holding = ?, shares_price = ? WHERE id = ? AND company_name = ?',
                       (float(request.form.get("shares"))+int(rows[0]['share_holding'])), data['price'], session.get("user_id"), request.form.get("symbol").upper())
        else:
            db.execute('INSERT INTO usershares VALUES(?,?,?,?)', session.get("user_id"),
                       request.form.get("symbol").upper(), request.form.get("shares"), data['price'])
        db.execute("INSERT INTO history VALUES(?,?,?,?)", request.form.get("symbol").upper(), request.form.get("shares"), data['price'], time.asctime(
            time.localtime(time.time())))

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    data = db.execute('SELECT * FROM history;')
    return render_template('history.html', items=data)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        if len(rows) <= 0:
            return apology("invalid username and/or password", 403)
        # Ensure username exists and password is correct
        temp = check_password_hash(rows[0]['hash'], request.form.get("password"))
        if temp == True:
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == 'POST':
        if not request.form.get("symbol"):
            return apology("must provide company's symbol", 400)
        data = lookup(request.form.get("symbol"))
        if data == None:
            return apology("Invalid company's symbol provide", 400)
        C_name = data['name']
        C_symbol = data['symbol']
        Price = usd(data['price'])
        return render_template('quote.html', name=C_name, symbol=C_symbol, price=Price)

    else:
        return render_template('quote.html')


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        password = request.form.get("password")
        if len(password) < 8:
            return apology("password length must be greater than 8", 400)

        # Ensure confirm password was submitted
        elif not request.form.get("confirmation"):
            return apology("must provide confirm password", 400)

        # Ensure password and confirm password are same
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("must provide same literals in password and confirm password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) >= 1:
            return apology("Username name already exists try with different Username", 400)

        # Ensure that the new User credentials are saved in database
        username = request.form.get("username")
        hashpass = generate_password_hash('request.form.get("password")')
        db.execute("INSERT INTO users(username,	hash) VALUES(?,?)", username, hashpass)

        # Redirect user to home page
        return render_template('login.html')

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":
        names_final = []
        names = db.execute("SELECT company_name FROM usershares WHERE id=?", session.get("user_id"))
        for i in range(len(names)):
            names_final.append(names[i]['company_name'])
        return render_template('sell.html', names=names_final)
    else:
        # Ensure company name is submitted
        if not request.form.get("symbol"):
            return apology("must provide company name", 400)

        # Ensure company shares are submitted
        elif not request.form.get("shares"):
            return apology("must provide company shares", 400)

        data = db.execute("SELECT * FROM usershares WHERE id = ? AND company_name = ?",
                          session.get("user_id"), request.form.get("symbol"))
        total_holdings = int(data[0]['share_holding'])

        if total_holdings < float(request.form.get("shares")):
            return apology("You do not have sufficient share to sell", 400)

        price_fetch = lookup(request.form.get("symbol"))
        data2 = db.execute('SELECT * FROM users WHERE id = ?', session.get("user_id"))
        price_fetch = lookup(request.form.get("symbol"))
        x = (total_holdings - float(request.form.get("shares")))*int(data[0]['shares_price'])
        y = (total_holdings - float(request.form.get("shares")))*int(price_fetch['price'])
        updated_cash = data2[0]['cash'] - x + y

        db.execute("UPDATE users SET cash=? WHERE id = ?", updated_cash, session.get("user_id"))
        db.execute("INSERT INTO history VALUES(?,?,?,?)", request.form.get("symbol").upper(), -
                   float(request.form.get("shares")), price_fetch['price'], time.asctime(
            time.localtime(time.time())))
        if (total_holdings - int(request.form.get("shares"))) == 0:
            db.execute('DELETE FROM usershares WHERE id = ? AND company_name = ?',
                       session.get("user_id"), request.form.get("symbol"))
        else:
            db.execute("UPDATE usershares SET share_holding=?, shares_price=? WHERE id = ? AND company_name = ?", total_holdings -
                       float(request.form.get("shares")), price_fetch['price'], session.get("user_id"), request.form.get("symbol"))
        return redirect("/")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
