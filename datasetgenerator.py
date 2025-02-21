import pandas as pd
import numpy as np

# Function to generate random delivery data
def generate_delivery_data(num_entries=100):
    # Random data for the columns
    order_ids = [f"ORD{str(i).zfill(3)}" for i in range(1, num_entries+1)]
    sender_ids = [f"S{str(i).zfill(3)}" for i in range(1, num_entries+1)]
    recipient_ids = [f"R{str(i).zfill(3)}" for i in range(1, num_entries+1)]
    addresses = [f"Address_{i}" for i in range(1, num_entries+1)]
    preferred_slots = np.random.choice(['9-11 AM', '10-12 AM', '11-1 PM', '1-3 PM', '2-4 PM', '3-5 PM'], num_entries)
    actual_slots = np.random.choice(['9-11 AM', '10-12 AM', '11-1 PM', '1-3 PM', '2-4 PM', '3-5 PM', '4-6 PM'], num_entries)
    statuses = np.random.choice(['Success', 'Failed'], num_entries)
    booking_dates = pd.date_range(start='2024-01-01', periods=num_entries).strftime('%Y-%m-%d').tolist()
    delivery_dates = pd.date_range(start='2024-01-02', periods=num_entries).strftime('%Y-%m-%d').tolist()
    distances = np.random.randint(5, 30, num_entries)  # Distances between 5 km and 30 km
    regions = np.random.choice(['Urban', 'Suburban', 'Rural'], num_entries)
    traffic_levels = np.random.choice(['Low', 'Medium', 'High'], num_entries)
    weather_conditions = np.random.choice(['Clear', 'Rain', 'Cloudy', 'Snow'], num_entries)
    success_rates = np.random.randint(65, 100, num_entries) / 100  # Success rates between 65% and 100%
    routes = [f"Route{str(i % 5 + 1)}" for i in range(num_entries)]
    stops = np.random.randint(3, 10, num_entries)
    vehicles = np.random.choice(['Van', 'Bike'], num_entries)
    
    # Create a dictionary for the data
    data = {
        'Order ID': order_ids,
        'Sender ID': sender_ids,
        'Recipient ID': recipient_ids,
        'Delivery Address': addresses,
        'Preferred Slot': preferred_slots,
        'Actual Slot': actual_slots,
        'Status': statuses,
        'Booking Date': booking_dates,
        'Delivery Date': delivery_dates,
        'Distance (km)': distances,
        'Region': regions,
        'Traffic Level': traffic_levels,
        'Weather': weather_conditions,
        'Success Rate': success_rates,
        'Route': routes,
        'Stops': stops,
        'Vehicle': vehicles
    }
    
    # Convert to a DataFrame
    df = pd.DataFrame(data)
    
    # Save to Excel
    file_name = 'delivery_data.xlsx'
    df.to_excel(file_name, index=False)
    
    return file_name

# Generate the dataset and save to an Excel file
file_path = generate_delivery_data(100)
print(f"Dataset saved to {file_path}")
