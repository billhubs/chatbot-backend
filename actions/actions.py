from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
import requests
import sqlite3

class ActionHandleChatbot(Action):
    def name(self) -> Text:
        return "action_handle_chatbot"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        user_message = tracker.latest_message.get('text', '')
        user_id = tracker.sender_id

        try:
            response = requests.post(
                'http://localhost:5000/chat',
                json={'message': user_message, 'user_id': user_id},
                timeout=5
            )
            response.raise_for_status()
            data = response.json()
            dispatcher.utter_message(text=data.get('response', 'Maaf, terjadi kesalahan.'))
        except requests.RequestException as e:
            dispatcher.utter_message(text=f"Maaf, ada masalah dengan server: {str(e)}")

        return []
    
class ActionCollectBookingDetails(Action):
    def name(self):
        return "action_collect_booking_details"
    async def run(self, dispatcher, tracker, domain):
        service_type = tracker.get_slot("service_type")
        if service_type and "charter_drop" in service_type.lower():
            if not tracker.get_slot("addresses"):
                dispatcher.utter_message(text="Berapa jumlah alamat tujuan? (misal, 4 alamat)")
                return [{"slot": "requested_slot", "value": "addresses"}]
        slots = ["name", "passengers", "phone", "address_pickup", "address_dropoff", "flight", "airline", "pickup_time", "pickup_date"]
        for slot in slots:
            if not tracker.get_slot(slot):
                dispatcher.utter_message(text=f"Masukkan {slot.replace('_', ' ')} (misal, Billy Tian Sunarto untuk nama).")
                return [{"slot": "requested_slot", "value": slot}]
        return []

class ActionCheckReservation(Action):
    def name(self):
        return "action_check_reservation"
    async def run(self, dispatcher, tracker, domain):
        pnr = tracker.get_slot("pnr")
        conn = sqlite3.connect("backend/database/reservations.db")
        cursor = conn.cursor()
        cursor.execute("SELECT name, route, price FROM reservations WHERE pnr = ?", (pnr,))
        result = cursor.fetchone()
        conn.close()
        if result:
            dispatcher.utter_message(text=f"Pemesanan ditemukan: Nama: {result[0]} Rute: {result[1]} Harga: Rp{result[2]} Status: Confirmed")
        else:
            dispatcher.utter_message(text="Kode booking tidak ditemukan.")
        return []