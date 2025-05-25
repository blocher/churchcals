import os
import time

from django.conf import settings
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

API_KEY = settings.GEMINI_API_KEY


# # Initialize the Gemini API client
# genai.configure(api_key=API_KEY)


def upload_pdfs(file_paths):
    """Uploads multiple PDF files to the Gemini API and returns a list of file objects."""
    uploaded_files = []
    file_paths = file_paths[:1]
    for path in file_paths:
        try:
            client = client = genai.Client(api_key=API_KEY)
            file = client.files.upload(file=path)
            uploaded_files.append(file)
        except Exception as e:
            print(f"\nError during file upload or processing: {str(e)}")
            raise

    return uploaded_files


class Saint(BaseModel):
    month: int = Field(description="Month the saint is commemorated on the calendar as an integer from 1 to 12")
    day: int = Field(
        description="Day of the month the saint is commemorated on the calendar as an integer from 1 to 31"
    )
    name: str = Field(description="Name of the saint")
    canonization_status: str = Field(
        description="Title of the saint, such as Saint (St), Saints (SS), Blessed (Bd), Blesseds (BB), Venerable, etc."
    )
    category: str = Field(
        description="Category or categories of the saint such as Martyr, Confessor, Virgin, King, Queen, Penitent, Bishop, Archbishop, etc."
    )
    biography_or_hagiography: str = Field(description="Biography or Hagiography of the saint")
    footnotes: str | None = Field(description="Footnotes to the biography of the saint, if provided")
    reflection: str | None = Field(description="A reflection or meditation on the life of the saint, if provided")
    volume: int = Field(description="Volume number of the book, from 1 to 4")
    page_number: int = Field(description="Page number of the book, from 1 to 3000")
    year_of_death: str = Field(
        description="Year of death often in the format 'A.D. 700', but can also be more generic such as 'Seventh Century' or a range"
    )


class Saints(BaseModel):
    saints: list[Saint] = Field(description="List of saints extracted from the document")


def extract_data_from_pdfs(text, Saints):
    """Extracts structured data from multiple PDF files using the Gemini API."""
    extracted_data_list = []
    #
    # for file in uploaded_files:
    try:
        print("Getting file...")
        # file_data = types.Part.from_uri(file_uri=file.uri, mime_type="application/pdf")
        client = genai.Client(api_key=API_KEY)
        response = client.models.generate_content(
            model="gemini-2.5-pro-exp-03-25",
            # contents=[
            #     {"role": "system", "parts": [{"text": "List the saints and their days based on the provided file."}]},
            #     {"role": "user", "parts": [types.Part.from_uri(
            #         file_uri=file.uri,
            #         mime_type='application/pdf',
            #     )]}
            # ]
            contents=[
                "List the saints and their days based on the provided data that has been extracted from a PDF.",
                text,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=Saints,
            ),
        )

        print(response)
        extracted_data_list.append(response)
    except Exception as e:
        print(f"\nError during file upload or processing: {str(e)}")
        raise

    return extracted_data_list


def process_saints():
    # Paths to your PDF files
    import os

    # Generate a list of paths from the project root for every file in the saints/butlers_lives_of_the_saints folder
    pdf_folder = "saints/butlers_lives_of_the_saints"
    pdf_paths = sorted([os.path.join(pdf_folder, file) for file in os.listdir(pdf_folder) if file.endswith(".pdf")])
    print(pdf_paths)

    # uploaded_files = upload_pdfs(pdf_paths)
    text = extract_text_from_pdf(pdf_paths[0])
    extracted_data_list = extract_data_from_pdfs(text, Saints)

    # Access and print the extracted information from each PDF
    for idx, extracted_data in enumerate(extracted_data_list):
        print(f"Data from PDF {idx + 1}:")
        for saint in extracted_data.saints:
            print(saint.name)
            saint_model = Saint.objects.get_or_create(name=saint.name, month=saint.month, day=saint.day)[0]
            saint_model.canonization_status = saint.canonization_status
            saint_model.category = saint.category
            saint_model.biography_or_hagiography = saint.biography_or_hagiography
            saint_model.footnotes = saint.footnotes
            saint_model.reflection = saint.reflection
            saint_model.volume = saint.volume
            saint_model.page_number = saint.page_number
            saint_model.year_of_death = saint.year_of_death
            saint_model.save()


def extract_text_from_pdf(pdf_path):
    """
    Extracts all text from a PDF file and returns it as a string.

    Args:
        pdf_path (str): Path to the PDF file

    Returns:
        str: All text content from the PDF
    """
    import PyPDF2

    text = ""
    try:
        with open(pdf_path, "rb") as file:
            pdf_reader = PyPDF2.PdfReader(file)
            num_pages = len(pdf_reader.pages)

            for page_num in range(num_pages):
                page = pdf_reader.pages[page_num]
                text += page.extract_text() + "\n"

    except Exception as e:
        print(f"Error extracting text from PDF {pdf_path}: {str(e)}")

    return text
