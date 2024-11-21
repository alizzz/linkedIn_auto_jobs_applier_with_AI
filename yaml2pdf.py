import argparse
import pkgutil
#print([module.name for module in pkgutil.iter_modules()])
import copy
import yaml
import tempfile
import sys
import os
#sys.path.append(os.path.abspath('../lib_resume_builder_AIHawk/lib_resume_builder_AIHawk'))
#sys.path.append(os.path.abspath('../lib_resume_builder_AIHawk'))
sys.path.append(r'C:\Users\al\PycharmProjects\lib_resume_builder_AIHawk')

from html2pdf import html2pdf, find_files, unique_file_name
from src.global_config import GlobalConfig

from lib_resume_builder_AIHawk.resume import Resume

from lib_resume_builder_AIHawk.html_resume import HtmlResume
from lib_resume_builder_AIHawk.html_cover import HtmlCover






import pdfkit
import re
import os

gc = GlobalConfig.create('html2pdf.config')


CSS_FILE = r'C:\Users\al\PycharmProjects\lib_resume_builder_AIHawk\lib_resume_builder_AIHawk\resume_style\style_hawk_al_blue.css'

def yaml2pdf(data_yaml, css):
    print(sys.path)
    if not data_yaml: return

    r = Resume(data_yaml)

    resume = HtmlResume(r).html_doc(css_file=css)
    cover = HtmlCover(r).html_doc(css_file=css)
    print(f'len cover = {len(cover)}')
    base_name = os.path.splitext(os.path.splitext(data_yaml)[0])[0]

    files = []
    if resume:
        fn = unique_file_name(f'{base_name}.Resume.html')
        with open(fn, 'w', encoding='utf-8') as f:
            f.write(resume)
            html2pdf(html=fn, pdf=None, css=css)
    if cover:
        fn = unique_file_name(f'{base_name}.Cover.html')
        with open(fn, 'w', encoding='utf-8') as f:
            print(f'saving cover to {fn}. css={css}')
            f.write(cover)
            html2pdf(html=fn, pdf=None, css=css)

if __name__ == "__main__":
    id=gc.get("id")
    bp = gc.get('base_path')
    yaml_files = find_files(id, base_path=bp, pattern='.yaml')
    if not yaml_files:
        print(f'Error. Unable to find source path for id: {id}')
        exit(1)

    yaml2pdf(yaml_files[-1], css=gc.css)

