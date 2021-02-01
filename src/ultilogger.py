#!/usr/bin/env python3
#
# This script will continuously check for new prints and log them automatically

import json
import csv
import time
import requests as http
from datetime import datetime
from argparse import ArgumentParser
from requests.exceptions import HTTPError

# Global values
PRINTER_IP  = '' # IP Address of the printer, use -ip to set value
OUTPUT_DIR  = '' # Output directory for CSV and PDF files, use -o to set dir
INTERVAL    = 1  # Amount of seconds between get_time()readings

# Try to get the data using the REST API
#
# @return JSON string of the fetched data
# @return -1 if no data could be fetched
def request_data(url):
    try:
        r = http.get(PRINTER_IP + url)
        r.raise_for_status()
    except HTTPError as error:
        # print(f'HTTP error occurred: {error}')
        return -1
    except Exception as error:
        # print(f'Other error occurred: {error}')
        return -1
    else:
        return json.loads(r.text)

# Checks if a print is running
#
# @return boolean the status of the printer
def is_printing():
    status = request_data('/printer/status')
    if status == "printing":
        state = request_data('/print_job/state')
        if state == 'none' \
        or state == 'post_print' \
        or state == 'wait_cleanup' \
        or state == 'wait_user_action':
            return False
        else:
            return True
    else:
        return False;

# Checks if a print is starting/calibrating
#
# @return boolean the status of the calibration
def is_pre_print():
    state = request_data('/print_job/state')
    return state == "pre_print"

# Check if print job is aborted
#
# @return boolean true if print job is aborted
def is_aborted():
    state = request_data('/print_job/result')
    return state == "Aborted"

# Gets the local time from the printer
#
# @return UTC timestamp
def get_time():
    request = request_data('/system/time')
    timestamp = datetime.fromtimestamp(request["utc"])
    return timestamp

# Gets the start time from the current print job
#
# @return UTC timestamp
def get_start_time():
    request = request_data('/print_job')
    timestamp = request["datetime_started"]
    return timestamp

# Gets the target and current bed temperature values
#
# @return JSON target/current bed temperatures
def get_bed_temps():
    return request_data('/printer/bed/temperature')

# Gets the target and current nozzle temperature values
#
# @param nozzle_id selects which nozzle (0 or 1)
# @return JSON target/current nozzle temperatures
def get_nozzle_temps(nozzle_id):
    request = '/printer/heads/0/extruders/' + nozzle_id + '/hotend/temperature'
    return request_data(request)

# Gets the XYZ nozzle positions
#
# @return JSON XYZ nozzle position
def get_extruder_position():
    request = '/printer/heads/0/position'
    return request_data(request)

# Starts logging a print to <file>
#
# @param FILENAME the filename for the CSV file
# @return boolean if logging was succesull or not
def log_print(FILENAME):
    # Create a new CSV file based of G-code filename
    file = open(FILENAME + '.csv', 'a', newline='')
    writer = csv.writer(file)

    # Setup the CSV file headers
    writer.writerow([
        'time_utc',
        'bed_target_temp',
        'bed_current_temp',
        'nozzle_1_target_temp',
        'nozzle_1_current_temp',
        'nozzle_2_target_temp',
        'nozzle_2_current_temp',
        'extruder_x',
        'extruder_y',
        'extruder_z'
    ])

    # Start logging sensors
    while is_printing():
        # Get values from API
        current_time = get_time()
        bed_temps = get_bed_temps()
        nozzle_1_temps = get_nozzle_temps('0')
        nozzle_2_temps = get_nozzle_temps('1')
        position = get_extruder_position()

        # Store values into CSV
        writer.writerow([
            current_time,
            bed_temps["target"],
            bed_temps["current"],
            nozzle_1_temps["target"],
            nozzle_1_temps["current"],
            nozzle_2_temps["target"],
            nozzle_2_temps["current"],
            position["x"],
            position["y"],
            position["z"]
        ])

        time.sleep(INTERVAL) # Wait before taking next measurement

    file.close() # Done logging
    return True

def main():
    # Print script information
    print('+----------------------+')
    print('| Press CTRL+C to exit |')
    print('+----------------------+')
    print('\n- Using API address: ' + PRINTER_IP)
    print('- Output directory: ' + OUTPUT_DIR)

    # Wait for connection connection
    print('- Connecting to API...')
    system = request_data('/system') # Get printer information
    while(system is None or system == -1):
        system = request_data('/system') # Get printer information
        time.sleep(1)

    # Keep logging and visualizing new prints automatically
    while True:
        print('\n> Waiting for new print job')
        while not is_printing():
            time.sleep(5) # Wait for a print to start

        # Setup filename for both CSV and PDF files
        SYSTEM_NAME = '[' + system["name"] + ']'
        START_TIME = '(' + get_start_time() + ') '
        PRINT_NAME = request_data('/print_job/name')

        # Setup filename for both CSV and PDF files
        # Format = [Printer Name](start time) name of print.csv
        FILENAME = SYSTEM_NAME + START_TIME + PRINT_NAME

        # Wait for pre-print procedures like bed leveling
        print('> Waiting for pre-print procedures to finish for: ' + PRINT_NAME)
        while is_pre_print():
            time.sleep(1)

        # Log the print, if the print was not aborted
        if not is_aborted():
            print('> Logging: ' + OUTPUT_DIR + FILENAME + '.csv')
            log_print(OUTPUT_DIR + FILENAME)

        # Check if print was not aborted during printing
        if is_aborted():
            print('> Print aborted')

# Set command arguments
parser = ArgumentParser(
    description = 'Log prints automatically on Ultimaker 3D printers')
parser.add_argument('-ip', required = True,
    help = 'specifies the ip of the printer')
parser.add_argument('-d', required = False,
    help = 'specifies an output directory, defaults to ./log')

# Handle command arguments
args = parser.parse_args()

# Setup the API address to use
PRINTER_IP  = args.ip
if not PRINTER_IP.startswith('http'):
    PRINTER_IP = 'http://' + PRINTER_IP
if not PRINTER_IP.endswith('/api/v1'):
    PRINTER_IP = PRINTER_IP + '/api/v1'

# Setup the ouput directory
if args.d:
    OUTPUT_DIR = args.d
else:
    OUTPUT_DIR = './log/'
if not OUTPUT_DIR.endswith('/'):
    OUTPUT_DIR = OUTPUT_DIR + '/'

# If arguments are OK, start logging
if __name__ == '__main__':
    main()
