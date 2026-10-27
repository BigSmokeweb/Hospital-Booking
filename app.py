import os
from flask import Flask, jsonify, request, render_template
from database import init_db, get_db_connection
from services import (
    search_doctors,
    book_appointment,
    cancel_appointment
)


def create_app(test_config=None):
    app = Flask(__name__, template_folder="templates")

    if test_config:
        app.config.update(test_config)

    db_path = app.config.get("DATABASE_PATH",
                             os.environ.get("DATABASE_PATH", "hospital.db"))
    app.config["DATABASE_PATH"] = db_path

    # Ensure DB is created
    init_db(db_path)

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/doctors", methods=["GET"])
    def get_doctors():
        query = request.args.get("q", "").strip()
        doctors = search_doctors(query, db_path=app.config["DATABASE_PATH"])
        return jsonify(doctors), 200

    @app.route("/api/patients", methods=["GET"])
    def get_patients():
        conn = get_db_connection(app.config["DATABASE_PATH"])
        patients = conn.execute(
            "SELECT id, name, phone, age, address FROM patients "
            "ORDER BY id DESC"
        ).fetchall()
        conn.close()
        return jsonify([dict(p) for p in patients]), 200

    @app.route("/api/appointments", methods=["GET"])
    def list_appointments():
        conn = get_db_connection(app.config["DATABASE_PATH"])
        rows = conn.execute("""
            SELECT a.id, a.doctor_id, d.name AS doctor_name,
                   d.specialization, a.patient_id, p.name AS patient_name,
                   p.phone AS patient_phone, p.age AS patient_age,
                   p.address AS patient_address, a.slot_time, a.fee,
                   a.status, a.refund_amount, a.refund_percentage,
                   a.created_at
            FROM appointments a
            JOIN doctors d ON a.doctor_id = d.id
            JOIN patients p ON a.patient_id = p.id
            ORDER BY a.id DESC
        """).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows]), 200

    @app.route("/api/appointments", methods=["POST"])
    def create_appointment():
        data = request.get_json() or {}
        doctor_id = data.get("doctor_id")
        slot_time = data.get("slot_time")

        patient_id = data.get("patient_id")
        patient_name = data.get("patient_name")
        patient_phone = data.get("patient_phone")
        patient_age = data.get("patient_age")
        patient_address = data.get("patient_address")

        if not doctor_id or not slot_time:
            return jsonify({
                "success": False,
                "error": "Missing required fields: doctor_id or slot_time."
            }), 400

        if not patient_id and (not patient_name or not patient_phone):
            return jsonify({
                "success": False,
                "error": "Please enter Patient Name and Phone Number."
            }), 400

        result = book_appointment(
            doctor_id=int(doctor_id),
            patient_id=int(patient_id) if patient_id else None,
            slot_time_str=slot_time,
            patient_name=patient_name,
            patient_phone=patient_phone,
            patient_age=int(patient_age) if patient_age else None,
            patient_address=patient_address,
            db_path=app.config["DATABASE_PATH"]
        )
        return jsonify(result), result["status_code"]

    @app.route("/api/appointments/<int:appointment_id>/cancel",
               methods=["POST"])
    def cancel_appointment_endpoint(appointment_id):
        result = cancel_appointment(
            appointment_id=appointment_id,
            db_path=app.config["DATABASE_PATH"]
        )
        return jsonify(result), result["status_code"]

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)
