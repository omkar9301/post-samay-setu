import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
from collections import Counter
import joblib

# Load dataset
def load_dataset(file_path):
    return pd.read_excel(file_path)

# Preprocessing the data
def preprocess_data(df):
    # Dropping irrelevant columns
    df = df.drop(columns=['Order ID', 'Sender ID', 'Recipient ID', 'Booking Date', 'Delivery Date', 'Route'])
    
    # Encode categorical columns
    label_encoders = {}
    categorical_columns = ['Delivery Address', 'Preferred Slot', 'Actual Slot', 'Region', 'Traffic Level', 'Weather', 'Vehicle']
    for col in categorical_columns:
        le = LabelEncoder()
        df[col] = le.fit_transform(df[col])
        label_encoders[col] = le

    return df, label_encoders

# Save model and encoders
def save_model(encoders, encoders_file):
    joblib.dump(encoders, encoders_file)
    print(f"Encoders saved to {encoders_file}")

# Suggest delivery time slot based on historical data
def suggest_time_slot(df, encoders, address_input):
    # Encode the input address
    encoded_address = encoders['Delivery Address'].transform([address_input])[0]
    
    # Filter the dataset for the given address
    filtered_data = df[df['Delivery Address'] == encoded_address]
    
    if filtered_data.empty:
        return "No data available for the given address"
    
    # Determine the most frequent preferred slot for the given address
    most_common_slot = filtered_data['Preferred Slot'].mode()
    if not most_common_slot.empty:
        slot_encoded = most_common_slot[0]
        time_slot = encoders['Preferred Slot'].inverse_transform([slot_encoded])[0]
        return time_slot
    else:
        return "No preferred slot found"

# Main function
def main():
    # Load and preprocess dataset
    file_path = 'delivery_data.xlsx'  # Change to your file path
    df = load_dataset(file_path)
    df, encoders = preprocess_data(df)

    # Save the encoders (no model to save since we are using historical data)
    save_model(encoders, 'encoders.pkl')

    # Collect input from the user
    delivery_address = input("Enter Delivery Address: ")  # Example address
    
    # Suggest time slot
    suggested_slot = suggest_time_slot(df, encoders, delivery_address)
    print(f"Suggested Delivery Slot: {suggested_slot}")

if __name__ == "__main__":
    main()
