import argparse
import pdfkit
import re
import os

from src.global_config import GlobalConfig
gc = GlobalConfig.create('html2pdf.config')

#def html2pdf(html, pdf=None, css=None):

def find_files(id, base_path, pattern:str='.html'):
    dir_pattern = re.compile((rf"{re.escape(id)}$"))
    search_expression = re.compile(pattern)
    lst_files = []

    # Walk through the directory and subdirectories
    for root, dirs, files in os.walk(base_path):
        if dir_pattern.search(os.path.basename(root)):
            for file in files:
                if bool(search_expression.search(file)):
                    lst_files.append(os.path.abspath(os.path.join(root, file)))
    return lst_files

def find_html_files(id, base_path):
    return find_files(id, base_path=base_path, pattern='.html')

def unique_file_name(fn, counter_width = 4):
    if not os.path.exists(fn): return fn
    base_name, ext = os.path.splitext(fn)
    counter = 0

    # Check if filename has an existing counter at the end (like `file_0003.txt`)
    match = re.search(r".(\d+)$", base_name)
    if match:
        counter = int(match.group(1))
        base_name = base_name[:match.start()]  # Remove existing counter to increment anew
    # Keep incrementing counter until a unique filename is found

    while os.path.exists(f"{base_name}.{str(counter).zfill(counter_width)}{ext}"):
        counter += 1

    return f"{base_name}.{str(counter).zfill(counter_width)}{ext}"


def html2pdf(html, pdf=None, css=None):
    print('In html2pdf')
    # Implement the functionality here


    if not pdf:
        pdf = f'{os.path.splitext(html)[0]}.pdf'
    pdf_ = unique_file_name(pdf)
    print(f"About to create a pdf from html. src is {html}. Output is stored in {pdf_}")

    if css:
        #remove inline css if any
        print('css is supplied. Cleaning up existing style tag')
        pattern = r"<style type=\"text/css\">.*?</style>"
        clean_html=''
        with open(html, 'r', encoding='utf-8') as f:
            html_content = f.read()
            clean_html = re.sub(pattern, "", html_content, flags=re.DOTALL)
            print(f'Before cleanup len(html_cover)={len(html_content)}. After cleanup len(clena_html)={len(clean_html)}')

        html_file = unique_file_name(html)
        with open(html_file, 'w', encoding='utf-8') as fe:
            fe.write(clean_html)
        pdfkit.from_file(html_file, pdf_, css=css)
        os.remove(html_file)
        return
    else:
        html_file = html
        css = ''
        pdfkit.from_file(html_file, pdf_, css=css)

def create_argparser(default_config_path="default_config.yaml"):
    parser = argparse.ArgumentParser(description="Global Config Parser")

    # Explicitly specified arguments
    parser.add_argument("--config", type=str, default=default_config_path, help="Path to the YAML configuration file")
    #parser.add_argument("--mandatory_arg", type=str, required=True, help="A mandatory argument without a default value")
    #parser.add_argument("--optional_arg", type=int, default=42, help="An optional argument with a default value")

    return parser

if __name__ == "__main__":
    id=gc.get("id")
    bp = gc.get('base_path')
    html_files = find_html_files(id, bp)
    if not html_files:
        print(f'Error. Unable to find source path for id: {id}')
        exit(1)

    css = os.path.join(bp, gc.get('css'))

    for html in html_files:
        pdf = os.path.splitext(html)[0]+'.pdf'
        html2pdf(html=html, pdf=pdf, css=css)