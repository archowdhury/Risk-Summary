from dotenv import load_dotenv
import pandas as pd
import streamlit as st
import os
import google.generativeai as genai
from langchain_openai import OpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

import requests
from bs4 import BeautifulSoup 
import io
import requests
import PyPDF2

from langchain_openai import AzureChatOpenAI


pd.set_option('display.max_colwidth', None)

load_dotenv()

MAX_CONTEXT_LENGTH = 100000

#======================================================================================
# Define the functions
#======================================================================================

def get_content_type(url):
    
    content_type, page_link = "", ""
    
    try:
    
        HEADERS = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:98.0) Gecko/20100101 Firefox/98.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }

        page_link = requests.get(url, headers=HEADERS)
        
        header = page_link.headers.get('content-type')
        
        if 'html' in header:
            content_type = 'HTML'
        elif 'pdf' in header:
            content_type = 'PDF'
        else:
            content_type = 'Unknown'
    
    except:
        
        print("get_content_type ==> Unable to parse the HTML link : ", url)
        
        
    return content_type, page_link
    
    
    
def get_pdf_data(page_link):
    
    try:
        
        f = io.BytesIO(page_link.content)
        reader = PyPDF2.PdfReader(f)

        text = "".join([page.extract_text() for page in reader.pages])
        
    except:
        
        print("get_pdf_data ==> Unable to parse the HTML link : ", page_link)
        text = ""
    
    return text




def get_HTML_data(page_link):
    
    context, soup = "", ""
    
    try:
        
        soup = BeautifulSoup(page_link.content, "lxml")
        
        for data in soup(['style', 'script']):
            data.decompose()
            
        context = ' '.join(soup.stripped_strings)

    except:
        print("get_HTML_data ==> Unable to parse the HTML link : ", page_link)
    
    return context, soup
    


def get_doj_data(url, max_length=MAX_CONTEXT_LENGTH):
    
    # Read the full data from the DOJ site
    #-------------------------------------
   
    content_type, page_link = get_content_type(url)
    print("Content_type : ", content_type)
    
    if content_type == 'HTML':
        
        # Get the main body of the article
        #---------------------------------
        
        soup = BeautifulSoup(page_link.content, "lxml")
        
        div = soup.find('div', class_ = "field-formatter--text-default field-text-format--wysiwyg text-formatted field_body")
        paras = div.find_all('p')
        
        context = ""
        for p in paras:
            context += p.text + ' \n\n'
            
        print("Lenth of main article : ", len(context))
    
        # Get the list of attachments
        #----------------------------
        attachments = soup.find_all('div', class_ = 'field__item downloadable downloadable__attachment')
        parent_url = "https://www.justice.gov/" 

        links = []
        for a in attachments:
            link = parent_url + a.find('a')['href']
            links.append(link)
        
        # if there are attachments then divide the remaining available context length evenly among the attachments
        #---------------------------------------------------------------------------------------------------------
        if len(links) > 0:
            max_chars_per_attachment = max(0, int((max_length - len(context)) / len(links)))
            print("Max_chars_per_attachment : ", max_chars_per_attachment)
            
            
        # Append the data for any attachments
        #------------------------------------
        for link in links:
        
            content_type, sub_page = get_content_type(link)
        
            if content_type == 'PDF':
                attachment_data = get_pdf_data(sub_page)
            elif content_type == 'HTML':
                attachment_data, _ = get_HTML_data(sub_page)
            else:
                attachment_data = ""
                
            print(f"Processed {content_type} attachment : {link}   Length of data extracted : {len(attachment_data)}") 
            context += "\n " + attachment_data[:max_chars_per_attachment]
        
    elif content_type == 'PDF':
        
        context = get_pdf_data(page_link)

        
    else:
        
        context = ""
        print("Unable to fetch the context. Invalid page type")
        
        
    # Clip the context if it is beyond the maximum size
    context = context[:max_length]
    
    return context



def get_sec_data(url, max_length=MAX_CONTEXT_LENGTH):
    
    # Read the full data from the DOJ site
    #-------------------------------------
   
    content_type, page_link = get_content_type(url)
    
    if content_type == 'HTML':
        
        # Get the main body of the article
        #---------------------------------
        
        soup = BeautifulSoup(page_link.content, "lxml")
        
        div = soup.find('div', class_ = 'article-body')
        paras = div.find_all('p')
        
        context = ""
        for p in paras:
            context += p.text + ' \n\n'
            
  
        # Get other supporting documents
        #-------------------------------
        
        div = soup.find_all('div', class_ = 'block related-materials')
        links = []
        for L in div[0].find_all('li'):
            
            attachment_url = L.a['href']
            
            if attachment_url[0] == '/':                    # It's a relative link
                attachment_url = 'https://www.sec.gov' + attachment_url
                
            links.append(attachment_url)
            
        print("Found the following attachments :", links)
        
        
        # if there are attachments then divide the remaining available context length evenly among the attachments
        # ---------------------------------------------------------------------------------------------------------
        if len(links) > 0:
            max_chars_per_attachment = max(0, int((max_length - len(context)) / len(links)))
            
                        
        # Append the data for any attachments
        #------------------------------------
        for link in links:
        
            content_type, sub_page = get_content_type(link)
        
            if content_type == 'PDF':
                attachment_data = get_pdf_data(sub_page)
            elif content_type == 'HTML':
                attachment_data, _ = get_HTML_data(sub_page)
            else:
                attachment_data = ""
                
            print(f"Processed {content_type} attachment : {link}   Length of data extracted : {len(attachment_data)}") 
            context += "\n " + attachment_data[:max_chars_per_attachment]
        
    elif content_type == 'PDF':
        
        context = get_pdf_data(page_link)
        
    else:
        
        context = ""
        print("Unable to fetch the context. Invalid page type")
        
        
    # Clip the context if it is beyond the maximum size
    context = context[:max_length]
    
    return context





def get_data(url, max_length=MAX_CONTEXT_LENGTH):
    
    context = ""
    
    try:
        
        content_type, page_link = get_content_type(url)
        
        if 'justice.gov' in url:
            context = get_doj_data(url)
            
        elif 'sec.gov' in url:
            context = get_sec_data(url)

        elif content_type == 'HTML':
            context = get_HTML_data(page_link)
                
        elif content_type == 'PDF':
            context = get_pdf_data(page_link)
            
        else:
            context = ""
            
        # Restrict the context to the maximum length
        context = context[:max_length]
        
    except:
        pass
    
    return context
      
    


#======================================================================================
# Start of the main program
#======================================================================================

# Connect to the LLM
#-------------------

generation_config = {
    "temperature" : 0.9,
    "top_p" : 1,
    "top_k" : 1,
    "max_output_tokens" : 20000
}

safety_settings = [
    {
        "category" : "HARM_CATEGORY_HARASSMENT",    
        "threshold" : "BLOCK_NONE" 
    },

    {
        "category" : "HARM_CATEGORY_HATE_SPEECH",    
        "threshold" : "BLOCK_NONE" 
    },

    {
        "category" : "HARM_CATEGORY_DANGEROUS_CONTENT",    
        "threshold" : "BLOCK_NONE" 
    },
    
    {
        "category" : "HARM_CATEGORY_SEXUALLY_EXPLICIT",    
        "threshold" : "BLOCK_NONE" 
    }   
]

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

model = genai.GenerativeModel('gemini-pro',
                              generation_config=generation_config,
                              safety_settings=safety_settings)

# model = AzureChatOpenAI(azure_endpoint="https://aeroopenaiqa.openai.azure.com/",
#                                    api_version='2023-07-01-preview',
#                                    api_key='7ac37c9968b048b4a03ef2ea869698a6',
#                                    deployment_name= 'gpt-35-turbo-0301')




# The question template
#----------------------

question = f"""
You are an Experienced Compliance Risk Auditor. From the given context do the following two things:

1) Write a 300 word text summary of the context. Then mention bullet points like the accused, dates, penalty amounts, laws broken etc.
2) Identify all the compliance risks. Present the results in a tabular format.

Do not state anything directly from the context. Do not throw RECITATION errors. Paraphrase the results in your own words.
Do not use headers like #, ##, ###, etc.
In some cases the text may be malformed or have incorrect newlines and missing spaces or indentation. There may also be cases where excessive newlines, spaces, and tabs are used. Detect and correct such issues.


Present the final output as per the below formats. SOme examples are shown below:

#### Example 1

**Summary**

Violation of FCPA: The Securities and Exchange Commission (SEC) announced that 3M Company has agreed to pay over $6.5 million to settle charges of violating the books and records and internal controls provisions of the Foreign Corrupt Practices Act (FCPA).
Allegations: Employees of a 3M wholly owned subsidiary in China arranged for Chinese government officials from state-owned health care facilities to attend overseas conferences, educational events, and health care facility visits. However, these events often served as a pretext to provide the officials with overseas travel, including tourism activities, to induce them to purchase 3M products.
Improper Tourism Activities: From 2014 to 2017, 3M's Chinese subsidiary provided Chinese government officials with overseas travel that included guided tours, shopping visits, day trips, and other leisure activities. Some officials missed whole days of the events or never attended at all, and certain events were conducted in English without adequate translation services for non-English speaking officials.
Collusion and False Documentation: To obtain approval for the trips, employees of the Chinese subsidiary created legitimate travel itineraries, but also colluded with Chinese travel agencies to create alternate itineraries consisting of tourism activities. These alternate itineraries were provided to the Chinese officials, and employees falsified internal compliance documents to hide the tourism activities.
Direct Payments to Travel Agency: Between February 2016 and September 2018, 3M's Chinese subsidiary arranged for 3M to transfer $254,000 directly to a Chinese travel agency to help pay for some of the improper tourism activities.
SEC Findings: The SEC found that 3M violated the books and records and internal accounting controls provisions of Sections 13(b)(2)(A) and 13(b)(2)(B) of the Securities Exchange Act of 1934.
Settlement and Penalties: 3M neither admitted nor denied the findings but agreed to cease and desist from future violations. The company will pay disgorgement plus prejudgment interest totaling $4,581,618 and a civil penalty of $2 million.

**Accused:** 3M company

**Dates:** February 2016 to September 2018

**Penalty amount:** fine of $6.5 million, civil penalty of $2 million

**Laws broken:** 
Sections 13(b)(2)(A) and 13(b)(2)(B) of the Securities Exchange Act of 1934,
Foreign Corrupt Practices Act (FCPA)




**Compliance Risks**

| **Risk Type** | **Risk Details** | **Potential Data** |
|---|---|---|
| **Violation of compliance laws** | Violation of FCPA: The Securities and Exchange Commission (SEC) announced that 3M Company has agreed to pay over $6.5 million to settle charges of violating the books and records and internal controls provisions of the Foreign Corrupt Practices Act (FCPA) | Compliance Laws, Compliance Audit Reports|
| **Collusion with government officials** | Employees of a 3M wholly owned subsidiary in China arranged for Chinese government officials from state-owned health care facilities to attend overseas conferences, educational events, and health care facility visits. However, these events often served as a pretext to provide the officials with overseas travel, including tourism activities, to induce them to purchase 3M products. | General Ledger, Accounts Payable, Expense Reports |
| **Falsified claims submitted** | Falsified fake itinerary submitted for Compliance approval including legitimate business, training, marketing activities. Approval sought by omission / misreporting facts. Non-reimbursable expenses were covered by inflating the invoices billed by the travel agencies by showing ostensibly legitimate expense. Expenses not covered via above, routed directly to travel agency by 3M Employees for reimbursement. | General Ledger, Accounts Payable, Expense Reports |
| **Improper Tourism Activities** | From 2014 to 2017, 3M's Chinese subsidiary provided Chinese government officials with overseas travel that included guided tours, shopping visits, day trips, and other leisure activities. Some officials missed whole days of the events or never attended at all, and certain events were conducted in English without adequate translation services for non-English speaking officials. | Claim documents, Creadit card bills, Audit Reports |
| **Direct Payments to Travel Agency** | Between February 2016 and September 2018, 3M's Chinese subsidiary arranged for 3M to transfer $254,000 directly to a Chinese travel agency to help pay for some of the improper tourism activities. | Travel and expense documents, Employee claims | 




#### Example 2

**Summary**

Violation and Settlement: Cognizant Technology Solutions Corporation agreed to pay $25 million to settle charges that it violated the Foreign Corrupt Practices Act (FCPA). The charges stem from allegations that two former executives facilitated the payment of millions of dollars in bribes to an Indian government official.
Allegations: In 2014, a senior government official in the Indian state of Tamil Nadu demanded a $2 million bribe from the construction firm responsible for building Cognizant's campus in Chennai, India. Cognizant's President Gordon Coburn and Chief Legal Officer Steven E. Schwartz allegedly authorized the payment of this bribe and directed subordinates to conceal it by manipulating change orders. Additionally, two more bribes totaling over $1.6 million were authorized by Cognizant. The company allegedly used sham change order requests to conceal these payments.
SEC Charges: The Securities and Exchange Commission (SEC) charged Coburn and Schwartz with violating anti-bribery, books and records, and internal accounting controls provisions of the federal securities laws. The SEC is seeking permanent injunctions, monetary penalties, and officer-and-director bars against Coburn and Schwartz.
SEC's Findings and Settlement: The SEC's order found that Cognizant violated anti-bribery, books and records, and internal accounting controls provisions of the federal securities laws. Cognizant agreed to pay disgorgement and prejudgment interest of approximately $19 million and a penalty of $6 million.
Criminal Charges: The Department of Justice and the U.S. Attorney's Office for the District of New Jersey announced the indictment of Coburn and Schwartz on criminal charges of violating and conspiring to violate the FCPA's anti-bribery and accounting provisions.

**Accused:** Cognizant Technology Solutions Corporation

**Dates:** March 2014 to December 2015

**Penalty amount:** prejudgment interest of approximately $19 million, SEC penalty of penalty of $6 million

**Laws broken:** FCPA's anti-bribery and accounting provisions, books and records, and internal accounting controls provisions of the federal securities laws



**Compliance Risks**

| **Risk Type** | **Risk Details** | **Potential Data** |
|---|---|---|
| **Bribery scheme** | authorized a third-party construction company to pay bribe to an Indian government official for the issuance of a planning permit. A senior government official of the india demanded a $2 million bribe from the construction firm responsible for building Cognizant's 2.7 million square foot campus in Chennai, India. The bribes were made to ensure a construction permit necessary to complete the development of an office campus would be issued. The new campus was designed to support thousands of employees and become one of Cognizant's largest facilities in India. In 2014 Cognizant authorized a contractor to pay a $2 million bribe to a senior government official for the issuance of a planning permit for a project in Chennai, India. The payment, along with a scheme to conceal a $2.5 million reimbursement to the contractor, was authorized by two senior executives at Cognizant's U.S. headquarters. | Audit reports, Accounting books|
| **Unlawful payments** | Cognizant's Indian subsidiary authorized the same third party contractor to pay a bribe of approximately $770,000 to a government official for an environmental clearance for a project in Pune, India. In 2015, the Indian subsidiary retroactively authorized and reimbursed the same third party contractor for approximately $870,000 in bribes that it had paid to government officials for construction-related permits in Siruseri, India. Cognizant received ill-gotten gains of approximately $16,394,351 as a result of the conduct. | General Ledger, Accounts Payable, Expense Reports,  Books and records |
| **Violation of anti-bribery laws** | Cognizant violated anti-bribery, books and records, and internal accounting controls provisions of the federal securities laws. Cognizant agreed to pay disgorgement and prejudgment interest of approximately $19 million and a penalty of $6 million. | Compliance Reports, Risk Reports |
| **Inefficient accounting systems** | Cognizant also failed to devise and maintain a sufficient system of internal accounting controls at its corporate headquarters and at Cognizant India. This conduct took place in an environment in which Cognizant failed to adequately enforce its corporate antibribery and anticorruption policies | Compliance Reports, Risk Reports, Accounting books |
| **Collusion with third-parties** | Cognizant's Indian subsidiary authorized the same third party contractor to pay a bribe of approximately $770,000 to a government official for an environmental clearance for a project in Pune, India. In 2015, the Indian subsidiary retroactively authorized and reimbursed the same third party contractor for approximately $870,000 in bribes that it had paid to government officials | Compliance Reports, Accounting books |
| **Tampering with transactions** | The unlawful payments were paid from Cognizant India's bank accounts and were not accurately reflected in Cognizant's consolidated books and records | Accounting books, Cash flow statements |




### Example 3

**Summary**

Violation and Settlement: Deutsche Bank Aktiengesellschaft (Deutsche Bank) agreed to pay more than $130 million to resolve two investigations. One involves violations of the Foreign Corrupt Practices Act (FCPA), and the other is related to a commodities fraud scheme.
Deutsche Bank was accused of concealing corrupt payments and bribes made to third-party intermediaries by falsely recording them on the company's books and records. This violated the FCPA and involved internal accounting control violations.
Additionally, Deutsche Bank was involved in fraudulent and manipulative commodities trading practices concerning publicly-traded precious metals futures contracts.
Deferred Prosecution Agreement (DPA) : Deutsche Bank entered into a three-year DPA with the Criminal Division's Fraud Section and Money Laundering and Asset Recovery Section (MLARS) and with the U.S. Attorney's Office for the Eastern District of New York.
Under the DPA, Deutsche Bank agreed to pay criminal penalties, disgorgement, and victim compensation payments. The criminal information charged Deutsche Bank with conspiracy to violate the books and records and internal accounting controls provisions of the FCPA and conspiracy to commit wire fraud affecting a financial institution in relation to the commodities conduct.
FCPA Violations: Between 2009 and 2016, Deutsche Bank, through its employees and agents, knowingly maintained false books, records, and accounts to conceal corrupt payments and bribes.
The bank conspired to falsify its books, records, and accounts by misrepresenting the purpose of payments to business development consultants (BDCs) and falsely characterizing payments to others as payments to BDCs.
Deutsche Bank employees failed to implement internal accounting controls, including conducting due diligence regarding BDCs and making payments to certain BDCs without adequate documentation.
Penalties: Deutsche Bank agreed to pay a total criminal penalty of $79,561,206 for the FCPA violations, along with $43,329,622 in disgorgement and prejudgment interest to the SEC.
In relation to the commodities fraud scheme, Deutsche Bank agreed to pay a total criminal amount of $7,530,218.
Cooperation and Remediation: Deutsche Bank did not voluntarily disclose the conduct to the authorities but received credit for its cooperation with the investigations and significant remediation efforts.
Prosecution and Investigations: The FCPA investigation was conducted by the U.S. Postal Inspection Service and prosecuted by the Criminal Division's Fraud Section and MLARS, along with the U.S. Attorney's Office for the Eastern District of New York.
The commodities case was investigated by the FBI's New York Field Office and prosecuted by the Fraud Section.

**Accused:** Deutsche Bank Aktiengesellschaft (Deutsche Bank)

**Dates:** Between 2009 to 2016

**Penalty amount:**  
Total criminal penalty of $79,561,206 for the FCPA violations
$43,329,622 in disgorgement and prejudgment interest to the SEC
Total criminal amount of $7,530,218

**Laws broken:** 
Foreign Corrupt Practices Act (FCPA)
Commodities fraud scheme



**Compliance Risks**

| **Risk Type** | **Risk Details** | **Potential Data** |
|---|---|---|
| **Concealing payments** | Deutsche Bank was accused of concealing corrupt payments and bribes made to third-party intermediaries by falsely recording them on the company's books and records. This violated the FCPA and involved internal accounting control violations. | Audit reports, Accounting books|
| **Fraudulent trading practices** | Additionally, Deutsche Bank was involved in fraudulent and manipulative commodities trading practices concerning publicly-traded precious metals futures contracts. | General Ledger, Accounts Payable, Expense Reports,  Books and records |
| **Violation of accounting controls** | Deutsche Bank entered into a three-year DPA with the Criminal Division's Fraud Section and Money Laundering and Asset Recovery Section (MLARS) and with the U.S. Attorney's Office for the Eastern District of New York. Under the DPA, Deutsche Bank agreed to pay criminal penalties, disgorgement, and victim compensation payments. The criminal information charged Deutsche Bank with conspiracy to violate the books and records and internal accounting controls provisions of the FCPA and conspiracy to commit wire fraud affecting a financial institution in relation to the commodities conduct. | Compliance Reports, Risk Reports, Audit reports |
| **Bribery** | Between 2009 and 2016, Deutsche Bank, through its employees and agents, knowingly maintained false books, records, and accounts to conceal corrupt payments and bribes. | Accounting journals, Book of records |
| **Misrepresenting the purpose of payments** | The bank conspired to falsify its books, records, and accounts by misrepresenting the purpose of payments to business development consultants (BDCs) and falsely characterizing payments to others as payments to BDCs. | Compliance Reports, Accounting books |
| **Failure to implement accounting controls** | Deutsche Bank employees failed to implement internal accounting controls, including conducting due diligence regarding BDCs and making payments to certain BDCs without adequate documentation. | Compliance Reports, Accounting books |
| **Non-disclosure** | Deutsche Bank did not voluntarily disclose the conduct to the authorities but received credit for its cooperation with the investigations and significant remediation efforts. Failure to keep books and records which accurately reflect transactions and disposition of assets. | Accounting books, Cash flow statements |
| **Favouritism in hiring** | Deutsche Bank APAC was hiring relatives of Chinese SOE executives by their requests. Numerous Referral Hires at request of GO in China and Russia provided DB with unjust enrichment by approx. $11 M. Deutsche Bank hired Large Chinese SOE Chairman's daughter;Two Chinese SOEs executive's son; Russian Deputy Minister's daughter; Chinese SOE Chairman's son;Russian SOE executive's son. | Employee records, Background check reports |

"""


# Create the context by scraping the URL data
#--------------------------------------------

# URL = "https://www.justice.gov/opa/pr/walmart-inc-and-brazil-based-subsidiary-agree-pay-137-million-resolve-foreign-corrupt"
# # URL = "https://www.justice.gov/opa/press-release/file/1175781/dl"

# URL = "https://www.justice.gov/storage/US_v_Trump_23_cr_257.pdf"
##------problem------# URL = "https://www.sec.gov/news/press-release/2019-12"
# URL = "https://www.sec.gov/news/press-release/2023-160"
# URL = "https://ag.ny.gov/press-release/2022/attorney-general-james-sues-donald-trump-years-financial-fraud"
# URL = "https://www.sec.gov/enforce/34-85819-s"

# URL = "https://www.justice.gov/opa/pr/deutsche-bank-agrees-pay-over-130-million-resolve-foreign-corrupt-practices-act-and-fraud"

# context = get_data(URL)

# summary = None
# for i in range(5):
    
#     response = model.generate_content([context, question])
    
#     if response.candidates[0].finish_reason == 4:
#         print(f"Trial : {i}  ----------  RECITATION problem")
#     else:
#         summary = response.text
#         break
    
# if summary:
#     print(summary)
# else:
#     print("Sorry, unable to create a summary. Please try again.")

    






#----------------
# Streamlit app
#----------------

app_name = "CAMS Risks Identifier"

st.set_page_config(page_title=app_name)

st.header(app_name)

url = st.text_input("Paste the link to the site :", key="url")

# If the user has entered some URL
if url:
        
    with st.spinner('Getting the data...'):
        context = get_data(url)
    
    # Get the results
    
    summary = None
    
    for i in range(5):
        
        try:
            response = model.generate_content([context, question])
            
            if response.candidates[0].finish_reason == 4:
                print(f"Trial : {i}  ----------  RECITATION problem")
            else:
                summary = response.text
                break
        except:
            pass
            
    if summary:
        st.header(summary)
    else:
        st.write("Sorry, there was some problem in creating the summary. Please try again.")


