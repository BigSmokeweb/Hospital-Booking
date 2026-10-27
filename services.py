from datetime import datetime
from database import get_db_connection, parse_datetime

MAX_ACTIVE_APPOINTMENTS_PER_PATIENT = 2


def search_doctors(query=None, db_path=None):
    """
    Search doctors by name or specialization.
    Uses case-insensitive substring match.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    if not query:
        cursor.execute(
            "SELECT id, name, specialization, consultation_fee "
            "FROM doctors ORDER BY name ASC"
        )
    else:
        term = f"%{query.strip()}%"
        cursor.execute(
            "SELECT id, name, specialization, consultation_fee FROM doctors "
            "WHERE LOWER(name) LIKE LOWER(?) OR "
            "LOWER(specialization) LIKE LOWER(?) "
            "ORDER BY name ASC",
            (term, term)
        )

    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_or_create_patient(name, phone, age=None, address=None,
                          email=None, db_path=None):
    """
    Finds an existing patient by phone number or creates a new record.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, name, phone, age, address FROM patients WHERE phone = ?",
        (phone.strip(),)
    )
    patient = cursor.fetchone()

    if patient:
        patient_id = patient["id"]
        # Update details if provided
        cursor.execute(
            """
            UPDATE patients
            SET name = ?, age = COALESCE(?, age),
                address = COALESCE(?, address),
                email = COALESCE(?, email)
            WHERE id = ?
            """,
            (name.strip(), age, address, email, patient_id)
        )
    else:
        cursor.execute(
            """
            INSERT INTO patients (name, phone, age, address, email)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name.strip(), phone.strip(), age, address, email)
        )
        patient_id = cursor.lastrowid

    conn.commit()
    conn.close()
    return patient_id


def book_appointment(doctor_id, patient_id=None, slot_time_str=None,
                     current_time=None, db_path=None,
                     patient_name=None, patient_phone=None,
                     patient_age=None, patient_address=None):
    """
    Books an appointment enforcing all business constraints:
    1. Handles manual patient registration (name, phone, age, address).
    2. Validation: Appointments in past are rejected.
    3. Limit: Patient cannot hold more than 2 active appointments.
    4. Double booking: Same doctor & time slot cannot be booked twice.
    """
    if current_time is None:
        current_time = datetime.now()

    try:
        slot_time = parse_datetime(slot_time_str)
    except (ValueError, TypeError) as exc:
        return {"success": False, "error": str(exc), "status_code": 400}

    # Validation: appointments in the past are rejected
    if slot_time <= current_time:
        return {
            "success": False,
            "error": "Cannot book appointment in the past.",
            "status_code": 400
        }

    formatted_slot = slot_time.strftime("%Y-%m-%d %H:%M:%S")

    # If patient details provided manually
    if patient_name and patient_phone:
        patient_id = get_or_create_patient(
            name=patient_name,
            phone=patient_phone,
            age=patient_age,
            address=patient_address,
            db_path=db_path
        )
    elif not patient_id:
        return {
            "success": False,
            "error": "Patient details or Patient ID required.",
            "status_code": 400
        }

    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Check doctor exists
    cursor.execute(
        "SELECT id, consultation_fee FROM doctors WHERE id = ?",
        (doctor_id,)
    )
    doctor = cursor.fetchone()
    if not doctor:
        conn.close()
        return {"success": False, "error": "Doctor not found.",
                "status_code": 404}

    # Check patient exists
    cursor.execute("SELECT id FROM patients WHERE id = ?", (patient_id,))
    patient = cursor.fetchone()
    if not patient:
        conn.close()
        return {"success": False, "error": "Patient not found.",
                "status_code": 404}

    # Limit: a patient cannot hold more than 2 active appointments
    cursor.execute(
        "SELECT COUNT(*) AS count FROM appointments "
        "WHERE patient_id = ? AND status = 'ACTIVE'",
        (patient_id,)
    )
    active_count = cursor.fetchone()["count"]
    if active_count >= MAX_ACTIVE_APPOINTMENTS_PER_PATIENT:
        conn.close()
        return {
            "success": False,
            "error": f"Patient limit reached: Maximum "
                     f"{MAX_ACTIVE_APPOINTMENTS_PER_PATIENT} active "
                     f"appointments allowed.",
            "status_code": 400
        }

    # Double booking: same doctor and time slot cannot be booked twice
    cursor.execute(
        "SELECT id FROM appointments "
        "WHERE doctor_id = ? AND slot_time = ? AND status = 'ACTIVE'",
        (doctor_id, formatted_slot)
    )
    existing_slot = cursor.fetchone()
    if existing_slot:
        conn.close()
        return {
            "success": False,
            "error": "Double booking error: Doctor already has an "
                     "active appointment at this slot.",
            "status_code": 409
        }

    fee = doctor["consultation_fee"]
    now_str = current_time.strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute(
        """
        INSERT INTO appointments (
            doctor_id, patient_id, slot_time, fee, status,
            refund_amount, refund_percentage, created_at
        ) VALUES (?, ?, ?, ?, 'ACTIVE', 0.0, 0.0, ?)
        """,
        (doctor_id, patient_id, formatted_slot, fee, now_str)
    )
    appointment_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "success": True,
        "appointment_id": appointment_id,
        "doctor_id": doctor_id,
        "patient_id": patient_id,
        "slot_time": formatted_slot,
        "fee": fee,
        "status": "ACTIVE",
        "status_code": 201
    }


def calculate_refund(fee, slot_time, cancel_time):
    """
    Refund policy:
    - 100% refund if cancelled more than 24 hours ahead.
    - 50% refund if cancelled 24 hours or less ahead, but before slot.
    - 0% refund if cancelled after the appointment slot time.
    """
    diff_seconds = (slot_time - cancel_time).total_seconds()
    hours_ahead = diff_seconds / 3600.0

    if hours_ahead > 24.0:
        pct = 100.0
    elif hours_ahead >= 0.0:
        pct = 50.0
    else:
        pct = 0.0

    refund_amt = round(fee * (pct / 100.0), 2)
    return pct, refund_amt


def cancel_appointment(appointment_id, cancel_time=None, db_path=None):
    """
    Cancels an active appointment and calculates refund.
    """
    if cancel_time is None:
        cancel_time = datetime.now()

    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, doctor_id, patient_id, slot_time, fee, status "
        "FROM appointments WHERE id = ?",
        (appointment_id,)
    )
    appointment = cursor.fetchone()

    if not appointment:
        conn.close()
        return {
            "success": False,
            "error": "Appointment not found.",
            "status_code": 404
        }

    if appointment["status"] == "CANCELLED":
        conn.close()
        return {
            "success": False,
            "error": "Appointment is already cancelled.",
            "status_code": 400
        }

    slot_time = parse_datetime(appointment["slot_time"])
    fee = appointment["fee"]
    pct, refund_amount = calculate_refund(fee, slot_time, cancel_time)

    cursor.execute(
        """
        UPDATE appointments
        SET status = 'CANCELLED',
            refund_percentage = ?,
            refund_amount = ?
        WHERE id = ?
        """,
        (pct, refund_amount, appointment_id)
    )
    conn.commit()
    conn.close()

    return {
        "success": True,
        "appointment_id": appointment_id,
        "status": "CANCELLED",
        "fee": fee,
        "refund_percentage": pct,
        "refund_amount": refund_amount,
        "status_code": 200
    }
