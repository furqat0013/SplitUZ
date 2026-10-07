# SplitUZ ERD

```mermaid
erDiagram
    GROUPS ||--o{ MEMBERS : contains
    GROUPS ||--o{ EXPENSES : owns
    MEMBERS ||--o{ EXPENSES : pays
    EXPENSES ||--|{ EXPENSE_SHARES : splits_into
    MEMBERS ||--o{ EXPENSE_SHARES : owes
    MEMBERS ||--o{ SETTLEMENTS : sends
    MEMBERS ||--o{ SETTLEMENTS : receives

    GROUPS {
        varchar id PK
        varchar name
        varchar kind
        varchar currency
        date created_at
    }
    MEMBERS {
        varchar group_id PK,FK
        varchar id PK
        varchar name
        varchar bank
        date joined_at
    }
    EXPENSES {
        varchar id PK
        varchar group_id FK
        varchar paid_by FK
        bigint amount
        varchar currency
        varchar category
        varchar note
        varchar split_method
        timestamp spent_at
        boolean deleted
    }
    EXPENSE_SHARES {
        varchar expense_id PK,FK
        varchar group_id PK,FK
        varchar member_id PK,FK
        bigint amount
    }
    SETTLEMENTS {
        varchar id PK
        varchar group_id FK
        varchar sender_id FK
        varchar receiver_id FK
        bigint amount
        date settled_at
        varchar status
    }
```

## Financial integrity

- Money is stored as integer `BIGINT` UZS; floating-point arithmetic is never used.
- `(group_id, member_id)` is the participant identity, preventing cross-group references.
- `(expense_id, group_id)` on shares must reference the same expense and group.
- Expense and settlement amounts must be positive; share amounts must be non-negative.
- Sender and receiver of a settlement must be different.
- Expense plus all normalized shares is committed in one transaction.

