CREATE TABLE reservations (
    pnr TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    service TEXT NOT NULL,
    route TEXT NOT NULL,
    passengers INTEGER NOT NULL,
    phone TEXT NOT NULL,
    address_pickup TEXT NOT NULL,
    address_dropoff TEXT,
    flight TEXT,
    pickup_time TEXT,
    pickup_date TEXT,
    vehicle TEXT,
    total_cost INTEGER NOT NULL,
    status TEXT NOT NULL
);

-- Index for quick search
CREATE INDEX idx_reservations_pickup_date ON reservations(pickup_date);
CREATE INDEX idx_reservations_phone ON reservations(phone);
