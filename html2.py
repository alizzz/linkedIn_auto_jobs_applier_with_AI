import os
import click
import datetime
from src.utils import printc
from lib_resume_builder_AIHawk.utils import HTML_to_PDF

class Utils:
    @staticmethod
    def isdirfile(path)->(bool, bool):
        if not os.path.exists(path):
            return False, False
        return os.path.isdir(path), os.path.isfile(path)

    @staticmethod
    def dirwalk(path, ext='.html'):
        file_list = []
        for root, _, files in os.walk(path):
            for file in files:
                if file.endswith(ext):
                    file_list.append((root, file))

        return file_list


@click.command()
@click.option('--src', type=str, help="Source file or dir. Assumes html")
@click.option('--recursive', '-r', is_Flag=True, help = 'Flag to run this directory and all subdirectories, if --src is a directory')
#ToDo - not implemented
@click.option('--dst', '-d', type=str, default=None, help="Run just conversion of html file to txt.")
@click.option('--pdf', '-p', is_Flag=True, help="Run just conversion of html file to pdf.")
@click.option('--txt', '-t', is_Flag=True, help="Run just conversion of html file to txt.")
@click.option('--overwrite','-o', is_Flag=True, help="Run just conversion of html file to pdf.")
def html2(src, dst, recursive, pdf, txt, overwrite):
    start_time = datetime.datetime.now()
    printc.printcolor(f'Process started @ {start_time.strftime("%Y-%m-%d %H:%M:%S")}', "Blue")
    
    dir = None
    src_ = None
    dst_ = None
    try:
        if os.path.isfile(src):
            src_ = src
            dst_ = src.rsplit(src,1)[0]
        elif os.path.isdir(src):
            html_files = []
            # Loop through the files in the directory
            for file in os.listdir(src):
                if file.endswith(".html"):
                    html_files.append(os.path.join(src, file.rsplit('.',1)[0]))

            if len(html_files)==0:
                printc.printred(f"There's no .html files in src directory {src}. Aborting")
                exit(3)
            if len(html_files)>1:
                printc.printyellow(f"There's more than one html file in directory {src}. Using the first one {html_files[0]}. Other files are {html_files[1:]}")

            src_ = os.path.join(src, html_files[0])
            dst_ = os.path.join(src, html_files[0].rsplit('.',1)[0])
    except Exception as e:
        printc.printred(f'src path should be string, os.PathLike. Received {src}. Error {e}')
        exit(2)

    if dir:
        k=0
        list_files = Utils.dirwalk(src, recursive)
        for dir, html_file in list_files:
            pdf_file = os.path.join(dir, f'{html_file.rsplit('.',1)[0]}.pdf')
            if not os.path.exists(pdf_file) or overwrite:
                #html_2_pdf(resume_file = os.path.join(dir, html_file))
                #html_2_txt(resume_file=os.path.join(dir, html_file), by = (By.TAG_NAME, 'body'))
                print(f'{k}: Competed for {dir}')
                k+=1
        pass
    else:
        pass
        #html_2_pdf(resume_file=html2pdf)
        #html_2_txt(resume_file=html2pdf, by=(By.TAG_NAME, 'body'))

    end_time = datetime.datetime.now()
    printc.printcolor(
        f'Process finished @ {end_time.strftime("%Y-%m-%d %H:%M:%S")}. Execution time {end_time - start_time}',
        "Blue")
    return
