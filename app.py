import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

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


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    """Show portfolio of stocks"""

    user_id = session["user_id"]

    cash_dic = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
    cash = cash_dic[0]["cash"]

    if request.method == "POST":
        faucet = float(request.form.get("faucet"))
        db.execute("UPDATE users SET cash = ? WHERE id = ?", (cash + faucet), user_id)
        return redirect("/")

    rows = db.execute(
        "SELECT symbol, SUM(shares) AS shares FROM transactions WHERE user_id = ? GROUP BY symbol HAVING SUM(shares) > 0",
        user_id,
    )
    for row in rows:
        symb_dic = lookup(row["symbol"])
        row["name"] = symb_dic["name"]
        row["price"] = symb_dic["price"]
        row["sum"] = usd(symb_dic["price"] * row["shares"])

    total = cash
    for row in rows:
        total += row["price"] * row["shares"]
    return render_template(
        "index.html", portfolio=rows, cash=usd(cash), total=usd(total)
    )


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":
        # get info from the page
        symb = request.form.get("symbol")
        try:
            shares = int(request.form.get("shares"))
        except ValueError:
            return apology("enter a number of shares", 400)
        if shares <= 0:
            return apology("enter a positive number of shares", 400)

        symb_dic = lookup(symb)

        # check wallet
        user_id = session["user_id"]
        cash_dic = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        cash = cash_dic[0]["cash"]

        # estimate a transaction
        try:
            purch_amnt = symb_dic["price"] * shares
        except TypeError:
            return apology("invalid symbol", 400)
        cash_left = cash - purch_amnt
        if cash_left < 0:
            return apology("can't afford", 400)

        # change cash amount
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash_left, user_id)

        # update history
        db.execute(
            "INSERT INTO transactions (user_id, symbol, shares, price) VALUES (?, ?, ?, ?)",
            user_id,
            symb_dic["symbol"],
            shares,
            symb_dic["price"],
        )
        return redirect("/")
    return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]
    rows = db.execute(
        "SELECT symbol, shares, price, time FROM transactions WHERE user_id = ?",
        user_id,
    )

    return render_template("history.html", portfolio=rows)


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
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
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
        symb = request.form.get("symbol")
        symb_dic = lookup(symb)

        try:
            return render_template(
                "quoted.html",
                name=symb_dic["name"],
                price=usd(symb_dic["price"]),
                symbol=symb_dic["symbol"],
            )
        except TypeError:
            return apology("invalid symbol", 400)

    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # clear session
    session.clear()

    if request.method == "POST":
        # get a username and password
        username = request.form.get("username")
        password = request.form.get("password")

        # check them
        if not username:
            return apology("missing username", 400)
        elif not password:
            return apology("missing password", 400)
        elif password != request.form.get("confirmation"):
            return apology("passwords don't match", 400)

        # insert data in database if possible
        try:
            db.execute(
                "INSERT INTO users (username, hash) VALUES (?, ?)",
                username,
                generate_password_hash(password),
            )
        except ValueError:
            return apology("Username is not available", 400)

        # log in
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)
        session["user_id"] = rows[0]["id"]

        return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    user_id = session["user_id"]
    rows = db.execute(
        "SELECT symbol, SUM(shares) AS shares FROM transactions WHERE user_id = ? GROUP BY symbol HAVING SUM(shares) > 0",
        user_id,
    )
    cash_dic = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
    cash = cash_dic[0]["cash"]

    if request.method == "POST":
        symb = request.form.get("symbol")
        shares = int(request.form.get("shares"))
        symb_dic = lookup(symb)

        for row in rows:
            if row["symbol"] == symb:
                if (row["shares"] - shares) >= 0:
                    sell_amnt = symb_dic["price"] * shares
                    cash_left = cash + sell_amnt
                    db.execute(
                        "UPDATE users SET cash = ? WHERE id = ?", cash_left, user_id
                    )
                    db.execute(
                        "INSERT INTO transactions (user_id, symbol, shares, price) VALUES (?, ?, ?, ?)",
                        user_id,
                        symb_dic["symbol"],
                        (-1 * shares),
                        symb_dic["price"],
                    )
                else:
                    return apology("too many shares", 400)
        return redirect("/")

    return render_template("sell.html", portfolio=rows)
