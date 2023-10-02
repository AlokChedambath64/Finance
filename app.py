import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
import datetime
from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    #get the current user
    user = session.get("user_id")
    #get list of users's portfolio
    list = db.execute("SELECT * FROM portfolio WHERE portnum = ?", user)
    balance = (db.execute("SELECT cash FROM users WHERE id = ?", user)[0]['cash'])
    stocks = db.execute("SELECT stock FROM portfolio WHERE portnum = ?", user)
    price = []
    for row in stocks:
        stock_data = lookup(row["stock"])
        if stock_data is not None:
                price.append((stock_data['price']))
    i = 0
    sum = balance
    for row in list:
        row['price'] = price[i]
        sum += row['value']
        i+=1

    sum = sum
    return render_template("index.html", list = list, sum = sum, balance = balance)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":

        #to get the inputted values
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        if not symbol or not shares:
            return apology("One or more fields have been left blank", 403)
        if not shares.isdigit():
            return apology("You cannot purchase partial shares.")
        shares = int(shares)

        #to check if the numbers of shares inputted is a positive number
        if shares < 0:
            return apology("Number of shares has to positive", 400)

        #dict with the share price
        dict = lookup(symbol)
        if not dict:
            return apology("Invalid Symbol", 400)
        #total price to buy
        cost = int(shares * dict["price"])

        #current user
        user = session.get("user_id")

        #sql query to get how much money the person currently has
        current = int(db.execute("SELECT cash FROM users WHERE id = (?)", user)[0]["cash"])
        #to check if they can afford and updating current money if can do so
        if cost > current:
            return apology("Not Enough Money", 403)
        else:
            current = current - cost
            #update money
            db.execute("UPDATE users SET cash = ? WHERE id = ?", current, user)

        #updating the portfolio table
        db.execute("INSERT INTO portfolio(portnum, stock, shares, price, value) VALUES(?,?,?,?,?)", user, dict["symbol"], shares, dict["price"], shares * dict["price"])

        current_datetime = datetime.datetime.now()

        db.execute("INSERT INTO TRANSACTIONS (portnum, stock, trans, price, shares, dandt) VALUES (?, ?, ?, ?, ?, ?)", user, symbol, "buy", dict["price"], shares, current_datetime)

        return redirect("/")

    return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    list = db.execute("SELECT * FROM TRANSACTIONS;")
    return render_template("history.html", list = list)


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

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
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
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Field has been left blank", 400)
        dict = lookup(symbol)
        if not dict:
            return apology("Invalid Symbol", 400)
        price = dict['price']
        dict['price'] = usd(price)

        return render_template("quoted.html", dict = dict)

    return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if (password != confirmation):
            return apology("Password and Confirmation do not match", 400)

        if not username or not password or not confirmation:
            return apology("One or more fields have been left blank", 400)

        rows = db.execute("SELECT username FROM users;")

        for row in rows:
            if username == row["username"]:
                return apology("Duplicate Username", 400)

        db.execute("INSERT INTO users (username, hash) VALUES(?,?)", username,generate_password_hash(password, method='pbkdf2:sha256', salt_length=8) )
        return render_template("login.html")

    return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    user = session.get("user_id")
    #for the drop down menu
    stocks = db.execute("SELECT stock FROM portfolio WHERE portnum = ?", user)
    if request.method == 'POST':
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        #to check if some fields have been left blank
        if not symbol or not shares:
            return apology("One or more fields have been left blank", 400)

        shares = int(shares)
        #to check if no of shares is positive
        if (shares <= 0):
            return apology("Please send positive amount of shares", 400)

        #data on how much of each stock the person has
        current = db.execute("SELECT * FROM portfolio WHERE portnum = ? AND stock = ?", user, symbol)
        print(current)
        if (shares > current[0]["shares"]):
            return apology("Do not posses that amount of shares", 400)

        price = lookup(symbol)
        amount = price["price"] * shares
        currentcash = db.execute("SELECT cash FROM users WHERE id = ?", user)[0]['cash']

        db.execute("UPDATE users SET cash = ? WHERE id = ?", currentcash + amount, user)
        db.execute("UPDATE portfolio SET shares = ? WHERE portnum = ? AND stock = ?", current[0]["shares"] - shares, user, symbol)

        current_datetime = datetime.datetime.now()
        #update history table
        db.execute("INSERT INTO TRANSACTIONS (portnum, stock, trans, price, shares, dandt) VALUES (?, ?, ?, ?, ?, ?)", user, symbol, "sell", price["price"], shares, current_datetime)

        return redirect("/")

    return render_template("sell.html", stocks = stocks)
