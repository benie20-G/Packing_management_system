import math
import serial
import csv
from datetime import datetime, timedelta
import os

# Configuration
CSV_FILE = 'plates_log.csv'
HOURLY_RATE = 200  # Example hourly rate (200 RWF per hour)
MINIMUM_BALANCE = 500

# Initialize serial connection
ser = serial.Serial('COM10', 9600, timeout=1)

def calculate_charges(plate_number):
    """Calculate charges based on unpaid hours from CSV entries"""
    unpaid_hours = 0
    current_time = datetime.now()

    with open(CSV_FILE, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['Plate Number'] == plate_number and row['Payment Status'] == '0':
                try:
                    entry_time = datetime.strptime(row['Timestamp'], '%Y-%m-%d %H:%M:%S')
                    duration = current_time - entry_time
                    hours = math.ceil(duration.total_seconds() / 3600)  # Round up to nearest hour
                    unpaid_hours += hours
                except ValueError:
                    continue

    total_charge = unpaid_hours * HOURLY_RATE
    return total_charge, unpaid_hours

def update_csv(plate_number):
    """Update payment status and add payment timestamp for calculated hours"""
    updated_rows = []
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    with open(CSV_FILE, 'r') as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames
        # Ensure 'Payment Timestamp' is in fieldnames
        if 'Payment Timestamp' not in fieldnames:
            fieldnames.append('Payment Timestamp')
        
        for row in reader:
            if row['Plate Number'] == plate_number and row['Payment Status'] == '0':
                row['Payment Status'] = '1'  # Mark as paid
                row['Payment Timestamp'] = current_time  # Set payment timestamp
            # Ensure 'Payment Timestamp' exists in row
            if 'Payment Timestamp' not in row:
                row['Payment Timestamp'] = ''  # Empty for unpaid or existing rows
            updated_rows.append(row)

    with open(CSV_FILE, 'w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)

def process_payment(plate_number, current_balance):
    try:
        total_charge, hours = calculate_charges(plate_number)

        if hours == 0:
            return "NO_PENDING_HOURS", current_balance

        if current_balance < total_charge:
            return f"INSUFFICIENT_FUNDS: Need {total_charge}, have {current_balance}", current_balance

        new_balance = current_balance - total_charge
        update_csv(plate_number)

        return "SUCCESS", new_balance

    except Exception as e:
        return f"PROCESSING_ERROR: {str(e)}", current_balance

def main():
    print("Payment System Running. Waiting for RFID scans...")

    while True:
        try:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8').strip()

                if line.startswith("PROCESS_PAYMENT:"):
                    # Extract plate number and balance
                    data = line[len("PROCESS_PAYMENT:"):].split(',')
                    if len(data) == 2:
                        plate_number = data[0]
                        current_balance = int(data[1])

                        # Process payment
                        status, new_balance = process_payment(plate_number, current_balance)

                        # Send response back to Arduino
                        if status == "SUCCESS":
                            ser.write(f"NEW_BALANCE:{new_balance}\n".encode())
                        else:
                            ser.write(f"ERROR:{status}\n".encode())

                        # Log transaction
                        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        log_entry = f"{timestamp} - {plate_number} - Status: {status}, Old Balance: {current_balance}, New Balance: {new_balance}\n"
                        print(log_entry)
                        with open('payment_log.txt', 'a') as log_file:
                            log_file.write(log_entry)

                elif line.startswith("INSUFFICIENT_BALANCE:"):
                    balance = line[len("INSUFFICIENT_BALANCE:"):]
                    print(f"Insufficient balance detected: {balance}")

        except KeyboardInterrupt:
            print("\nShutting down payment system...")
            ser.close()
            break
        except Exception as e:
            print(f"Error: {str(e)}")
            continue

if __name__ == "__main__":
    # Create CSV file if it doesn't exist
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['Plate Number', 'Payment Status', 'Timestamp', 'Payment Timestamp'])

    main()