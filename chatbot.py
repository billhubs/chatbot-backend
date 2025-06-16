from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import os
import re
from datetime import datetime
import sqlite3
import uuid
import logging

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": ["http://192.168.0.9:3000", "http://localhost:3000", "http://192.168.18.175:3000"]}})

# Define absolute path for database file
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database', 'reservations.db')

# Setup logging
logging.basicConfig(level=logging.INFO, filename='chatbot.log', filemode='a',
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize user states
user_states = {}

# Pricing logic updated to match client request in hcd_enchance.txt

# Base prices and additional charges for Reguler service
REGULER_BASE_PRICE = 180000
REGULER_ADDITIONAL_PASSENGER = 25000
REGULER_ADDITIONAL_ADDRESS = 25000
REGULER_SPECIAL_RATE = 150000  # for >3 passengers and >3 addresses

# Charter Drop package prices by vehicle type
CHARTER_DROP_PRICES = {
    'avanza': 395000,
    'innova': 900000,
    'hiace': 1900000
}
CHARTER_DROP_MAX_CAPACITY = {
    'avanza': 4,
    'innova': 4,
    'hiace': 10
}

# Charter Harian hourly rates by vehicle type and region
CHARTER_HARIAN_RATES = {
    'avanza': {'malang-sby': 650000, 'luar_jatim': 750000},
    'innova': {'malang-sby': 1000000, 'luar_jatim': 1100000},
    'hiace': {'malang-sby': 1500000, 'luar_jatim': 1600000}
}
CHARTER_HARIAN_BONUS_HOURS = 2
CHARTER_HARIAN_BONUS_THRESHOLD = 8
CHARTER_HARIAN_OVERTIME_FEE_PER_HOUR = 50000

# Overtime charge schedule
OVERTIME_CHARGES = [
    (18, 19, 50000),
    (20, 21, 100000),
    (22, 23, 150000)
]

# Holiday pricing adjustments (example for Lebaran 2025)
HOLIDAY_PRICING = {
    'reguler': 200000,
    'charter_drop_avanza': 450000
}

def normalize_phone(phone):
    phone = re.sub(r'\s+', '', phone)
    if phone.startswith('08'):
        phone = '+62' + phone[1:]
    elif not phone.startswith('+62'):
        phone = '+62' + phone.lstrip('0')
    return phone if re.match(r'^\+628[0-9]{8,12}$', phone) else None

def normalize_passengers(passenger_input):
    passenger_input = passenger_input.lower().strip()
    number_words = {
        'satu': 1, 'dua': 2, 'tiga': 3, 'empat': 4, 'lima': 5, 'enam': 6, 'tujuh': 7,
        'delapan': 8, 'sembilan': 9, 'sepuluh': 10
    }
    match = re.match(r'(\d+|\w+)\s*(penumpang|orang)?', passenger_input)
    if match:
        num = match.group(1)
        try:
            return int(num)
        except ValueError:
            return number_words.get(num, None)
    return None

def calculate_price(service, route, passengers, addresses=1, vehicle_type=None, rental_hours=0, pickup_time=None, is_holiday=False):
    total_price = 0
    route = route.lower()
    service = service.lower()

    if service == 'reguler':
        base_price = HOLIDAY_PRICING['reguler'] if is_holiday else REGULER_BASE_PRICE
        # Calculate additional charges
        additional_passenger_fee = 0
        additional_address_fee = 0
        if passengers > 3 and addresses > 3:
            additional_passenger_fee = REGULER_SPECIAL_RATE * passengers
        else:
            if passengers > 1:
                additional_passenger_fee = REGULER_ADDITIONAL_PASSENGER * (passengers - 1)
            if addresses > 1:
                additional_address_fee = REGULER_ADDITIONAL_ADDRESS * (addresses - 1)
        total_price = base_price + additional_passenger_fee + additional_address_fee

    elif service == 'charter_drop':
        if vehicle_type is None:
            vehicle_type = 'avanza'  # default
        base_price = CHARTER_DROP_PRICES.get(vehicle_type.lower(), 395000)
        if is_holiday and vehicle_type.lower() == 'avanza':
            base_price = HOLIDAY_PRICING['charter_drop_avanza']
        total_price = base_price

    elif service == 'charter_harian':
        if vehicle_type is None:
            vehicle_type = 'avanza'
        region = 'malang-sby'  # default region
        base_rate = CHARTER_HARIAN_RATES.get(vehicle_type.lower(), {}).get(region, 650000)
        # Calculate hours with bonus
        chargeable_hours = rental_hours
        if rental_hours > CHARTER_HARIAN_BONUS_THRESHOLD:
            chargeable_hours = CHARTER_HARIAN_BONUS_THRESHOLD + (rental_hours - CHARTER_HARIAN_BONUS_THRESHOLD - CHARTER_HARIAN_BONUS_HOURS)
        total_price = base_rate * chargeable_hours
        # Overtime charges based on pickup_time hour
        if pickup_time:
            try:
                hour = int(pickup_time.split(':')[0])
                for start, end, fee in OVERTIME_CHARGES:
                    if start <= hour <= end:
                        total_price += fee
                        break
            except Exception:
                pass

    return total_price

# --- Llama Maverick endpoint ---
@app.route('/llama/respond', methods=['POST'])
def llama_respond():
    data = request.json
    prompt = data.get('prompt', '')
    # Here you would call your Llama Maverick model or API
    # For demo, just echo the prompt
    answer = f"Llama Maverick response for: {prompt}"
    return jsonify({"answer": answer})

# --- Random Forest endpoint ---
@app.route('/rf/predict', methods=['POST'])
def rf_predict():
    data = request.json
    # Example: Use features from data to predict
    # For demo, just echo the input
    prediction = f"RF prediction for input: {data}"
    return jsonify({"prediction": prediction})

def process_input(message):
    message_lower = message.lower()
    if any(x in message_lower for x in ['pesan', 'booking', 'reservasi']):
        return 'booking', message_lower.split()
    elif any(x in message_lower for x in ['cek', 'cari', 'status']):
        return 'check_reservation', message_lower.split()
    elif any(x in message_lower for x in ['harga', 'price']):
        return 'get_price', message_lower.split()
    elif any(x in message_lower for x in ['rekomendasi', 'recommend', 'saran']):
        return 'recommend_service', message_lower.split()
    elif any(x in message_lower for x in ['terima kasih', 'makasih', 'thanks']):
        return 'thank_you', message_lower.split()
    elif any(x in message_lower for x in ['halo', 'hai', 'selamat']):
        return 'greet', message_lower.split()
    else:
        return 'unknown', message_lower.split()

def calculate_cost(service, route, passengers, addresses=1, vehicle_type=None, rental_hours=0, pickup_time=None, is_holiday=False):
    price = calculate_price(service, route, passengers, addresses, vehicle_type, rental_hours, pickup_time, is_holiday)
    # Add service fee or other adjustments if needed
    service_fee = 10000
    total = price + service_fee
    details = {
        'base_price': price,
        'service_fee': service_fee,
        'total_price': total
    }
    return total, details

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    message = data.get('message', '').strip()
    user_id = data.get('user_id', 'default_user')
    logging.info(f"User {user_id} sent: {message}")

    # Initialize user state if not exists
    if user_id not in user_states:
        user_states[user_id] = {
            'step': None,
            'booking_data': {},
            'error_count': 0
        }

    state = user_states[user_id]
    booking_data = state['booking_data']

    # Intent detection (improved for typos and recommend)
    message_lower = message.lower()
    if any(x in message_lower for x in ['pesan', 'booking', 'reservasi']):
        # Relaxed regex to allow typos in service and route
        match = re.search(r'(reguler|charter drop|charter harian|charter dropp|regulerr|charter hariann)\s*(malang-juanda|juanda-malang|malang-surabaya|surabaya-malang|malang-juandaa|juanda-malangg)', message_lower)
        if match:
            booking_data['service'] = match.group(1).lower()
            booking_data['route'] = match.group(2).lower()
            state['error_count'] = 0
            # Set next step based on service type
            if booking_data['service'] == 'charter harian':
                state['step'] = 'vehicle_type'
                return jsonify({'response': 'Silakan pilih tipe kendaraan untuk Charter Harian (Avanza, Innova, Hiace).'})
            elif booking_data['service'] == 'charter drop':
                state['step'] = 'vehicle_type'
                return jsonify({'response': 'Silakan pilih tipe kendaraan untuk Charter Drop (Avanza, Innova, Hiace).'})
            else:
                state['step'] = 'name'
                return jsonify({'response': 'Silakan masukkan nama pemesan (misal, Budi Santoso).'})
    elif any(x in message_lower for x in ['rekomendasi', 'recommend', 'saran']):
        # Provide recommendation response
        base_price = HOLIDAY_PRICING['reguler'] if False else REGULER_BASE_PRICE
        price_per_passenger = base_price + REGULER_ADDITIONAL_PASSENGER  # Approximate
        return jsonify({'response': f'Untuk rute Malang-Juanda kami sarankan layanan Reguler (Rp{price_per_passenger}/orang) atau Charter Drop (mulai Rp395000). Ketik "Pesan Reguler Malang-Juanda" untuk mulai.'})
    
    # Handle booking steps
    if state['step'] == 'name':
        if re.match(r'[A-Za-z\s]{3,50}', message):
            booking_data['name'] = message
            state['step'] = 'passengers'
            state['error_count'] = 0
            return jsonify({'response': 'Berapa jumlah penumpang? (misal, 3 penumpang atau dua orang)'})
        else:
            state['error_count'] += 1
            if state['error_count'] > 2:
                state['step'] = None
                return jsonify({'response': 'Maaf, terlalu banyak kesalahan. Silakan mulai lagi dengan "Pesan Reguler Malang-Juanda".'})
            return jsonify({'response': 'Nama tidak valid. Silakan masukkan nama lengkap (misal, Budi Santoso).'})
    
    elif state['step'] == 'passengers':
        passengers = normalize_passengers(message)
        if passengers and 1 <= passengers <= 10:
            booking_data['passengers'] = passengers
            state['step'] = 'phone'
            state['error_count'] = 0
            return jsonify({'response': 'Masukkan nomor telepon (misal, +628123456789 atau 08123456789).'})
        else:
            state['error_count'] += 1
            if state['error_count'] > 2:
                state['step'] = None
                return jsonify({'response': f'Maaf, terlalu banyak kesalahan. Silakan mulai lagi dengan "Pesan {booking_data.get("service", "Reguler").title()} {booking_data.get("route", "")}".'})
            return jsonify({'response': 'Jumlah penumpang tidak valid. Silakan masukkan seperti "3 penumpang" atau "dua orang".'})
    
    elif state['step'] == 'phone':
        phone = normalize_phone(message)
        if phone:
            booking_data['phone'] = phone
            state['error_count'] = 0
            # Next step depends on service type
            if booking_data['service'] in ['charter drop', 'charter harian']:
                state['step'] = 'address_pickup'
                return jsonify({'response': 'Masukkan alamat jemput (misal, Jl. Kawi No. 10).'})
            else:
                state['step'] = 'address_pickup'
                return jsonify({'response': 'Masukkan alamat jemput (misal, Jl. Kawi No. 10).'})
        else:
            state['error_count'] += 1
            if state['error_count'] > 2:
                state['step'] = None
                return jsonify({'response': f'Maaf, terlalu banyak kesalahan. Silakan mulai lagi dengan "Pesan {booking_data.get("service", "Reguler").title()} {booking_data.get("route", "")}".'})
            return jsonify({'response': 'Nomor telepon tidak valid. Silakan masukkan seperti "+628123456789" atau "08123456789".'})
    
    elif state['step'] == 'address_pickup':
        if len(message) > 5:
            booking_data['address_pickup'] = message
            state['error_count'] = 0
            # Next step depends on service type
            if booking_data['service'] == 'charter harian':
                state['step'] = 'rental_hours'
                return jsonify({'response': 'Masukkan jumlah jam sewa untuk Charter Harian (misal, 5).'})
            else:
                state['step'] = 'address_dropoff'
                return jsonify({'response': 'Masukkan alamat antar (misal, Jl. Sudirman No. 5). Ketik "tidak ada" jika tidak ada.'})
        else:
            state['error_count'] += 1
            if state['error_count'] > 2:
                state['step'] = None
                return jsonify({'response': f'Maaf, terlalu banyak kesalahan. Silakan mulai lagi dengan "Pesan {booking_data.get("service", "Reguler").title()} {booking_data.get("route", "")}".'})
            return jsonify({'response': 'Alamat jemput tidak valid. Silakan masukkan alamat lengkap (misal, Jl. Kawi No. 10).'})
    
    elif state['step'] == 'address_dropoff':
        booking_data['address_dropoff'] = message if message.lower() != 'tidak ada' else None
        state['error_count'] = 0
        if booking_data['service'] == 'charter harian':
            state['step'] = 'pickup_time'
            return jsonify({'response': 'Masukkan jam jemput (misal, 07:00).'})
        else:
            state['step'] = 'flight'
            return jsonify({'response': 'Masukkan kode penerbangan (misal, GA123). Ketik "tidak ada" jika tidak ada.'})
    
    elif state['step'] == 'flight':
        booking_data['flight'] = message if message.lower() != 'tidak ada' else None
        state['step'] = 'airline'
        state['error_count'] = 0
        return jsonify({'response': 'Masukkan nama maskapai (misal, Garuda Indonesia). Ketik "tidak ada" jika tidak ada.'})
    
    elif state['step'] == 'airline':
        booking_data['airline'] = message if message.lower() != 'tidak ada' else None
        state['step'] = 'pickup_time'
        state['error_count'] = 0
        return jsonify({'response': 'Masukkan jam jemput (misal, 07:00).'})
    
    elif state['step'] == 'pickup_time':
        if re.match(r'^\d{2}:\d{2}$', message):
            booking_data['pickup_time'] = message
            state['step'] = 'pickup_date'
            state['error_count'] = 0
            return jsonify({'response': 'Masukkan tanggal jemput (misal, 2025-06-20).'})
        else:
            state['error_count'] += 1
            if state['error_count'] > 2:
                state['step'] = None
                return jsonify({'response': 'Maaf, terlalu banyak kesalahan. Silakan mulai lagi dengan "Pesan Reguler Malang-Juanda".'})
            return jsonify({'response': 'Jam jemput tidak valid. Silakan masukkan seperti "07:00".'})
    
    elif state['step'] == 'pickup_date':
        if re.match(r'^\d{4}-\d{2}-\d{2}$', message):
            booking_data['pickup_date'] = message
            state['step'] = 'summary'
            state['error_count'] = 0
            # Generate summary
            if 'service' in booking_data and 'route' in booking_data and 'passengers' in booking_data:
                total_cost = calculate_price(booking_data['service'], booking_data['route'], booking_data['passengers'])
            else:
                total_cost = 0
            summary = (
                f"\nRincian Pemesanan:\n"
                f"Nama: {booking_data.get('name', 'Tidak ada')}\n"
                f"Layanan: {booking_data.get('service', 'Tidak ada').title() if 'service' in booking_data else 'Tidak ada'}\n"
                f"Rute: {booking_data.get('route', 'Tidak ada').title() if 'route' in booking_data else 'Tidak ada'}\n"
                f"Penumpang: {booking_data.get('passengers', 'Tidak ada')}\n"
                f"Telepon: {booking_data.get('phone', 'Tidak ada')}\n"
                f"Alamat Jemput: {booking_data.get('address_pickup', 'Tidak ada')}\n"
                f"Alamat Antar: {booking_data.get('address_dropoff', 'Tidak ada')}\n"
                f"Penerbangan: {booking_data.get('flight', 'Tidak ada')}\n"
                f"Maskapai: {booking_data.get('airline', 'Tidak ada')}\n"
                f"Jam Jemput: {booking_data.get('pickup_time', 'Tidak ada')}\n"
                f"Tanggal Jemput: {booking_data.get('pickup_date', 'Tidak ada')}\n"
                f"Total Harga: Rp{total_cost:,}\n"
                f"Silakan ketik 'konfirmasi' untuk melanjutkan, 'ulang' untuk mengisi ulang, atau 'batal' untuk membatalkan."
            )
            return jsonify({'response': summary})
        else:
            state['error_count'] += 1
            if state['error_count'] > 2:
                state['step'] = None
                return jsonify({'response': 'Maaf, terlalu banyak kesalahan. Silakan mulai lagi dengan "Pesan Reguler Malang-Juanda".'})
            return jsonify({'response': 'Tanggal jemput tidak valid. Silakan masukkan seperti "2025-06-20".'})
    
    elif state['step'] == 'summary':
        if message_lower in ['konfirmasi', 'confirm', 'confirmed']:
            # Save booking
            booking_data['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            booking_data['total_cost'] = calculate_price(booking_data['service'], booking_data['route'], booking_data['passengers'])
            booking_data['pnr'] = 'KR-' + str(uuid.uuid4())[:6].upper()
            booking_data['status'] = 'pending'

            # Save to CSV
            csv_data = {
                'timestamp': booking_data['timestamp'],
                'name': booking_data['name'],
                'service': booking_data['service'],
                'route': booking_data['route'],
                'passengers': booking_data['passengers'],
                'phone': booking_data['phone'],
                'address_pickup': booking_data['address_pickup'],
                'address_dropoff': booking_data.get('address_dropoff', ''),
                'flight': booking_data.get('flight', ''),
                'pickup_time': booking_data['pickup_time'],
                'pickup_date': booking_data['pickup_date'],
                'vehicle': booking_data.get('vehicle', ''),
                'total_cost': booking_data['total_cost']
            }
            df = pd.DataFrame([csv_data])
            csv_path = 'data/bookings.csv'
            if os.path.exists(csv_path):
                df.to_csv(csv_path, mode='a', header=False, index=False)
            else:
                df.to_csv(csv_path, index=False)

            # Save to SQLite
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS reservations
                            (pnr TEXT PRIMARY KEY, name TEXT, service TEXT, route TEXT, passengers INTEGER,
                             phone TEXT, address_pickup TEXT, address_dropoff TEXT, flight TEXT, pickup_time TEXT,
                             pickup_date TEXT, vehicle TEXT, total_cost INTEGER, status TEXT)''')
            cursor.execute('''INSERT INTO reservations
                            (pnr, name, service, route, passengers, phone, address_pickup, address_dropoff, flight,
                             pickup_time, pickup_date, vehicle, total_cost, status)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                           (booking_data['pnr'], booking_data['name'], booking_data['service'],
                            booking_data['route'], booking_data['passengers'], booking_data['phone'],
                            booking_data['address_pickup'], booking_data.get('address_dropoff', ''),
                            booking_data.get('flight', ''), booking_data['pickup_time'],
                            booking_data['pickup_date'], booking_data.get('vehicle', ''),
                            booking_data['total_cost'], booking_data['status']))

            conn.commit()
            conn.close()

            response = (
                f"Pemesanan dikonfirmasi untuk {booking_data['name']}:\n"
                f"Kode Booking: {booking_data['pnr']}\n"
                f"Apa yang ingin dilakukan selanjutnya? Ketik: 'selesai', 'buatkan reservasi lagi', atau 'cari pesanan'."
            )
            state['step'] = 'next_action'
            return jsonify({'response': response})
        elif message_lower == 'ulang':
            state['step'] = 'name'
            state['booking_data'] = {}
            state['error_count'] = 0
            return jsonify({'response': 'Silakan masukkan nama pemesan (misal, Budi Santoso).'})
        elif message_lower == 'batal':
            state['step'] = None
            state['booking_data'] = {}
            state['error_count'] = 0
            return jsonify({'response': 'Pemesanan dibatalkan. Silakan mulai lagi dengan "Pesan Reguler Malang-Juanda" atau ketik "bantuan".'})
        else:
            return jsonify({'response': "Silakan ketik 'konfirmasi' untuk melanjutkan, 'ulang' untuk mengisi ulang, atau 'batal' untuk membatalkan."})
    
    elif state['step'] == 'next_action':
        if message_lower == 'selesai':
            state['step'] = None
            state['booking_data'] = {}
            return jsonify({'response': 'Terima kasih! Silakan ketik "Pesan Reguler Malang-Juanda" untuk memesan lagi.'})
        elif message_lower == 'buatkan reservasi lagi':
            state['step'] = 'name'
            state['booking_data'] = {}
            state['error_count'] = 0
            return jsonify({'response': 'Silakan masukkan nama pemesan (misal, Budi Santoso).'})
        elif message_lower == 'cari pesanan':
            state['step'] = 'check_reservation'
            return jsonify({'response': 'Silakan masukkan kode booking (misalnya, KIR0001 atau KR-ABC123).'})
        else:
            return jsonify({'response': "Apa yang ingin dilakukan selanjutnya? Ketik: 'selesai', 'buatkan reservasi lagi', atau 'cari pesanan'."})
    
    elif state['step'] == 'check_reservation':
        if re.match(r'^(KIR|KR)-[A-Z0-9]{4,6}$', message):
            conn = sqlite3.connect('../backend/database/reservations.db')
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM reservations WHERE pnr = ?", (message,))
            reservation = cursor.fetchone()
            conn.close()
            if reservation:
                response = (
                    f"Detail pesanan:\n"
                    f"Kode Booking: {reservation[0]}\n"
                    f"Nama: {reservation[1]}\n"
                    f"Layanan: {reservation[2].title()}\n"
                    f"Rute: {reservation[3].title()}\n"
                    f"Status: {reservation[13].title()}\n"
                    f"Apa yang ingin dilakukan selanjutnya? Ketik: 'selesai', 'buatkan reservasi lagi', atau 'cari pesanan'."
                )
                state['step'] = 'next_action'
                return jsonify({'response': response})
            else:
                return jsonify({'response': 'Kode booking tidak ditemukan. Silakan masukkan kode lain atau ketik "batal".'})
        elif message_lower in ['batal', 'tidak ada', 'ga ada']:
            state['step'] = None
            state['booking_data'] = {}
            return jsonify({'response': 'Pengecekan dibatalkan. Silakan mulai lagi dengan "Pesan Reguler Malang-Juanda" atau ketik "bantuan".'})
        else:
            return jsonify({'response': 'Kode booking tidak valid. Silakan masukkan kode seperti "KIR0001" atau "123456" atau ketik "batal".'})
    
    # Handle other intents
    if any(x in message_lower for x in ['bantuan', 'help']):
        return jsonify({
            'response': (
                'Halo! Silakan ketik:\n'
                '"Pesan Reguler Malang-Juanda" untuk memesan.\n'
                '"Rekomendasi layanan Malang-Juanda" untuk saran.\n'
                '"Cek pesanan KIR0001" untuk cek status.'
            )
        })
    elif any(x in message_lower for x in ['rekomendasi', 'suggest']):
        # Calculate price per passenger for Reguler service
        base_price = HOLIDAY_PRICING['reguler'] if False else REGULER_BASE_PRICE
        price_per_passenger = base_price + REGULER_ADDITIONAL_PASSENGER  # Approximate
        return jsonify({'response': f'Untuk rute Malang-Juanda, kami sarankan layanan Reguler (Rp{price_per_passenger:,}/orang) atau Charter Drop (mulai Rp395,000). Ketik "Pesan Reguler Malang-Juanda" untuk mulai.'})
    elif any(x in message_lower for x in ['terima kasih', 'makasih', 'thanks']):
        return jsonify({'response': 'Terima kasih! Silakan ketik "bantuan" jika perlu bantuan lagi.'})
    elif any(x in message_lower for x in ['selamat', 'halo', 'hai']):
        return jsonify({'response': 'Halo! Silakan ketik "Pesan Reguler Malang-Juanda" untuk memesan atau "bantuan" untuk informasi lebih lanjut.'})

    # Fallback
    if state['step'] == 'summary':
        # If user inputs full data at once, show summary and prompt for confirmation
        summary = (
            f"\nRincian Pemesanan:\n"
            f"Nama: {booking_data.get('name', 'Tidak ada')}\n"
            f"Layanan: {booking_data.get('service', 'Tidak ada').title() if 'service' in booking_data else 'Tidak ada'}\n"
            f"Rute: {booking_data.get('route', 'Tidak ada').title() if 'route' in booking_data else 'Tidak ada'}\n"
            f"Penumpang: {booking_data.get('passengers', 'Tidak ada')}\n"
            f"Telepon: {booking_data.get('phone', 'Tidak ada')}\n"
            f"Alamat Jemput: {booking_data.get('address_pickup', 'Tidak ada')}\n"
            f"Alamat Antar: {booking_data.get('address_dropoff', 'Tidak ada')}\n"
            f"Penerbangan: {booking_data.get('flight', 'Tidak ada')}\n"
            f"Maskapai: {booking_data.get('airline', 'Tidak ada')}\n"
            f"Jam Jemput: {booking_data.get('pickup_time', 'Tidak ada')}\n"
            f"Tanggal Jemput: {booking_data.get('pickup_date', 'Tidak ada')}\n"
            f"Silakan ketik 'konfirmasi' untuk melanjutkan, 'ulang' untuk mengisi ulang, atau 'batal' untuk membatalkan."
        )
        return jsonify({'response': summary})
    else:
        return jsonify({'response': 'Maaf, saya kurang paham. Silakan ketik "Pesan Reguler Malang-Juanda" atau "bantuan".'})

@app.route('/reservations/', methods=['GET'])
def get_reservations():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(reservations)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'pnr' not in columns:
            conn.close()
            return jsonify({'reservations': [], 'error': 'Database schema mismatch: missing pnr column'})
        cursor.execute("SELECT pnr, name, service, route, passengers, total_cost, status, pickup_date, pickup_time, address_pickup, address_dropoff FROM reservations")
        reservations_raw = cursor.fetchall()
        conn.close()

        reservations = []
        for row in reservations_raw:
            pnr, name, service, route, passengers, total_cost, status, pickup_date, pickup_time, address_pickup, address_dropoff = row
            if '-' in route:
                route_origin, route_destination = route.split('-', 1)
            else:
                route_origin, route_destination = route, ''
            reservation = {
                'reservation_id': pnr,
                'customer_name': name,
                'reservation_timestamp': None,
                'route_origin': route_origin.strip(),
                'route_destination': route_destination.strip(),
                'reservation_type': service,
                'num_passengers': passengers,
                'travel_date': pickup_date,
                'pickup_time': pickup_time,
                'pickup_address': address_pickup,
                'dropoff_address': address_dropoff,
                'flight_details': None,
                'notes': None,
                'cancellation_reason': None,
                'price': total_cost,
                'status': status
            }
            reservations.append(reservation)

        return jsonify(reservations)
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        app.logger.error(f"Error in get_reservations: {error_msg}")
        return jsonify({'reservations': [], 'error': str(e)})

@app.route('/api/reports', methods=['GET'])
def get_reports():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM reservations")
        total_reservations = cursor.fetchone()[0]

        cursor.execute("SELECT status, COUNT(*) FROM reservations GROUP BY status")
        status_counts = dict(cursor.fetchall())

        cursor.execute("SELECT SUM(total_cost) FROM reservations")
        total_revenue = cursor.fetchone()[0] or 0

        cursor.execute("SELECT AVG(total_cost) FROM reservations")
        avg_booking_value = cursor.fetchone()[0] or 0

        conn.close()

        report = {
            "total_reservations": total_reservations,
            "status_counts": status_counts,
            "total_revenue": total_revenue,
            "avg_booking_value": avg_booking_value
        }
        return jsonify(report)
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        app.logger.error(f"Error in get_reports: {error_msg}")
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    import os
    os.makedirs('data', exist_ok=True)
    os.makedirs('db', exist_ok=True)
    # Use Gunicorn for production deployment
    # For local testing, you can still use app.run()
    app.run(debug=True, host='0.0.0.0', port=5000)
