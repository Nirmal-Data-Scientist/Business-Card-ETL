from streamlit_extras.add_vertical_space import add_vertical_space
from streamlit_lottie import st_lottie
from pymongo import MongoClient
import streamlit as st
import pandas as pd
import numpy as np
import difflib
import easyocr
import json
import cv2
import re
import io

client = MongoClient(st.secrets.mongo_db.URI)
db = client['bizcardx']
collection = db['business_cards']


def extract_information(image):
    
    reader = easyocr.Reader(['en'])
    result = reader.readtext(image)
    

    extracted_info = {
        'name': '',
        'designation': '',
        'company_name': '',
        'mobile_number': '',
        'email': '',
        'website': '',
        'address': '',
        'city': '',
        'state': '',
        'pincode': ''
    }

    extracted_lines = [text[1] for text in result]
    # Extract name
    if extracted_lines:
        extracted_info['name'] = extracted_lines.pop(0).title()

    # Keywords for designation
    keywords = ['engineer', 'manager', 'director', 'executive', 'ceo', 'cto','designer', 'stylist', 'cfo', 'coo', 'vp', 'president', 'chairman', 'founder', 'partner', 'consultant']

    # Extract designation
    for line in extracted_lines:
        for keyword in keywords:
            if keyword in line.lower():
                extracted_info['designation'] = line.title()
                extracted_lines.remove(line)
                break

     # Extract mobile number
    for line in extracted_lines:
        mobile_number = re.search(r'(\+?\d{1,4}\s?)?(\d{1,4}-\d{1,4}-\d{1,4}|\d{9,12})', line)
        if mobile_number:
            extracted_info['mobile_number'] = line
            extracted_lines.remove(line)
            break

    # Extract email
    for line in extracted_lines:
        email = re.search(r'[\w\.-]+@[\w\.-]+', line)
        if email:
            extracted_info['email'] = email.group(0)
            extracted_lines.remove(line)
            break

    # Extract website
    for line in extracted_lines:
        website = re.search(r'((https?://)?([wW]{3}([\. ]))?\S+\.\S+)', line)
        if website:
            website_text = website.group(0)
            if 'www' in website_text.lower() and 'www.' not in website_text.lower() and website_text.count('.') == 1:
                website_text = website_text.replace('www', 'www.').replace('WWW', 'www.')
                website_text = website_text.replace('www. ', 'www.')
            
            elif 'www' not in website_text.lower():
                website_text = 'www.' + website_text
                
            extracted_info['website'] = website_text
            extracted_lines.remove(line)

    # Extract address
    for line in extracted_lines:
        address_match = re.search(r'(\d+\s+[A-Za-z]+(?:\s+[A-Za-z]+)*)(?:\s+(?:st|ST|sT|St|street|Street|Road|road)\b(.+))?', line)
        if address_match:
            address = address_match.group(1)
            remaining_content = line.replace(address, "").strip()
            extracted_info['address'] = address.strip()
            if remaining_content:
                extracted_lines[extracted_lines.index(line)] = remaining_content
            else:
                extracted_lines.remove(line)
            break
    
    for line in extracted_lines:
        if line == 'St ,':
            extracted_lines.remove(line)

    state_names = [
                    'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh', 'Goa', 'Gujarat', 'Haryana',
                    'Himachal Pradesh', 'Jharkhand', 'Karnataka', 'Kerala', 'Madhya Pradesh', 'Maharashtra', 'Manipur',
                    'Meghalaya', 'Mizoram', 'Nagaland', 'Odisha', 'Punjab', 'Rajasthan', 'Sikkim', 'Tamil Nadu', 'Telangana',
                    'Tripura', 'Uttar Pradesh', 'Uttarakhand', 'West Bengal', 'Andaman and Nicobar Islands', 'Chandigarh',
                    'Dadra and Nagar Haveli and Daman and Diu', 'Delhi', 'Ladakh', 'Lakshadweep', 'Puducherry'
                    ]
    
    for i, line in enumerate(extracted_lines):
        state_match = difflib.get_close_matches(line.lower(), state_names, n=1, cutoff=0.5)
        if state_match:
            extracted_info['state'] = state_match[0].strip()
            extracted_lines[i] = line.replace('TamilNadu', '')
            break
               
    # Extract pincode
    pincode_patterns = [
                        r'(?<!\S)\d{6,7}\b'
                        ]
    
    for pattern in pincode_patterns:
        for line in extracted_lines:
            pincode_match = re.search(pattern, line)
            if pincode_match:
                extracted_info['pincode'] = pincode_match.group(0)
                extracted_lines.remove(line)
                break
    
    keywords = ['electricals', 'medicals', 'chemicals', 'digitals', 'designs', 'insurance', 'airlines', 'solutions', 'restaurant', 'hotel', 'pharmacy', 'mechanicals', 'automobiles', 'constructions', 'finance', 'tech', 'supermarket', 'hospital', 'school', 'logistics', 'telecommunications', 'telecom']

    # Extract company name
    removal_indices = []
    for i, line in enumerate(extracted_lines):
        for keyword in keywords:
            if keyword.lower() in line.lower() and keyword.lower() != 'electricals':
                if i > 0:
                    previous_line = extracted_lines[i-1].strip()
                    extracted_info['company_name'] = (previous_line + ' ' + line.strip()).title()
                    removal_indices.extend([i-1, i])
                break
            elif keyword.lower() in line.lower() and keyword.lower() == 'electricals':
                if i > 0:
                    extracted_info['company_name'] = (line.strip()).title()
                    removal_indices.extend([i])
                break

    # Remove lines from extracted_lines list
    
    for index in sorted(removal_indices, reverse=True):
        extracted_lines.pop(index)

    # Extract remaining lines as city
    
    city_line = extracted_lines[-1].strip()
    city_line = re.sub(r'[^\w\s]', '', city_line)
    city_words = city_line.split()
    extracted_info['city'] = city_words[-1] if city_words else ''
    extracted_lines.remove(extracted_lines[-1])
    return extracted_info

def insert_data(data):
    filter = {
        "name": data["name"],
        "designation": data["designation"],
        "company_name": data["company_name"]
    }
    collection.replace_one(filter, data, upsert=True)

def get_unique_company_names():
    result = collection.distinct('company_name')
    return result

def get_person_names(company_name):
    result = collection.find({'company_name': company_name}, {'name': 1})
    return [row['name'] for row in result]

def get_person_data(company_name, person_name):
    
    query = {
        'name': person_name,
        'company_name': company_name
    }
    projection = {'_id': 0}  # Exclude the _id field from the result
    result = collection.find_one(query, projection)
    return result

def update_field(company_name, person_name, field, value):
    
    query = {'company_name': company_name, 'name': person_name}
    update = {'$set': {field: value}}
    collection.update_one(query, update)

def delete_card(company_name, person_name):
    collection.delete_one({'company_name': company_name, 'name': person_name})

def get_data():
    result = collection.find({}, {'_id': 0})
    data = list(result)
    return data

def main():
    
    st.set_page_config(page_title = 'BizCardX', page_icon='Related images and Videos/card.png', layout='wide')
    
    page_title, lottie, buff= st.columns([65, 37, 5])

    page_title.title('Business Card Extractor')

    with open (r"Related Images and Videos/Biz.json") as f:
        lottie_json = json.load(f)
    with lottie:
        st_lottie(lottie_json, height= 100, width=200)
    
    add_vertical_space(2)
    
    col, buff = st.columns([2, 1])
        
    uploaded_file = col.file_uploader("Upload an image of the business card", type=["jpg", "jpeg", "png"])
    
    if uploaded_file:
        image = cv2.imdecode(np.fromstring(uploaded_file.read(), np.uint8), 1)
        add_vertical_space(1)
        st.image(image, width = 400)
    
    add_vertical_space(1)    
    
    extract = st.button('Extract and Upload', key = 'ext')
    
    add_vertical_space(1)
    
    extracted_info = {}
    
    if uploaded_file and extract:
        
        extracted_info = extract_information(image)

        st.subheader("Extracted Information")
        df = pd.DataFrame.from_dict(extracted_info, orient="index", columns=["Value"])
        df.index = df.index.str.replace('_', ' ').str.title()
        st.data_editor(df, key = 'edit')
        insert_data(extracted_info)        
        st.write(f"Business card saved successfully!")
        
        
    tab1, tab2, tab3 = st.tabs(["View and Update Data", "Delete Data", "Download Data"])
    
    with tab1:
        st.subheader("Update Data")
        
        col1, col2, buff = st.columns([2.5, 2.5, 3.5])
        
        company_names = get_unique_company_names()
        selected_company = col1.selectbox("Company", ["Select Company"] + company_names, key = 'company')

        if selected_company != "Select Company":
            person_names = get_person_names(selected_company)
            selected_person = col2.selectbox("Person", ["Select Person"] + person_names, key = 'person')

            if selected_person != "Select Person":
                person_data = get_person_data(selected_company, selected_person)

                df = pd.DataFrame([person_data])
                df.columns = df.columns.str.replace("_", " ").str.title()
                                
                add_vertical_space(1)
                
                st.dataframe(df)
                
                col3, buff1, col4, buff2 = st.columns([2, 0.3, 3, 2])
                selected_field = col3.selectbox("Select a Field to Modify", ["Select Field"] + list(df.columns), key = 'field')
                
                if selected_field != "Select Field":
                    new_value = col4.text_input("Enter New Value", df[selected_field].iloc[0], key = 'value')
                    col5, col6 = st.columns([2, 1.6])
                    update_button = col6.button("Update Value")
                    
                    if update_button:
                        
                        selected_field = selected_field.lower().replace(' ', '_')
                        update_field(selected_company, selected_person, selected_field, new_value)
                        st.success(f"Updated {selected_field} of {selected_person} to {new_value}")
    with tab2:
        
        st.subheader("Delete Data")
        
        col7, col8, buff = st.columns([2.5, 2.5, 3.5])
        
        company_names = get_unique_company_names()
        selected_company = col7.selectbox("Company", ["Select Company"] + company_names, key = 'company_1')

        if selected_company != "Select Company":
            person_names = get_person_names(selected_company)
            selected_person = col8.selectbox("Person", ["Select Person"] + person_names, key = 'person_1')

            add_vertical_space(1)   
            
            if selected_person != "Select Person":
                
                person_data = get_person_data(selected_company, selected_person)

                df = pd.DataFrame([person_data])
                df.columns = df.columns.str.replace("_", " ").str.title()
                
                st.dataframe(df)
                
                delete_button = st.button("Delete Card")
                if delete_button:
                    delete_card(selected_company, selected_person)
                    st.success("Card data deleted successfully.")

    with tab3:
        
        st.subheader("Download Data")
        
        col1, col2, col3 = st.columns(3)
        
        data = get_data()

        df = pd.DataFrame(data)[1:]

        csv_bytes = df.to_csv(index=False).encode()
        col1.download_button("Download CSV file", data=csv_bytes,
                            file_name= "card_data.csv",
                            mime="text/csv")

        json_bytes = df.to_json(orient="records").encode()
        col2.download_button("Download JSON file", data=json_bytes,
                            file_name="card_data.json",
                            mime="application/json")

        excel_buffer = io.BytesIO()
        df.to_excel(excel_buffer, engine ='xlsxwriter', index = False)
        excel_bytes = excel_buffer.getvalue()

        col3.download_button("Download Excel file", data = excel_bytes,
                            file_name = 'card_data.xlsx',
                            mime = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                            key = 'excel'
                            )
        
    st.sidebar.image('Related images and Videos/Biz.gif')
    add_vertical_space(2)
    st.sidebar.subheader("How can this app be handy?")
    st.sidebar.markdown("""
                        - Simplify the extraction, transformation, and loading of information from business cards.
                        - Capture and manage essential details like names, designations, contact information, and more.
                        - Stay organized, save time, and eliminate manual data entry with this BizcardX webapp.
                        """)

if __name__ == "__main__":
    main()