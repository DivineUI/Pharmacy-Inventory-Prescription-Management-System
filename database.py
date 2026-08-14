"""
database.py

Owns the shared MariaDB connection pool, schema definitions, seed data, 
views, and triggers for the Pharmacy Inventory & Prescription Management System (PIPMS).
"""

import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text

# -----------------------------------------------------------------------------
# 1. SHARED CONNECTION ENGINE
# -----------------------------------------------------------------------------
@st.cache_resource
def get_engine():
    """Returns a single, shared connection engine connected to Railway MariaDB."""
    db = st.secrets["mysql"]
    
    # Cast port explicitly to int (Railway public ports are usually 5 digits, e.g. 14283)
    port = int(db.get("port", 3306))
    
    connection_url = (
        f"mysql+pymysql://{db['username']}:{db['password']}"
        f"@{db['host']}:{port}/{db['database']}"
    )
    
    return create_engine(
        connection_url, 
        pool_recycle=3600, 
        pool_pre_ping=True,
        connect_args={
            "connect_timeout": 10,
            "ssl": {"ssl_mode": "PREFERRED"}
        }
    )

engine = get_engine()

# -----------------------------------------------------------------------------
# 2. QUERY & EXECUTE HELPER FUNCTIONS
# -----------------------------------------------------------------------------
def query(sql: str, params: dict = None):
    """Run a SELECT query and return a list of plain dicts."""
    with engine.connect() as conn:
        result = conn.execute(text(sql), params or {})
        return [dict(row._mapping) for row in result.fetchall()]

def query_one(sql: str, params: dict = None):
    """Run a SELECT query and return a single row dict, or None."""
    rows = query(sql, params)
    return rows[0] if rows else None

def execute(sql: str, params: dict = None):
    """Run an INSERT/UPDATE/DELETE statement inside a transaction."""
    with engine.begin() as conn:
        result = conn.execute(text(sql), params or {})
        return result.lastrowid

def get_dataframe(sql: str, params: dict = None):
    """Utility to load query results straight into a Pandas DataFrame."""
    with engine.connect() as conn:
        return pd.read_sql(text(sql), con=conn, params=params)

# -----------------------------------------------------------------------------
# 3. MARIADB COMPATIBLE SCHEMA & STATEMENTS (FOR INITIAL SEEDING)
# -----------------------------------------------------------------------------
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS CUSTOMER (
  CustomerID INT AUTO_INCREMENT PRIMARY KEY,
  FirstName VARCHAR(50) NOT NULL,
  LastName VARCHAR(50) NOT NULL,
  ContactNumber VARCHAR(20) NOT NULL,
  Address VARCHAR(100),
  DateOfBirth DATE
);

CREATE TABLE IF NOT EXISTS PHARMACIST (
  PharmacistID INT AUTO_INCREMENT PRIMARY KEY,
  Name VARCHAR(50) NOT NULL,
  ContactNumber VARCHAR(20) NOT NULL,
  Email VARCHAR(100) UNIQUE,
  Position VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS STAFF (
  StaffID INT AUTO_INCREMENT PRIMARY KEY,
  Username VARCHAR(50) UNIQUE NOT NULL,
  PasswordHash VARCHAR(255) NOT NULL,
  FullName VARCHAR(100) NOT NULL,
  Role ENUM('Admin', 'Pharmacist', 'Cashier') NOT NULL,
  IsActive BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS SUPPLIER (
  SupplierID INT AUTO_INCREMENT PRIMARY KEY,
  SupplierName VARCHAR(100) NOT NULL,
  ContactNumber VARCHAR(20) NOT NULL,
  Address VARCHAR(100),
  Email VARCHAR(100) UNIQUE
);

CREATE TABLE IF NOT EXISTS MEDICINE (
  MedicineID INT AUTO_INCREMENT PRIMARY KEY,
  MedicineName VARCHAR(100) NOT NULL,
  Category VARCHAR(50),
  Dosage VARCHAR(50),
  UnitPrice DECIMAL(10,2) NOT NULL CHECK (UnitPrice >= 0),
  StockQuantity INT NOT NULL DEFAULT 0 CHECK (StockQuantity >= 0),
  ExpiryDate DATE NOT NULL,
  SupplierID INT,
  FOREIGN KEY (SupplierID) REFERENCES SUPPLIER(SupplierID)
    ON UPDATE CASCADE ON DELETE SET NULL,
  INDEX idx_medicine_name (MedicineName),
  INDEX idx_medicine_expiry (ExpiryDate)
);

CREATE TABLE IF NOT EXISTS PRESCRIPTION (
  PrescriptionID INT AUTO_INCREMENT PRIMARY KEY,
  PrescriptionDate DATE NOT NULL,
  DosageInstructions VARCHAR(255),
  Duration VARCHAR(50),
  CustomerID INT NOT NULL,
  PharmacistID INT NOT NULL,
  FOREIGN KEY (CustomerID) REFERENCES CUSTOMER(CustomerID)
    ON UPDATE CASCADE ON DELETE RESTRICT,
  FOREIGN KEY (PharmacistID) REFERENCES PHARMACIST(PharmacistID)
    ON UPDATE CASCADE ON DELETE RESTRICT,
  INDEX idx_prescription_date (PrescriptionDate)
);

CREATE TABLE IF NOT EXISTS PRESCRIPTION_ITEM (
  PrescriptionItemID INT AUTO_INCREMENT PRIMARY KEY,
  PrescriptionID INT NOT NULL,
  MedicineID INT NOT NULL,
  Quantity INT NOT NULL CHECK (Quantity > 0),
  Dosage VARCHAR(50),
  Frequency VARCHAR(50),
  Duration VARCHAR(50),
  FOREIGN KEY (PrescriptionID) REFERENCES PRESCRIPTION(PrescriptionID)
    ON UPDATE CASCADE ON DELETE CASCADE,
  FOREIGN KEY (MedicineID) REFERENCES MEDICINE(MedicineID)
    ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS PURCHASE (
  PurchaseID INT AUTO_INCREMENT PRIMARY KEY,
  PurchaseDate DATE NOT NULL,
  SupplierID INT NOT NULL,
  FOREIGN KEY (SupplierID) REFERENCES SUPPLIER(SupplierID)
    ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS PURCHASE_ITEM (
  PurchaseItemID INT AUTO_INCREMENT PRIMARY KEY,
  PurchaseID INT NOT NULL,
  MedicineID INT NOT NULL,
  QuantityPurchased INT NOT NULL CHECK (QuantityPurchased > 0),
  UnitCost DECIMAL(10,2) NOT NULL CHECK (UnitCost >= 0),
  FOREIGN KEY (PurchaseID) REFERENCES PURCHASE(PurchaseID)
    ON UPDATE CASCADE ON DELETE CASCADE,
  FOREIGN KEY (MedicineID) REFERENCES MEDICINE(MedicineID)
    ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS AUDIT_LOG (
  AuditID INT AUTO_INCREMENT PRIMARY KEY,
  TableName VARCHAR(50),
  Action VARCHAR(20),
  RecordID INT,
  Details VARCHAR(255),
  ChangedAt DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

VIEWS_SQL = """
CREATE OR REPLACE VIEW View_ExpiringMedicines AS
SELECT MedicineID, MedicineName, Category, ExpiryDate, StockQuantity,
       DATEDIFF(ExpiryDate, CURDATE()) AS DaysToExpiry
FROM MEDICINE 
WHERE ExpiryDate < DATE_ADD(CURDATE(), INTERVAL 60 DAY)
ORDER BY ExpiryDate;

CREATE OR REPLACE VIEW View_LowStock AS
SELECT MedicineID, MedicineName, Category, StockQuantity
FROM MEDICINE 
WHERE StockQuantity < 10
ORDER BY StockQuantity;

CREATE OR REPLACE VIEW View_SalesSummary AS
SELECT p.PrescriptionID, p.PrescriptionDate, SUM(pi.Quantity) AS TotalItems,
       ROUND(SUM(pi.Quantity * m.UnitPrice), 2) AS TotalValue
FROM PRESCRIPTION_ITEM pi
JOIN PRESCRIPTION p ON pi.PrescriptionID = p.PrescriptionID
JOIN MEDICINE m ON pi.MedicineID = m.MedicineID
GROUP BY p.PrescriptionID, p.PrescriptionDate
ORDER BY p.PrescriptionDate DESC;

CREATE OR REPLACE VIEW View_SupplierPurchaseHistory AS
SELECT s.SupplierID, s.SupplierName, m.MedicineName, pi.QuantityPurchased, pi.UnitCost, p.PurchaseDate
FROM SUPPLIER s
JOIN PURCHASE p ON s.SupplierID = p.SupplierID
JOIN PURCHASE_ITEM pi ON p.PurchaseID = pi.PurchaseID
JOIN MEDICINE m ON pi.MedicineID = m.MedicineID
ORDER BY p.PurchaseDate DESC;

CREATE OR REPLACE VIEW View_PrescriptionHistory AS
SELECT c.CustomerID, c.FirstName, c.LastName, p.PrescriptionID, p.PrescriptionDate,
       p.DosageInstructions, p.Duration, ph.Name AS PharmacistName
FROM CUSTOMER c
JOIN PRESCRIPTION p ON c.CustomerID = p.CustomerID
JOIN PHARMACIST ph ON p.PharmacistID = ph.PharmacistID
ORDER BY p.PrescriptionDate DESC;
"""
