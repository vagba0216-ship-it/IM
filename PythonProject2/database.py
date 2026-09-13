import os
import mysql.connector
from mysql.connector import pooling
from dotenv import load_dotenv

load_dotenv()


class DatabaseManager:
    def __init__(self):
        self.host = os.getenv("DB_HOST", "localhost")
        self.user = os.getenv("DB_USER", "root")
        self.password = os.getenv("DB_PASSWORD", "")
        self.database = os.getenv("DB_NAME", "test")
        self.pool = None
        self.init_database()

    def init_database(self):
        try:
            conn = mysql.connector.connect(host=self.host, user=self.user, password=self.password)
            cursor = conn.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {self.database}")
            cursor.close()
            conn.close()

            self.pool = mysql.connector.pooling.MySQLConnectionPool(
                pool_name="erp_pool",
                pool_size=5,
                pool_reset_session=True,
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database
            )
            self._create_tables()
        except mysql.connector.Error as err:
            print(f"Database Security Error: {err}")

    def get_connection(self):
        if self.pool is None:
            self.init_database()
            if self.pool is None:
                return None
        try:
            return self.pool.get_connection()
        except mysql.connector.Error as err:
            print(f"Pool Connection Error: {err}")
            return None

    def _create_tables(self):
        conn = self.get_connection()
        if not conn:
            return
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                item_id INT AUTO_INCREMENT PRIMARY KEY,
                particulars VARCHAR(255) NOT NULL,
                brand VARCHAR(100) DEFAULT '',
                description VARCHAR(255) NOT NULL,
                unit VARCHAR(50) NOT NULL DEFAULT 'pcs',
                qty INT NOT NULL DEFAULT 0,
                unit_cost DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                image_path TEXT DEFAULT NULL,
                INDEX idx_particulars (particulars),
                INDEX idx_search (description, brand)
            ) ENGINE=InnoDB
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS presets (
                preset_id INT AUTO_INCREMENT PRIMARY KEY,
                category VARCHAR(50) NOT NULL,
                value VARCHAR(255) NOT NULL UNIQUE
            ) ENGINE=InnoDB
        """)

        default_presets = [
            ('unit', 'pcs'), ('unit', 'set'), ('unit', 'box'), ('unit', 'ltr'), ('unit', 'can'),
            ('particulars', 'Oil filter'), ('particulars', 'Fuel filter'), ('particulars', 'Brake pad'), ('particulars', 'Spark plug'),
            ('brand', 'Vic'), ('brand', 'Baldwin'), ('brand', 'Bosch'), ('brand', 'NGK')
        ]
        cursor.executemany("INSERT IGNORE INTO presets (category, value) VALUES (%s, %s)", default_presets)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                sale_id INT AUTO_INCREMENT PRIMARY KEY,
                customer_name VARCHAR(255) NOT NULL,
                vatable_sales DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                vat_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
                total_amount DECIMAL(10,2) NOT NULL,
                sale_date DATETIME NOT NULL,
                INDEX idx_sale_date (sale_date)
            ) ENGINE=InnoDB
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sale_items (
                sale_item_id INT AUTO_INCREMENT PRIMARY KEY,
                sale_id INT,
                item_id INT,
                qty_sold INT,
                unit_cost DECIMAL(10,2),
                subtotal DECIMAL(10,2),
                FOREIGN KEY (sale_id) REFERENCES sales (sale_id) ON DELETE CASCADE,
                FOREIGN KEY (item_id) REFERENCES inventory (item_id) ON DELETE RESTRICT
            ) ENGINE=InnoDB
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_estimates (
                estimate_id INT AUTO_INCREMENT PRIMARY KEY,
                customer_name VARCHAR(255) NOT NULL,
                vehicle_details VARCHAR(255),
                parts_cost DECIMAL(10,2) NOT NULL,
                materials_cost DECIMAL(10,2) NOT NULL,
                labor_cost DECIMAL(10,2) NOT NULL,
                total_estimate DECIMAL(10,2) NOT NULL,
                estimate_date DATETIME NOT NULL
            ) ENGINE=InnoDB
        """)

        conn.commit()
        cursor.close()
        conn.close()