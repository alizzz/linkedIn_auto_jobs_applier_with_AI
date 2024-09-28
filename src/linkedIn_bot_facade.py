from src.gpt import GPTAnswerer
import datetime
import base64
import os
import traceback

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
    def __init__(self, login_component, apply_component):
        self.login_component = login_component
        self.apply_component = apply_component
        self.state = LinkedInBotState()
        self.job_application_profile = None
        self.resume = None
        self.email = None
        self.password = None
        self.parameters = None

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

    def start_login(self):
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
                        _file_name = f'{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.Resume.frm_file'
                        self._generate_resume(url=None, text=text, file_name_out=_file_name)
                else:
                    print(f"WARNING: File doesn't exist. In generate_resume_from_src reading from file {file}")
            except Exception as e:
                print(f'Exception: In generate_resume_from_src reading from file {file} Error {e}')
        elif text is not None:
            _file_name = f'{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.Resume.frm_txt'
            self._generate_resume(url=None, text=text, file_name_out=_file_name)

    def generate_resume_from_url(self, url, is_linkedin:bool=True):
        if is_linkedin:
            self.start_login()
            job_desc_id = url.split('/')[-1]
            _file_name = f'{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.{job_desc_id}.Resume'
        else:
            _file_name = f'{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.Resume'

        self._generate_resume(url=url, text=None, file_name_out=_file_name)

    def _generate_resume(self, url=None, text=None, file_name_out=None):
        try:
            output_folder = os.environ.get('OUTPUT_JOBS_DIRECTORY')
            pdf64 = self.apply_component.resume_generator_manager.pdf_base64(job_description_url=url,
                                                                             job_description_text=text,
                                                                             html_file_name=os.path.join(output_folder,
                                                                                                         f'{file_name_out}.html'),
                                                                             delete_html_file=False)

            pdf_data = base64.b64decode(pdf64)

            with open(os.path.join(output_folder, f'{file_name_out}.pdf'), "xb") as f:
                f.write(pdf_data)
        except Exception as e:
            print(f"Exception generating resume from url {url}. Error {e}")
            print(f'Traceback {traceback.format_exc()}')