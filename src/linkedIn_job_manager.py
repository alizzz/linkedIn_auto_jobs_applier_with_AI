import copy
import datetime
import os
import random
import time
import traceback
from dotenv import load_dotenv
from itertools import product
from pathlib import Path
from typing import List, Optional, Any, Tuple
import re
import json
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support import expected_conditions as EC
import src.utils as utils
from src.utils import EnvironmentKeys
from src.utils import printc
from src.utils import is_job_in_path
from src.job import Job
from src.utils import make_valid_path, make_valid_os_path_string, EnvironmentKeys, save_job_list
from src.linkedIn_easy_applier import LinkedInEasyApplier
from lib_resume_builder_AIHawk.config import global_config
from CustomExceptions import NotRelevantError, NoJobsOnPageError, AlreadyRetrievedError, OutOfPolicyError
from urllib.parse import quote

from lib_resume_builder_AIHawk.resume import Resume
from lib_resume_builder_AIHawk.resume_html import HtmlResume

load_dotenv()



def wait_page_to_load(driver, timeout=10, post_sleep=(1.0, 2.5)):
    try:
        WebDriverWait(driver, timeout).until(
            lambda driver: driver.execute_script("return document.readyState") == "complete"
        )
        if post_sleep is not None:
            time.sleep(random.uniform(*post_sleep))
    except:
        print("Page load timed out.")

def find_element_with_wait(driver, by:By, value:str, timeout=5, post_sleep=(1.0, 2.5) ):
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
        if post_sleep is not None:
            time.sleep(random.uniform(*post_sleep))
        return element
    except Exception as e:
        print(f"Element not found: {value}")
        return None

def find_elements_with_wait(driver, by:By, value:str, timeout=5, post_sleep=(1.0, 2.5) ):
    try:
        # Wait until at least one element is present on the page
        WebDriverWait(driver, timeout).until(
            lambda d: len(d.find_elements(by, value)) > 0
        )
        return driver.find_elements(by, value)
    except Exception as e:
        print(f"Elements not found: {value}")
        return []

class JobSearchElement:
    def __init__(self, tile: Any, driver, job:Job=None):
        self.driver = driver
        self.tile = tile
        self.job = job if job is not None else Job()
        self.rc = self.load_job_details_right_container()
        self.set_job_insigts()

    def load_job_details_right_container(self):
        rc = None
        try:
            a = self.tile.find_element(By.TAG_NAME, 'a')
            if a is not None:
                a.click()
                time.sleep(random.uniform(3.5, 5.1))
                return self.driver.find_element(By.CLASS_NAME, 'jobs-search__job-details--container')
        except:
            pass
        return None

    def is_easy_apply(self)->bool:
        try:
            return 'Easy Apply' in [x.text for x in self.driver.find_elements(By.TAG_NAME, 'button')]
        except:
            pass
        return False

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
        #res = "unk"
        return 'Easy Apply' if self.is_easy_apply() else 'Apply'
        #try:
        #    res= self.tile.find_element(By.CLASS_NAME, 'job-card-container__apply-method').text
        #except:
        #    pass
        #return res
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
            link = self.tile.find_element(By.CLASS_NAME, 'job-card-list__title').get_attribute('href')
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

    def get_job_description(self):
        jd = self.rc.find_element(By.CLASS_NAME, 'jobs-description-content__text').find_element(By.CLASS_NAME, 'mt4')
        jd_text = jd.text
        #cleaning?
        return jd_text

    def set_job_insigts(self):
        salary:str=None
        office_policy:str=None
        experience_level:str=None
        try:
            elem = self.rc.find_element(By.CLASS_NAME, 'job-details-preferences-and-skills')
            if elem is None:
                elem = self.rc.find_element(By.CLASS_NAME, "job-details-jobs-unified-top-card__job-insight")

            insigts = [x.text for x in elem.find_elements(By.TAG_NAME, 'span')]
            for x in insigts:
                if x is not None:
                    if '$' in x:
                        salary = x
                    elif x.lower() in ['hybrid', 'remote', 'on-site']:
                        office_policy = x
                    elif x.lower() in ['internship', 'level', 'associate', 'director', 'executive']:
                        experience_level = x
        except Exception as e:
            printc.printred(f'Error set_job_insights for job id:{e}')

        return salary, office_policy, experience_level

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
            "austin_": "Austin, Texas Metropolitan Area",
            "portland_oregon_": "Portland, Oregon Metropolitan Area",
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
    def start_applying(self, max_pages_per_location=15):
        self.easy_applier_component = LinkedInEasyApplier(self.driver, self.resume_path, self.set_old_answers, self.gpt_answerer, self.resume_generator_manager)
        searches = self.get_searches()
        page_sleep = 0
        minimum_time = 60 * 3
        minimum_page_time = time.time() + minimum_time
        jobs_stat_run = {
            'completed': 0,
            'found': 0,
            'already_processed': 0,
            'blacklisted': 0,
            'not_relevant': 0
        }
        jobs_stat_search = jobs_stat_run.copy()

        for position, location in searches:

            location_url = self.get_location_url(location)
            job_page_number = -1
            printc.printyellow(f"Starting the search for {position} in {location}.")

            os.makedirs(os.path.join(EnvironmentKeys.get_key('OUTPUT_JOBS_DIRECTORY',False), make_valid_path(location)), exist_ok=True)

            try:
                for key in jobs_stat_run.keys():
                    jobs_stat_run[key]+=jobs_stat_search[key]
                    jobs_stat_search[key]=0

                while True:
                    page_sleep += 1
                    job_page_number += 1
                    if job_page_number>max_pages_per_location:
                        break
                    printc.printyellow(f"Going to search page {job_page_number} for {position} in {location}")
                    self.next_job_search_page(position, location_url, job_page_number)

                    if self.is_no_more_jobs_found():
                        printc.printcolor(f"No more matching jobs found for {position} in {location}\nFound {jobs_stat_search['found']}. Processed: {jobs_stat_search['completed']}. Skipped: {jobs_stat_search['already_processed']+jobs_stat_search['blacklisted']+jobs_stat_search['not_relevant']}: (Already Processed: {jobs_stat_search['already_processed']}. Blacklisted:{jobs_stat_search['blacklisted']}, Not relevant: {jobs_stat_search['not_relevant']})", 'magenta')
                        break

                    printc.printyellow(f"Loaded search page {job_page_number} position: {position}, location_url: {location_url}")
                    time.sleep(random.uniform(1.5, 3.5))
                    printc.printyellow(f"Starting the application process for the search page {job_page_number} for {position} in {location}...")
                    jobs_applied = self.apply_jobs(search_position=position, search_location=location)
                    try:
                        for key in jobs_stat_search:
                            jobs_stat_search[key]+=jobs_applied[key]
                    except:
                        pass

                    printc.printyellow(f"Applying to jobs on the search page {job_page_number} for {position} in {location} has been completed!")

                    time_left = minimum_page_time - time.time()
                    if time_left > 0:
                        printc.printyellow(f"Sleeping for {time_left} seconds.")
                        time.sleep(time_left)
                        minimum_page_time = time.time() + minimum_time
                    if page_sleep % 5 == 0:
                        sleep_time = random.randint(5, 15)
                        printc.printyellow(f"Sleeping for {sleep_time / 60} minutes.")
                        time.sleep(sleep_time)
                        page_sleep += 1
            except Exception as e:
                print(f'Exception {e}')
                traceback.format_exc()
                pass
            time_left = minimum_page_time - time.time()
            if time_left > 0:
                printc.printyellow(f"Sleeping for {time_left} seconds.")
                time.sleep(time_left)
                minimum_page_time = time.time() + minimum_time
            if page_sleep % 5 == 0:
                sleep_time = random.randint(50, 90)
                printc.printyellow(f"Sleeping for {sleep_time / 60} minutes.")
                time.sleep(sleep_time)
                page_sleep += 1

        printc.printcolor(f'Jobs processed: {jobs_stat_run}', 'Magenta')

    def get_searches(self):
        searches = list(product(self.positions, self.locations))
        random.shuffle(searches)
        return searches

    def get_jobs_from_search(self, position, location, max_pages_per_location=15, jobs_stat_search = None, page_sleep=0, no_expected:int=0):
        jobs=[]
        location_url = self.get_location_url(location=location)
        if jobs_stat_search is None:
            jobs_stat_search = {
                'completed': 0,
                'found': 0,
                'already_processed': 0,
                'blacklisted': 0,
                'not_relevant': 0
            }
        job_page_number = -1
        printc.printyellow(f"Starting the search for {position} in {location}.")

        #os.makedirs(os.path.join(EnvironmentKeys.get_key('OUTPUT_JOBS_DIRECTORY', False), make_valid_path(location)), exist_ok=True)

        while True:
            page_sleep += 1
            job_page_number += 1
            if job_page_number > max_pages_per_location:
                break
            printc.printyellow(f"Going to search page {job_page_number} for {position} in {location}")
            self.next_job_search_page(position, location_url, job_page_number)
            if self.is_no_more_jobs_found():
                printc.printcolor(
                    f"No more matching jobs found for {position} in {location}\nFound {jobs_stat_search['found']}. Processed: {jobs_stat_search['completed']}. Skipped: {jobs_stat_search['already_processed'] + jobs_stat_search['blacklisted'] + jobs_stat_search['not_relevant']}: (Already Processed: {jobs_stat_search['already_processed']}. Blacklisted:{jobs_stat_search['blacklisted']}, Not relevant: {jobs_stat_search['not_relevant']})",
                    'magenta')
                break

            try:
                if no_expected==0:
                    no_expected_str = self.driver.find_element(By.CLASS_NAME, 'class="jobs-search-results-list__subtitle').text
                    if no_expected_str is not None and len(no_expected_str) > 0:
                        no_expected = int(no_expected_str.split(' ')[0])
            except:
                pass
            jobs_ = self.build_job_list(num_expected=no_expected, search_location=location)
            #will save inline as goes in build_job_list
            #save_job_list(jobs_, location)
            jobs += jobs_

            printc.printyellow(
                f"Loaded search page {job_page_number} position: {position}, location_url: {location_url}")
            time.sleep(random.uniform(1.5, 3.5))
            printc.printyellow(
                    f"Starting the application process for the search page {job_page_number} for {position} in {location}...")

        return jobs



    def load_job_from_url(self, job_url):
        job = Job(id=os.path.split(job_url)[1], link=job_url)
        #company_name=None
        #title=None
        #loc_raw=None
        #desc_list=None
        #job_description = ''
        #apply_method = 'unk'
        #salary=''
        #skills=[]
        #office_policy='unk'
        #experience_level = 'unk'
        #location = 'unk'

        try:
            self.driver.get(job_url)
            wait_page_to_load(self.driver, 10, (0.5, 1.5))
        except Exception as e:
            pass
        try:
            job.company = self.driver.find_element(By.CLASS_NAME,
                                                                    "job-details-jobs-unified-top-card__company-name").text.strip()

        except Exception as e:
            pass
        try:
            job.title = self.driver.find_element(By.CLASS_NAME,"job-details-jobs-unified-top-card__job-title").text.strip()
        except Exception as e:
            pass

        try:
            job.location = self.driver.find_element(By.CLASS_NAME,
                                                               "job-details-jobs-unified-top-card__primary-description-container").find_element(
                By.TAG_NAME, 'span').text
        except Exception as e:
            pass
        try:
            #not really useful
            desc_list = [x.text for x in self.driver.find_element(By.CLASS_NAME, "job-details-jobs-unified-top-card__primary-description-container").find_elements(By.TAG_NAME, 'span')]
        except Exception as e:
            pass
        try:
            use_text=True #for some reason I used html. It removes delimiters ('.', .\n\n' etc) the way it is implemented here.
            if use_text:
                elm_job_desc = find_element_with_wait(driver=self.driver, by=By.ID, value="job-details", post_sleep=(0,0.1))
                if elm_job_desc:
                    txt = elm_job_desc.text
                    # Replace any remaining multiple "\n" with "\n\n"
                    text = re.sub(r'\n{3,}', '\n\n', txt)
                    job.description = text
            else:
                html = self.driver.find_element(By.ID, "job-details").get_attribute('innerHTML')
                #remove html tags
                clean_tags = re.compile('<.*?>')
                jd_ = re.sub(clean_tags, '', html)
                #remove extra \n and white space
                job.description = re.sub(r'\s+', ' ', jd_).strip()
        except Exception as e:
            printc.printred(f'Error while extracting job description. Error {e}')
        try:
            artdeco_buttons_list = self.driver.find_elements(By.CLASS_NAME, "artdeco-button__text")
            if 'apply' in [s.text.lower() for s in artdeco_buttons_list]:
                job.apply_method='Apply'
            elif 'easy apply' in [s.text.lower() for s in artdeco_buttons_list]:
                job.apply_method = 'Easy Apply'
        except Exception as e:
            pass
        try:
            job.salary = self.driver.find_element(By.CLASS_NAME, "jobs-details__salary-main-rail-card").text
        except Exception as e:
            pass
        try:
            skills = ','.join([x.text for x in
                       self.driver.find_element(By.CLASS_NAME, "pt5").find_elements(By.TAG_NAME, "a")])

        except Exception as e:
            pass
        try:
            job.skills = re.sub(r'\s+and\s+', ' ', skills).split(',')
        except Exception as e:
            pass
        try:
            elem = find_element_with_wait(self.driver, By.CLASS_NAME, 'job-details-preferences-and-skills')
            if elem is None:
                elem = find_element_with_wait(self.driver, By.CLASS_NAME, "job-details-jobs-unified-top-card__job-insight")


            if elem is None:
                raise NoSuchElementException('Salary-OfficePolicy-ExperienceLevel not found')

            elem_arr = elem.find_elements(By.TAG_NAME, 'span')
            if elem_arr is None or len(elem_arr)==0:
                raise NoSuchElementException('Can not find span elements in Salary-OfficePolicy-ExperienceLevel')

            job_insight_list = [x.text for x in elem_arr]
            #['$203K/yr - $317K/yr Hybrid Full-time Executive', '$203K/yr - $317K/yr', 'Hybrid', 'Full-time', 'Executive'
            for x in job_insight_list[1:]:
                if '$' in x:
                    job.salary = x
                elif x.lower() in ['hybrid', 'remote','on-site'] :
                    job._office_policy = x
                elif x.lower() in ['internship', 'level', 'associate', 'director', 'executive']:
                    job.experience_level = x
        except Exception as e:
            printc.printred(f'Exception while loading salary-office policy: Error: {e}:{traceback.format_exc()}')
            pass

        return job

    #has a side effect. It save job as it is loaded
    def build_job_list(self, job_list: List[Job]=None, search_location: str=None, search_position: str=None, num_expected:int=0):
        if job_list is None: job_list = []
        try:
            job_results = self.driver.find_element(By.CLASS_NAME, "jobs-search-results-list")
            #utils.scroll_slow(self.driver, job_results)
            #utils.scroll_slow(self.driver, job_results, step=300, reverse=True)
            job_list_elements = self.driver.find_elements(By.CLASS_NAME, 'scaffold-layout__list-container')[
                0].find_elements(By.CLASS_NAME, 'jobs-search-results__list-item')
            printc.printyellow(f"job_list_elements: {job_list_elements}")
            if not job_list_elements:
                print("No job class elements found on page")
                raise Exception("No job class elements found on page")
            num_expected+=len(job_list_elements)
            print(f"There're {len(job_list_elements)} jobs on page")
            c = 0
            for job_element in job_list_elements:
                try:
                    job_element_a_details = find_element_with_wait(job_element, by=By.TAG_NAME, value='a')
                    #job_element_a_details = job_element.find_element(By.TAG_NAME, 'a')
                    if job_element_a_details is None: raise NoSuchElementException(f'Unable to locate element by tag "a" from {job_element}')
                    id = Job.get_id_from_link(job_element_a_details.get_attribute('href'))
                    job_is_found = is_job_in_path(id, Job.get_base_path())
                    if  job_is_found:
                        pos = job_element_a_details.get_attribute('aria-label')
                        if pos is not None:
                            msg = f"ALREADY COMPLETED: Job {pos} id:{id}. Skipping"
                        else:
                            msg = f"ALREADY COMPLETED: Job id:{id}. Skipping"
                        raise AlreadyRetrievedError(msg)

                    self.driver.execute_script("arguments[0].scrollIntoView();", job_element_a_details)
                    job_element_a_details.click()
                    job_tile = JobSearchElement(job_element, self.driver)
                    id = job_tile.get_id()
                    job_title = job_tile.get_job_title()
                    company_name = job_tile.get_company()
                    location_raw = job_tile.get_job_location()
                    link = job_tile.get_link()
                    apply_method = job_tile.get_apply_method()
                    jd = job_tile.get_job_description()

                    salary, office_policy, experience_level = job_tile.set_job_insigts()
                    easy_apply = job_tile.is_easy_apply()

                    job = Job(title=job_title,
                              company=company_name,
                              location_raw=location_raw,
                              link=link,
                              apply_method=apply_method,
                              id=id,
                              description=jd,
                              compensation=salary,
                              _office_policy=office_policy,
                              experience_level=experience_level,
                              _search_location=search_location,
                              _search_position=search_position
                              )

                    if EnvironmentKeys.get_key('REMOTE_ONLY') and job._office_policy.lower()!= 'remote':
                        raise OutOfPolicyError(f'REMOTE_ONLY is set to True and job.office_policy is {job._office_policy} for Job {job_title} at {company_name} in {location_raw} id:{id}. Skipping')

                    #GPT
                    job.set_job_description_summary(self.gpt_answerer.summarize_job_description(jd))
                    self.gpt_answerer.is_relevant_job(job)


                    job_list.append(job)
                    job.save(location=search_location)
                    print(f"Added job {c+1} to the list. Company:{job.company}, Title:{job.title}, id:{job.id}")
                except AlreadyRetrievedError as e:
                    printc.printyellow(e)
                except OutOfPolicyError as e:
                    printc.printyellow(e)
                except NoSuchElementException as e:
                    printc.printyellow(f'Exception while processing job {c+1}. Error {e}')
                except Exception as e:
                    printc.printred(f'Exception while processing job {c+1}. Error {e}')
                    print(traceback.format_exc())
                c += 1
                printc.printyellow(f"completed {c} out of {len(job_list_elements)} jobs on the page")
        except Exception as e:
            print(f'Exception while adding jobs from page. len(job_list):{len(job_list)} Error: {e}')
        return job_list

    def is_no_more_jobs_found(self) -> bool:
        try:
            no_jobs_found_element = self.driver.find_element(By.CLASS_NAME, "jobs-search-no-results-banner")
            if no_jobs_found_element is not None:
                return True
        except NoSuchElementException:
            return False
        except Exception as e:
            print(f'Exception in is_no_more_jobs_found. Error: {e}')
        return False

    def apply_jobs(self, search_location: str=None, search_position: str = ''):
        #job_list=[]
        try:
            no_jobs_element = self.driver.find_element(By.CLASS_NAME, 'jobs-search-two-pane__no-results-banner--expand')
            #printc.printyellow(f"no_jobs_element: {no_jobs_element}")
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
        _jobs_stat = {
            'completed': 0,
            'found':len(job_list),
            'already_processed':0,
            'blacklisted':0,
            'not_relevant':0
        }
        for job in job_list:

            k+=1
            printc.printyellow(f"Processing job {k}; title: {job.title}; company name: {job.company}; jobid: {job.id}; apply_method: {job.apply_method}")
            if self.is_blacklisted(job.title, job.company, job.link):
                printc.printyellow(f"SKIPPING: Blacklisted {job.title} at {job.company}, skipping...")
                self.write_to_json(job.base_loc_path, data=job.json, name='skipped')
                #self.write_to_status_log_json(job, "skipped")
                _jobs_stat['blacklisted']+=1
                continue
            if self.is_completed(job):
                printc.printyellow(f"SKIPPING: Has been already completed {job.title} at {job.company}, skipping...")
                self.write_to_json(job.base_loc_path, data=job.json, name='skipped')
                _jobs_stat['already_processed']+=1
                #self.write_to_status_log_json(job, "skipped")
                continue
            try:
                if job.apply_method not in {"Continue", "Applied"}:
                    self.easy_applier_component.job_apply(job)
                    utils.printc.printcolor(f"COMPLETED: Has completed {job.title} at {job.company}, jobid: {job.id}", 'Blue')
                    self.write_to_json(job.base_loc_path, data=job.json, name='success')
                    self.write_to_json(job.base_loc_path, data={"link": f'{job.link}'}, name='seen')
                    _jobs_stat['completed']+=1
                    #self.write_to_status_log_json(job, "success")
            except NotRelevantError as e:
                printc.printcolor(e,'blue')
                self.write_to_json(job.base_loc_path, data=job.json, name='skipped')
                _jobs_stat["not_relevant"]+=1
                continue
            except Exception as e:
                utils.printc.printred(f'FAILED: Failed job_apply for job id:{job.id}')
                utils.printc.printred(traceback.format_exc())
                self.write_to_json(job.base_loc_path, data=job.json, name='failed')
                #self.write_to_status_log_json(job, "failed")
                continue

        return _jobs_stat

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
        printc.printyellow(f"Writing to file: pdf_path: {pdf_path}; title: {job.title}; company: {job.company}")
        if not os.path.exists(file_path):
            printc.printyellow(f"file {file_path} doesn't exist, creating")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        else:
            with open(file_path, 'r+', encoding='utf-8') as f:
                try:
                    existing_data = json.load(f)
                except json.JSONDecodeError:
                    printc.printyellow(f"unable to decode json")
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
    
    def next_job_search_page(self, position, location, job_page, timeout = random.uniform(8,12)):
        #go by search page number
        search_url = f"https://www.linkedin.com/jobs/search/{self.base_search_url}&keywords={position}{location}&start={job_page * 25}"
        print(f'In Linkedin_job_manager::next_job_page({position},{location},{job_page}). Search URL={search_url} ')
        self.driver.get(search_url)
        wait_page_to_load(self.driver, timeout, None)

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
                        printc.printyellow(
                            f"ASSERT: {job.path} exists but {resume_warning_string}{' ' if is_resume and is_job_desc else ' and '}{job_desc_warning_string}")
                        res = True

        return res


    def is_completed(self, job):
        link_seen = job.link in self.seen_jobs
        return utils.is_job_in_path(id=job.id, path=job.base_path)
