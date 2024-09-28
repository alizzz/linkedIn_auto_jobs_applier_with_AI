import datetime
import os
import re
import sys
import base64
import traceback
from pathlib import Path
from urllib.parse import urlparse
import yaml
import click
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import WebDriverException, TimeoutException
from lib_resume_builder_AIHawk import Resume,StyleManager,FacadeManager,ResumeGenerator
from src.utils import chromeBrowserOptions
from src.utils import printcolor, printyellow, printred
from src.utils import EnvironmentKeys
#from lib_resume_builder_AIHawk.utils import get_dict_names_from_dir
from src.gpt import GPTAnswerer
from src.linkedIn_authenticator import LinkedInAuthenticator
from src.linkedIn_bot_facade import LinkedInBotFacade
from src.linkedIn_job_manager import LinkedInJobManager
from src.job_application_profile import JobApplicationProfile

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
            'titleBlacklist': list
        }

        for key, expected_type in required_keys.items():
            if key not in parameters:
                if key in ['companyBlacklist', 'titleBlacklist']:
                    parameters[key] = []
                else:
                    raise ConfigError(f"Missing or invalid key '{key}' in config file {config_yaml_path}")
            elif not isinstance(parameters[key], expected_type):
                if key in ['companyBlacklist', 'titleBlacklist'] and parameters[key] is None:
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

class FileManager:
    @staticmethod
    def find_file(name_containing: str, with_extension: str, at_path: Path) -> Path:
        return next((file for file in at_path.iterdir() if name_containing.lower() in file.name.lower() and file.suffix.lower() == with_extension.lower()), None)

    @staticmethod
    def validate_data_folder(app_data_folder: Path, required_dict: dict = None, jobs_folder: str=None) -> tuple:
        if not app_data_folder.exists() or not app_data_folder.is_dir():
            raise FileNotFoundError(f"Data folder not found: {app_data_folder}")

        if required_dict is None:
            required_dict = {
                'plain_resume': 'plain_text_resume.yaml',
                'secrets': 'secrets.yaml',
                'config': 'config.yaml'
            }
        #required_files = ['secrets.yaml', 'config.yaml', 'plain_text_resume.yaml']
        missing_files = [file for file in required_dict.values() if not (app_data_folder / file).exists()]
        if missing_files:
            raise FileNotFoundError(f"Missing files in the data folder: {', '.join(missing_files)}")

        output_folder = app_data_folder / 'output'
        output_folder.mkdir(exist_ok=True)

        print(f"loading config files: {','.join(required_dict.values())}")
        return (app_data_folder / required_dict["secrets"], app_data_folder / required_dict["config"], app_data_folder / required_dict["plain_resume"], output_folder)

    @staticmethod
    def file_paths_to_dict(resume_file: Path | None, plain_text_resume_file: Path) -> dict:
        if not plain_text_resume_file.exists():
            raise FileNotFoundError(f"Plain text resume file not found: {plain_text_resume_file}")

        result = {'plainTextResume': plain_text_resume_file}

        if resume_file:
            if not resume_file.exists():
                raise FileNotFoundError(f"Resume file not found: {resume_file}")
            result['resume'] = resume_file

        return result

def init_browser() -> webdriver.Chrome:
    try:
        options = chromeBrowserOptions()
        service = ChromeService(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)
    except Exception as e:
        raise RuntimeError(f"Failed to initialize browser: {str(e)}")

def create_and_run_bot(email: str, password: str, parameters: dict, openai_api_key: str):
    try:
        style_manager = StyleManager(styles_file=parameters['css'])
        resume_generator = ResumeGenerator()
        with open(parameters['uploads']['plainTextResume'], "r", encoding='iso-8859-1') as file:
            plain_text_resume = file.read()
        resume_object = Resume(plain_text_resume)
        resume_generator_manager = FacadeManager(openai_api_key, style_manager, resume_generator, resume_object, Path("data_folder/output"))
        os.system('cls' if os.name == 'nt' else 'clear')
        resume_generator_manager.choose_style()
        os.system('cls' if os.name == 'nt' else 'clear')
        
        job_application_profile_object = JobApplicationProfile(plain_text_resume)
        
        browser = init_browser()
        login_component = LinkedInAuthenticator(browser)
        apply_component = LinkedInJobManager(browser)
        gpt_answerer_component = GPTAnswerer(openai_api_key)
        bot = LinkedInBotFacade(login_component, apply_component)
        bot.set_secrets(email, password)
        bot.set_job_application_profile_and_resume(job_application_profile_object, resume_object)
        bot.set_gpt_answerer_and_resume_generator(gpt_answerer_component, resume_generator_manager)
        bot.set_parameters(parameters)

        _jobs_folder = parameters['jobs']
        user_dir = 'name_s'
        try:
            user_dir = f'{bot.resume.personal_information.name}_{bot.resume.personal_information.surname[0]}'
        except:
            pass
        jobs_folder = Path(parameters['outputFileDirectory'], _jobs_folder if _jobs_folder is not None else 'Jobs', user_dir)
        os.makedirs(jobs_folder, exist_ok=True)

        parameters['outputJobsDirectory'] = jobs_folder.__str__()
        os.environ["OUTPUT_JOBS_DIRECTORY"]=jobs_folder.__str__()

        bot.start_login()

        job_desc = parameters['job_desc']
        if job_desc[0]:
            if job_desc[1]=='linkedin':
                try:
                    job_desc_id = job_desc[2].split('/')[-1]
                    _file_name = f'{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.{job_desc_id}.Resume'
                    pdf64 = resume_generator_manager.pdf_base64(job_description_url = job_desc[2], job_description_text = None,
                                                                html_file_name=os.path.join(jobs_folder, f'{_file_name}.html'), delete_html_file=False)

                    pdf_data = base64.b64decode(pdf64)

                    with open(os.path.join(jobs_folder, f'{_file_name}.pdf'), "xb") as f:
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

def validate_job_file_desc(job_file_desc):
    if job_file_desc is None or len(job_file_desc)==0: return False
    if os.path.exists(job_file_desc):
        return True
    return False


@click.command()
@click.option('--resume', type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path), help="Path to the resume PDF file")
@click.option('--plain', type=str, default="plain_text_resume.yaml", help="Path to default plain text resume yaml file")
@click.option('--secret', type=str, default="secrets.yaml", help="Path to default plain text resume yaml file")
@click.option('--config', type=str, default="config.yaml", help="Path to default plain text resume yaml file")
@click.option('--jobs', type=str, default=r'Jobs', help=r'Path to the jobs output folder. Default value `data_folder\output\Jobs`')
@click.option('--data_folder', type=str, default=r'data_folder', help='Path to the output data folder. Default value `data_folder`')
@click.option('--debug', type=str, default='False', help='is application being debugged')
@click.option('--css',type=str, default = 'style_hawk.css', help='path to a style sheet')
@click.option('--resume_template',type=str, default = 'hawk_resume_template.html', help='file name resume template')
@click.option('--linkedin_url', type=str, default=None, help="Linkedin URL to job description - requires linkedin login")
@click.option('--job_url', type=str, default=None, help="URL to job description - can be read without logging in (non-linkedin)")
@click.option('--linkedin_id', type=str, default=None, help="Jobid on linkedin. Requires logging in")
@click.option('--job_file_desc', type=str, default=None, help="Text file that contains job description")
@click.option('--llm_cheap', type=str, default='gpt-4o-mini', help="cheap LLM model to use for tasks")
@click.option('--llm', type=str, default='gpt-4o', help="LLM model")
def main(resume: Path = None, plain: str = None, secret: str = None, config: str = None, jobs: str=None, data_folder: str=None, debug:str=None, css:str=None, resume_template:str=None,
         linkedin_url: str=None, job_url: str=None, linkedin_id: str = None, job_file_desc:str=None,
         llm_cheap: str=None, llm: str=None):

    try:
        data_folder = Path(data_folder)
        config_dict = {
            'plain_resume': plain,
            'secrets': secret,
            'config': config
        }

        secrets_file, config_file, plain_text_resume_file, output_folder = FileManager.validate_data_folder(data_folder, config_dict, jobs_folder=jobs)
        
        parameters = ConfigValidator.validate_config(config_file)
        email, password, openai_api_key = ConfigValidator.validate_secrets(secrets_file)
        
        parameters['uploads'] = FileManager.file_paths_to_dict(resume, plain_text_resume_file)
        parameters['outputFileDirectory'] = output_folder.__str__()
        os.environ['OUTPUT_FILE_DIRECTORY'] = output_folder.__str__()

        parameters['jobs'] = jobs
        parameters['css'] = css
        parameters['resume_template']=resume_template
        EnvironmentKeys.set_key('resume_template', resume_template)

        # only one (or none) of the job options are allowed. If more than one is specified, only the first valid one is used
        # can infer probably
        job_in=(False, '', None)
        try:
            if validate_linkedin_url(linkedin_url):
                job_in = (True, 'linkedin', linkedin_url)
            elif validate_linkedin_id(linkedin_id):
                job_in = (True, 'linkedin', f'https://www.linkedin.com/jobs/view/{linkedin_id}')
            elif validate_url(job_url):
                job_in = (True, 'url', job_url)
            elif validate_job_file_desc(job_file_desc):
                job_in = (True, 'desc', job_file_desc)
        except:
            pass
        parameters['job_desc']=job_in

        parameters['llm_cheap'] = llm_cheap
        EnvironmentKeys.set_key(key='llm_cheap', value=llm_cheap)
        parameters['llm'] = llm
        EnvironmentKeys.set_key(key='llm',value=llm)

        os.environ['DEBUG']=debug
        parameters['DEBUG']=debug
        printcolor(f'DEBUG flag is set to {debug}','Red')

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

if __name__ == "__main__":
    main()
