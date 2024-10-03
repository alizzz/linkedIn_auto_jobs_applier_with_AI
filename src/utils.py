import os
import random
import time
import re
from selenium import webdriver
import json
from collections import defaultdict
from lib_resume_builder_AIHawk.utils import HTML_to_PDF

chromeProfilePath = os.path.join(os.getcwd(), "chrome_profile", "linkedin_profile")


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
def make_valid_os_path_string(path_string: str, invalid_chars: str=r'[<>:"/\\|?*,\s+]', repl: str='_'):
    return make_valid_path(path_string, invalid_chars, repl)
def make_valid_path(path_string: str, invalid_chars: str=r'[<>:"/\\|?*,\s+]', repl: str='_') -> str:
    if path_string is None: return ''
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

    # Replace invalid characters with underscores
    valid_name = re.sub(invalid_chars, repl=repl, string=path_string)

    # Trim leading and trailing spaces
    valid_name = valid_name.strip()

    # Optionally: Replace multiple underscores with a single underscore
    valid_name = re.sub(pattern=f'{repl}+', repl=repl, string=valid_name)

    return valid_name

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

def get_state_from_loc(loc, pattern = r",?\s([A-Z]{2})$|,\s([A-Za-z\s]+)$", valid_path = True):
    try:
        match = re.search(pattern, loc)
        if match:
            return match.group(1) or match.group(2)  # Return the first matching group (abbreviation or full name)
        else:
            return make_valid_path(loc) if valid_path else loc
    except Exception as e:
        printred(f'Failed get_state_from loc. Loc={loc}, error = {e}')
    return loc  # Return None if no match is found

def printred(text):
    # Codice colore ANSI per il rosso
    RED = "\033[91m"
    RESET = "\033[0m"
    # Stampa il testo in rosso
    print(f"{RED}{text}{RESET}")

def printyellow(text):
    # Codice colore ANSI per il giallo
    YELLOW = "\033[93m"
    RESET = "\033[0m"
    # Stampa il testo in giallo
    print(f"{YELLOW}{text}{RESET}")

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



