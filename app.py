import os
import logging

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, record_transaction, TransactionType

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

# Minimum withdrawal/ deposit amounts
minimum_amount = 100.00
logging.getLogger("cs50").disabled = False

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

    user_id = session["user_id"]
    cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)

    if not cash:
        session.clear()
        return redirect("/login")
    else:
        balance = round(float(cash[0]["cash"]), 2)

    portfolio = db.execute("SELECT * FROM portfolio WHERE user_id = ?", user_id)
    
    if portfolio:
        symbols = [symbol["symbol"] for symbol in portfolio]
        shares = [share["shares"] for share in portfolio]
        total_value = []
        holdings = []

        for symbol, share in zip(symbols, shares):
            stock_info = lookup(symbol)
            if stock_info:
                price_per_share = round(float(stock_info["price"]), 2)
                subtotal = int(share) * price_per_share
                total_value.append(subtotal)
                holdings.append({
                    "symbol": symbol,
                    "shares": share,
                    "price_per_share": usd(price_per_share),
                    "total": usd(subtotal)
                    })

        return render_template("index.html",
                               portfolio=holdings,
                               balance=usd(balance),
                               total_value=usd(sum(total_value) + balance))
    else:
        return render_template("index.html",
                               balance=usd(balance),
                               total_value=usd(balance))
    

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":
        if not request.form.get("username"):
            return apology("must provide username", 400)

        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Confirm password
        if request.form.get("confirmation") != request.form.get("password"):
            return apology("passwords do not match", 400)

        try:
            # Check username duplication
            db.execute(
                "INSERT INTO users (username, hash) VALUES (?, ?)",
                request.form.get("username"),
                generate_password_hash(request.form.get("password"))
            )

        # Return 'username already exists' apology
        except Exception as error:
            print(error)
            return apology(f"username already exists", 400)

        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        session["user_id"] = rows[0]["id"]
        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

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

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?",
            request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 400)

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
    """Get stock quote"""

    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("missing symbol", 400)

        # Fetch stock info
        stock_info = lookup(request.form.get("symbol"))

        if stock_info is not None:
            name = stock_info["name"]
            price_per_share = usd(stock_info["price"])
            symbol = stock_info["symbol"]

            # Display stock info
            return render_template("quoted.html",
                                   name=name,
                                   symbol=symbol,
                                   price_per_share=price_per_share)

        # Return apology if symbol does not exist
        else:
            return apology(f"invalid symbol - ({request.form.get('symbol').upper()})", 400)

    else:
        return render_template("quote.html")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":
        user_id = session["user_id"]
        balance = round(
            float(db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]), 2)

        if not request.form.get("symbol"):
            return apology("missing symbol", 403)

        elif not request.form.get("shares"):
            return apology("missing shares", 403)

        # Ensure users submit valid input
        try:
            shares = int(request.form.get("shares"))
        except ValueError:
            return apology("shares must be a positive integer", 400)

        if shares < 1:
            return apology("shares must be a positive integer", 400)

        stock_info = lookup(request.form.get("symbol"))
        if stock_info is not None:
            name = stock_info["name"]
            price_per_share = round(float(stock_info['price']), 2)
            symbol = stock_info["symbol"]
        else:
            return apology("invalid symbol", 400)

        total_amount = shares * price_per_share

        # Check if users have enough balance
        if balance < total_amount:
            return apology("not enough cash", 403)
        else:
            final_balance = balance - total_amount

            # Update Balance and record transaction
            record_transaction(
                db, user_id, symbol, TransactionType.BUY, shares, price_per_share, final_balance
            )

            # List stocks permanently
            db.execute(
                "INSERT OR IGNORE INTO stocks (symbol, company_name) VALUES (?, ?)", symbol, name
            )

            # Update Portfolio
            db.execute(
                "INSERT INTO portfolio (user_id, symbol, shares) VALUES (?, ?, ?) ON CONFLICT(user_id, symbol) DO UPDATE SET shares = shares + excluded.shares",
                user_id, symbol, shares
            )

            # Success: Bought
            flash("Bought!")
            return redirect("/")

    else:
        return render_template("buy.html")
    

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    user_id = session["user_id"]
    balance = round(
            float(db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]), 2
        )
    portfolio = db.execute("SELECT symbol FROM portfolio WHERE user_id = ?", user_id)
    symbols = [stock["symbol"] for stock in portfolio]

    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)

        if not request.form.get("shares"):
            return apology("must provide shares", 400)

        try:
            shares_to_sell = int(request.form.get("shares"))
        except ValueError:
            return apology("shares input accept only positive integer", 403)

        if shares_to_sell < 1:
            return apology("must provide positive integer", 400)
        
        symbol = request.form.get("symbol")
        shares = db.execute("SELECT shares FROM portfolio WHERE user_id = ? AND symbol = ?", user_id, symbol)

        if not shares:
            return apology("You do not own this stock", 404)
        
        shares_owned = shares[0]["shares"]

        # Lookup current stock price
        stock_info = lookup(symbol)
        if stock_info is not None:
            price_per_share = round(float(stock_info["price"]), 2)
        else:
            return apology("invalid symbol", 404)

        # Check if user has enough shares to sell
        if shares_owned >= shares_to_sell:
            trade_value = shares_to_sell * price_per_share
            final_balance = balance + trade_value
            net_shares = shares_owned - shares_to_sell

            # Update Balance and record transaction
            record_transaction(
                db, user_id, symbol, TransactionType.SELL, shares_to_sell, price_per_share, final_balance
            )

            # Update Portfolio
            if net_shares == 0:
                db.execute(
                    "DELETE FROM portfolio WHERE user_id = ? AND symbol = ?",
                    user_id, symbol
                )

            else:
                db.execute(
                    "UPDATE portfolio SET shares = ? WHERE user_id = ? AND symbol = ?",
                    net_shares, user_id, symbol
                )

        else:
            return apology(f"You only have {shares_owned} {symbol} shares", 400)

        # Success: Sold
        flash("Sold!")
        return redirect("/")

    else:
        return render_template("sell.html", symbols=symbols)
    

@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    """Deposit cash"""

    if request.method == "POST":
        user_id = session["user_id"]
        balance = round(
            float(db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]), 2)

        if not request.form.get("amount"):
            return apology("must provide amount of cash", 400)

        try:
            deposit = round(float(request.form.get("amount")), 2)
        except ValueError:
            return apology("deposit amount must be a positive number", 400)

        if deposit < minimum_amount:
            return apology(f"minimum deposit amount is {usd(minimum_amount)}", 403)

        final_balance = balance + deposit

        # Update balance and record transaction
        record_transaction(
            db, user_id, None, TransactionType.DEPOSIT, 0, deposit, final_balance
        )

        flash("Success: Deposit!")
        return redirect("/")

    else:
        return render_template("deposit.html")


@app.route("/withdraw", methods=["GET", "POST"])
@login_required
def withdraw():
    """Withdraw cash"""

    if request.method == "POST":
        user_id = session["user_id"]
        balance = round(
            float(db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]), 2
        )

        if not request.form.get("amount"):
            return apology("must provide amount of cash", 400)

        elif not request.form.get("password"):
            return apology("must provide password", 400)

        elif not request.form.get("confirmation"):
            return apology("must confirm password", 400)

        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords do not match", 403)

        # Query database for password
        rows = db.execute(
            "SELECT * FROM users WHERE id = ?",
            user_id
        )

        # Ensure password is correct
        if not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid password", 400)

        try:
            withdrawal = round(float(request.form.get("amount")), 2)
        except ValueError:
            return apology("withdrawal amount must be a positive number", 400)

        if withdrawal < minimum_amount:
            return apology(f"minimum withdrawal amount is {usd(minimum_amount)}", 403)

        if balance >= withdrawal:
            final_balance = balance - withdrawal

            # Update balance and record transaction
            record_transaction(
                db, user_id, None, TransactionType.WITHDRAW, 0, withdrawal, final_balance
            )

        else:
            return apology("withdrawal amount exceeds available balance", 403)

        flash("Success: Withdrawal!")
        return redirect("/")

    else:
        return render_template("withdraw.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    user_id = session["user_id"]
    transaction_history = []
    transactions = db.execute(
        "SELECT symbol, transaction_type, shares, price_per_share, timestamp FROM transaction_history WHERE user_id = ? ORDER BY id DESC",
        user_id
    )

    for transaction in transactions:
        price_per_share = transaction["price_per_share"]

        if price_per_share is None:
            price_per_share = "N/A"
        else:
            price_per_share = usd(price_per_share)

        transaction_history.append({
            "symbol": transaction["symbol"],
            "shares": transaction["shares"],
            "transaction_type": transaction["transaction_type"],
            "price_per_share": price_per_share,
            "timestamp": transaction["timestamp"]
        })

    return render_template("history.html", transaction_history=transaction_history)

