import datetime
import json
import os.path
import re
from typing import Type, TypeVar
from dataclasses import dataclass, asdict, astuple
import pathlib
from src.utils import printcolor,printred,printyellow
from src.utils import EnvironmentKeys
from src.utils import is_valid_non_empty_string, make_valid_os_path_string, make_valid_path, get_state_from_loc, get_id_from_linkedin_url
from src.utils import custom_job_serializer, deserialize
import traceback
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
    id: str = ""
    _date_time: datetime.datetime = None
    title: str =''
    company: str=''
    location_raw: str=''
    apply_method: str = 'unk'
    description: str = ""
    compensation: str=""
    _office_policy: str = "unk"
    job_description_summary: str = ""
    link: str = ''
    skills = []
    quals = []
    recruiter_link: str = ""
    resume_path: str = ''
    location: str = ''
    relevancy: str='unk'
    is_relevant_confidence: str='unk'
    industry: str = 'unk'
    family: str='unk'
    experience_level:str=''
    _user_path: str = None
    _applied: str = 'unk'
    _abbreviated_position: str= None
    _truncated_company_name: str= None
    _search_location: str=None
    _search_position: str=None
    _salary: str=None
    _blacklisted:bool=None
    _created:datetime.datetime=None
    _description_added:datetime.datetime=None
    _resume_added:datetime.datetime=None

    #base_path: str = ''
    #pdf_file: str = ""
    #html_file: str = ""
    #job_file: str = ""
    resume: DocSet = None
    job_docset: DocSet = None
    cover: DocSet = None


    def serialize(self)->str:
        return json.dumps(asdict(self), default=custom_job_serializer)

    #example use: job=Job.deserialize(Job, json_str, job_custom_deserializer)

    def deserialize(self, data: str):
        if is_valid_non_empty_string(data):
        # Load the JSON data into a dictionary, using custom_deserializer to handle special cases
            return deserialize(Job, data)
        else:
            return None


    def save(self, location=None, position=None, base_path=None):
        try:
            if location is None:
                location = self.loc_path
            if position is None:
                position=make_valid_path(self.abbreviated_position, self.title, max_len=35)
            if base_path is None:
                base_path=self.base_path

            loc = make_valid_path(location, max_len=20)
            path_relevant_remote = os.path.join(base_path, 'Relevant', '_Remote')
            path_relevant_loc = os.path.join(base_path, 'Relevant', loc)
            path_x_relevant_loc = os.path.join(base_path, 'X_relevant', loc)
            path_x_relevant_remote = os.path.join(base_path, 'X_relevant', '_Remote')

            fn_co = f'{make_valid_path(self.truncated_co_name, self.company, max_len=20)}'
            fn_op = f'{self.office_policy}' if self.office_policy.lower() in ['remote','hybrid','on-site'] else 'unk'
            fn_easy = 'easy' if self.is_easyApply else 'site'
            fn_relevant = 'rlv' if self.is_relevant else 'x_rlv'
            fn = f'{self.get_dt_string(fmt='%Y-%m-%d')}.{fn_co}.{position}.{fn_op}.{fn_relevant}.{fn_easy}.{self.id}'

            if self.is_relevant:
                if self.office_policy.lower() == 'remote':
                    path = path_relevant_remote
                else:
                    path = path_relevant_loc
            else:
                if self.office_policy.lower() == 'remote':
                    path = path_x_relevant_remote
                else:
                    path = path_x_relevant_loc

            os.makedirs(os.path.join(path, fn), exist_ok=True)
            try:
                with open(os.path.join(path, fn, 'desc.txt'), 'w', encoding='utf-8') as f:
                    f.write(self.description)
            except Exception as e:
                printred(f'ERROR while saving job description for job id {self.id}. Error: {e}')
            try:
                with open(os.path.join(path, fn, 'desc_summary.txt'), 'w', encoding='utf-8') as f:
                    f.write(self.job_description_summary)
            except Exception as e:
                printred(f'ERROR while saving job description summary for job id {self.id}. Error: {self.id}')
            try:
                with open(os.path.join(path, fn, 'job.json'), 'w', encoding='utf-8') as f:
                    s = self.serialize()
                    f.write(s)
            except Exception as e:
                printred(f'ERROR while serializing job id {self.id}. Error: {self.id}')
            try:
                with open(os.path.join(path, fn, f'job_{self.id}.url'), 'w') as f:
                    f.write(f"[InternetShortcut]\nURL={self.link}\n")
            except Exception as e:
                printred(f"Exception while saving shortcut for id {self.id}. Error {e}")
        except Exception as e:
            printred(f'ERROR while saving job id {self.id}. Error: {self.id}')
            print(traceback.format_exc())

    @property
    def search_location(self):
        return make_valid_os_path_string(self._search_location)

    @property
    def search_position(self):
        return make_valid_os_path_string(self.title)
    def __post_init__(self):
        if id == "": self.set_id_from_link(self.link)
        self.set_office_policy(Job.get_office_policy_from_raw_location(self.location_raw))
        self.location=Job.get_location_from_raw(self.location_raw) if (self.location is None or len(self.location)==0) else self.location
        self.title=self.title.split('\n')[0].strip() if self.title is not None else ''
        self.resume = DocSet('resume')
        self.job_docset=DocSet('job')
        self.cover = DocSet('cover')
        #self._created=datetime.datetime.now()
        self.set_date_time()

    def get_list(self, header=True):
        pass
    def get_json_string(self)->str:
        data = {
            "datetime": self.get_dt_string(ms=True),
            "job_id": self.id,
            "job_title": self.title,
            "company_name": self.company,
            "job_location": self.location,
            "office_policy": self._office_policy,
            "job_compensation": self.compensation,
            "is_relevant":self.is_relevant_str,
            "relevant_confidence":self.is_relevant_confidence,
            "applied": self.is_applied,
            "easy_apply": self.is_easyApply,
            "link": self.link,
            "job_recruiter": self.recruiter_link,
            "blacklisted": self._blacklisted if self._blacklisted is not None else 'unk',
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
        return get_id_from_linkedin_url(lnk)
    @staticmethod
    def get_office_policy_from_raw_location(location: str = ""):
        office_policy = 'unk'

        if not is_valid_non_empty_string(location):
            #print(f'Unable to set office policy location is None or zero length')
            return office_policy

        #print(f'Extracting office policy from {location}')
        loc_split = location.split("(")
        if len(loc_split)>1:
            office_policy=loc_split[1][:-1].strip()
        return office_policy

    @staticmethod
    def get_location_from_raw(location: str=""):
        if not is_valid_non_empty_string(location):
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
            "office_policy": self._office_policy,
            "job_compensation": self.compensation,
            "easy_apply": self.is_easyApply,
            "applied": self.is_applied,
            "link": self.link,
            "job_recruiter": self.recruiter_link,
            "base_path": self.base_loc_path,
            "skills": self.skills,
            "quals": self.quals,
            "relevancy": self.is_relevant_str,
            "is_relevant": self.is_relevant,
            "is_relevant_confidence": self.is_relevant_confidence,
            "blacklisted": f'{self._blacklisted}' if self._blacklisted is not None else 'unk',
            "job_desc": self.description,
            "job_desc_summary": self.job_description_summary,
            "industry": self.industry,
            "job_family": self.family,
            "job_desc_file": self.job_docset.txt,
            "resume_pdf": self.resume.pdf,
            "resume_html": self.resume.html
        }
        return data
    #@property
    #def base_path(self):


    @property
    def is_blacklisted(self)->bool:
        return self._blacklisted
    @property
    def is_relevant_str(self):
        if self.relevancy is None or self.relevancy=='unk': return 'relev_unk'
        return 'relevant' if self.is_relevant else 'not_relevant'
    @property
    def is_relevant(self) ->bool:
        rel = False
        if self.relevancy is not None:
            rel = self.relevancy.lower() in ['y','yes', '1', 'on', 't','true']
        return rel
    @is_relevant.setter
    def is_relevant(self, value):
        self.relevancy = value
    @property
    def abbreviated_position(self):
        if (self._abbreviated_position is None or len(self._abbreviated_position)==0):
            txt = 'UnkPosition'
            if self.title:
                txt=self.title
                pattern_replacement_list = [
                    ('Senior','Sr'),
                    ('Director', 'Dir'),
                    ('Manager', 'Mgr'),
                    ('Management','Mgmt'),
                    ('Product', 'Prod'),
                    ('Vice President', 'VP'),
                    ('Software', 'SW'),
                    ('Engineering', 'Eng'),
                    ('Machine Learning','ML'),
                    ('Artificial Intelligence','AI'),
                    ('Data Science', 'DS'),
                    ('Development', 'Dev'),
                    ('Business','Bus'),
                    ('Corporate', 'Corp'),
                    ('Project', 'Proj'),
                    ('President', 'Pres'),
                    ('Operations', 'Oper'),
                    ('Architect','Arch'),
                    ('Technical', 'Tech'),
                    ('Recruitment', 'Recr'),
                    ('Solution', 'Sol'),
                    ('Solutions', 'Sols'),
                    ('Program', 'Prgm'),
                    ('Platform', 'Pfrm'),
                    ('Scientist', 'Scntst'),
                    ('Customer', 'Cust'),
                    ('Temporary', 'Temp'),
                    ('Technology', 'Tech'),
                    ('Technologies', 'Techs'),
                    ('Principal','Princ'),
                    ('Generative', 'Gen'),
                    ('Community', 'Comnty'),
                    ('Finance', 'Fin'),
                    ('Corporate', 'Corp'),
                    ('Economics', 'Econ'),
                    ('Marketing', 'Mktg'),
                    ('Fullfilment', 'Ffmnt'),
                    ('Research', 'Rsch'),
                    ('Qualitative', 'Qual'),
                    ('Quality Assurance', 'QA'),
                    ('Performance', 'Perf'),
                    ('Business Intelligence', 'BI'),
                    ('Manufacturing', 'Manuf'),
                    ('Information','Inf'),
                    ('Application','App'),
                    ('Biostatistics','Biostat'),
                    ('Statistics','Stat')
                ]
                for p, r in pattern_replacement_list:
                    txt = re.sub(p, r, txt, flags=re.IGNORECASE)
            return make_valid_path(txt)
        else:
            return self._abbreviated_position

    @staticmethod
    def _get_truncated(str, delim=r'[,\-\s;:\\/()]+', unk='unk'):
        if str is None or len(str)==0: return unk
        delim = r'[,\-\s;:\\/()]+'
        # Use regular expression to split by spaces, commas, dashes, semicolons, and colons
        # The pattern includes: space (\s), comma (,), dash (-), semicolon (;), colon (:)
        parts = re.split(delim, str)
        # Remove any empty strings from the resulting list
        parts = [part for part in parts if part]
        return parts[0]

    def get_truncated_co_name(self):
        if self._truncated_company_name is not None:
            return  self._truncated_company_name

        if self.company is None or len(self.company)==0:
            return 'co_'

        return Job._get_truncated(self.company, unk='co_')

    @property
    def truncated_co_name(self):
        return self.get_truncated_co_name()

    @property
    def date_time_string(self):
        return self.get_dt_string()

    def get_dt_string(self, ms=False, fmt=None):
        self.set_date_time() #setting date_time only if it has not been set before
        if fmt is not None:
            return self._date_time.strftime(fmt)
        if ms:
            return self._date_time.strftime("%Y-%m-%d_%H%M%S.%f")[:-3]

        return self._date_time.strftime("%Y-%m-%d_%H%M%S")

    def set_date_time(self, overwrite=False):
        if overwrite or self._date_time is None:
            self._date_time = datetime.datetime.now()

    # base_path\DT.ID.co.pos\
    @property
    def path(self):
        return self.get_path()
    def get_path(self):
        name = self.get_fname()
        loc = make_valid_path(get_state_from_loc(self.location)) if self.location is not None else 'loc_unk'

        if name is None:
            return self.base_loc_path
        else:
            return os.path.join(self.base_path, self.is_relevant_str, loc, name)

    def get_fname(self):
        self.set_date_time()  # setting it only if it has not been set before
        office_policy = f'.{self._office_policy}' if self._office_policy.lower() in ['remote', 'hybrid'] else ''
        co_name = f'.{self.truncated_co_name}' if self.truncated_co_name is not None else '.Co_'
        pos = f'.{self.abbreviated_position}'
        fname = f'{self.get_dt_string(fmt='%Y-%m-%d')}{co_name}{pos}{office_policy}.{self.id}'
        return fname
    @property
    def fname(self):
        return self.get_fname()

    @staticmethod
    def get_base_path(dt:datetime.datetime = None):
        if dt is None:
            dt_str = datetime.datetime.now().strftime("%Y-%m-%d")
        else:
            dt_str = dt.strftime("%Y-%m-%d")
        return os.path.join(EnvironmentKeys.get_key('OUTPUT_JOBS_DIRECTORY', False, r'data_folder\output\Jobs\name_s'), dt_str).__str__()

    @property
    def base_path(self):
        if self._date_time is None:
            dt = datetime.datetime.now()
        else:
            dt = self._date_time
        return Job.get_base_path(dt)

    @property
    def base_loc_path(self):
        return self.get_base_loc_path()

    @property
    def loc_path(self)->str:
        loc = ''
        if is_valid_non_empty_string(self.search_location):
            loc = self.search_location
        elif is_valid_non_empty_string(self.location):
            loc_split = self.location.split(',')
            if len(loc_split)>1:
                loc = loc_split[1].strip()
        return make_valid_path(loc) if loc is not None else ''
    def get_base_loc_path(self):
        loc = self.loc_path
        if loc is None or len(loc)==0:
            base_loc_path = Job.get_base_path()
        else:
            base_loc_path = os.path.join(Job.get_base_path(), loc)

        return base_loc_path
    @property
    def applied_file(self):
        return os.path.join(self.get_path(), f'.{DocSet.key_applied}')
    @property
    def is_applied(self)->bool:
        return os.path.exists(self.applied_file)

    def get_csv(self, delim=',', header = False):
        data = self.json


    #ToDo: check and move from 'ready' to 'applied'
    def set_applied(self):
        path = self.get_path()
        if os.path.exists(path):
            with open(os.path.join(path, f'.{DocSet.key_applied}'),'w'): pass

        self.applied = True
    def set_office_policy_from_raw_location(self, raw_location, overwrite = False):
        self.set_office_policy(policy=Job.get_office_policy_from_raw_location(raw_location), overwrite=overwrite)
        return self._office_policy

    def set_office_policy(self, policy="unk", overwrite=False):
        if policy == self._office_policy: return
        if overwrite or self._office_policy is None or self._office_policy == "" or self._office_policy == 'unk':
            if policy.lower() in ['unk', 'on-site', 'hybrid', 'remote']:
                self._office_policy = policy
            else:
                print(f'WARNING: Attempt setting office_policy to undefined value {policy} for job {self.id}. Current office policy is {self._office_policy}. Aborting')
        else:
            print(f'WARNING: Attempt overwriting current office_policy value: `{self._office_policy}` with value: `{policy}` for job {self.id}. Overwrite flag is {overwrite}. Aborting')

    @property
    def office_policy(self):
        if self._office_policy is None: return 'unk'
        return self._office_policy

    @office_policy.setter
    def office_policy(self, value):
        self.set_office_policy(value)

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
