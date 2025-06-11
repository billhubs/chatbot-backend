import sqlite3
from datetime import datetime
import random
import uuid

DB_PATH = 'backend/database/reservations.db'

sample_names = [
    "Budi Santoso", "Siti Aminah", "Joko Widodo", "Dewi Lestari", "Agus Salim",
    "Rina Marlina", "Andi Prasetyo", "Lina Marlina", "Hendra Gunawan", "Sari Dewi"
]

sample_routes = [
    "malang-juanda", "juanda-malang", "malang-surabaya", "surabaya-malang"
]

sample_services = [
    "reguler", "charter_drop", "charter_harian"
]

sample_statuses = [
    "pending", "confirmed", "cancelled"
]

def random_date():
    return datetime(2025, random.randint(6, 12), random.randint(1, 28)).strftime('%Y-%m-%d')

def random_time():
    return f"{random.randint(0, 23):02d}:{random.choice(['00', '15', '30', '45'])}"

def insert_sample_reservations(n=1):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS reservations
                      (pnr TEXT PRIMARY KEY, name TEXT, service TEXT, route TEXT, passengers INTEGER,
                       phone TEXT, address_pickup TEXT, address_dropoff TEXT, flight TEXT, pickup_time TEXT,
                       pickup_date TEXT, vehicle TEXT, total_cost INTEGER, status TEXT)''')

    for _ in range(n):
        pnr = 'KR-' + str(uuid.uuid4())[:6].upper()
        name = random.choice(sample_names)
        service = random.choice(sample_services)
        route = random.choice(sample_routes)
        passengers = random.randint(1, 5)
        phone = '+6281234567890'
        address_pickup = f"Jl. Contoh No. {random.randint(1, 100)}"
        address_dropoff = f"Jl. Tujuan No. {random.randint(1, 100)}"
        flight = f"GA{random.randint(100, 999)}"
        pickup_time = random_time()
        pickup_date = random_date()
        vehicle = "avanza"
        total_cost = 200000 * passengers
        status = random.choice(sample_statuses)

        cursor.execute('''INSERT OR IGNORE INTO reservations
                          (pnr, name, service, route, passengers, phone, address_pickup, address_dropoff,
                           flight, pickup_time, pickup_date, vehicle, total_cost, status)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                       (pnr, name, service, route, passengers, phone, address_pickup, address_dropoff,
                        flight, pickup_time, pickup_date, vehicle, total_cost, status))
    conn.commit()
    conn.close()
    print(f"Inserted {n} sample reservations.")

if __name__ == "__main__":
    insert_sample_reservations()
