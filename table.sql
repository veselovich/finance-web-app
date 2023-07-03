CREATE TABLE transactions (
    user_id INTEGER,
    symbol TEXT NOT NULL,
    shares INTEGER,
    price NUMERIC CHECK (price > 0),
    time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id));

SELECT symbol, SUM(shares) FROM transactions GROUP BY symbol WHERE user_id = ?