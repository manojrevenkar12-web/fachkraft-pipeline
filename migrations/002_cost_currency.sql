-- Meta bills in the account's currency (EUR here); the amount column no longer names one.
ALTER TABLE messages RENAME COLUMN cost_usd TO cost;
