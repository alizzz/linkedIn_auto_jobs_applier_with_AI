import datetime
import json
import os.path
import re
from dataclasses import dataclass
import pathlib
from src.utils import printcolor,printred,printyellow
from src.utils import EnvironmentKeys

@dataclass
class DocSet:
    docset_name: str
    path: str=''
    created: bool=False
    _file_name: str = ''

    def _get_full_name(self, path, name:str='', ext:str = None, check_exists: bool = False):
        if ext is not None:
            if not ext.startswith('.'):
                ext = f'.{ext}'
        else:
            ext = ''
        full_path = os.path.join(path, f'{name}{ext}')
        if check_exists:
            if os.path.exists(full_path):
                return full_path
            else:
                return ''
        else:
            return full_path

    @property
    @staticmethod
    def key_ready(self): return 'ready'
    @property
    @staticmethod
    def key_created(self): return 'ready'
    @property
    @staticmethod
    def key_applied(self): return 'applied'

    @property
    def is_html(self):
        return self._is_valid_file(self._get_full_name(self.path, self._file_name,'.html'))
    @property
    def is_pdf(self):
        return self._is_valid_file(self._get_full_name(self.path, self._file_name,'.pdf'))
    @property
    def is_txt(self):
        return self._is_valid_file(self._get_full_name(self.path, self._file_name,'.txt'))
    @property
    def is_json(self):
        return self._is_valid_file(self._get_full_name(self.path, self._file_name,'.json'))

    def _is_valid_file(self, fn):
        return os.path.exists(os.path.join(self.path, fn))


    @property
    def file_name(self): return self._file_name
    @property
    def pdf(self):
        return self._get_full_name(self.path, self._file_name, '.pdf')
    @property
    def html(self):
        return self._get_full_name(self.path, self._file_name, '.html')
    @property
    def txt(self):
        return self._get_full_name(self.path, self._file_name, '.txt')
    @property
    def json(self): return self._get_full_name(self.path, self._file_name, '.json')

    def set_docset(self, docset_name, path, name):
        self.docset_name=docset_name
        self.path=path
        self._file_name=name


@dataclass
class Job:
    title: str =''
    company: str=''
    location_raw: str=''
    link: str=''
    apply_method: str = 'unk'
    description: str = ""
    job_description_summary: str = ""
    recruiter_link: str = ""
    compensation: str=""
    id: str = ""
    office_policy: str = "unk"
    skills = []
    quals = []
    _user_path: str = None
    _applied: str = 'unk'
    _abbreviated_position: str= None
    _truncated_company_name: str= None
    resume_path: str=''
    location: str =''
    _date_time: datetime.datetime = None
    #base_path: str = ''
    #pdf_file: str = ""
    #html_file: str = ""
    #job_file: str = ""
    resume: DocSet = None
    job_docset: DocSet = None
    cover: DocSet = None

    def __post_init__(self):
        self.title=self.title.split('\n')[0].strip()
        self.resume = DocSet('resume')
        self.job_docset=DocSet('job')
        self.cover = DocSet('cover')
        if id == "": self.set_id_from_link(self.link)
        self.set_office_policy(Job.get_office_policy_from_raw_location(self.location_raw))
        self.location=Job.get_location_from_raw(self.location_raw)

    def get_json_string(self)->str:
        data = {
            "datetime": self.get_dt_string(ms=True),
            "job_id": self.id,
            "job_title": self.title,
            "company_name": self.company,
            "job_location": self.location,
            "office_policy": self.office_policy,
            "job_compensation": self.compensation,
            "applied": self.is_applied,
            "easy_apply": self.is_easyApply,
            "link": self.link,
            "job_recruiter": self.recruiter_link,
            "job_desc_file": os.path.split(self.job_docset.txt)[1],
            "resume_pdf": os.path.split(self.resume.pdf)[1],
            "resume_html": os.path.split(self.resume.html)[1]
        }
        try:
            return json.dumps(data, indent = 4)
        except:
            printred(f"ERROR: failed to create a json object in get_json_string for job id {self.id}")
            return '{}'

    @staticmethod
    def get_id_from_link(lnk):
        if lnk is not None and len(lnk)>0:
            return lnk.split('/')[-2].strip()

    @staticmethod
    def get_office_policy_from_raw_location(location: str = ""):
        office_policy = 'unk'

        if location is None or len(location)==0:
            print(f'Unable to set office policy location is None or zero length')
            return office_policy

        #print(f'Extracting office policy from {location}')
        loc_split = location.split("(")
        if len(loc_split)>1:
            office_policy=loc_split[1][:-1].strip()
        return office_policy

    @staticmethod
    def get_location_from_raw(location: str=""):
        if location is None or len(location)==0:
            return location
        loc = location.split('(')
        loc = loc[0]
        loc = loc.strip()
        return loc

    @property
    def json(self):
        data = {
            "datetime": self.date_time_string,
            "job_id": self.id,
            "job_title": self.title,
            "company_name": self.company,
            "job_location": self.location,
            "office_policy": self.office_policy,
            "job_compensation": self.compensation,
            "applied": self.is_applied,
            "link": self.link,
            "job_recruiter": self.recruiter_link,
            "base_path": self.base_path,
            "skills": self.skills,
            "quals": self.quals,
            "job_desc_file": self.job_docset.txt,
            "resume_pdf": self.resume.pdf,
            "resume_html": self.resume.html
        }
        return data
    #@property
    #def base_path(self):


    @property
    def abbreviated_position(self):
        if (self._abbreviated_position is None or len(self._abbreviated_position)==0):
            return "nnn"
        else:
            return self._abbreviated_position

    def get_truncated_co_name(self):
        return self.truncated_co_name
    @property
    def truncated_co_name(self):
        if self._truncated_company_name is not None:
            return  self._truncated_company_name

        if self.company is None or len(self.company)==0:
            return 'ccc'
        delim = r'[,\-\s;:\\/()]+'
        # Use regular expression to split by spaces, commas, dashes, semicolons, and colons
        # The pattern includes: space (\s), comma (,), dash (-), semicolon (;), colon (:)
        parts = re.split(delim, self.company)
        # Remove any empty strings from the resulting list
        parts = [part for part in parts if part]
        return parts[0]

    @property
    def date_time_string(self):
        return self.get_dt_string()

    def get_dt_string(self, ms=False, fmt=None):
        self.set_date_time() #setting date_time only if it has not been set before
        if fmt is not None:
            return self._date_time.strftime(fmt)
        if ms:
            return self._date_time.strftime("%Y%m%d_%H%M%S.%f")[:-3]

        return self._date_time.strftime("%Y%m%d_%H%M%S")

    def set_date_time(self, overwrite=False):
        if overwrite or self._date_time is None:
            self._date_time = datetime.datetime.now()

    # base_path\DT.ID.co.pos\
    @property
    def path(self):
        return self.get_path()
    def get_path(self):
        self.set_date_time() # setting it only if it has not been set before
        name = f'{self.date_time_string}.{self.truncated_co_name}.{self._abbreviated_position}.{self.id}'
        return os.path.join(self.base_path, name)
    @property
    def base_path(self):
        return self.get_base_path()
    def get_base_path(self):
        return EnvironmentKeys.get_key('OUTPUT_JOBS_DIRECTORY', False, r'data_folder\output\Jobs\name_s')

    @property
    def applied_file(self):
        return os.path.join(self.get_path(), f'.{DocSet.key_applied}')
    @property
    def is_applied(self)->bool:
        return os.path.exists(self.applied_file)

    #ToDo: check and move from 'ready' to 'applied'
    def set_applied(self):
        path = self.get_path()
        if os.path.exists(path):
            with open(os.path.join(path, f'.{DocSet.key_applied}'),'w'): pass

        self.applied = True
    def set_office_policy_from_raw_location(self, raw_location, overwrite = False):
        self.set_office_policy(policy=Job.get_office_policy_from_raw_location(raw_location), overwrite=overwrite)
        return self.office_policy

    def set_office_policy(self, policy="unk", overwrite=False):
        if policy == self.office_policy: return
        if overwrite or self.office_policy == "" or self.office_policy == 'unk':
            if policy.lower() in ['unk', 'on-site', 'hybrid', 'remote']:
                self.office_policy = policy
            else:
                print(f'WARNING: Attempt setting office_policy to undefined value {policy} for job {self.id}. Current office policy is {self.office_policy}. Aborting')
        else:
            print(f'WARNING: Attempt overwriting current office_policy value: `{self.office_policy}` with value: `{policy}` for job {self.id}. Overwrite flag is {overwrite}. Aborting')


    def set_id_from_link(self, job_link):
        self.id = Job.get_id_from_link(job_link)
        return self.id

 #   def set_location(self, location):
 #       if self.location == location: return
 #       if location is None or len(location)==0:
 #           self.location = Job.remove_office_policy_from_location_info(location)
 #       return self.location

    @property
    def is_easyApply(self):
        return self.apply_method=="Easy Apply"

    def set_application_status(self, status='unk'):
        self.applied = status

    def set_compensaton(self, compensation):
        self.compensation = compensation
    def set_html_path(self, html_path):
        self.html_file = html_path

    def set_job_description_summary(self, job_description_summary):
        self.job_description_summary = job_description_summary

    def set_job_description(self, description):
        self.description = description

    def set_recruiter_link(self, recruiter_link):
        self.recruiter_link = recruiter_link

    def formatted_job_information(self):
        """
        Formats the job information as a markdown string.
        """
        job_information = f"""
        # Job Description
        ## Job Information 
        - Position: {self.title}
        - At: {self.company}
        - Location: {self.location}
        - Recruiter Profile: {self.recruiter_link or 'Not available'}
        - Compensation: {self.compensation or 'Not available'}
        
        ## Description
        {self.description or 'No description provided.'}
        """
        return job_information.strip()
