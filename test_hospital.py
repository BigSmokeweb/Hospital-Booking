import pytest
from datetime import datetime, timedelta
from app import create_app
from database import init_db
from services import (
    search_doctors,
    book_appointment,
    cancel_appointment,
    calculate_refund
)


@pytest.fixture
def temp_db(tmp_path):
    """Provides a fresh isolated database path for each test."""
    db_file = str(tmp_path / "test_hospital.db")
    init_db(db_file)
    return db_file


@pytest.fixture
def client(temp_db):
    """Flask test client configured with isolated database."""
    app = create_app({"TESTING": True, "DATABASE_PATH": temp_db})
    with app.test_client() as client:
        yield client


# ============================================================================
# 1. SEARCH TESTS
# Doctors can be found by name or specialization
# ============================================================================

def test_search_doctors_by_specialization(temp_db):
    results = search_doctors(query="Cardiology", db_path=temp_db)
    assert len(results) >= 2
    specializations = {d["specialization"] for d in results}
    assert specializations == {"Cardiology"}


def test_search_doctors_by_name(temp_db):
    results = search_doctors(query="Rajesh Sharma", db_path=temp_db)
    assert len(results) == 1
    assert results[0]["name"] == "Dr. Rajesh Sharma"


def test_search_doctors_case_insensitive_and_partial(temp_db):
    results = search_doctors(query="derma", db_path=temp_db)
    assert len(results) >= 1
    for doc in results:
        assert "Dermatology" in doc["specialization"]


def test_search_doctors_empty_query_returns_all(temp_db):
    all_doctors = search_doctors(query="", db_path=temp_db)
    assert len(all_doctors) == 50


def test_search_doctors_api_endpoint(client):
    response = client.get("/api/doctors?q=Pediatrics")
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) >= 1
    for doc in data:
        assert doc["specialization"] == "Pediatrics"


# ============================================================================
# 2. VALIDATION TESTS
# Appointments in the past are rejected
# ============================================================================

def test_book_appointment_in_past_rejected(temp_db):
    past_time = datetime(2020, 1, 1, 10, 0, 0)
    current_time = datetime(2020, 1, 1, 12, 0, 0)

    res = book_appointment(
        doctor_id=1,
        patient_id=1,
        slot_time_str=past_time.strftime("%Y-%m-%d %H:%M:%S"),
        current_time=current_time,
        db_path=temp_db
    )
    assert res["success"] is False
    assert res["status_code"] == 400
    assert "past" in res["error"].lower()


def test_book_appointment_invalid_date_format(temp_db):
    res = book_appointment(
        doctor_id=1,
        patient_id=1,
        slot_time_str="invalid-date-string",
        db_path=temp_db
    )
    assert res["success"] is False
    assert res["status_code"] == 400


# ============================================================================
# 3. DOUBLE BOOKING TESTS
# The same doctor and time slot cannot be booked twice
# ============================================================================

def test_prevent_double_booking_same_doctor_and_slot(temp_db):
    current_time = datetime(2026, 11, 1, 9, 0, 0)
    slot_time = "2026-11-02 10:00:00"

    # First booking for doctor 1 (patient 1)
    first_res = book_appointment(
        doctor_id=1,
        patient_id=1,
        slot_time_str=slot_time,
        current_time=current_time,
        db_path=temp_db
    )
    assert first_res["success"] is True
    assert first_res["status_code"] == 201

    # Second booking for SAME doctor & SAME slot (different patient 2)
    second_res = book_appointment(
        doctor_id=1,
        patient_id=2,
        slot_time_str=slot_time,
        current_time=current_time,
        db_path=temp_db
    )
    assert second_res["success"] is False
    assert second_res["status_code"] == 409
    assert "Double booking error" in second_res["error"]


def test_different_doctors_same_slot_allowed(temp_db):
    current_time = datetime(2026, 11, 1, 9, 0, 0)
    slot_time = "2026-11-02 14:00:00"

    res1 = book_appointment(
        doctor_id=1,
        patient_id=1,
        slot_time_str=slot_time,
        current_time=current_time,
        db_path=temp_db
    )
    res2 = book_appointment(
        doctor_id=2,
        patient_id=2,
        slot_time_str=slot_time,
        current_time=current_time,
        db_path=temp_db
    )
    assert res1["success"] is True
    assert res2["success"] is True


def test_same_slot_bookable_after_cancellation(temp_db):
    """If an appointment is cancelled, the doctor's slot becomes free."""
    current_time = datetime(2026, 11, 1, 9, 0, 0)
    slot_time = "2026-11-03 11:00:00"

    # Book slot
    b1 = book_appointment(
        doctor_id=1,
        patient_id=1,
        slot_time_str=slot_time,
        current_time=current_time,
        db_path=temp_db
    )
    assert b1["success"] is True

    # Cancel it
    cancel_res = cancel_appointment(
        b1["appointment_id"],
        cancel_time=current_time,
        db_path=temp_db
    )
    assert cancel_res["success"] is True

    # Re-book the same slot by another patient
    b2 = book_appointment(
        doctor_id=1,
        patient_id=2,
        slot_time_str=slot_time,
        current_time=current_time,
        db_path=temp_db
    )
    assert b2["success"] is True


# ============================================================================
# 4. LIMIT TESTS
# A patient cannot hold more than 2 active appointments
# ============================================================================

def test_patient_active_appointment_limit(temp_db):
    current_time = datetime(2026, 11, 1, 8, 0, 0)
    patient_id = 1

    # Book 1st appointment
    res1 = book_appointment(
        doctor_id=1,
        patient_id=patient_id,
        slot_time_str="2026-11-02 10:00:00",
        current_time=current_time,
        db_path=temp_db
    )
    assert res1["success"] is True

    # Book 2nd appointment
    res2 = book_appointment(
        doctor_id=2,
        patient_id=patient_id,
        slot_time_str="2026-11-02 11:00:00",
        current_time=current_time,
        db_path=temp_db
    )
    assert res2["success"] is True

    # Attempt to book 3rd active appointment -> must be rejected
    res3 = book_appointment(
        doctor_id=3,
        patient_id=patient_id,
        slot_time_str="2026-11-02 12:00:00",
        current_time=current_time,
        db_path=temp_db
    )
    assert res3["success"] is False
    assert res3["status_code"] == 400
    assert "limit reached" in res3["error"].lower()


def test_patient_can_book_after_cancelling_one(temp_db):
    current_time = datetime(2026, 11, 1, 8, 0, 0)
    patient_id = 1

    res1 = book_appointment(
        doctor_id=1,
        patient_id=patient_id,
        slot_time_str="2026-11-02 10:00:00",
        current_time=current_time,
        db_path=temp_db
    )
    res2 = book_appointment(
        doctor_id=2,
        patient_id=patient_id,
        slot_time_str="2026-11-02 11:00:00",
        current_time=current_time,
        db_path=temp_db
    )
    assert res1["success"] is True and res2["success"] is True

    # Cancel the 1st
    cancel_appointment(res1["appointment_id"], cancel_time=current_time,
                       db_path=temp_db)

    # Now booking a new 2nd active appointment should succeed
    res3 = book_appointment(
        doctor_id=3,
        patient_id=patient_id,
        slot_time_str="2026-11-02 12:00:00",
        current_time=current_time,
        db_path=temp_db
    )
    assert res3["success"] is True


# ============================================================================
# 5. CANCELLATION & REFUND TESTS
# 100% refund if >24 hours ahead, 50% otherwise (within 24h)
# ============================================================================

def test_refund_more_than_24_hours_ahead():
    slot_time = datetime(2026, 11, 10, 10, 0, 0)
    # Cancelled 30 hours ahead
    cancel_time = slot_time - timedelta(hours=30)
    fee = 150.0

    pct, refund_amount = calculate_refund(fee, slot_time, cancel_time)
    assert pct == 100.0
    assert refund_amount == 150.0


def test_refund_within_24_hours_ahead():
    slot_time = datetime(2026, 11, 10, 10, 0, 0)
    # Cancelled 5 hours ahead
    cancel_time = slot_time - timedelta(hours=5)
    fee = 150.0

    pct, refund_amount = calculate_refund(fee, slot_time, cancel_time)
    assert pct == 50.0
    assert refund_amount == 75.0


def test_refund_exactly_24_hours_ahead():
    slot_time = datetime(2026, 11, 10, 10, 0, 0)
    # Exactly 24 hours ahead falls under <= 24 hours (50%)
    cancel_time = slot_time - timedelta(hours=24)
    fee = 100.0

    pct, refund_amount = calculate_refund(fee, slot_time, cancel_time)
    assert pct == 50.0
    assert refund_amount == 50.0


def test_cancellation_flow_end_to_end(temp_db):
    booking_time = datetime(2026, 11, 1, 9, 0, 0)
    slot_time = "2026-11-05 10:00:00"

    book_res = book_appointment(
        doctor_id=1,
        patient_id=1,
        slot_time_str=slot_time,
        current_time=booking_time,
        db_path=temp_db
    )
    appt_id = book_res["appointment_id"]
    fee = book_res["fee"]

    # Cancel > 24 hours ahead (e.g. on 2026-11-01)
    cancel_res = cancel_appointment(
        appt_id,
        cancel_time=booking_time,
        db_path=temp_db
    )
    assert cancel_res["success"] is True
    assert cancel_res["refund_percentage"] == 100.0
    assert cancel_res["refund_amount"] == fee

    # Trying to cancel again should fail
    duplicate_cancel = cancel_appointment(appt_id, db_path=temp_db)
    assert duplicate_cancel["success"] is False
    assert duplicate_cancel["status_code"] == 400


# ============================================================================
# 6. REST API INTEGRATION TESTS
# ============================================================================

def test_api_booking_and_cancellation(client):
    # Book via API
    book_payload = {
        "doctor_id": 1,
        "patient_id": 1,
        "slot_time": "2028-01-10 15:00:00"
    }
    res = client.post("/api/appointments", json=book_payload)
    assert res.status_code == 201
    data = res.get_json()
    assert data["success"] is True
    appt_id = data["appointment_id"]

    # List appointments
    list_res = client.get("/api/appointments")
    assert list_res.status_code == 200
    appts = list_res.get_json()
    assert any(a["id"] == appt_id for a in appts)

    # Cancel via API
    cancel_res = client.post(f"/api/appointments/{appt_id}/cancel")
    assert cancel_res.status_code == 200
    cancel_data = cancel_res.get_json()
    assert cancel_data["success"] is True
    assert cancel_data["status"] == "CANCELLED"
