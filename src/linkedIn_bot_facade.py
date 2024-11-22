import datetime
import base64
import datetime
import json
import os
import traceback
from pathlib import Path

from lib_resume_builder_AIHawk import Resume, StyleManager, FacadeManager, ResumeGenerator
from lib_resume_builder_AIHawk.resume import PersonalInformation
#from src.gpt import GPTAnswerer
from src.job import Job
from lib_resume_builder_AIHawk.gpt_resume_job_description import LLMResumeJobDescription
from src.job_application_profile import JobApplicationProfile
from src.linkedIn_authenticator import LinkedInAuthenticator
from src.linkedIn_job_manager import LinkedInJobManager
from src.utils import make_valid_path, read_file_content, is_valid_non_empty_string


class LinkedInBotState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.credentials_set = False
        self.api_key_set = False
        self.job_application_profile_set = False
        self.gpt_answerer_set = False
        self.parameters_set = False
        self.logged_in = False

    def validate_state(self, required_keys):
        for key in required_keys:
            if not getattr(self, key):
                raise ValueError(f"{key.replace('_', ' ').capitalize()} must be set before proceeding.")

class LinkedInBotFacade:
    def __init__(self, login_component, apply_component, parameters = None, password = None, email=None, resume=None):
        self.login_component = login_component
        self.apply_component = apply_component
        self.state = LinkedInBotState()
        self.job_application_profile = None
        self.resume = resume
        self.email = email
        self.password = password
        self.parameters = parameters

    @staticmethod
    def create_bot(email, openai_api_key, parameters, password, browser):
        style_manager = StyleManager(styles_file=parameters['css'])
        resume_generator = ResumeGenerator()
        with open(parameters['uploads']['plainTextResume'], "r", encoding='iso-8859-1') as file:
            plain_text_resume = file.read()
        resume_object = Resume(plain_text_resume)
        #ToDo - replace hardcoded string with config parameter
        resume_generator_manager = FacadeManager(openai_api_key, style_manager, resume_generator, resume_object,
                                                 Path("data_folder/output"))
        resume_generator_manager.choose_style()
        job_application_profile_object = JobApplicationProfile(plain_text_resume)
        login_component = LinkedInAuthenticator(browser)
        apply_component = LinkedInJobManager(browser)
        gpt_answerer_component = LLMResumeJobDescription(openai_api_key)
        bot = LinkedInBotFacade(login_component, apply_component)
        bot.set_secrets(email, password)
        bot.set_job_application_profile_and_resume(job_application_profile_object, resume_object)
        bot.set_gpt_answerer_and_resume_generator(gpt_answerer_component, resume_generator_manager)
        bot.set_parameters(parameters)
        return bot

    @property
    def jobs_folder(self):
        _jobs_folder = self.parameters['jobs']
        user_dir = 'name_s'
        try:
            user_dir = f'{self.resume.personal_information.name[0]}_{self.resume.personal_information.surname[0]}'
        except:
            pass
        return Path(self.parameters['outputFileDirectory'], _jobs_folder if _jobs_folder is not None else 'Jobs',
                           user_dir)

    def set_job_application_profile_and_resume(self, job_application_profile, resume):
        self._validate_non_empty(job_application_profile, "Job application profile")
        self._validate_non_empty(resume, "Resume")
        self.job_application_profile = job_application_profile
        self.resume = resume
        self.state.job_application_profile_set = True

    def set_secrets(self, email, password):
        self._validate_non_empty(email, "Email")
        self._validate_non_empty(password, "Password")
        self.email = email
        self.password = password
        self.state.credentials_set = True

    def set_gpt_answerer_and_resume_generator(self, gpt_answerer_component, resume_generator_manager):
        self._ensure_job_profile_and_resume_set()
        gpt_answerer_component.set_job_application_profile(self.job_application_profile)
        gpt_answerer_component.set_resume(self.resume)
        self.apply_component.set_gpt_answerer(gpt_answerer_component)
        self.apply_component.set_resume_generator_manager(resume_generator_manager)
        self.state.gpt_answerer_set = True

    def set_parameters(self, parameters):
        self._validate_non_empty(parameters, "Parameters")
        self.parameters = parameters
        self.apply_component.set_parameters(parameters)
        self.state.parameters_set = True

    def do_login(self):
        self.state.validate_state(['credentials_set'])
        self.login_component.set_secrets(self.email, self.password)
        self.login_component.start()
        self.state.logged_in = True

    def start_apply(self):
        self.state.validate_state(['logged_in', 'job_application_profile_set', 'gpt_answerer_set', 'parameters_set'])
        self.apply_component.start_applying()

    def _validate_non_empty(self, value, name):
        if not value:
            raise ValueError(f"{name} cannot be empty.")

    def _ensure_job_profile_and_resume_set(self):
        if not self.state.job_application_profile_set:
            raise ValueError("Job application profile and resume must be set before proceeding.")

    def generate_resume_from_src(self, url:str=None, file:str=None, text:str=None, is_linkedin:bool=True):
        #check if max one of the parameters is not None
        s = sum([url is None, file is None, text is None])
        if s<2:
            print(f"WARNING: In generate_resume_from_src. Only one of the url, file, text parameters could be not None. Currently there are {3-s} non-null parameters")
            print(f"In generate_resume_from_src. url={url if url is not None else 'None'}, "
              f"file={file if file is not None else 'None'}, text={text if text is not None else 'None'}")

        if url is not None:
            self.generate_resume_from_url(url=url, is_linkedin=is_linkedin)
        elif file is not None:
            try:
                if os.path.exists(file):
                    with open(file, 'r') as f:
                        text = f.read()
                        _file_name = f'{datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")}.Resume.frm_file'
                        self._generate_resume(url=None, text=text, job_title=None, file_name_out=_file_name)
                else:
                    print(f"WARNING: File doesn't exist. In generate_resume_from_src reading from file {file}")
            except Exception as e:
                print(f'Exception: In generate_resume_from_src reading from file {file} Error {e}')
        elif text is not None:
            _file_name = f'{datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")}.Resume.frm_txt'
            self._generate_resume(url=None, text=text, job_title=None, file_name_out=_file_name)


    def get_resume_fn(self, pi:PersonalInformation, param=None):
        return f'{pi.name}.{pi.surname}.Resume'

    #Notes:
    #at least one of job, desc, or desc_summary should be not None
    def generate_resume_from_job_desc(self, job=None, desc:str=None, desc_summary:str=None):
        desc_str = None
        desc_summary_str = None
        job_obj = None
        if sum([job is None, desc is None, desc_summary is None])==0: raise ValueError('Error in generate_resume_from_job_desc: at least one of job, desc, or desc_summary should be not None')
        if desc is not None:
            desc_str = read_file_content(desc) if os.path.exists(desc) else desc
        if desc_summary is not None:
            desc_summary_str = read_file_content(desc_summary) if os.path.exists(desc_summary) else desc_summary
        if job is not None:
            if type(job).__name__=='str':
                #if valid file try deserializing it from file, otherwise try deserializing it from string
                if os.path.exists(job):
                    job_string = read_file_content(job)
                    if job_string is not None:
                        job_obj = Job.deserialize(job_string)
                        if job_obj is None or type(job_obj).name!='Job':
                            job = None
                        else:
                            job = job_obj

            elif type(job).__name__ != 'Job': job=None

            if sum([is_valid_non_empty_string(desc_str), is_valid_non_empty_string(desc_summary_str)])>0:
                job_desc_str = '\n'.join([desc_summary_str if is_valid_non_empty_string(desc_summary_str) else '',
                                          desc_str if is_valid_non_empty_string(desc_str) else ''])
            else:
                job_desc_str = '\n'.join([job.job_description_summary if is_valid_non_empty_string(job.job_description_summary) else '',
                                          job.description if is_valid_non_empty_string(job.description) else ''])

            if not is_valid_non_empty_string(job_desc_str): raise ValueError(f'generate_resume_from_job_desc() no valid job description')

    def generate_resume_from_job(self, job:Job, relevant_only=False, path=None):
        if job is None:
            if is_valid_non_empty_string(path):
                #attempt deserializing job from job.json file from path
                job_json_path = os.path.join(path, 'job.json')
                if os.path.exists(job_json_path):
                    job_json_str = read_file_content(job_json_path)
                    if is_valid_non_empty_string(job_json_str):
                        job = Job.deserialize(job_json_str)

        if job is None: #check again if deserialization worked
            raise AttributeError(message = 'generate_resume_from_job() - job is None and unable to deserialize from path')
        if not is_valid_non_empty_string(path): path = job.path
        if is_valid_non_empty_string(job.relevancy) and job.relevancy.lower != 'unk':
            is_relevant = job.is_relevant
        else:
            is_relevant = self.apply_component.gpt_answerer.is_relevant_job(job)

        if not is_valid_non_empty_string(job.description) and not is_valid_non_empty_string(job.job_description_summary):
            raise ValueError('in generate_resume_from_job. both job.description and job_description summary are not valid string. unable to continue' )

        fn_resume = self.get_resume_fn(self.resume.personal_information, None)
        out_path = path

        if relevant_only and not is_relevant:
            print(
                f'Relevant_only is {relevant_only} and job relevancy is {job.is_relevant_str}. Skipping resume generation for jobid={job.id}')
        else:
            #if is_valid_non_empty_string(job.description) and not is_valid_non_empty_string(job.job_description_summary):
                #jd_summary = self.apply_component.gpt_answerer.summarize_job_description(job=job)
                #job.set_job_description_summary(jd_summary)

            #desc = job.job_description_summary if job.job_description_summary else job.description
                #'\n'.join([job.job_description_summary if is_valid_non_empty_string(job.job_description_summary) else '',
                              #job.description if is_valid_non_empty_string(job.description) else '']))
            #if len(desc)<50:
            #    raise ValueError(f'In generate_resume_from_job(). Job object does not contain valid job description. job-description: {job.description}. Job-description_summary: {job.job_description_summary}')

            #Can probably call directly LLMResumeJobDescription::generate_html_resume
            self._generate_resume(url=None, file_name_out=fn_resume, path=out_path, job=job)


    #This method has a few side effects
    #0. It creates an output directory if it doesn't exist
    #1. it creates at writes resume html
    #2. it creates and writes resume pdf
    #3. it writes job json
    #4. it writes job summary
    def generate_resume_from_url(self, url, relevant_only=False, is_linkedin:bool=True):
        job = self.apply_component.load_job_from_url(url)
        fn_job_desc = f'job.desc.{make_valid_path(job.apply_method)}.{job.is_relevant_str}.txt'
        fn_job_json = f'job.{job.id}.json'
        self.apply_component.gpt_answerer.is_relevant_job(job)
        out_path = job.path

        try:
            self.generate_resume_from_job(job, relevant_only, is_linkedin)
        except Exception as e:
            print(
                f'Failed generate_resume_from_job {job.id}: for {job.fname}. LinkedInBotFacade::generate_resume_from_url() Error:{e}')
            raise e

        os.makedirs(out_path, exist_ok=True)
        try:
            #if not (os.path.exists(os.path.join(out_path, fn_job_desc))):
            with open(os.path.join(out_path, fn_job_desc), 'w', encoding='utf-8') as f:
                f.write('\n**************  JOB DESCRIPTION SUMMARY  **********************\n')
                f.write(job.job_description_summary)
                f.write('\n***************************************************************\n')
                f.write('\n**************  JOB DESCRIPTION RAW  **************************\n')
                f.write(job.description)
        except Exception as e:
            print(f'Failed writing job description for job {job.id}: for {job.fname}. LinkedInBotFacade::generate_resume_from_url()')
        try:
            #write job json
            with open(os.path.join(out_path, fn_job_json), 'w', encoding='utf-8') as f:
                json.dump(job.json, f)
        except Exception as e:
            print(f'Failed writing json for job {job.id}: for {job.fname}. LinkedInBotFacade::generate_resume_from_url()')

        try:
            #write internet shortcut
            with open(os.path.join(out_path, f'job.link.{job.id}.url'), 'w', encoding='utf-8') as f:
                    f.write(f"[InternetShortcut]\nURL={job.link}\n")
        except:
            print(f'Failed writing internet shortcut for job {job.id}: for {job.fname}. LinkedInBotFacade::generate_resume_from_url()')
        print(f'Finished generating resume for {job.fname } from url {url}')

    def _generate_resume(self, url:str=None,  file_name_out=None, path=None, job:Job=None):
        try:
            output_folder = os.environ.get('OUTPUT_JOBS_DIRECTORY') if path is None else path
            if not os.path.exists(output_folder):
                os.makedirs(output_folder, exist_ok=True)

            #html_resume =  self.apply_component.resume_generator_manager.create_html_resume(job,
            #                                                                        html_file_name=os.path.join(output_folder, f'{file_name_out}.html'),
            #                                                                        delete_html_file=False)

           #pdf64 = pdf_base64(html, html_file_name=os.path.join(output_folder,f'{file_name_out}.html'))

            pdf64 = self.apply_component.resume_generator_manager.pdf_base64(job_description_url=url,
                                                                             resume_html_file_name=os.path.join(output_folder,
                                                                                                         f'{file_name_out}.html'),
                                                                             delete_html_file=False, job=job)

            if pdf64:
                pdf_data = base64.b64decode(pdf64)

                fn = os.path.join(output_folder, f'{file_name_out}.pdf')
                if os.path.exists(fn):
                    k=0
                    fn = os.path.join(output_folder, f'{file_name_out}.{k:03}.pdf')
                    while(os.path.exists(fn)):
                        k+=1
                        fn = os.path.join(output_folder, f'{file_name_out}.{k:03}.pdf')
                with open(fn, "xb") as f: f.write(pdf_data)

        except Exception as e:
            print(f"Exception generating resume from url {url}. Error {e}")
            print(f'Traceback {traceback.format_exc()}')

    def generate_job_list_from_search(self, search_param):

        pass