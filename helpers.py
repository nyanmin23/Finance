import requests

from flask import redirect, render_template, session
from enum import Enum
from functools import wraps

class TransactionType(Enum):
    BUY = "BUY"
    SELL = "SELL"
    DEPOSIT = "DEPOSIT"
    WITHDRAW = "WITHDRAW"

def record_transaction(db, user_id, symbol, transaction_type, shares, price_per_share, final_balance):
    """ Record a transaction in the database. """

    # Update Balance
    db.execute("UPDATE users SET cash = ? WHERE id = ?", final_balance, user_id)

    # Update Transaction History
    db.execute(
        "INSERT INTO transaction_history (user_id, symbol, transaction_type, shares, price_per_share) VALUES (?, ?, ?, ?, ?)",
        user_id,
        symbol, 
        transaction_type.value, 
        shares, 
        price_per_share
    )


def apology(message, code=400):
    """Render message as an apology to user."""

    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [
            ("-", "--"),
            (" ", "-"),
            ("_", "__"),
            ("?", "~q"),
            ("%", "~p"),
            ("#", "~h"),
            ("/", "~s"),
            ('"', "''"),
        ]:
            s = s.replace(old, new)
        return s

    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/latest/patterns/viewdecorators/
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function


def lookup(symbol):
    """Look up quote for symbol."""
    symbol = symbol.upper()
    url = f"https://finance.cs50.io/quote?symbol={symbol}"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for HTTP error responses
        quote_data = response.json()
        return {
            "name": quote_data["companyName"],
            "price": quote_data["latestPrice"],
            "symbol": symbol
        }
    except requests.RequestException as e:
        print(f"Request error: {e}")
    except (KeyError, ValueError) as e:
        print(f"Data parsing error: {e}")
    return None


def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"
