import datetime
from dataclasses import dataclass

@dataclass
class Job:
    title: str
    company: str
    location: str
    link: str
    apply_method: str
    description: str = ""
    summarize_job_description: str = ""
    pdf_path: str = ""
    recruiter_link: str = ""
    html_path: str = ""
    compensation: str=""
    applied: str='unk'
    id: str = ""

    def set_application_status(self, status='unk'):
        self.applied = f'{status} on {datetime.datetime.now().strftime('%Y-%m-%d.%H-%M-%S.%f')[:-3]}'
    def set_compensaton(self, compensation):
        self.compensation = compensation
    def set_html_path(self, html_path):
        self.html_path = html_path

    def set_summarize_job_description(self, summarize_job_description):
        self.summarize_job_description = summarize_job_description

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
