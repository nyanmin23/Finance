CREATE TABLE users(
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    username TEXT NOT NULL,
    hash TEXT NOT NULL,
    cash NUMERIC NOT NULL DEFAULT 10000.00
);

CREATE TABLE stocks(
    symbol TEXT PRIMARY KEY NOT NULL,
    company_name TEXT NOT NULL DEFAULT 'N/A'
);

CREATE TABLE portfolio(
    user_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    shares INTEGER NOT NULL CHECK(shares > 0),
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(symbol) REFERENCES stocks(symbol),
    PRIMARY KEY (user_id, symbol)
);

CREATE TABLE transaction_history(
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    user_id INTEGER NOT NULL,
    symbol TEXT,
    transaction_type TEXT NOT NULL,
    shares INTEGER NOT NULL,
    price_per_share NUMERIC NOT NULL DEFAULT 0,
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(symbol) REFERENCES stocks(symbol),
    CONSTRAINT transaction_rules CHECK(
        (transaction_type IN ('BUY', 'SELL') AND shares > 0 AND symbol IS NOT NULL) OR
        (transaction_type IN ('DEPOSIT', 'WITHDRAW') AND shares = 0 AND symbol IS NULL)
    )
);

CREATE UNIQUE INDEX username ON users(username);
