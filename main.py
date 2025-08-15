import streamlit as st
import pandas as pd
import mysql.connector
import plotly.express as px
from datetime import datetime
from mysql.connector import Error
import re
import numpy as np

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '1234567890',
    'database': 'food_wastage_management'
}

def convert_date_format(date_str):
    try:
        # Handle various date formats including single-digit months/days
        if isinstance(date_str, str):
            # Try to parse with different formats
            for fmt in ['%m/%d/%Y', '%m/%d/%y', '%-m/%-d/%Y', '%-m/%-d/%y']:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.strftime('%Y-%m-%d')
                except ValueError:
                    continue

            # Try to extract components with regex as fallback
            match = re.match(r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})', date_str)
            if match:
                month, day, year = match.groups()
                month = month.zfill(2)
                day = day.zfill(2)
                if len(year) == 2:
                    year = f"20{year}" if int(year) < 50 else f"19{year}"
                return f"{year}-{month}-{day}"

        # If all parsing fails, return today's date as fallback
        return datetime.now().strftime('%Y-%m-%d')
    except Exception as e:
        st.error(f"Date conversion error for '{date_str}': {e}")
        return datetime.now().strftime('%Y-%m-%d')

def initialize_database():
    try:
        connection = mysql.connector.connect(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password']
        )
        cursor = connection.cursor()

        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']}")
        cursor.execute(f"USE {DB_CONFIG['database']}")

        # Create tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS providers (
                provider_id INT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                type VARCHAR(50) NOT NULL,
                address VARCHAR(200) NOT NULL,
                city VARCHAR(50) NOT NULL,
                contact VARCHAR(50) NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS receivers (
                receiver_id INT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                type VARCHAR(50) NOT NULL,
                city VARCHAR(50) NOT NULL,
                contact VARCHAR(50) NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS food_listings (
                food_id INT PRIMARY KEY,
                food_name VARCHAR(100) NOT NULL,
                quantity INT NOT NULL,
                expiry_date DATE NOT NULL,
                provider_id INT NOT NULL,
                provider_type VARCHAR(50) NOT NULL,
                location VARCHAR(50) NOT NULL,
                food_type VARCHAR(50) NOT NULL,
                meal_type VARCHAR(50) NOT NULL,
                FOREIGN KEY (provider_id) REFERENCES providers(provider_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS claims (
                claim_id INT PRIMARY KEY,
                food_id INT NOT NULL,
                receiver_id INT NOT NULL,
                status VARCHAR(20) NOT NULL,
                timestamp DATETIME NOT NULL,
                FOREIGN KEY (food_id) REFERENCES food_listings(food_id),
                FOREIGN KEY (receiver_id) REFERENCES receivers(receiver_id)
            )
        """)

        connection.commit()

        # Loading data
        for table in ['providers', 'receivers', 'food_listings', 'claims']:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            if cursor.fetchone()[0] == 0:
                load_sample_data(connection)
                break

        cursor.close()
        connection.close()
        return True
    except Error as e:
        st.error(f"Error initializing database: {e}")
        return False

def load_sample_data(connection):
    try:
        cursor = connection.cursor()

        # Load providers data
        providers_df = pd.read_csv('providers_data.csv')
        for _, row in providers_df.iterrows():
            cursor.execute(
                "INSERT INTO providers (provider_id, name, type, address, city, contact) VALUES (%s, %s, %s, %s, %s, %s)",
                (row['Provider_ID'], row['Name'], row['Type'], row['Address'], row['City'], row['Contact'])
            )

        # Load receivers data
        receivers_df = pd.read_csv('receivers_data.csv')
        for _, row in receivers_df.iterrows():
            cursor.execute(
                "INSERT INTO receivers (receiver_id, name, type, city, contact) VALUES (%s, %s, %s, %s, %s)",
                (row['Receiver_ID'], row['Name'], row['Type'], row['City'], row['Contact'])
            )

        # Load food listings data
        food_listings_df = pd.read_csv('food_listings_data.csv')
        for _, row in food_listings_df.iterrows():
            # Convert expiry_date
            expiry_date = convert_date_format(str(row['Expiry_Date']))

            cursor.execute(
                """INSERT INTO food_listings 
                (food_id, food_name, quantity, expiry_date, provider_id, provider_type, location, food_type, meal_type) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (row['Food_ID'], row['Food_Name'], row['Quantity'], expiry_date,
                 row['Provider_ID'], row['Provider_Type'], row['Location'],
                 row['Food_Type'], row['Meal_Type'])
            )

        # Load claims data
        claims_df = pd.read_csv('claims_data.csv')
        for _, row in claims_df.iterrows():
            # Convert timestamp
            timestamp = convert_date_format(str(row['Timestamp'])) + " 00:00:00"

            cursor.execute(
                "INSERT INTO claims (claim_id, food_id, receiver_id, status, timestamp) VALUES (%s, %s, %s, %s, %s)",
                (row['Claim_ID'], row['Food_ID'], row['Receiver_ID'], row['Status'], timestamp)
            )

        connection.commit()
        st.success("Data loaded successfully!")
    except Error as e:
        connection.rollback()
        st.error(f"Error loading data: {e}")
    finally:
        cursor.close()


# Database connection
def create_db_connection():
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        st.error(f"Database connection error: {e}")
        return None


# Execute SQL query
def execute_query(query, params=None, fetch=True):
    connection = create_db_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            if fetch:
                result = cursor.fetchall()
                return result
            else:
                connection.commit()
                return True
        except Error as e:
            st.error(f"Query execution error: {e}")
            return None
        finally:
            cursor.close()
            connection.close()
    return None


# Display dataset with editing capability
def editable_dataframe(table_name, key_columns):
    query = f"SELECT * FROM {table_name}"
    data = execute_query(query)

    if data:
        df = pd.DataFrame(data)
        st.subheader(f"Edit {table_name.replace('_', ' ').title()}")

        # Display current data
        st.write("Current Data:")
        st.dataframe(df)

        # Edit form
        with st.expander(f"Edit {table_name}"):
            edit_option = st.radio("Edit Option", ["Add New", "Update Existing", "Delete"], key=f"edit_{table_name}")

            if edit_option == "Add New":
                with st.form(f"add_{table_name}"):
                    new_data = {}
                    for col in df.columns:
                        if col in key_columns:
                            new_data[col] = st.number_input(f"New {col}", min_value=1)
                        elif df[col].dtype == 'int64':
                            new_data[col] = st.number_input(f"New {col}", min_value=0)
                        elif df[col].dtype == 'object':
                            if col == 'expiry_date' and table_name == 'food_listings':
                                new_data[col] = st.date_input(f"New {col}").strftime('%Y-%m-%d')
                            elif col == 'timestamp' and table_name == 'claims':
                                new_data[col] = st.date_input(f"New {col}").strftime('%Y-%m-%d') + " 00:00:00"
                            else:
                                new_data[col] = st.text_input(f"New {col}")

                    if st.form_submit_button("Add Record"):
                        columns = ', '.join(new_data.keys())
                        placeholders = ', '.join(['%s'] * len(new_data))
                        query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
                        if execute_query(query, tuple(new_data.values()), fetch=False):
                            st.success("Record added successfully!")
                            st.experimental_rerun()

            elif edit_option == "Update Existing":
                with st.form(f"update_{table_name}"):
                    record_id = st.selectbox(f"Select {key_columns[0]} to update", df[key_columns[0]].tolist())
                    selected_record = df[df[key_columns[0]] == record_id].iloc[0]

                    update_data = {}
                    for col in df.columns:
                        if col in key_columns:
                            update_data[col] = record_id
                        elif df[col].dtype == 'int64':
                            update_data[col] = st.number_input(f"New {col}", value=int(selected_record[col]),
                                                               min_value=0)
                        elif df[col].dtype == 'object':
                            if col == 'expiry_date' and table_name == 'food_listings':
                                try:
                                    date_value = datetime.strptime(selected_record[col], '%Y-%m-%d').date()
                                except:
                                    date_value = datetime.now().date()
                                update_data[col] = st.date_input(
                                    f"New {col}",
                                    value=date_value
                                ).strftime('%Y-%m-%d')
                            elif col == 'timestamp' and table_name == 'claims':
                                try:
                                    date_part = selected_record[col].split()[0]
                                    date_value = datetime.strptime(date_part, '%Y-%m-%d').date()
                                except:
                                    date_value = datetime.now().date()
                                update_data[col] = st.date_input(
                                    f"New {col}",
                                    value=date_value
                                ).strftime('%Y-%m-%d') + " 00:00:00"
                            else:
                                update_data[col] = st.text_input(f"New {col}", value=selected_record[col])

                    if st.form_submit_button("Update Record"):
                        set_clause = ', '.join([f"{col} = %s" for col in update_data.keys() if col not in key_columns])
                        where_clause = ' AND '.join([f"{col} = %s" for col in key_columns])
                        values = tuple([v for k, v in update_data.items() if k not in key_columns] +
                                       [v for k, v in update_data.items() if k in key_columns])

                        query = f"UPDATE {table_name} SET {set_clause} WHERE {where_clause}"
                        if execute_query(query, values, fetch=False):
                            st.success("Record updated successfully!")
                            st.experimental_rerun()

            elif edit_option == "Delete":
                with st.form(f"delete_{table_name}"):
                    record_id = st.selectbox(f"Select {key_columns[0]} to delete", df[key_columns[0]].tolist())

                    if st.form_submit_button("Delete Record"):
                        where_clause = ' AND '.join([f"{col} = %s" for col in key_columns])
                        query = f"DELETE FROM {table_name} WHERE {where_clause}"
                        if execute_query(query, (record_id,), fetch=False):
                            st.success("Record deleted successfully!")
                            st.experimental_rerun()

        # Visualizations
        st.subheader(f"{table_name.replace('_', ' ').title()} Visualizations")

        if table_name == 'providers':
            # Providers by city
            providers_by_city = execute_query("SELECT city, COUNT(*) as count FROM providers GROUP BY city")
            fig1 = px.bar(providers_by_city, x='city', y='count', title='Providers by City')
            st.plotly_chart(fig1, use_container_width=True)

            # Providers by type
            providers_by_type = execute_query("SELECT type, COUNT(*) as count FROM providers GROUP BY type")
            fig2 = px.pie(providers_by_type, values='count', names='type', title='Providers by Type')
            st.plotly_chart(fig2, use_container_width=True)

        elif table_name == 'receivers':
            # Receivers by city
            receivers_by_city = execute_query("SELECT city, COUNT(*) as count FROM receivers GROUP BY city")
            fig1 = px.bar(receivers_by_city, x='city', y='count', title='Receivers by City')
            st.plotly_chart(fig1, use_container_width=True)

            # Receivers by type
            receivers_by_type = execute_query("SELECT type, COUNT(*) as count FROM receivers GROUP BY type")
            fig2 = px.pie(receivers_by_type, values='count', names='type', title='Receivers by Type')
            st.plotly_chart(fig2, use_container_width=True)

        elif table_name == 'food_listings':
            # Food by type
            food_by_type = execute_query(
                "SELECT food_type, SUM(quantity) as total FROM food_listings GROUP BY food_type")
            fig1 = px.pie(food_by_type, values='total', names='food_type', title='Food by Type')
            st.plotly_chart(fig1, use_container_width=True)

            # Food by meal type
            food_by_meal = execute_query(
                "SELECT meal_type, SUM(quantity) as total FROM food_listings GROUP BY meal_type")
            fig2 = px.bar(food_by_meal, x='meal_type', y='total', title='Food by Meal Type')
            st.plotly_chart(fig2, use_container_width=True)

        elif table_name == 'claims':
            # Claims by status
            claims_by_status = execute_query("SELECT status, COUNT(*) as count FROM claims GROUP BY status")
            fig1 = px.pie(claims_by_status, values='count', names='status', title='Claims by Status')
            st.plotly_chart(fig1, use_container_width=True)

            # Claims over time
            claims_over_time = execute_query("""
                SELECT DATE(timestamp) as date, COUNT(*) as count 
                FROM claims 
                GROUP BY DATE(timestamp) 
                ORDER BY date
            """)
            if claims_over_time:
                fig2 = px.line(claims_over_time, x='date', y='count', title='Claims Over Time')
                st.plotly_chart(fig2, use_container_width=True)


# Main application
def main():
    st.set_page_config(page_title="Food Wastage Management", layout="wide")

    # Initialize database
    if not initialize_database():
        st.error("Failed to initialize database. Please check your MySQL connection.")
        return

    st.title("🍏 Food Wastage Management System")
    st.markdown("""
    This application helps reduce food wastage by connecting food providers with receivers in need.
    """)

    # Navigation
    menu = ["Dashboard", "Food Listings", "Claims Management", "Data Management", "Advanced Analytics"]
    choice = st.sidebar.selectbox("Menu", menu)

    if choice == "Dashboard":
        st.header("📊 Dashboard")

        col1, col2, col3 = st.columns(3)

        # Total food available
        total_food = execute_query("SELECT SUM(quantity) as total FROM food_listings")
        col1.metric("Total Food Available", f"{total_food[0]['total']} units" if total_food else "N/A")

        # Total providers
        total_providers = execute_query("SELECT COUNT(*) as count FROM providers")
        col2.metric("Total Providers", total_providers[0]['count'] if total_providers else "N/A")

        # Total receivers
        total_receivers = execute_query("SELECT COUNT(*) as count FROM receivers")
        col3.metric("Total Receivers", total_receivers[0]['count'] if total_receivers else "N/A")

        # Recent food listings
        st.subheader("Recent Food Listings")
        recent_listings = execute_query("""
            SELECT f.food_id, f.food_name, f.quantity, f.expiry_date, p.name as provider_name, p.city 
            FROM food_listings f
            JOIN providers p ON f.provider_id = p.provider_id
            ORDER BY f.expiry_date ASC
            LIMIT 10
        """)
        st.dataframe(pd.DataFrame(recent_listings if recent_listings else []))

        # Claims status
        st.subheader("Claims Status Distribution")
        claims_status = execute_query("""
            SELECT status, COUNT(*) as count 
            FROM claims 
            GROUP BY status
        """)
        if claims_status:
            fig1 = px.pie(claims_status, values='count', names='status', title='Claims Status')
            st.plotly_chart(fig1, use_container_width=True)

        # Expiring soon food items
        st.subheader("Food Expiring Soon (Next 3 Days)")
        expiring_soon = execute_query("""
            SELECT f.food_id, f.food_name, f.quantity, f.expiry_date, p.name as provider_name, p.city
            FROM food_listings f
            JOIN providers p ON f.provider_id = p.provider_id
            WHERE f.expiry_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 3 DAY)
            ORDER BY f.expiry_date ASC
        """)
        st.dataframe(pd.DataFrame(expiring_soon if expiring_soon else []))

    elif choice == "Food Listings":
        st.header("🍽️ Food Listings Management")

        # Filters
        col1, col2, col3 = st.columns(3)
        cities = [city['city'] for city in execute_query("SELECT DISTINCT city FROM providers") or []]
        city_filter = col1.selectbox("Filter by City", ["All"] + cities)

        food_types = [ft['food_type'] for ft in execute_query("SELECT DISTINCT food_type FROM food_listings") or []]
        food_type_filter = col2.selectbox("Filter by Food Type", ["All"] + food_types)

        meal_types = [mt['meal_type'] for mt in execute_query("SELECT DISTINCT meal_type FROM food_listings") or []]
        meal_type_filter = col3.selectbox("Filter by Meal Type", ["All"] + meal_types)

        # Build query
        query = """
            SELECT f.food_id, f.food_name, f.quantity, f.expiry_date, f.food_type, f.meal_type, 
                   p.name as provider_name, p.city, p.contact
            FROM food_listings f
            JOIN providers p ON f.provider_id = p.provider_id
            WHERE 1=1
        """
        params = []

        if city_filter != "All":
            query += " AND p.city = %s"
            params.append(city_filter)

        if food_type_filter != "All":
            query += " AND f.food_type = %s"
            params.append(food_type_filter)

        if meal_type_filter != "All":
            query += " AND f.meal_type = %s"
            params.append(meal_type_filter)

        query += " ORDER BY f.expiry_date ASC"

        # Display filtered results
        filtered_listings = execute_query(query, params if params else None)
        st.dataframe(pd.DataFrame(filtered_listings if filtered_listings else []))

        # CRUD operations for food listings
        editable_dataframe("food_listings", ["food_id"])

    elif choice == "Claims Management":
        st.header("📝 Claims Management")

        # Tabs for different claim statuses
        tab1, tab2, tab3 = st.tabs(["Pending Claims", "Completed Claims", "Cancelled Claims"])

        with tab1:
            st.subheader("Pending Claims")
            pending_claims = execute_query("""
                SELECT c.claim_id, f.food_name, f.quantity, p.name as provider_name, 
                       r.name as receiver_name, c.timestamp
                FROM claims c
                JOIN food_listings f ON c.food_id = f.food_id
                JOIN providers p ON f.provider_id = p.provider_id
                JOIN receivers r ON c.receiver_id = r.receiver_id
                WHERE c.status = 'Pending'
                ORDER BY c.timestamp ASC
            """)
            st.dataframe(pd.DataFrame(pending_claims if pending_claims else []))

            # Update claim status
            st.subheader("Update Claim Status")
            with st.form("update_claim"):
                claim_id = st.number_input("Claim ID to update", min_value=1)
                new_status = st.selectbox("New Status", ["Completed", "Cancelled"])

                if st.form_submit_button("Update Status"):
                    update_result = execute_query("""
                        UPDATE claims SET status = %s WHERE claim_id = %s
                    """, (new_status, claim_id), fetch=False)

                    if update_result:
                        st.success(f"Claim {claim_id} updated to {new_status}")
                        if new_status == "Completed":
                            # Reduce food quantity
                            execute_query("""
                                UPDATE food_listings 
                                SET quantity = quantity - (
                                    SELECT quantity FROM food_listings 
                                    WHERE food_id = (
                                        SELECT food_id FROM claims WHERE claim_id = %s
                                    )
                                )
                                WHERE food_id = (
                                    SELECT food_id FROM claims WHERE claim_id = %s
                                )
                            """, (claim_id, claim_id), fetch=False)
                            st.experimental_rerun()

        with tab2:
            st.subheader("Completed Claims")
            completed_claims = execute_query("""
                SELECT c.claim_id, f.food_name, f.quantity, p.name as provider_name, 
                       r.name as receiver_name, c.timestamp
                FROM claims c
                JOIN food_listings f ON c.food_id = f.food_id
                JOIN providers p ON f.provider_id = p.provider_id
                JOIN receivers r ON c.receiver_id = r.receiver_id
                WHERE c.status = 'Completed'
                ORDER BY c.timestamp DESC
            """)
            st.dataframe(pd.DataFrame(completed_claims if completed_claims else []))

        with tab3:
            st.subheader("Cancelled Claims")
            cancelled_claims = execute_query("""
                SELECT c.claim_id, f.food_name, f.quantity, p.name as provider_name, 
                       r.name as receiver_name, c.timestamp, c.status
                FROM claims c
                JOIN food_listings f ON c.food_id = f.food_id
                JOIN providers p ON f.provider_id = p.provider_id
                JOIN receivers r ON c.receiver_id = r.receiver_id
                WHERE c.status = 'Cancelled'
                ORDER BY c.timestamp DESC
            """)
            st.dataframe(pd.DataFrame(cancelled_claims if cancelled_claims else []))

        # CRUD operations for claims
        editable_dataframe("claims", ["claim_id"])

    elif choice == "Data Management":
        st.header("🗃️ Data Management")

        # Select dataset to manage
        dataset = st.selectbox("Select Dataset", ["providers", "receivers", "food_listings", "claims"])

        if dataset == "providers":
            editable_dataframe("providers", ["provider_id"])
        elif dataset == "receivers":
            editable_dataframe("receivers", ["receiver_id"])
        elif dataset == "food_listings":
            editable_dataframe("food_listings", ["food_id"])
        elif dataset == "claims":
            editable_dataframe("claims", ["claim_id"])

    elif choice == "Advanced Analytics":
        st.header("📈 Advanced Analytics")

        # Analysis options
        analysis_option = st.selectbox("Select Analysis", [
            "Food Distribution by City",
            "Top Providers by Donations",
            "Top Receivers by Claims",
            "Food Wastage Trends",
            "Claim Processing Time",
            "Food Expiration Analysis"
        ])

        if analysis_option == "Food Distribution by City":
            st.subheader("Food Distribution by City")
            food_by_city = execute_query("""
                SELECT p.city, SUM(f.quantity) as total_quantity
                FROM food_listings f
                JOIN providers p ON f.provider_id = p.provider_id
                GROUP BY p.city
                ORDER BY total_quantity DESC
            """)
            if food_by_city:
                fig = px.bar(food_by_city, x='city', y='total_quantity',
                             title='Total Food Available by City')
                st.plotly_chart(fig, use_container_width=True)

            # Add map visualization with robust numeric handling
            st.subheader("Geographical Distribution")
            city_coords = execute_query("""
                SELECT 
                    p.city, 
                    COUNT(*) as providers, 
                    IFNULL(SUM(f.quantity), 0) as food_quantity,
                    COUNT(DISTINCT r.receiver_id) as receivers
                FROM providers p
                LEFT JOIN food_listings f ON p.provider_id = f.provider_id
                LEFT JOIN receivers r ON p.city = r.city
                GROUP BY p.city
            """)
            if city_coords:
                city_coords_df = pd.DataFrame(city_coords)
                # Ensure food_quantity is numeric and replace NaN/None with 0
                city_coords_df['food_quantity'] = pd.to_numeric(city_coords_df['food_quantity'],
                                                                errors='coerce').fillna(0)
                # Filter out cities with zero food quantity if needed
                city_coords_df = city_coords_df[city_coords_df['food_quantity'] > 0]

                if not city_coords_df.empty:
                    fig = px.scatter(city_coords_df, x='providers', y='receivers',
                                     size='food_quantity', color='city',
                                     title='Food Distribution Network by City',
                                     size_max=40)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No food distribution data available for visualization")

        elif analysis_option == "Top Providers by Donations":
            st.subheader("Top Providers by Food Donations")
            top_providers = execute_query("""
                SELECT p.name, SUM(f.quantity) as total_donated, COUNT(f.food_id) as items_donated
                FROM food_listings f
                JOIN providers p ON f.provider_id = p.provider_id
                GROUP BY p.name
                ORDER BY total_donated DESC
                LIMIT 10
            """)
            if top_providers:
                fig = px.bar(top_providers, x='name', y='total_donated',
                             hover_data=['items_donated'],
                             title='Top Providers by Total Quantity Donated')
                st.plotly_chart(fig, use_container_width=True)

        elif analysis_option == "Top Receivers by Claims":
            st.subheader("Top Receivers by Food Claims")
            top_receivers = execute_query("""
                SELECT r.name, COUNT(c.claim_id) as total_claims, 
                       SUM(f.quantity) as total_quantity
                FROM claims c
                JOIN receivers r ON c.receiver_id = r.receiver_id
                JOIN food_listings f ON c.food_id = f.food_id
                WHERE c.status = 'Completed'
                GROUP BY r.name
                ORDER BY total_claims DESC
                LIMIT 10
            """)
            if top_receivers:
                fig = px.bar(top_receivers, x='name', y='total_claims',
                             hover_data=['total_quantity'],
                             title='Top Receivers by Number of Claims')
                st.plotly_chart(fig, use_container_width=True)

        elif analysis_option == "Food Wastage Trends":
            st.subheader("Food Wastage Trends")
            wastage_trends = execute_query("""
                SELECT 
                    DATE(expiry_date) as date,
                    SUM(quantity) as total_quantity,
                    COUNT(*) as item_count
                FROM food_listings
                WHERE expiry_date < CURDATE()
                GROUP BY DATE(expiry_date)
                ORDER BY date
            """)

            if wastage_trends:
                fig = px.line(wastage_trends, x='date', y='total_quantity',
                              title='Expired Food Quantity Over Time')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No expired food data available")

        elif analysis_option == "Claim Processing Time":
            st.subheader("Claim Processing Time Analysis")
            processing_time = execute_query("""
                SELECT 
                    c.claim_id,
                    TIMESTAMPDIFF(HOUR, c.timestamp, 
                        (SELECT MIN(c2.timestamp) 
                         FROM claims c2 
                         WHERE c2.food_id = c.food_id 
                         AND c2.status = 'Completed' 
                         AND c2.timestamp > c.timestamp)) as hours_to_complete
                FROM claims c
                WHERE c.status = 'Pending'
                HAVING hours_to_complete IS NOT NULL
                ORDER BY hours_to_complete
            """)

            if processing_time:
                fig = px.histogram(pd.DataFrame(processing_time), x='hours_to_complete',
                                   title='Distribution of Claim Processing Times (Hours)')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No completed claims data available for analysis")

        elif analysis_option == "Food Expiration Analysis":
            st.subheader("Food Expiration Analysis")
            expiration_analysis = execute_query("""
                SELECT 
                    CASE 
                        WHEN expiry_date < CURDATE() THEN 'Expired'
                        WHEN expiry_date = CURDATE() THEN 'Today'
                        WHEN expiry_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 3 DAY) THEN 'Next 3 Days'
                        WHEN expiry_date BETWEEN DATE_ADD(CURDATE(), INTERVAL 4 DAY) AND DATE_ADD(CURDATE(), INTERVAL 7 DAY) THEN 'Next 4-7 Days'
                        ELSE 'Future'
                    END as expiration_category,
                    SUM(quantity) as total_quantity,
                    COUNT(*) as item_count
                FROM food_listings
                GROUP BY expiration_category
                ORDER BY FIELD(expiration_category, 'Expired', 'Today', 'Next 3 Days', 'Next 4-7 Days', 'Future')
            """)

            if expiration_analysis:
                fig = px.bar(expiration_analysis, x='expiration_category', y='total_quantity',
                             hover_data=['item_count'],
                             title='Food Inventory by Expiration Status')
                st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__":
    main()