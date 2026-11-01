-- Esquema da base operacional da Emporio da Musica.
-- Fonte: data/*.csv (dados) e data/policies/*.md (politicas curadas a partir do PDF).
-- Reconstruido integralmente por scripts/build_db.py; nenhum dado e editado a mao.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE categories (
    category_id INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT
);

CREATE TABLE products (
    product_id     INTEGER PRIMARY KEY,
    name           TEXT NOT NULL,
    category_id    INTEGER NOT NULL REFERENCES categories(category_id),
    price_brl      REAL NOT NULL CHECK (price_brl >= 0),
    stock_quantity INTEGER NOT NULL CHECK (stock_quantity >= 0),
    status         TEXT NOT NULL CHECK (status IN ('active', 'discontinued', 'coming_soon')),
    description    TEXT,
    specs_json     TEXT,
    created_at     TEXT
);

CREATE TABLE customers (
    customer_id  INTEGER PRIMARY KEY,
    name         TEXT NOT NULL,
    phone        TEXT NOT NULL,
    phone_digits TEXT NOT NULL UNIQUE,
    email        TEXT,
    city         TEXT
);

CREATE INDEX idx_customers_phone ON customers(phone_digits);

CREATE TABLE orders (
    order_id           INTEGER PRIMARY KEY,
    customer_id        INTEGER NOT NULL REFERENCES customers(customer_id),
    order_date         TEXT NOT NULL,
    status             TEXT NOT NULL CHECK (
        status IN ('pending', 'confirmed', 'shipped', 'delivered', 'cancelled')
    ),
    total_brl          REAL NOT NULL CHECK (total_brl >= 0),
    payment_method     TEXT,
    tracking_code      TEXT,
    estimated_delivery TEXT,
    notes              TEXT
);

CREATE INDEX idx_orders_customer ON orders(customer_id);

CREATE TABLE order_items (
    order_id   INTEGER NOT NULL REFERENCES orders(order_id),
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    quantity   INTEGER NOT NULL CHECK (quantity > 0),
    PRIMARY KEY (order_id, product_id)
);

CREATE TABLE promotions (
    promotion_id     INTEGER PRIMARY KEY,
    product_id       INTEGER NOT NULL REFERENCES products(product_id),
    discount_percent REAL NOT NULL CHECK (discount_percent BETWEEN 0 AND 100),
    description      TEXT,
    is_active        INTEGER NOT NULL CHECK (is_active IN (0, 1))
);

-- Visao de leitura usada pelas ferramentas: preco de tabela + promocao ativa (se houver).
-- Quando existe mais de uma promocao ativa para o mesmo produto, vale a de maior desconto.
CREATE VIEW v_products AS
SELECT
    p.product_id,
    p.name,
    p.category_id,
    c.name AS category_name,
    p.price_brl,
    p.stock_quantity,
    p.status,
    p.description,
    p.specs_json,
    promo.discount_percent AS promo_percent,
    promo.description      AS promo_name,
    CASE
        WHEN promo.discount_percent IS NOT NULL
        THEN ROUND(p.price_brl * (1 - promo.discount_percent / 100.0), 2)
        ELSE p.price_brl
    END AS price_final
FROM products p
JOIN categories c ON c.category_id = p.category_id
LEFT JOIN (
    SELECT product_id, MAX(discount_percent) AS discount_percent, MAX(description) AS description
    FROM promotions
    WHERE is_active = 1
    GROUP BY product_id
) promo ON promo.product_id = p.product_id;

-- Politicas: um registro por bloco (secao ou subsecao) do manual.
CREATE TABLE policies (
    policy_id     INTEGER PRIMARY KEY,
    secao         TEXT NOT NULL UNIQUE,
    secao_pai     TEXT NOT NULL,
    titulo        TEXT NOT NULL,
    texto         TEXT NOT NULL,
    pagina        INTEGER,
    versao        TEXT,
    atualizado_em TEXT,
    fonte         TEXT
);

-- Indice lexical (BM25 nativo do SQLite). Sem embeddings: 25 blocos nao justificam ANN.
CREATE VIRTUAL TABLE policies_fts USING fts5(
    secao UNINDEXED,
    titulo,
    texto,
    tokenize = 'unicode61 remove_diacritics 2'
);
