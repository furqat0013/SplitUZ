CREATE TABLE groups (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    kind VARCHAR(64) NOT NULL,
    currency VARCHAR(8) NOT NULL DEFAULT 'UZS',
    created_at DATE NOT NULL
);

CREATE TABLE members (
    group_id VARCHAR(64) NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    id VARCHAR(64) NOT NULL,
    name VARCHAR(255) NOT NULL,
    bank VARCHAR(64) NOT NULL,
    joined_at DATE NOT NULL,
    PRIMARY KEY (group_id, id)
);

CREATE TABLE expenses (
    id VARCHAR(64) PRIMARY KEY,
    group_id VARCHAR(64) NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    paid_by VARCHAR(64) NOT NULL,
    amount BIGINT NOT NULL CHECK (amount > 0),
    currency VARCHAR(8) NOT NULL,
    category VARCHAR(100) NOT NULL,
    note VARCHAR(500) NOT NULL,
    split_method VARCHAR(20) NOT NULL CHECK (split_method IN ('teng','foiz','aniq','pozitsiya')),
    spent_at TIMESTAMP NOT NULL,
    deleted BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (id, group_id),
    FOREIGN KEY (group_id, paid_by) REFERENCES members(group_id, id)
);

CREATE INDEX ix_expenses_group_id ON expenses(group_id);

CREATE TABLE expense_shares (
    expense_id VARCHAR(64) NOT NULL,
    group_id VARCHAR(64) NOT NULL,
    member_id VARCHAR(64) NOT NULL,
    amount BIGINT NOT NULL CHECK (amount >= 0),
    PRIMARY KEY (expense_id, group_id, member_id),
    FOREIGN KEY (expense_id, group_id) REFERENCES expenses(id, group_id) ON DELETE CASCADE,
    FOREIGN KEY (group_id, member_id) REFERENCES members(group_id, id)
);

CREATE INDEX ix_shares_group_member ON expense_shares(group_id, member_id);

CREATE TABLE settlements (
    id VARCHAR(64) PRIMARY KEY,
    group_id VARCHAR(64) NOT NULL,
    sender_id VARCHAR(64) NOT NULL,
    receiver_id VARCHAR(64) NOT NULL,
    amount BIGINT NOT NULL CHECK (amount > 0),
    settled_at DATE NOT NULL,
    status VARCHAR(32) NOT NULL,
    CHECK (sender_id <> receiver_id),
    FOREIGN KEY (group_id, sender_id) REFERENCES members(group_id, id),
    FOREIGN KEY (group_id, receiver_id) REFERENCES members(group_id, id)
);

CREATE INDEX ix_settlements_group_id ON settlements(group_id);

