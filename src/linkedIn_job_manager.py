import datetime
import os
import random
import time
import traceback
from itertools import product
from pathlib import Path
from typing import List, Optional, Any, Tuple
import re
import json
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
import src.utils as utils
from src.utils import EnvironmentKeys
from src.utils import printcolor, printyellow, printred
from src.job import Job
from src.utils import make_valid_path, make_valid_os_path_string
from src.linkedIn_easy_applier import LinkedInEasyApplier
from lib_resume_builder_AIHawk.config import global_config

from urllib.parse import quote



class JobTile:
    def __init__(self, tile: Any):
        self.tile = tile
    def get_job_title(self):
        res = ""
        try:
            res=self.tile.find_element(By.CLASS_NAME, 'job-card-list__title').text.split('\n')[0].strip()
        except:
            pass
        return res
    def get_company(self):
        res = ""
        try:
            res=self.tile.find_element(By.CLASS_NAME, 'job-card-container__primary-description').text
        except:
            pass
        return res
    def get_job_location(self):
        res = ""
        try:
            res = self.tile.find_element(By.CLASS_NAME, 'job-card-container__metadata-item').text
        except:
            pass
        return res
    def get_apply_method(self):
        res = "unk"
        try:
            res= self.tile.find_element(By.CLASS_NAME, 'job-card-container__apply-method').text
        except:
            pass
        return res
    def get_link(self):
        res = ""
        try:
            res = self.tile.find_element(By.CLASS_NAME, 'job-card-list__title').get_attribute('href').split('?')[0]
        except:
            pass
        return res
    def get_id(self):
        id = ""
        try:
            link = self.tile.find_element(By.CLASS_NAME, 'job-card-list__title').get_attribute('href').split('?')[0]
            id = Job.get_id_from_link(link)
        except:
            pass
        return id
    def get_office_policy(self):
        res = "unk"
        try:
            res = Job.get_office_policy_from_raw_location(self.tile.find_element(By.CLASS_NAME, 'job-card-container__metadata-item').text)
        except:
            pass
        return res
    def is_applied(self):
        applied = False
        try:
            res = self.tile.find_element(By.CLASS_NAME, 'job-card-container__footer-job-state').text
            if res.lower() == 'applied': return True
        except:
            pass
        return applied

class LinkedInJobManager:
    def __init__(self, driver):
        self.driver = driver
        self.set_old_answers = set()
        self.easy_applier_component = None
        self.is_debug = EnvironmentKeys.get_key('DEBUG', is_bool=True)

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


    def get_location_url(self, location="", geoid : int = 0):
        loc = ""
        geoids = {
            "new york": 90000070,
            "nyc": 90000070,
            "newyork": 90000070,
            "los angeles": 90000049,
            "la": 90000049,
            "chicago": 90000014,
            "dallas": 90000031,
            "houston": 90000042,
            "washington": 90000097,
            "miami": 90000056,
            "philadelphia": 90000077,
            "phoenix": 90000620,
            "boston": 90000007,
            "san francisco bay": 90000084,
            "sf": 90000084,
            "sfO": 90000084,
            "detroit": 90000035,
            "seattle": 90000091,
            "minneapolis": 90000512,
            "san diego": 90010472,
            "tampa": 90000828,
            "denver": 90000034,
            "st.louis": 90000704,
            "salt lake city": 90000716,
            "slc": 90000716,
            "salt lake": 90000716,
            "atlanta": 90000052,
            "ralleigh": 90000664,
            "durham": 90000664,
            "chappelhill": 90000664,
            "delhi": 90009626,
            "chennai": 90009647,
            "bengaluru": 90009633,
            "paris": 90009659,
            "barcelona": 90009761,
            "madrid": 90009790,
            "sydney": 90009524,
            "melbourne": 90009521,
            "brisbane": 90009518,
            "united states": 103644278,
            "unitedstates": 103644278,
            "usa": 103644278,
            "us": 103644278,
            "spain": 105646813,
            "france": 105015875,
            "germany": 101282230,
            "united Kingdom": 101165590,
            "uk": 101165590,
            "england": 102299470,
            "london": 102257491,
            "singapore": 102454443,
            "thailand": 105146118,
            "hong Kong": 4021079441,
            "australia": 3996465737
        }
        metro_locations = {
            "boston_": "Greater Boston",
            "new_york_": "New York Metropolitan Area",
            "los_angeles_": "Los Angeles Metropolitan Area",
            "chicago_": "Greater Chicago Area",
            "dallas_fort_worth_": "Dallas-Fort Worth Metroplex",
            "houston_": "Greater Houston",
            "washington_dc_": "Washington DC-Baltimore Area",
            "miami_": "Miami-Fort Lauderdale Area",
            "philadelphia_": "Greater Philadelphia",
            "atlanta_": "Atlanta Metropolitan Area",
            "phoenix_": "Greater Phoenix Area",
            "san_francisco_": "San Francisco Bay Area",
            "sf_": "San Francisco Bay Area",
            "sf": "San Francisco Bay Area",
            "sfo": "San Francisco Bay Area",
            "bay_area": "San Francisco Bay Area",
            "silicone_valley": "San Francisco Bay Area",
            "san_jose_": "San Francisco Bay Area",
            "sjc_": "San Francisco Bay Area",
            "sj_": "San Francisco Bay Area",
            "detroit_": "Detroit Metropolitan Area",
            "seattle_": "Greater Seattle Area",
            "minneapolis_saint_paul_": "Greater Minneapolis-St. Paul Area",
            "san_diego_": "San Diego Metropolitan Area",
            "tampa_": "Greater Tampa Bay Area",
            "denver_": "Denver Metropolitan Area",
            "baltimore_": "Baltimore metropolitan area, Maryland, United States",
            "salt_lake_city_": "Salt Lake City Metropolitan Area",
            "salt_lake_": "Salt Lake City Metropolitan Area",
            "slc_": "Salt Lake City Metropolitan Area",
            "slc": "Salt Lake City Metropolitan Area",
            "barcelona_": "Greater Barcelona Metropolitan Area",
            "valencia_": "Greater Valencia Metropolitan Area",
            "schengen_": "Schengen Area"
        }
        if geoid==0 and len(location)==0:
            return ""
        if geoid==0: #location is not empty
            geoid = geoids.get(location.lower(), 0)
            if geoid==0:
                loc =f'&location={metro_locations.get(location.lower(), location)}'
        else:
            loc = f'&geoid={geoid}'
        return loc
    def start_applying(self):
        self.easy_applier_component = LinkedInEasyApplier(self.driver, self.resume_path, self.set_old_answers, self.gpt_answerer, self.resume_generator_manager)
        searches = list(product(self.positions, self.locations))
        random.shuffle(searches)
        page_sleep = 0
        minimum_time = 60 * 5
        minimum_page_time = time.time() + minimum_time

        for position, location in searches:
            location_url = self.get_location_url(location)
            job_page_number = -1
            utils.printyellow(f"Starting the search for {position} in {location}.")

            os.makedirs(os.path.join(EnvironmentKeys.get_key('OUTPUT_JOBS_DIRECTORY',False), make_valid_path(location)), exist_ok=True)

            try:
                while True:
                    page_sleep += 1
                    job_page_number += 1
                    utils.printyellow(f"Going to job page {job_page_number} for {position} in {location}")
                    self.next_job_page(position, location_url, job_page_number)

                    utils.printyellow(f"Loaded page {job_page_number} position: {position}, location_url: {location_url}")
                    time.sleep(random.uniform(1.5, 3.5))
                    utils.printyellow(f"Starting the application process for the page {job_page_number} for {position} in {location}...")
                    self.apply_jobs(search_position=position, search_location=location)
                    utils.printyellow(f"Applying to jobs on the page {job_page_number} for {position} in {location} has been completed!")

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
            except Exception as e:
                print(f'Exception {e}')
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

    def build_job_list(self, job_list: List[Job]=None, search_location: str=None, search_position: str=None):
        if job_list is None: job_list = []
        try:
            job_results = self.driver.find_element(By.CLASS_NAME, "jobs-search-results-list")
            utils.scroll_slow(self.driver, job_results)
            utils.scroll_slow(self.driver, job_results, step=300, reverse=True)
            job_list_elements = self.driver.find_elements(By.CLASS_NAME, 'scaffold-layout__list-container')[
                0].find_elements(By.CLASS_NAME, 'jobs-search-results__list-item')
            utils.printyellow(f"job_list_elements: {job_list_elements}")
            if not job_list_elements:
                print("No job class elements found on page")
                raise Exception("No job class elements found on page")
            print(f"There're {len(job_list_elements)} jobs on page")
            c = 0
            for job_element in job_list_elements:
                job_tile = JobTile(job_element)
                job_title = job_tile.get_job_title()
                company_name = job_tile.get_company()
                location_raw = job_tile.get_job_location()
                link = job_tile.get_link()
                apply_method = job_tile.get_apply_method()
                id = job_tile.get_id()

                if job_tile.is_applied():
                    print(f"ALREADY APPLIED: Job {job_title} at {company_name} in {location_raw} id:{id}. Skipping")
                    continue

                job = Job(title=job_title,
                          company=company_name,
                          location_raw=location_raw,
                          link=link,
                          apply_method=apply_method,
                          id=id,
                          _search_location=search_location,
                          _search_position=search_position
                          )

                #check if that job id has already been processed:
                if self.is_completed(job):
                    printyellow(f"ALREADY APPLIED: Job {job_title} at {company_name} in {location_raw} id:{id}. Skipping")
                    continue

                job_list.append(job)
                c += 1
                print(f"Added job {c} to the list. Company:{job.company}, Title:{job.title}, id:{job.id}")

            utils.printyellow(f"len(job_list): {len(job_list)}")
        except Exception as e:
            print(f'Exception while adding jobs from page. len(job_list):{len(job_list)} Error: {e}')
        return job_list

    def apply_jobs(self, search_location: str=None, search_position: str = ''):
            #job_list=[]
            try:
                no_jobs_element = self.driver.find_element(By.CLASS_NAME, 'jobs-search-two-pane__no-results-banner--expand')
                #utils.printyellow(f"no_jobs_element: {no_jobs_element}")
                if 'No matching jobs found' in no_jobs_element.text:
                    print("No matching jobs found")
                    raise Exception("No more jobs on this page")
                if 'unfortunately, things aren' in self.driver.page_source.lower():
                    print("unfortunately, things aren")
                    raise Exception("No more jobs on this page")
            except NoSuchElementException:
                pass

            job_list = self.build_job_list(search_location=search_location, search_position=search_position)

            if job_list is None or len(job_list)==0:
                print("Job list is empty. No jobs found")
                raise Exception("No more jobs on this page")
            else:
                print(f'Found {len(job_list)} jobs on the page')

            k=-1
            for job in job_list:

                k+=1
                utils.printyellow(f"Processing job {k}; title: {job.title}; company name: {job.company}; jobid: {job.id}; apply_method: {job.apply_method}")
                if self.is_blacklisted(job.title, job.company, job.link):
                    utils.printyellow(f"SKIPPING: Blacklisted {job.title} at {job.company}, skipping...")
                    self.write_to_json(job.base_loc_path, data=job.json, name='skipped')
                    #self.write_to_status_log_json(job, "skipped")
                    continue
                if self.is_completed(job):
                    utils.printyellow(f"SKIPPING: Has been already completed {job.title} at {job.company}, skipping...")
                    self.write_to_json(job.base_loc_path, data=job.json, name='skipped')
                    #self.write_to_status_log_json(job, "skipped")
                    continue
                try:
                    if job.apply_method not in {"Continue", "Applied", "Apply"}:
                        self.easy_applier_component.job_apply(job)
                        utils.printcolor(f"COMPLETED: Has completed {job.title} at {job.company}, jobid: {job.id}", 'Blue')
                        self.write_to_json(job.base_loc_path, data=job.json, name='success')
                        self.write_to_json(job.base_loc_path, data={"link": f'{job.link}'}, name='seen')
                        #self.write_to_status_log_json(job, "success")

                except Exception as e:
                    utils.printred(f'FAILED: Failed job_apply for job id:{job.id}')
                    utils.printred(traceback.format_exc())
                    self.write_to_json(job.base_loc_path, data=job.json, name='failed')
                    #self.write_to_status_log_json(job, "failed")
                    continue

    def write_to_json(self, base_path, data, name, indent=4):
        file_path = os.path.join(base_path, f'{name}.json')
        if os.path.exists(file_path):
            # File exists, read and append the new data
            with open(file_path, 'r+') as file:
                try:
                    # Load existing data
                    existing_data = json.load(file)

                    # If existing data is not a list, convert it to a list
                    if not isinstance(existing_data, list):
                        existing_data = [existing_data]

                    # Append the new data
                    existing_data.append(data)

                    # Move the pointer to the beginning and write the updated data
                    file.seek(0)
                    json.dump(existing_data, file, indent=indent)
                    file.truncate()  # In case the new content is shorter than the original
                except json.JSONDecodeError:
                    # If file is empty or corrupted, write new data
                    file.seek(0)
                    json.dump([data], file, indent=indent)
                    file.truncate()
        else:
            # File does not exist, create a new file with the new data
            with open(file_path, 'w') as file:
                json.dump([data], file, indent=indent)
    def write_to_status_log_json(self, job, file_name):
        def split_string(str, sep=',', pos=0):
            ss = str
            try:
                ss = str.split(sep)[pos].strip()
            except Exception as e:
                print(f"Failed to split string {str}, sep={sep}, pos={pos}. "
                      f"Exception {e}")
            return ss

        pdf_path = Path(job.resume.pdf).resolve().as_uri()
        resume_pdf_file = os.path.split(job.resume.pdf)[1]

        html_path = Path(job.resume.html).resolve().as_uri()
        resume_html_file = os.path.split(html_path)[1]

        #dt = job.get_dt_string(ms=True)
        #job_title = job.title
        #company_name = job.company
        #company_location = job.location
        #office_policy = job.office_policy
        #job_desc_path = self.output_file_directory / "job_desc"
        #sometimes there are invalid characters in the company name or job title, i.e. AI/ML
        #sanitize prior to creating a job desc file path
        #comp_id = make_valid_path(company_name)
        #job_desc_file = job_desc_path / f'{job_id}.{make_valid_path(company_name)}.{make_valid_path(job_title)}.{dt}.txt'
        #job_desc_file = f'{job.id}.{make_valid_path(company_name)}.{make_valid_path(job_title)}.{dt}.txt'

        data = job.json

        file_path = os.path.join(job.base_loc_path, f"{file_name}.json")
        utils.printyellow(f"Writing to file: pdf_path: {pdf_path}; title: {job.title}; company: {job.company}")
        if not os.path.exists(file_path):
            utils.printyellow(f"file {file_path} doesn't exist, creating")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
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
        if parameters["easy_apply"]:
            url_parts.append("f_LF=f_AL")  # Easy Apply
        base_url = "&".join(url_parts)
        return f"?{base_url}{date_param}"
    
    def next_job_page(self, position, location, job_page):
        search_url = f"https://www.linkedin.com/jobs/search/{self.base_search_url}&keywords={position}{location}&start={job_page * 25}"
        print(f'In Linkedin_job_manager::next_job_page({position},{location},{job_page}). Search URL={search_url} ')
        self.driver.get(search_url)


    @staticmethod
    def get_job_title_from_tile(self, job_tile):
        job_title = ""
        try:
            job_title = job_tile.find_element(By.CLASS_NAME, 'job-card-list__title').text.split('\n')[0].strip()
        except:
            pass
        return job_title

    @staticmethod
    def get_job_link_from_tile(self, job_tile):
        job_link = ""
        try:
            job_link = link = job_tile.find_element(By.CLASS_NAME, 'job-card-list__title').get_attribute('href').split('?')[0]
        except:
            pass
        return job_link

    def extract_job_information_from_tile(self, job_tile):
        job_title, company, job_location, job_location_raw, apply_method, link, id, office_policy = "", "", "", "", "unk", "", "", "unk"
        try:
            job_title = job_tile.find_element(By.CLASS_NAME, 'job-card-list__title').text.split('\n')[0].strip()
            link = job_tile.find_element(By.CLASS_NAME, 'job-card-list__title').get_attribute('href').split('?')[0]
            id = Job.get_id_from_link(link)
            company = job_tile.find_element(By.CLASS_NAME, 'job-card-container__primary-description').text
        except:
            pass
        try:
            job_location_raw = job_tile.find_element(By.CLASS_NAME, 'job-card-container__metadata-item').text
            office_policy = Job.get_office_policy_from_raw_location(job_location_raw)
            job_location = Job.get_location_from_raw(job_location_raw)
        except:
            pass
        try:
            apply_method = job_tile.find_element(By.CLASS_NAME, 'job-card-container__apply-method').text
        except:
            apply_method = "unk"

        print(f'In extract_job_information_from_tile(). job_title:{job_title}, company:{company}, job_location:{job_location}, link:{link}, apply_method:{apply_method}')
        return job_title, company, job_location_raw, apply_method, link, id, office_policy, job_location
    
    def is_blacklisted(self, job_title, company, link):
        job_title_words = job_title.lower().split(' ')
        title_blacklisted = any(word in job_title_words for word in self.title_blacklist)
        company_blacklisted = company.strip().lower() in (word.strip().lower() for word in self.company_blacklist)
        link_seen = False
        #link_seen = link in self.seen_jobs
        return title_blacklisted or company_blacklisted or link_seen

    def is_completed_old(self, job):
        res = False
        link_seen = job.link in self.seen_jobs
        for root, dirs, files in os.walk(job.base_path):
            for subfolder in dirs:
                # Check if subfolder name matches the pattern
                if subfolder.split('.')[-1]==job.id:
                    res = True
                    is_resume = os.path.exists(os.path.join(job.base_loc_path, subfolder, job.resume.file_name))
                    is_job_desc = os.path.exists(os.path.join(job.base_loc_path, subfolder, job.job_docset.file_name))
                    if not( is_resume and is_job_desc):
                        resume_warning_string = '' if is_resume else 'Resume file does not'
                        job_desc_warning_string = '' if is_job_desc else 'Job description file does not'
                        printyellow(
                            f"ASSERT: {job.path} exists but {resume_warning_string}{' ' if is_resume and is_job_desc else ' and '}{job_desc_warning_string}")
                        res = True

        return res

    def is_completed(self, job):
        res = False
        link_seen = job.link in self.seen_jobs
        if job.id is None or len(job.id)==0: return False
        for root, dirs, _ in os.walk(job.base_path):
            for dir in dirs:
                if job.id in dir.split('.'):
                    print(f'in LinkedInJobManager::is_completed() Job Id {job.id} has been found in a folder {dir}, path: {root}. DEBUG={self.is_debug}')
                    return True

        return False