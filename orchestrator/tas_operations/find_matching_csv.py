import csv
import aiofiles


async def find_matching_row(csv_file_path, match_criteria):
    """
    Finds the first row in a csv file that matches the given criteria.

    Args:
        csv_file_path (str): The path to the CSV file.
        match_criteria (dict): A dictionary containing the criteria to match against the CSV rows.
    
    Returns:
         dict: The first matching row as a dictionary, or None if no match is found.    
    """ 

    try:
        async with aiofiles.open(csv_file_path, mode='r') as file:
            # Read the CSV file asynchronously
            reader = csv.DictReader(await file.read().splitlines())
            for row in reader:
                # Check if the row matches the criteria
                if all(row[key] == value for key, value in match_criteria.items()):
                    return row
            return None
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return None
