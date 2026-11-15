CREATE TABLE IF NOT EXISTS state_trucks (
    code TEXT PRIMARY KEY,
    message TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS state_orders (
    code TEXT PRIMARY KEY,
    message TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS state_trips (
    code TEXT PRIMARY KEY,
    message TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alert_types (
    code TEXT PRIMARY KEY,
    message TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trucks (
    id TEXT PRIMARY KEY,
    brand TEXT NOT NULL,
    model TEXT NOT NULL,
    license_plate TEXT NOT NULL UNIQUE,
    id_state_truck TEXT NOT NULL REFERENCES state_trucks(code),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    middle_name TEXT,
    email TEXT NOT NULL UNIQUE,
    phone TEXT,
    birthdate DATE,
    password_hash TEXT NOT NULL,
    is_admin BOOLEAN NOT NULL DEFAULT false,
    id_truck_default TEXT REFERENCES trucks(id),
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS stores (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT,
    location TEXT NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS routes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    deliver_days INTEGER[] NOT NULL DEFAULT '{}',
    id_assigned_user TEXT REFERENCES users(id),
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS route_stores (
    route_id TEXT NOT NULL REFERENCES routes(id) ON DELETE CASCADE,
    store_id TEXT NOT NULL REFERENCES stores(id),
    sequence INTEGER NOT NULL,
    PRIMARY KEY (route_id, store_id)
);

CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    date TIMESTAMPTZ NOT NULL,
    delivered TIMESTAMPTZ,
    id_created_by_user TEXT REFERENCES users(id),
    id_store TEXT NOT NULL REFERENCES stores(id),
    id_state_order TEXT NOT NULL REFERENCES state_orders(code),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS order_logs (
    id TEXT PRIMARY KEY,
    date TIMESTAMPTZ NOT NULL,
    id_order TEXT REFERENCES orders(id),
    id_state_order TEXT REFERENCES state_orders(code)
);

CREATE TABLE IF NOT EXISTS trips (
    id TEXT PRIMARY KEY,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ,
    id_truck TEXT NOT NULL REFERENCES trucks(id),
    id_user_driver TEXT NOT NULL REFERENCES users(id),
    id_route TEXT NOT NULL REFERENCES routes(id),
    id_state_trip TEXT NOT NULL REFERENCES state_trips(code),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS trip_orders (
    id BIGSERIAL PRIMARY KEY,
    trip_id TEXT NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    order_id TEXT NOT NULL REFERENCES orders(id),
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    sequence INTEGER NOT NULL DEFAULT 0,
    UNIQUE (trip_id, order_id)
);

CREATE TABLE IF NOT EXISTS trip_logs (
    id TEXT PRIMARY KEY,
    date TIMESTAMPTZ NOT NULL,
    id_trip TEXT REFERENCES trips(id) ON DELETE CASCADE,
    id_state_trip TEXT REFERENCES state_trips(code),
    orders JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE TABLE IF NOT EXISTS readings (
    id TEXT PRIMARY KEY,
    date TIMESTAMPTZ NOT NULL,
    door_state BOOLEAN NOT NULL DEFAULT false,
    temp DOUBLE PRECISION NOT NULL,
    perc_humidity INTEGER NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    id_truck TEXT NOT NULL REFERENCES trucks(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS alerts (
    id TEXT PRIMARY KEY,
    date TIMESTAMPTZ NOT NULL,
    state BOOLEAN NOT NULL DEFAULT true,
    id_reading TEXT REFERENCES readings(id),
    id_alert_type TEXT NOT NULL REFERENCES alert_types(code),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS parameters (
    id INTEGER PRIMARY KEY,
    max_temperature NUMERIC(6,2) NOT NULL,
    min_temperature NUMERIC(6,2) NOT NULL,
    max_humidity INTEGER NOT NULL,
    min_humidity INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS truck_logs (
    id TEXT PRIMARY KEY,
    date TIMESTAMPTZ NOT NULL,
    id_truck TEXT NOT NULL REFERENCES trucks(id),
    id_state_truck TEXT NOT NULL REFERENCES state_trucks(code)
);

CREATE TABLE IF NOT EXISTS door_events (
    id TEXT PRIMARY KEY,
    state BOOLEAN NOT NULL,
    time_opened TIMESTAMPTZ NOT NULL,
    id_truck TEXT NOT NULL REFERENCES trucks(id)
);

CREATE TABLE IF NOT EXISTS osrm_routes (
    id TEXT PRIMARY KEY,
    start_latitude DOUBLE PRECISION NOT NULL,
    start_longitude DOUBLE PRECISION NOT NULL,
    end_latitude DOUBLE PRECISION NOT NULL,
    end_longitude DOUBLE PRECISION NOT NULL,
    distance DOUBLE PRECISION NOT NULL DEFAULT 0,
    duration DOUBLE PRECISION NOT NULL DEFAULT 0,
    geometry JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_readings_truck_date ON readings (id_truck, date DESC);
CREATE INDEX IF NOT EXISTS idx_readings_date ON readings (date DESC);
CREATE INDEX IF NOT EXISTS idx_orders_date ON orders (date DESC);
CREATE INDEX IF NOT EXISTS idx_orders_state ON orders (id_state_order);
CREATE INDEX IF NOT EXISTS idx_alerts_state ON alerts (state);
CREATE INDEX IF NOT EXISTS idx_trips_start ON trips (start_time DESC);
CREATE INDEX IF NOT EXISTS idx_osrm_points ON osrm_routes (start_latitude, start_longitude, end_latitude, end_longitude);
