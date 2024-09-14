import datetime
import os
import random
import time
import traceback
from itertools import product
from pathlib import Path
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
import src.utils as utils
from src.job import Job
from src.linkedIn_easy_applier import LinkedInEasyApplier
import json
from lib_resume_builder_AIHawk.config import global_config
import re
def make_valid_path(path_string):
    # Define the invalid characters for file paths
    # On Windows: \ / : * ? " < > |
    # On Unix-like systems, only '/' is invalid
    if os.name == 'nt':  # Windows
        # Replace invalid characters with underscores
        return re.sub(r'[<>:"/\\|?*]', '_', path_string)
    else:  # Unix-like (Linux, macOS)
        # Replace '/' with underscores
        return path_string.replace('/', '_')

class EnvironmentKeys:
    def __init__(self):
        self.skip_apply = self._read_env_key_bool("SKIP_APPLY")
        self.disable_description_filter = self._read_env_key_bool("DISABLE_DESCRIPTION_FILTER")

    @staticmethod
    def _read_env_key(key: str) -> str:
        return os.getenv(key, "")

    @staticmethod
    def _read_env_key_bool(key: str) -> bool:
        return os.getenv(key) == "True"

class LinkedInJobManager:
    def __init__(self, driver):
        self.driver = driver
        self.set_old_answers = set()
        self.easy_applier_component = None

    def set_parameters(self, parameters):
        self.company_blacklist = parameters.get('companyBlacklist', []) or []
        self.title_blacklist = parameters.get('titleBlacklist', []) or []
        self.positions = parameters.get('positions', [])
        self.locations = parameters.get('locations', [])
        self.base_search_url = self.get_base_search_url(parameters)
        self.seen_jobs = []
        resume_path = parameters.get('uploads', {}).get('resume', None)
        if resume_path is not None and Path(resume_path).exists():
            self.resume_path = Path(resume_path)
        else:
            self.resume_path = None
        self.output_file_directory = Path(parameters['outputFileDirectory'])
        self.env_config = EnvironmentKeys()
        #self.old_question()

    def set_gpt_answerer(self, gpt_answerer):
        self.gpt_answerer = gpt_answerer

    def set_resume_generator_manager(self, resume_generator_manager):
        self.resume_generator_manager = resume_generator_manager

    """ def old_question(self):
        self.set_old_answers = {}
        file_path = 'data_folder/output/old_Questions.csv'
        if os.path.exists(file_path):
            with open(file_path, 'r', newline='', encoding='utf-8', errors='ignore') as file:
                csv_reader = csv.reader(file, delimiter=',', quotechar='"')
                for row in csv_reader:
                    if len(row) == 3:
                        answer_type, question_text, answer = row
                        self.set_old_answers[(answer_type.lower(), question_text.lower())] = answer"""


    def start_applying(self):
        self.easy_applier_component = LinkedInEasyApplier(self.driver, self.resume_path, self.set_old_answers, self.gpt_answerer, self.resume_generator_manager)
        searches = list(product(self.positions, self.locations))
        random.shuffle(searches)
        page_sleep = 0
        minimum_time = 60 * 5
        minimum_page_time = time.time() + minimum_time

        for position, location in searches:
            location_url = "&location=" + location
            job_page_number = -1
            utils.printyellow(f"Starting the search for {position} in {location}.")

            try:
                while True:
                    page_sleep += 1
                    job_page_number += 1
                    utils.printyellow(f"Going to job page {job_page_number}")
                    self.next_job_page(position, location_url, job_page_number)
                    utils.printyellow(f"position: {position}, location_url: {location_url}")
                    time.sleep(random.uniform(1.5, 3.5))
                    utils.printyellow("Starting the application process for this page...")
                    self.apply_jobs()
                    utils.printyellow("Applying to jobs on this page has been completed!")

                    time_left = minimum_page_time - time.time()
                    if time_left > 0:
                        utils.printyellow(f"Sleeping for {time_left} seconds.")
                        time.sleep(time_left)
                        minimum_page_time = time.time() + minimum_time
                    if page_sleep % 5 == 0:
                        sleep_time = random.randint(5, 15)
                        utils.printyellow(f"Sleeping for {sleep_time / 60} minutes.")
                        time.sleep(sleep_time)
                        page_sleep += 1
            except Exception:
                traceback.format_exc()
                pass
            time_left = minimum_page_time - time.time()
            if time_left > 0:
                utils.printyellow(f"Sleeping for {time_left} seconds.")
                time.sleep(time_left)
                minimum_page_time = time.time() + minimum_time
            if page_sleep % 5 == 0:
                sleep_time = random.randint(50, 90)
                utils.printyellow(f"Sleeping for {sleep_time / 60} minutes.")
                time.sleep(sleep_time)
                page_sleep += 1

    def apply_jobs(self):
        try:
            no_jobs_element = self.driver.find_element(By.CLASS_NAME, 'jobs-search-two-pane__no-results-banner--expand')
            utils.printyellow(f"no_jobs_element: {no_jobs_element}")
            if 'No matching jobs found' in no_jobs_element.text:
                print("No matching jobs found")
                raise Exception("No more jobs on this page")
            if 'unfortunately, things aren' in self.driver.page_source.lower():
                print("unfortunately, things aren")
                raise Exception("No more jobs on this page")
        except NoSuchElementException:
            pass
        
        job_results = self.driver.find_element(By.CLASS_NAME, "jobs-search-results-list")
        utils.scroll_slow(self.driver, job_results)
        utils.scroll_slow(self.driver, job_results, step=300, reverse=True)
        job_list_elements = self.driver.find_elements(By.CLASS_NAME, 'scaffold-layout__list-container')[0].find_elements(By.CLASS_NAME, 'jobs-search-results__list-item')
        utils.printyellow(f"job_list_elements: {job_list_elements}")
        if not job_list_elements:
            print("No job class elements found on page")
            raise Exception("No job class elements found on page")
        job_list = [Job(*self.extract_job_information_from_tile(job_element)) for job_element in job_list_elements]
        utils.printyellow(f"job_list: {job_list}")

        for job in job_list:
            utils.printyellow(f"Processing job title: {job.title}, company: {job.company} apply_method: {job.apply_method}")
            if self.is_blacklisted(job.title, job.company, job.link):
                utils.printyellow(f"Blacklisted {job.title} at {job.company}, skipping...")
                self.write_to_file(job, "skipped")
                continue
            try:
                if job.apply_method not in {"Continue", "Applied", "Apply"}:
                    self.easy_applier_component.job_apply(job)
                    self.write_to_file(job, "success")
            except Exception as e:
                utils.printred(traceback.format_exc())
                self.write_to_file(job, "failed")
                continue
        
    def write_to_file(self, job, file_name):
        def split_string(str, sep=',', pos=0):
            ss = str
            try:
                ss = str.split(sep)[pos].strip()
            except Exception as e:
                print(f"Failed to split string {str}, sep={sep}, pos={pos}. "
                      f"Exception {e}")
            return ss

        def extract_office_policy(str):
            print(f'Extracting office policy from {str}')
            office_policy = split_string(str, "(", 1)[:-1]
            print(f'returning office policy {office_policy}')
            return office_policy


        pdf_path = Path(job.pdf_path).resolve().as_uri()
        pdf_file_name = os.path.split(job.pdf_path)[1]

        html_path = Path(job.html_path).resolve().as_uri()
        html_file_name = os.path.split(job.html_path)[1]

        dt = datetime.datetime.now().strftime("%Y-%m-%d.%H-%M-%S.%f")[:-3]
        job_title = split_string(job.title, sep="\n", pos=0)
        company_name = split_string(job.company, sep='·', pos=0)
        company_location = split_string(job.location, sep="(", pos=0).strip()
        job.id = split_string(job.link, sep='/',pos=-2)

        office_policy = extract_office_policy(job.location)
        job_desc_path = self.output_file_directory / "job_desc"
        #sometimes there are invalid characters in the company name or job title, i.e. AI/ML
        #sanitize prior to creating a job desc file path
        comp_id = make_valid_path(company_name)
        #job_desc_file = job_desc_path / f'{job_id}.{make_valid_path(company_name)}.{make_valid_path(job_title)}.{dt}.txt'
        job_desc_file = f'{job.id}.{make_valid_path(company_name)}.{make_valid_path(job_title)}.{dt}.txt'

        data = {
            "datetime": dt,
            "job_id": job.id,
            "job_title": job_title,
            "company_name": company_name,
            "company_location": company_location,
            "office_policy": office_policy,
            "job_compensation": job.compensation,
            "job_location": job.location,
            "job_recruiter": job.recruiter_link,
            "link": job.link,
            "resume_pdf": pdf_file_name,
            "resume_html": html_file_name,
            "job_desc_path": job_desc_file,
            "applied": "unk"
        }
        try:
            utils.printyellow(f"Writing to job description to file {job_desc_file}; title: {job_title}; company: {company_name}")
            if not os.path.exists(job_desc_path):
                os.makedirs(job_desc_path)
            with open(job_desc_path / job_desc_file, 'w') as file:
                file.write(job.description)
        except Exception as e:
            print(f'Exception while saving job description file {job_desc_file}. Exception {e}')

        file_path = self.output_file_directory / f"{file_name}.json"
        utils.printyellow(f"Writing to file: pdf_path: {pdf_path}; title: {job_title}; company: {company_name}")
        if not file_path.exists():
            utils.printyellow(f"file_path {file_path} doesn't exist, creating")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump([data], f, indent=4)
        else:
            with open(file_path, 'r+', encoding='utf-8') as f:
                try:
                    existing_data = json.load(f)
                except json.JSONDecodeError:
                    utils.printyellow(f"unable to decode json")
                    existing_data = []
                existing_data.append(data)
                f.seek(0)
                json.dump(existing_data, f, indent=4)
                f.truncate()

    def get_base_search_url(self, parameters):
        url_parts = []
        if parameters['remote']:
            url_parts.append("f_CF=f_WRA")
        experience_levels = [str(i+1) for i, (level, v) in enumerate(parameters.get('experienceLevel', {}).items()) if v]
        if experience_levels:
            url_parts.append(f"f_E={','.join(experience_levels)}")
        url_parts.append(f"distance={parameters['distance']}")
        job_types = [key[0].upper() for key, value in parameters.get('jobTypes', {}).items() if value]
        if job_types:
            url_parts.append(f"f_JT={','.join(job_types)}")
        date_mapping = {
            "all time": "",
            "month": "&f_TPR=r2592000",
            "week": "&f_TPR=r604800",
            "24 hours": "&f_TPR=r86400"
        }
        date_param = next((v for k, v in date_mapping.items() if parameters.get('date', {}).get(k)), "")
        url_parts.append("f_LF=f_AL")  # Easy Apply
        base_url = "&".join(url_parts)
        return f"?{base_url}{date_param}"
    
    def next_job_page(self, position, location, job_page):
        self.driver.get(f"https://www.linkedin.com/jobs/search/{self.base_search_url}&keywords={position}{location}&start={job_page * 25}")
    
    def extract_job_information_from_tile(self, job_tile):
        job_title, company, job_location, apply_method, link = "", "", "", "", ""
        try:
            job_title = job_tile.find_element(By.CLASS_NAME, 'job-card-list__title').text
            link = job_tile.find_element(By.CLASS_NAME, 'job-card-list__title').get_attribute('href').split('?')[0]
            company = job_tile.find_element(By.CLASS_NAME, 'job-card-container__primary-description').text
        except:
            pass
        try:
            job_location = job_tile.find_element(By.CLASS_NAME, 'job-card-container__metadata-item').text
        except:
            pass
        try:
            apply_method = job_tile.find_element(By.CLASS_NAME, 'job-card-container__apply-method').text
        except:
            apply_method = "ApplyMethodNotFound"

        return job_title, company, job_location, link, apply_method
    
    def is_blacklisted(self, job_title, company, link):
        job_title_words = job_title.lower().split(' ')
        title_blacklisted = any(word in job_title_words for word in self.title_blacklist)
        company_blacklisted = company.strip().lower() in (word.strip().lower() for word in self.company_blacklist)
        link_seen = link in self.seen_jobs
        return title_blacklisted or company_blacklisted or link_seen
