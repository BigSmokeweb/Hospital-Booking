# AarogyaCare - Hospital Appointment Booking System

An enterprise-grade Hospital Appointment Booking and Schedule Management System built with **Python Flask**, **SQLite**, **pytest**, and **flake8**. 

Designed with a sleek **Black, Grey & White monochrome gradient UI**, formatted in **Indian Rupees (₹ INR)**, and seeded with **50 Indian Doctors and Patients**.

---

## Features

- **Doctor Directory & Search**: Real-time search across 50 Indian doctors by name or medical specialization (Cardiology, Dermatology, Neurology, Pediatrics, Orthopedics, etc.).
- **Double Booking Prevention**: Ensures the same doctor cannot be booked twice for an identical time slot (`HTTP 409 Conflict`). Re-opening the slot automatically occurs if an appointment is cancelled.
- **Automated ₹ Refund Policy**:
  - **100% refund** credited if cancelled **more than 24 hours ahead**.
  - **50% refund** credited if cancelled **within 24 hours**.
  - **0% refund** after the appointment slot time.
- **Past Date Validation**: Appointments in the past are automatically rejected (`HTTP 400 Bad Request`).
- **Patient Active Limit**: A patient cannot hold more than **2 active appointments** simultaneously (tracked via phone number).
- **Manual Patient Intake**: Form captures Patient Name, Phone Number, Age, and Address/City.
- **Calendar & Time Picker**: Interactive dark-themed Flatpickr calendar dropdown with 24-hour time selection at 15-minute intervals.
- **Testing & Code Quality**: 100% pass rate across **17 pytest tests** and **0 flake8 PEP 8 warnings**.

---

## Tech Stack

- **Backend**: Python 3.12, Flask
- **Database**: SQLite3
- **Testing**: `pytest`
- **Code Linter**: `flake8`
- **Frontend**: HTML5, Vanilla CSS (Monochrome Gradient Theme), Vanilla JavaScript, Flatpickr

---

## Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/BigSmokeweb/Hospital-Booking.git
cd Hospital-Booking
```

### 2. Install Dependencies
Make sure you have Python 3.10+ installed. Install the required Python packages:
```bash
pip install flask pytest flake8
```

---

## How to Run the Project

### Start the Flask Web Application
Run the main server file:
```bash
python app.py
```

Once started, open your web browser and navigate to:
```
http://127.0.0.1:5000
```

---

## How to Run Tests & Code Linter

### Run the Pytest Test Suite
To execute all 17 automated unit and integration tests:
```bash
python -m pytest -v
```

### Run Flake8 Code Quality Linter
To verify code formatting and PEP 8 compliance:
```bash
python -m flake8 .
```

---

## Project Structure

```
Hospital-Booking/
├── app.py                # Flask application routes and REST API endpoints
├── database.py           # SQLite schema initialization and seeding
├── services.py           # Core business logic (bookings, refunds, validations, limits)
├── initial_data.json     # 50 Indian doctors and patients seed dataset
├── test_hospital.py      # Automated pytest suite (17 comprehensive test cases)
├── templates/
│   └── index.html        # Monochrome single-page dashboard UI
├── PROJECT_REPORT.md     # Detailed architecture and code report
└── README.md             # Project overview and run instructions
```

---

## API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Main hospital appointment booking dashboard |
| `GET` | `/api/doctors?q=<search>` | Search doctors by name or specialization |
| `GET` | `/api/patients` | Retrieve registered patient records |
| `GET` | `/api/appointments` | List all booked appointments |
| `POST` | `/api/appointments` | Book a new appointment (validates past slots, limits & double bookings) |
| `POST` | `/api/appointments/<id>/cancel` | Cancel an appointment and calculate refund in ₹ |

---

## License
MIT License
Built By Milind Sahu
