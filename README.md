# Setup Guide

## 1. Clone the Repository
git clone (https://github.com/rajlaxmi-21/BE-project.git)
cd FinalYearProject

---

## 2. Backend Setup (FastAPI)

cd backend  
python -m venv venv  
venv\Scripts\activate  

pip install -r requirements.txt  

Run backend:
uvicorn main:app --reload  

Backend URL: http://127.0.0.1:8000  
Swagger Docs: http://127.0.0.1:8000/docs  

---

## 3. Frontend Setup (Streamlit)

cd frontend  
python -m venv venv  
venv\Scripts\activate  

pip install -r requirements.txt  

Run frontend:
streamlit run app.py  

Frontend URL: http://localhost:8501  

---

## 4. Database Setup (PostgreSQL + PostGIS)

Open pgAdmin and create a database named:
FinalYearProject  

Run the following queries:

CREATE EXTENSION postgis;

CREATE TABLE permits (
    permit_id VARCHAR(50) PRIMARY KEY,
    geometry GEOMETRY(POLYGON, 4326),
    issue_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    permit_type VARCHAR(100),
    authority VARCHAR(100),
    project_name VARCHAR(255),
    status VARCHAR(50)
);

CREATE TABLE detected_deforestation (
    detection_id SERIAL PRIMARY KEY,
    geometry GEOMETRY(POLYGON, 4326),
    centroid GEOMETRY(POINT, 4326)
        GENERATED ALWAYS AS (ST_Centroid(geometry)) STORED,
    detected_at DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

---

## 5. AWS Setup (Image Fetching Module)

- Get the .pem key file from your team
- Save it on your system
- Update path in:

backend/services/image_fetch.py

Example:
KEY = "C:/Users/YourName/Downloads/s2dr3-keypair.pem"

---

## 6. Run the Full System

Step 1: Start Backend  
cd backend  
venv\Scripts\activate  
uvicorn main:app --reload  

Step 2: Start Frontend  
cd frontend  
venv\Scripts\activate  
streamlit run app.py  

Step 3: Open browser  
http://localhost:8501  

Step 4: Select area and click "Analyze"  

---

## Notes

- Do not upload .pem file to GitHub  
- Do not upload .tif files  
- Make sure AWS instance is running before analysis  
- Ensure database connection is configured correctly  

---

## Team Usage

Install dependencies:
pip install -r requirements.txt  

Pull latest code:
git pull origin main  
