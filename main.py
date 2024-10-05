import datetime
import json
import os
import re
import sys
import base64
import traceback
from pathlib import Path
from urllib.parse import urlparse
import yaml
import click
from dataclasses import dataclass
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import WebDriverException, TimeoutException
from selenium.webdriver.common.by import By
from src.job import Job
from src.utils import chromeBrowserOptions
from src.utils import printcolor, printyellow, printred
from src.utils import EnvironmentKeys, make_valid_path
from src.gpt import GPTAnswerer
from src.linkedIn_authenticator import LinkedInAuthenticator
from src.linkedIn_bot_facade import LinkedInBotFacade
from src.linkedIn_job_manager import LinkedInJobManager
from src.job_application_profile import JobApplicationProfile
from src.file_manager import FileManager
from src.config import linkedin_url_fmt
from lib_resume_builder_AIHawk.utils import HTML_to_PDF
from lib_resume_builder_AIHawk import Resume,StyleManager,FacadeManager,ResumeGenerator
#from lib_resume_builder_AIHawk.utils import get_dict_names_from_dir


from string import Template
from typing import Any
from lib_resume_builder_AIHawk.gpt_resume import LLMResumer
from lib_resume_builder_AIHawk.gpt_resume_job_description import LLMResumeJobDescription
from lib_resume_builder_AIHawk.module_loader import load_module
from lib_resume_builder_AIHawk.config import global_config


import os
import re

import context

# Suppress stderr
sys.stderr = open(os.devnull, 'w')

class ConfigError(Exception):
    pass


class ConfigValidator:
    @staticmethod
    def validate_email(email: str) -> bool:
        return re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email) is not None
    
    @staticmethod
    def validate_yaml_file(yaml_path: Path) -> dict:
        try:
            with open(yaml_path, 'r') as stream:
                return yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            raise ConfigError(f"Error reading file {yaml_path}: {exc}")
        except FileNotFoundError:
            raise ConfigError(f"File not found: {yaml_path}")
    
    
    def validate_config(config_yaml_path: Path) -> dict:
        parameters = ConfigValidator.validate_yaml_file(config_yaml_path)
        required_keys = {
            'remote': bool,
            'easy_apply': bool,
            'experienceLevel': dict,
            'jobTypes': dict,
            'date': dict,
            'positions': list,
            'locations': list,
            'distance': int,
            'companyBlacklist': list,
            'titleBlacklist': list,
            'companyWhitelist':list
        }

        for key, expected_type in required_keys.items():
            if key not in parameters:
                if key in ['companyBlacklist', 'titleBlacklist', 'companyWhitelist']:
                    parameters[key] = []
                else:
                    raise ConfigError(f"Missing or invalid key '{key}' in config file {config_yaml_path}")
            elif not isinstance(parameters[key], expected_type):
                if key in ['companyBlacklist', 'titleBlacklist', 'companyWhitelist'] and parameters[key] is None:
                    parameters[key] = []
                else:
                    raise ConfigError(f"Invalid type for key '{key}' in config file {config_yaml_path}. Expected {expected_type}.")

        experience_levels = ['internship', 'entry', 'associate', 'mid-senior level', 'director', 'executive']
        for level in experience_levels:
            if not isinstance(parameters['experienceLevel'].get(level), bool):
                raise ConfigError(f"Experience level '{level}' must be a boolean in config file {config_yaml_path}")

        job_types = ['full-time', 'contract', 'part-time', 'temporary', 'internship', 'other', 'volunteer']
        for job_type in job_types:
            if not isinstance(parameters['jobTypes'].get(job_type), bool):
                raise ConfigError(f"Job type '{job_type}' must be a boolean in config file {config_yaml_path}")

        date_filters = ['all time', 'month', 'week', '24 hours']
        for date_filter in date_filters:
            if not isinstance(parameters['date'].get(date_filter), bool):
                raise ConfigError(f"Date filter '{date_filter}' must be a boolean in config file {config_yaml_path}")

        if not all(isinstance(pos, str) for pos in parameters['positions']):
            raise ConfigError(f"'positions' must be a list of strings in config file {config_yaml_path}")
        if not all(isinstance(loc, str) for loc in parameters['locations']):
            raise ConfigError(f"'locations' must be a list of strings in config file {config_yaml_path}")

        approved_distances = {0, 5, 10, 25, 50, 100}
        if parameters['distance'] not in approved_distances:
            raise ConfigError(f"Invalid distance value in config file {config_yaml_path}. Must be one of: {approved_distances}")

        for blacklist in ['companyBlacklist', 'titleBlacklist']:
            if not isinstance(parameters.get(blacklist), list):
                raise ConfigError(f"'{blacklist}' must be a list in config file {config_yaml_path}")
            if parameters[blacklist] is None:
                parameters[blacklist] = []

        return parameters



    @staticmethod
    def validate_secrets(secrets_yaml_path: Path) -> tuple:
        secrets = ConfigValidator.validate_yaml_file(secrets_yaml_path)
        mandatory_secrets = ['email', 'password', 'openai_api_key']

        for secret in mandatory_secrets:
            if secret not in secrets:
                raise ConfigError(f"Missing secret '{secret}' in file {secrets_yaml_path}")

        if not ConfigValidator.validate_email(secrets['email']):
            raise ConfigError(f"Invalid email format in secrets file {secrets_yaml_path}.")
        if not secrets['password']:
            raise ConfigError(f"Password cannot be empty in secrets file {secrets_yaml_path}.")
        if not secrets['openai_api_key']:
            raise ConfigError(f"OpenAI API key cannot be empty in secrets file {secrets_yaml_path}.")

        return secrets['email'], str(secrets['password']), secrets['openai_api_key']



def init_browser() -> webdriver.Chrome:
    try:
        options = chromeBrowserOptions()
        service = ChromeService(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)
    except Exception as e:
        raise RuntimeError(f"Failed to initialize browser: {str(e)}")

def create_and_run_bot(email: str, password: str, parameters: dict, openai_api_key: str):
    try:
        browser = init_browser()
        bot = LinkedInBotFacade.create_bot(email=email, openai_api_key= openai_api_key, parameters= parameters, browser=browser, password = password)

        job_desc = parameters['job_desc']
        if job_desc[0]:
            if job_desc[1]=='linkedin':
                try:
                    job_desc_id = job_desc[2].split('/')[-1]
                    _file_name = f'{datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")}.{job_desc_id}.Resume'
                    pdf64 = bot.apply_component.resume_generator_manager.pdf_base64(job_description_url = job_desc[2], job_description_text = None,
                                                                html_file_name=os.path.join(bot.jobs_folder, f'{_file_name}.html'), delete_html_file=False)

                    pdf_data = base64.b64decode(pdf64)

                    with open(os.path.join(bot.jobs_folder, f'{_file_name}.pdf'), "xb") as f:
                        f.write(pdf_data)
                except Exception as e:
                    print(f"Exception generating resume from url {job_desc[2]}. Error {e}")
                    print(f'Traceback {traceback.format_exc()}')

        else:
            bot.start_apply()
    except WebDriverException as e:
        print(f"WebDriver error occurred: {e}")
    except Exception as e:
        raise RuntimeError(f"Error running the bot: {str(e)}")


#call browser = init_browser() prior to create_bot
def create_bot(email, openai_api_key, parameters, password, browser):
    bot = LinkedInBotFacade.create_bot(email=email, openai_api_key=openai_api_key, parameters=parameters, password=password, browser=browser)
    os.makedirs(bot.jobs_folder, exist_ok=True)
    parameters['outputJobsDirectory'] = bot.jobs_folder.__str__()
    os.environ["OUTPUT_JOBS_DIRECTORY"] = bot.jobs_folder.__str__()
    return bot


def validate_url(url):
    if url is None or len(url)==0: return False
    try:
        result = urlparse(url)
        if all([result.scheme, result.netloc]):
            return True
    except:
        pass

    return False

def validate_linkedin_id(linkedin_job_id):
    # Check if the job ID is a numeric string of reasonable length (1 to 12 digits)
    return bool(re.fullmatch(r'\d{1,12}', linkedin_job_id))

def validate_linkedin_url(url: str):
    if url is None or len(url)==0: return False
    try:
        # Parse the URL
        result = urlparse(url)
        # Check if it has a valid scheme and netloc
        if all([result.scheme, result.netloc]):
            # Check if the URL contains 'linkedin.com' and 'jobs/view'
            if 'linkedin.com' in result.netloc and '/jobs/view/' in result.path:
                return True
    except:
        pass
    return False

def lkdn_url(data:str=None):
    if validate_linkedin_url(data): return data
    if validate_linkedin_id(data):
        return linkedin_url_fmt.format(id=data)

def validate_job_file_desc(job_file_desc):
    if job_file_desc is None or len(job_file_desc)==0: return False
    if os.path.exists(job_file_desc):
        return True
    return False

def html_2_pdf(resume_file, overwrite=False):
    try:
        dir, file = os.path.split(resume_file)
        pdf_file = os.path.join(dir, f'{file.rsplit('.',1)[0]}.pdf')
        if os.path.exists(pdf_file):
                if not overwrite:
                    print(f'PDF file {pdf_file} exists and overwrite flag is {overwrite}. Skipping')
                else:
                    print(f'PDF file {pdf_file} exists and overwrite flag is {overwrite}. TBH')
                return

        pdf_b64 = base64.b64decode(HTML_to_PDF(resume_file))
        with open(pdf_file, "xb") as f:
            f.write(pdf_b64)
    except Exception as e:
        print(f'EXCEPTION: Failed to convert file to pdf. File: {resume_file}, error: {e}')

def html_2_txt(resume_file, by=(None, None)):
    try:
        dir, file = os.path.split(resume_file)
        txt_file = os.path.join(dir, f'{file.rsplit('.',1)[0]}.txt')
        txt = HTML_to_PDF(resume_file, by=by)
        with open(txt_file, "w") as f:
            f.write(txt)
    except Exception as e:
        print(f'EXCEPTION: Failed to convert file to txt. File: {resume_file}, error: {e}')


def dirwalk(path, ext='.html'):
    file_list = []
    for root, dir, files in os.walk(path):
        for file in files:
            if file.endswith(ext):
                file_list.append((root, file))

    return file_list

def isdirfile(path)->(bool, bool):
    dir:bool = False
    file:bool = False
    if not os.path.exists(path): return False, False
    if os.path.isdir(path):
        dir = True
        file = False
    elif os.path.isfile(path):
        dir = False
        file = True
    return dir, file


@dataclass
class ClickParam():
    resume:click.Path=None
    plain:str=None
    secret:str=None
    config:str=None
    jobs:str=None
    data_folder:str=None
    debug:str=None
    css:str=None
    resume_template:str=None
    lkdn:str=None
    job_url:str=None
    linkedin_id:str=None
    job_file_desc:str=None
    llm_cheap:str=None
    llm:str=None
    src_html:str=None
    easy_apply: bool = None
    mode:str=None

def convert_(clickParam:ClickParam ):
    try:
        src_html = clickParam.src_html

        if src_html is not None:
            overwrite = False
            dir, file = isdirfile(src_html)
            if not any([dir, file]):
                src_html = os.path.join(os.path.dirname(__file__), src_html)
                dir, file = isdirfile(src_html)
                if not any([dir, file]):
                    print(f'ERROR: html2pdf should be either a valid file or dir path. Passed {src_html}')
                    return

            if dir:
                k = 0
                list_files = dirwalk(src_html)
                for dir, html_file in list_files:
                    pdf_file = os.path.join(dir, f'{html_file.rsplit('.', 1)[0]}.pdf')
                    if not os.path.exists(pdf_file) or overwrite:
                        html_2_pdf(resume_file=os.path.join(dir, html_file))
                        html_2_txt(resume_file=os.path.join(dir, html_file), by=(By.TAG_NAME, 'body'))
                        print(f'{k}: Competed for {dir}')
                        k += 1
                pass
            else:
                html_2_pdf(resume_file=src_html)
                html_2_txt(resume_file=src_html, by=(By.TAG_NAME, 'body'))
    except Exception as e:
        printred(f'Exception in convert. Error: {e}')

    return

def exit_(code:int=0, start_time:datetime.datetime=None, color:str='Blue'):
    exec_time = ''
    if start_time is not None: 
        end_time = datetime.datetime.now()
        exec_time = f' Execution time {end_time - start_time}'
    
    printcolor(f'Process finished @ {end_time.strftime("%Y-%m-%d %H:%M:%S")}. {exec_time}',color)
    exit(code)

def save_job_list(jobs, location):
    try:
        base_path = jobs[0].base_path
        loc = make_valid_path(location)
        path_relevant_remote = os.path.join(base_path, 'relevant', '_remote')
        os.makedirs(path_relevant_remote, exist_ok=True)
        path_relevant_loc = os.path.join(base_path, 'relevant', loc)
        os.makedirs(path_relevant_loc, exist_ok=True)
        path_x_relevant_loc = os.path.join(base_path, 'x_relevant', loc)
        os.makedirs(path_x_relevant_loc, exist_ok=True)
        path_x_relevant_remote = os.path.join(base_path, 'x_relevant', '_remote')
        os.makedirs(path_x_relevant_remote, exist_ok=True)
        for job in jobs:
            try:
                # saving job_desc.txt
                #       job_desc_summary.txt
                #       job.json
                easy = '.easy' if job.is_easyApply else ''
                fn_co = f'{make_valid_path(job.company) if job._truncated_company_name is None or len(job._truncated_company_name) == 0 else job._truncated_company_name}'
                fn_title =f'.{make_valid_path(job.title) if job.abbreviated_position is None or len(job.abbreviated_position) == 0 else job.abbreviated_position}'
                fn_op = f'.{job.office_policy}'
                fn_easy = 'easy_apply' if job.is_easyApply else 'site_apply'
                fn_relevant = 'rlvnt' if job.is_relevant else 'not_rlvnt'
                fn = f'{job.date_time_string}.{fn_co}.{fn_title}.{fn_op}.{fn_relevant}.{fn_easy}.{job.id}'

                if job.is_relevant:
                    if job.office_policy.lower() == 'remote':
                        path = path_relevant_remote
                    else:
                        path = path_relevant_loc
                else:
                    if job.office_policy.lower() == 'remote':
                        path = path_x_relevant_remote
                    else:
                        path = path_x_relevant_loc

                os.makedirs(os.path.join(path, fn), exist_ok=True)
                with open(os.path.join(path, fn,'job_desc.txt'), 'w', encoding='utf-8') as f:
                    f.write(job.description)
                with open(os.path.join(path, fn, 'job_desc_summary.txt'), 'w', encoding='utf-8') as f:
                    f.write(job.job_description_summary)
                with open(os.path.join(path, fn, 'job.json'), 'w', encoding='utf-8') as f:
                    s = job.serialize()
                    f.write(s)
                with open(os.path.join(path, fn, f'linkedin_job_{job.id}.url'), 'w', encoding='utf-8') as f:
                    f.write(f"[InternetShortcut]\nURL={job.link}\n")
            except Exception as e:
                printred(f"Exception while saving job id {job.id}. Error {e}")
                print(traceback.format_exc())

    except Exception as ex:
        printred(f"Exception while saving job list. Error {ex}")
        print(traceback.format_exc())


@click.command()
#@click.option('--resume', type=click.Path(exists=False, file_okay=True, dir_okay=False, path_type=Path), help="Path to the resume PDF file")
@click.option('--resume', type=str, default=None, help="Path to the resume PDF file")
@click.option('--plain', type=str, default="plain_text_resume.yaml", help="Path to default plain text resume yaml file")
@click.option('--secret', type=str, default="secrets.yaml", help="Path to default plain text resume yaml file")
@click.option('--config', type=str, default="config.yaml", help="Path to default plain text resume yaml file")
@click.option('--jobs', type=str, default=r'Jobs', help=r'Path to the jobs output folder. Default value `data_folder\output\Jobs`')
@click.option('--data_folder', type=str, default=r'data_folder', help='Path to the output data folder. Default value `data_folder`')
@click.option('--debug', type=str, default='False', help='is application being debugged')
@click.option('--css',type=str, default = 'style_hawk.css', help='path to a style sheet')
@click.option('--resume_template',type=str, default = 'hawk_resume_template.html', help='file name resume template')
@click.option('--lkdn', type=str, default=None, help="Linkedin URL to job description - requires linkedin login")
@click.option('--job_url', type=str, default=None, help="URL to job description - can be read without logging in (non-linkedin)")
@click.option('--linkedin_id', type=str, default=None, help="Jobid on linkedin. Requires logging in")
@click.option('--job_file_desc', type=str, default=None, help="Text file that contains job description")
@click.option('--llm_cheap', type=str, default='gpt-4o-mini', help="cheap LLM model to use for tasks")
@click.option('--llm', type=str, default='gpt-4o', help="LLM model")
@click.option('--src_html', type=str, default=None, help="Run just conversion of html file to pdf. --resume option is required")
@click.option('--easy_apply', is_flag=True, help='If shall continue to fill in easy_apply')
@click.option('--mode', type=click.Choice(['search_apply', 'convert', 'resume_lkdin', 'apply_txt', 'apply_url', 'search_lkdin']), default='search_apply', help='Mode of operation choose one of - search and apply(default), convert html to pdf and text, apply one that is provide')
def main(resume, plain, secret, config, jobs, data_folder, debug, css, resume_template,
         lkdn, job_url, linkedin_id, job_file_desc, llm_cheap, llm, src_html, easy_apply, mode):

    start_time = datetime.datetime.now()
    printcolor(f'Process started @ {start_time.strftime("%Y-%m-%d %H:%M:%S")}', "Blue")

    clickParam = ClickParam(resume, plain, secret, config, jobs, data_folder, debug, css, resume_template,
                            lkdn, job_url, linkedin_id, job_file_desc, llm_cheap, llm, src_html, easy_apply, mode)


    # <editor-fold desc="... process config parameters ...">
    secrets_file=None
    config_file=None
    plain_text_resume_file=None
    output_folder=None

    try:
        data_folder = Path(data_folder)
        config_dict = {
            'plain_resume': plain,
            'secrets': secret,
            'config': config
        }

        secrets_file, config_file, plain_text_resume_file, output_folder = FileManager.validate_data_folder(data_folder,
                                                                                                            config_dict,
                                                                                                            jobs_folder=jobs)

        parameters = ConfigValidator.validate_config(config_file)
        email, password, openai_api_key = ConfigValidator.validate_secrets(secrets_file)

        parameters['uploads'] = FileManager.file_paths_to_dict(resume, plain_text_resume_file)
        parameters['outputFileDirectory'] = output_folder.__str__()
        os.environ['OUTPUT_FILE_DIRECTORY'] = output_folder.__str__()

        parameters['jobs'] = jobs
        parameters['css'] = css
        parameters['resume_template'] = resume_template
        EnvironmentKeys.set_key('resume_template', resume_template)

        parameters['llm_cheap'] = llm_cheap
        EnvironmentKeys.set_key(key='llm_cheap', value=llm_cheap)
        parameters['llm'] = llm
        EnvironmentKeys.set_key(key='llm', value=llm)

        os.environ['DEBUG'] = debug
        parameters['DEBUG'] = debug
        printcolor(f'DEBUG flag is set to {debug}', 'Red')
        # </editor-fold>
    except Exception as e:
        printred(f'Failed while processing input paramters. Error: {e}')
        exit_(100, start_time)
    # </editor-fold>

    #convert
    if mode=='convert':
        convert_(clickParam)
        exit_(0, start_time)

    if mode=='resume_lkdin':
        print(f'In apply_lkdin. src={lkdn}')
        if lkdn is None: 
            printred(f'lkdn paramter is None. Should be either valid linkedin url or id. Aborting')
            end_time = datetime.datetime.now()
            printcolor(
                f'Process finished @ {end_time.strftime("%Y-%m-%d %H:%M:%S")}. Execution time {end_time - start_time}',
                "Blue")
            exit_(201, start_time)

        url=lkdn_url(lkdn)
        browser = None
        #try:
        with init_browser() as browser:
            bot = create_bot(email=email, openai_api_key=openai_api_key, parameters=parameters, password=password, browser=browser)
            bot.do_login()
            bot.generate_resume_from_url(url)
        #finally:
        #    browser.close()
        #    browser.quit()

        exit_(0, start_time)

    if mode=='search_lkdin':
        exit_code=0

        browser = init_browser()
        bot = create_bot(email=email, openai_api_key=openai_api_key, parameters=parameters, password=password,
                         browser=browser)
        bot.do_login()

        searches = bot.apply_component.get_searches()
        print(f'starting {len(searches)} searches')
        no_expected = 0
        job_list= []
        for position, location in searches:
            nn = 0
            jobs = bot.apply_component.get_jobs_from_search(position=position, location=location, no_expected=nn)
            if jobs is not None and len(jobs)>0:
                job_list+=jobs
                no_expected+=nn
                save_job_list(jobs, location)
                print(f'Expected: {nn} jobs. Retrieved {len(jobs)} jobs from {location} for {position}')

        print(f'Expected: {no_expected} jobs. Retrieved {len(job_list)} jobs from {len(searches)} searches')


        #bot.generate_job_list_from_search(search_param)

        exit_(exit_code, start_time)



    #scan and apply
    try:
        # only one (or none) of the job options are allowed. If more than one is specified, only the first valid one is used
        # can infer probably
        job_in=(False, '', None)
        try:
            if validate_linkedin_url(lkdn):
                job_in = (True, 'linkedin', lkdn)
            elif validate_linkedin_id(linkedin_id):
                job_in = (True, 'linkedin', f'https://www.linkedin.com/jobs/view/{linkedin_id}')
            elif validate_url(job_url):
                job_in = (True, 'url', job_url)
            elif validate_job_file_desc(job_file_desc):
                job_in = (True, 'desc', job_file_desc)
        except:
            pass
        parameters['job_desc']=job_in

        create_and_run_bot(email, password, parameters, openai_api_key)
    except ConfigError as ce:
        print(f"Configuration error: {str(ce)}")
        print("Refer to the configuration guide for troubleshooting: https://github.com/feder-cr/LinkedIn_AIHawk_automatic_job_application/blob/main/readme.md#configuration")
    except FileNotFoundError as fnf:
        print(f"File not found: {str(fnf)}")
        print("Ensure all required files are present in the data folder.")
        print("Refer to the file setup guide: https://github.com/feder-cr/LinkedIn_AIHawk_automatic_job_application/blob/main/readme.md#configuration")
    except RuntimeError as re:

        print(f"Runtime error: {str(re)}")

        print("Refer to the configuration and troubleshooting guide: https://github.com/feder-cr/LinkedIn_AIHawk_automatic_job_application/blob/main/readme.md#configuration")
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        print("Refer to the general troubleshooting guide: https://github.com/feder-cr/LinkedIn_AIHawk_automatic_job_application/blob/main/readme.md#configuration")

    end_time = datetime.datetime.now()
    printcolor(f'Process finished @ {end_time.strftime("%Y-%m-%d %H:%M:%S")}. Execution time {end_time-start_time}', "Blue")


if __name__ == "__main__":
    main()
