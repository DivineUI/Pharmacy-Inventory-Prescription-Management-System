"""
database.py — SQLite Local Connection, Schema, and Auto-Seeding Setup
"""

import sqlite3
import pandas as pd
import os

DB_FILE = "pharmacy.db"


def get_connection():
    """Returns a SQLite connection with dict-like row access enabled."""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables and views automatically if they do not exist."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Create Tables
        cursor.executescript("""
        CREATE TABLE IF NOT EXISTS CUSTOMER (
            CustomerID INTEGER PRIMARY KEY AUTOINCREMENT,
            FirstName TEXT NOT NULL,
            LastName TEXT NOT NULL,
            ContactNumber TEXT NOT NULL,
            Address TEXT,
            DateOfBirth TEXT
        );

        CREATE TABLE IF NOT EXISTS PHARMACIST (
            PharmacistID INTEGER PRIMARY KEY AUTOINCREMENT,
            Name TEXT NOT NULL,
            ContactNumber TEXT NOT NULL,
            Email TEXT UNIQUE,
            Position TEXT
        );

        CREATE TABLE IF NOT EXISTS SUPPLIER (
            SupplierID INTEGER PRIMARY KEY AUTOINCREMENT,
            SupplierName TEXT NOT NULL,
            ContactNumber TEXT NOT NULL,
            Address TEXT,
            Email TEXT UNIQUE
        );

        CREATE TABLE IF NOT EXISTS MEDICINE (
            MedicineID INTEGER PRIMARY KEY AUTOINCREMENT,
            MedicineName TEXT NOT NULL,
            Category TEXT,
            Dosage TEXT,
            UnitPrice REAL NOT NULL CHECK (UnitPrice >= 0),
            StockQuantity INTEGER NOT NULL DEFAULT 0 CHECK (StockQuantity >= 0),
            ExpiryDate TEXT NOT NULL,
            SupplierID INTEGER,
            FOREIGN KEY (SupplierID) REFERENCES SUPPLIER(SupplierID) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS PRESCRIPTION (
            PrescriptionID INTEGER PRIMARY KEY AUTOINCREMENT,
            PrescriptionDate TEXT NOT NULL,
            DosageInstructions TEXT,
            Duration TEXT,
            CustomerID INTEGER NOT NULL,
            PharmacistID INTEGER NOT NULL,
            FOREIGN KEY (CustomerID) REFERENCES CUSTOMER(CustomerID),
            FOREIGN KEY (PharmacistID) REFERENCES PHARMACIST(PharmacistID)
        );

        CREATE TABLE IF NOT EXISTS PRESCRIPTION_ITEM (
            PrescriptionItemID INTEGER PRIMARY KEY AUTOINCREMENT,
            PrescriptionID INTEGER NOT NULL,
            MedicineID INTEGER NOT NULL,
            Quantity INTEGER NOT NULL CHECK (Quantity > 0),
            Dosage TEXT,
            Frequency TEXT,
            Duration TEXT,
            FOREIGN KEY (PrescriptionID) REFERENCES PRESCRIPTION(PrescriptionID) ON DELETE CASCADE,
            FOREIGN KEY (MedicineID) REFERENCES MEDICINE(MedicineID)
        );

        CREATE TABLE IF NOT EXISTS PURCHASE (
            PurchaseID INTEGER PRIMARY KEY AUTOINCREMENT,
            PurchaseDate TEXT NOT NULL,
            SupplierID INTEGER NOT NULL,
            FOREIGN KEY (SupplierID) REFERENCES SUPPLIER(SupplierID)
        );

        CREATE TABLE IF NOT EXISTS PURCHASE_ITEM (
            PurchaseItemID INTEGER PRIMARY KEY AUTOINCREMENT,
            PurchaseID INTEGER NOT NULL,
            MedicineID INTEGER NOT NULL,
            QuantityPurchased INTEGER NOT NULL CHECK (QuantityPurchased > 0),
            UnitCost REAL NOT NULL CHECK (UnitCost >= 0),
            FOREIGN KEY (PurchaseID) REFERENCES PURCHASE(PurchaseID) ON DELETE CASCADE,
            FOREIGN KEY (MedicineID) REFERENCES MEDICINE(MedicineID)
        );
        """)

        # 2. Create Views
        cursor.executescript("""
        CREATE VIEW IF NOT EXISTS View_ExpiringMedicines AS
        SELECT MedicineID, MedicineName, Category, ExpiryDate, StockQuantity,
               CAST((julianday(ExpiryDate) - julianday('now')) AS INTEGER) AS DaysToExpiry
        FROM MEDICINE 
        WHERE ExpiryDate < date('now', '+60 days')
        ORDER BY ExpiryDate;

        CREATE VIEW IF NOT EXISTS View_LowStock AS
        SELECT MedicineID, MedicineName, Category, StockQuantity
        FROM MEDICINE 
        WHERE StockQuantity < 10
        ORDER BY StockQuantity;

        CREATE VIEW IF NOT EXISTS View_SalesSummary AS
        SELECT p.PrescriptionID, p.PrescriptionDate, SUM(pi.Quantity) AS TotalItems,
               ROUND(SUM(pi.Quantity * m.UnitPrice), 2) AS TotalValue
        FROM PRESCRIPTION_ITEM pi
        JOIN PRESCRIPTION p ON pi.PrescriptionID = p.PrescriptionID
        JOIN MEDICINE m ON pi.MedicineID = m.MedicineID
        GROUP BY p.PrescriptionID, p.PrescriptionDate
        ORDER BY p.PrescriptionDate DESC;
        """)
        
        conn.commit()


# Run DB setup on file import
init_db()


def query(sql: str, params: tuple = ()):
    """Run a SELECT query and return a list of plain dicts."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]


def query_one(sql: str, params: tuple = ()):
    """Run a SELECT query and return a single row dict, or None."""
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params: tuple = ()):
    """Run an INSERT/UPDATE/DELETE statement inside a transaction."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        return cursor.lastrowid


def get_dataframe(sql: str, params: tuple = ()):
    """Utility to load query results straight into a Pandas DataFrame."""
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=params)
