import click
import json
import os
import csv
from pathlib import Path

@click.option('--src', type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path), help="Path to the resume PDF file")
def json2csv(src):
    dst = src.split()[0]+'.csv'
    with open(src, 'r') as f:
        data = json.load(f)

    # Open a CSV file for writing
    with open(dst, 'w', newline='') as csvfile:
        if isinstance(data, list) and len(data) > 0:
            # Create a CSV writer object
            fieldnames = data[0].keys()  # Use keys from the first dictionary as the headers
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            # Write the header (field names)
            writer.writeheader()
            # Write each row of data to the CSV file
            for row in data:
                writer.writerow(row)
        else:
            raise ValueError("The JSON data must be a list of dictionaries.")
