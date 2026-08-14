from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import pandas as pd
from bs4 import BeautifulSoup
import re
from pypdf import PdfReader
import requests
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(exist_ok=True)

def extract_report_date(pdf_path):
    reader = PdfReader(str(pdf_path))
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += "\n" + page_text
    match = re.search(r"Date\s*of\s*Reporting.*?(\d{1,2}-[A-Za-z]{3}-\d{2,4})",text,re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    date_string = match.group(1)
    report_date = (pd.to_datetime(date_string, format="%d-%b-%y", errors="coerce").strftime("%Y-%m-%d")) if pd.to_datetime(date_string, format="%d-%b-%y", errors="coerce") is not pd.NaT else pd.to_datetime(date_string, format="%d-%b-%Y").strftime("%Y-%m-%d")
    return report_date

def web_scrape_table():
    options = Options()
    options.add_argument("--start-maximized")
    driver = webdriver.Chrome(options=options)

    driver.get("https://grid-india.in/en/reports/daily-psp-report")
    wait = WebDriverWait(driver, 20)

    all_df = pd.DataFrame()
    var_repeat = input('change range starting from last page')
    while var_repeat != 'Done':
        table = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="root"]/div/div[1]/main/div/div[3]/div/div/div[2]/table')))
        table_html = table.get_attribute("outerHTML")
        soup = BeautifulSoup(table_html, 'html.parser')
        table = soup.find('table')
        all_data = []
        for tr in table.find('tbody').find_all('tr'):
            row_data = [td.get_text(strip=True) for td in tr.find_all('td')]
            download_view_td = tr.find_all('td')[-1]
            href = download_view_td.find('a', href=True)['href'] if download_view_td.find('a', href=True) else None
            row_data.append(href)
            all_data.append(row_data)
        headers = [th.get_text(strip=True) for th in table.find('thead').find_all('th')]
        headers.append('URL')
        df = pd.DataFrame(all_data, columns=headers)
        all_df = pd.concat([all_df, df], ignore_index=True)
        print(len(df), len(all_df))
        var_repeat = input('repeat?')
    driver.quit()
    return all_df

table_df = web_scrape_table()
table_df = table_df.rename(columns={'Description▲▼': 'Description', 'Date▲▼': 'Upload Date', 'File Size▲▼': 'File Size'})
table_df = table_df[table_df['URL'].str.endswith('.pdf')]
table_df = table_df.drop_duplicates()
table_df['Upload Date'] = pd.to_datetime(table_df['Upload Date'], format='%d-%m-%Y')
table_df['Report Date'] = None

for index, pdf_url in table_df["URL"].items():
    file_name = pdf_url.split("/")[-1]
    print(file_name)
    pdf_path = TEMP_DIR / file_name
    try:
        response = requests.get(pdf_url, timeout=120, verify=False)
        response.raise_for_status()
        pdf_path.write_bytes(response.content)
        report_date = extract_report_date(pdf_path)
    except:
        report_date = None
    table_df.at[index, "Report Date"] = report_date

table_df = table_df[['Description', 'Upload Date', 'File Size', 'URL', 'Report Date']]
table_df.to_csv(r"NLDC Table new.csv", index=False)
