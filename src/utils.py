import os
import random
import time
import re
from selenium import webdriver
import json
from collections import defaultdict
import csv
import datetime
import traceback
from typing import Type, TypeVar
from dataclasses import dataclass, asdict, is_dataclass
from lib_resume_builder_AIHawk.utils import HTML_to_PDF

chromeProfilePath = os.path.join(os.getcwd(), "chrome_profile", "linkedin_profile")

def get_id_from_linkedin_url(url, pattern = r'linkedin\.com/.+?/(\d+)/'):
    if not is_valid_non_empty_string(url): return None
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    return None

def save_job_list(jobs, location):
    if jobs is None or len(jobs)==0:
        printc.printyellow(f'Warning: in save_job_list(): there is no jobs to save')
    try:
        for job in jobs:
            job.save(location=location)
    except Exception as ex:
        printc.printred(f"Exception while saving job list. Error {ex}")
        print(traceback.format_exc())

def is_valid_linkedin_id(linkedin_job_id):
    # Check if the job ID is a numeric string of reasonable length (1 to 12 digits)
    return bool(re.fullmatch(r'\d{1,12}', linkedin_job_id))
def find_jobs_in_path(path):
    if not os.path.exists(path): return []
    jobs = {}
    for root, dirs, _ in os.walk(path):
        for dir in dirs:
            id = dir.split('.')[-1]
            if is_valid_linkedin_id(id):
                jobs[id]=os.path.join(root,dir)

    return jobs

def is_job_in_path(id, path):
    if not is_valid_non_empty_string(id): return False
    if not os.path.exists(path): return False
    for root, dirs, _ in os.walk(path):
        for dir in dirs:
            if id in dir.split('.'):
                print(
                    f'Job Id {id} has been found in a folder {dir}, path: {root}')
                return True
    return False

#required for serializing dataclass with datetime fields
def custom_job_serializer(obj):
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()  # Convert datetime to ISO string
    raise TypeError(f"Type {type(obj)} not serializable")

def custom_job_deserializer(obj):
    # Look for the _date_time field and convert the string into a datetime object
    if '_date_time' in obj:
        # Convert the ISO format string back to a datetime object
        obj['_date_time'] = datetime.datetime.fromisoformat(obj['_date_time'])
    return obj

T = TypeVar('T')
def deserialize(dataclass_type: Type[T], json_data: str, custom_deserializer=custom_job_deserializer) -> T:
    # Load the JSON data into a dictionary, using custom_deserializer to handle special cases
    data_dict = json.loads(json_data, object_hook=custom_deserializer)

    # Create the dataclass instance by unpacking the dictionary into the dataclass
    return dataclass_type(**data_dict)


def dataclass_to_field_names(dataclass_instance, parent_prefix="", parent_delim = '.'):
    result = []
    dct = asdict(dataclass_instance) if is_dataclass(dataclass_instance) else dataclass_instance
    for field_name, field_value in dct.items():
        # Create the full field name path for nested fields
        full_field_name = f"{parent_prefix}{field_name}" if parent_prefix else field_name

        if is_dataclass(field_value) or isinstance(field_value, dict):
            # Recursively handle nested dataclasses
            result.extend(dataclass_to_field_names(field_value, f"{full_field_name}{parent_delim}"))
        elif isinstance(field_value, list):
            # Handle lists if they contain dataclasses
            for idx, item in enumerate(field_value):
                if is_dataclass(item) or isinstance(field_value, dict):
                    result.extend(dataclass_to_field_names(item, f"{full_field_name}[{idx}]."))
                else:
                    result.append(f"{full_field_name}[{idx}]")
        else:
            result.append(full_field_name)
    return result



def dataclass_to_list(dataclass_instance):
    result = []
    dct = asdict(dataclass_instance) if is_dataclass(dataclass_instance) else dataclass_instance
    for field_value in dct.values():
        if is_dataclass(field_value) or isinstance(field_value, dict):
            # Recursively convert nested dataclasses
            result.extend(dataclass_to_list(field_value))
        elif isinstance(field_value, list):
            # Handle lists if they contain dataclasses
            for item in field_value:
                if is_dataclass(item) or isinstance(field_value, dict):
                    result.extend(dataclass_to_list(item))
                else:
                    result.append(item)
        else:
            if isinstance(field_value, datetime.datetime):
                result.append(field_value.strftime('%Y-%d-%mT%H:%M:%S'))
            else:
                result.append(field_value)
    return result

def is_valid_non_empty_string(val: object) -> bool:
    if val is None: return False
    if type(val).__name__ != 'str': return False
    if val.strip()=='': return False
    return True

def flatten_dict(d, parent_key='', sep='__'):
    """
    Flatten a nested dictionary by concatenating keys with a separator.
    """
    items = []
    for key, value in d.items():
        new_key = f"{parent_key}{sep}{key}" if parent_key else key
        if isinstance(value, dict):
            items.extend(flatten_dict(value, new_key, sep=sep).items())
        else:
            items.append((new_key, value))
    return dict(items)

def read_file_content(fpath, flag:str='r', encoding:str='utf-8'):
    out_str = None
    try:
        if fpath is None:
            raise ValueError(f"Error in read_file_content - fpath is None")
        if not os.path.exists(fpath):
            raise FileNotFoundError(f"FileNotFound in read_file_content: {fpath} is not a valid path ")

        with open(fpath, flag, encoding) as f:
            out_str = f.read()
    except Exception as e:
        print(f'Exception while reading file {fpath}. Error {e}. Traceback: {traceback.format_exc()}')

    return out_str

def dict_to_csv(data_dict, csv_file_path, delimiter):
    # Flatten all dictionaries in the list
    flattened_data = [flatten_dict(item) for item in data_dict]

    # Extract all unique column names (keys) from the flattened dictionaries
    column_names = set()
    for item in flattened_data:
        column_names.update(item.keys())

    # Write to CSV file
    with open(csv_file_path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=sorted(column_names), delimiter=delimiter)

        # Write header
        writer.writeheader()

        # Write data rows
        for row in flattened_data:
            writer.writerow(row)

def ensure_chrome_profile():
    profile_dir = os.path.dirname(chromeProfilePath)
    if not os.path.exists(profile_dir):
        os.makedirs(profile_dir)
    if not os.path.exists(chromeProfilePath):
        os.makedirs(chromeProfilePath)
    return chromeProfilePath

def is_scrollable(element):
    scroll_height = element.get_attribute("scrollHeight")
    client_height = element.get_attribute("clientHeight")
    return int(scroll_height) > int(client_height)

def scroll_slow(driver, scrollable_element, start=0, end=3600, step=100, reverse=False):
    if reverse:
        start, end = end, start
        step = -step
    if step == 0:
        raise ValueError("Step cannot be zero.")
    script_scroll_to = "arguments[0].scrollTop = arguments[1];"
    try:
        if scrollable_element.is_displayed():
            if not is_scrollable(scrollable_element):
                print("The element is not scrollable.")
                return
            if (step > 0 and start >= end) or (step < 0 and start <= end):
                print("No scrolling will occur due to incorrect start/end values.")
                return        
            for position in range(start, end, step):
                try:
                    driver.execute_script(script_scroll_to, scrollable_element, position)
                except Exception as e:
                    print(f"Error during scrolling: {e}")
                time.sleep(random.uniform(1.0, 2.6))
            driver.execute_script(script_scroll_to, scrollable_element, end)
            time.sleep(1)
        else:
            print("The element is not visible.")
    except Exception as e:
        print(f"Exception occurred: {e}")

def chromeBrowserOptions():
    ensure_chrome_profile()
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")  # Avvia il browser a schermo intero
    options.add_argument("--no-sandbox")  # Disabilita la sandboxing per migliorare le prestazioni
    options.add_argument("--disable-dev-shm-usage")  # Utilizza una directory temporanea per la memoria condivisa
    options.add_argument("--ignore-certificate-errors")  # Ignora gli errori dei certificati SSL
    options.add_argument("--disable-extensions")  # Disabilita le estensioni del browser
    options.add_argument("--disable-gpu")  # Disabilita l'accelerazione GPU
    options.add_argument("window-size=1200x800")  # Imposta la dimensione della finestra del browser
    options.add_argument("--disable-background-timer-throttling")  # Disabilita il throttling dei timer in background
    options.add_argument("--disable-backgrounding-occluded-windows")  # Disabilita la sospensione delle finestre occluse
    options.add_argument("--disable-translate")  # Disabilita il traduttore automatico
    options.add_argument("--disable-popup-blocking")  # Disabilita il blocco dei popup
    options.add_argument("--no-first-run")  # Disabilita la configurazione iniziale del browser
    options.add_argument("--no-default-browser-check")  # Disabilita il controllo del browser predefinito
    options.add_argument("--disable-logging")  # Disabilita il logging
    options.add_argument("--disable-autofill")  # Disabilita l'autocompletamento dei moduli
    options.add_argument("--disable-plugins")  # Disabilita i plugin del browser
    options.add_argument("--disable-animations")  # Disabilita le animazioni
    options.add_argument("--disable-cache")  # Disabilita la cache 
    options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])  # Esclude switch della modalità automatica e logging

    # Preferenze per contenuti
    prefs = {
        "profile.default_content_setting_values.images": 2,  # Disabilita il caricamento delle immagini
        "profile.managed_default_content_settings.stylesheets": 2,  # Disabilita il caricamento dei fogli di stile
    }
    options.add_experimental_option("prefs", prefs)

    if len(chromeProfilePath) > 0:
        initialPath = os.path.dirname(chromeProfilePath)
        profileDir = os.path.basename(chromeProfilePath)
        options.add_argument('--user-data-dir=' + initialPath)
        options.add_argument("--profile-directory=" + profileDir)
    else:
        options.add_argument("--incognito")

    return options

#alias make_valid_path(...)
def make_valid_os_path_string(path_string: str, invalid_chars: str=r'[<>:"/\\|?*,&()\s+]', repl: str='_'):
    return make_valid_path(path_string, invalid_chars=invalid_chars, repl=repl)
def make_valid_path(primary_path_string: str, secondary_path_string: str = None, max_len = None, invalid_chars: str=r'[<>:"/\\|?*,&()\s+]', repl: str='_') -> str:
    if primary_path_string is None and secondary_path_string is None: return ''
    """
    Converts a given string into a valid folder name by replacing or removing invalid characters.
    Invalid characters are replaced with underscores, and leading/trailing spaces are trimmed.

    Args:
        path_string (str): The input folder name string.

    Returns:
        str: A sanitized, valid folder name.make_valid_path
    """
    # Define characters not allowed in folder names across major operating systems
    #invalid_chars = r'[<>:"/\\|?*]'
    str = primary_path_string if primary_path_string is not None and len(primary_path_string)>0 else secondary_path_string

    # Replace invalid characters with underscores
    valid_name = re.sub(invalid_chars, repl=repl, string=str)

    # Trim leading and trailing spaces
    valid_name = valid_name.strip()

    # Optionally: Replace multiple underscores with a single underscore
    valid_name = re.sub(pattern=f'{repl}+', repl=repl, string=valid_name)
    if max_len is not None:
        if len(valid_name)>max_len:
            valid_name = valid_name[:max_len]

    return valid_name

class printc:
    @staticmethod
    def printcolor(text, color="none", intensity="none"):
        RESET = "\033[0m"
        colors = {
            "none": 0,
            "black": 30,
            "red": 31,
            "green": 32,
            "yellow": 33,
            "blue": 34,
            "magenta": 35,
            "cyan": 36,
            "white": 37
        }

        intensity_offsets = {
            "none": 0,
            "normal": 0,
            "bright": 60
        }
        _color = colors.get(color.lower(), 0)
        _offset = intensity_offsets.get(intensity.lower(), 0)
        COLOR = f"\033[{_color+_offset}m"
        print(f"{COLOR}{text}{RESET}")

    @staticmethod
    def printred(text):
        # Codice colore ANSI per il rosso
        RED = "\033[91m"
        RESET = "\033[0m"
        # Stampa il testo in rosso
        print(f"{RED}{text}{RESET}")

    @staticmethod
    def printyellow(text):
        # Codice colore ANSI per il giallo
        YELLOW = "\033[93m"
        RESET = "\033[0m"
        # Stampa il testo in giallo
        print(f"{YELLOW}{text}{RESET}")

def get_state_from_loc(loc, pattern = r",?\s([A-Z]{2})$|,\s([A-Za-z\s]+)$", valid_path = True):
    if loc is None: return 'None'
    try:
        match = re.search(pattern, loc)
        if match:
            return match.group(1) or match.group(2)  # Return the first matching group (abbreviation or full name)
        else:
            return make_valid_path(loc) if valid_path else loc
    except Exception as e:
        printc.printred(f'Failed get_state_from loc. Loc={loc}, error = {e}')
    return loc  # Return None if no match is found



def process_items(input_json):
    # Parse the input JSON into a list of dictionaries
    items = None
    if os.path.isfile(input_json):
       with open(input_json, 'r', encoding='utf-8' ) as f:
            items = json.load(f)
    else:
        items = json.loads(input_json, strict=False)

    # Dictionary to store the unique combinations of type and question
    result_dict = defaultdict(lambda: {"repetitions": 0, "answers": set()})

    # Iterate through each item and aggregate based on type and question
    for item in items:
        key = (item['type'], item['question'])  # Tuple of type and question
        result_dict[key]["repetitions"] += 1  # Count occurrences
        result_dict[key]["answers"].add(item['answer'])  # Add distinct answers

    # Convert the result into the desired format
    result_list = []
    for (item_type, question), data in result_dict.items():
        result_list.append({
            "type": item_type,
            "question": question,
            "number_of_repetitions": data["repetitions"],
            "answers": list(data["answers"])  # Convert set to list for JSON serialization
        })
    result_list = sorted(result_list, key=lambda x: x['number_of_repetitions'], reverse=True)
    # Convert the final result to JSON
    return result_list

class EnvironmentKeys:
    def __init__(self):
        self.skip_apply = self._read_env_key_bool("SKIP_APPLY")
        self.disable_description_filter = self._read_env_key_bool("DISABLE_DESCRIPTION_FILTER")

    @staticmethod
    def set_key(key:str, value:str):
        if value.lower() in ['y','yes', '1', 'on', 't','true', 'n','no', '0', 'off', 'f','false']:
            EnvironmentKeys._set_key(value.lower() in ['y','yes', 't','true', '1', 'on'])
        else:
            EnvironmentKeys._set_key(key, value)

    @staticmethod
    def _set_key(key, value):
        os.environ[key]=value.__str__()

    #is_bool parameter is not used. It is there for backward compatibility to an old version.
    @staticmethod
    def get_key(key:str, is_bool=False, default=None):
        val = os.getenv(key, default=default)
        if is_bool or val.lower() in ['y','yes', '1', 'on', 't','true', 'n','no', '0', 'off', 'f','false']:
            return val.lower() in ['y','yes', '1', 'on', 't','true']
        return val

    def get_key_old(key:str, is_bool=False, key_default=None):
        key_d_str = ''
        key_d_bool = False
        if is_bool:
            key_d = key_default if key_default is not None else False
            return EnvironmentKeys._read_env_key_bool(key, key_d)
        else:
            key_d = key_default if key_default is not None else ''
            return EnvironmentKeys._read_env_key(key, key_d)

    @staticmethod
    def _read_env_key(key: str, default_value = '') -> str:
        return os.getenv(key, default_value)

    @staticmethod
    def _read_env_key_bool(key: str, default_value:bool = False) -> bool:
        key_value = os.getenv(key)
        if key_value is not None:
            key_true = key_value.lower() in ["true", 't', 'y', 'yes', '1', 'on']
            key_false= key_value.lower() in ["false", 'f', 'n', 'no', '0', 'off']
            if key_true: return key_true
            if key_false: return key_false
        else: return default_value if default_value is not None else False



