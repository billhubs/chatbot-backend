from flask import Flask, jsonify, request
import sqlite3

app = Flask(__name__)

@app.route('/reservations/', methods=['GET'])
def get_reservations():
    try:
        conn = sqlite3.connect('backend/database/reservations.db')
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(reservations)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'pnr' not in columns:
            conn.close()
            return jsonify({'reservations': [], 'error': 'Database schema mismatch: missing pnr column'})
        cursor.execute("SELECT pnr, name, service, route, passengers, total_cost, status FROM reservations")
        reservations_raw = cursor.fetchall()
        conn.close()

        reservations = []
        for row in reservations_raw:
            pnr, name, service, route, passengers, total_cost, status = row
            # Split route into origin and destination
            if '-' in route:
                route_origin, route_destination = route.split('-', 1)
            else:
                route_origin, route_destination = route, ''
            reservation = {
                'reservation_id': pnr,
                'customer_name': name,
                'reservation_timestamp': None,  # Not in DB, can be added if needed
                'route_origin': route_origin.strip(),
                'route_destination': route_destination.strip(),
                'reservation_type': service,
                'num_passengers': passengers,
                'travel_date': None,  # Not in DB, can be added if needed
                'pickup_time': None,  # Not in DB, can be added if needed
                'pickup_address': None,  # Not in DB, can be added if needed
                'dropoff_address': None,  # Not in DB, can be added if needed
                'flight_details': None,  # Not in DB, can be added if needed
                'notes': None,  # Not in DB, can be added if needed
                'cancellation_reason': None,  # Not in DB, can be added if needed
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

if __name__ == '__main__':
    app.run(debug=True)
