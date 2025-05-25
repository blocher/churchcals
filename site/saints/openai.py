import os
import time
from typing import List

import openai
from django.conf import settings
from pydantic import BaseModel, Field

openai.api_key = settings.OPENAI_API_KEY

# -----------------------------
# 1. Define Your Pydantic Model
# -----------------------------


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


# -----------------------------
# 2. Upload PDF
# -----------------------------


def upload_pdf(file_path: str) -> str:
    with open(file_path, "rb") as f:
        file_obj = openai.files.create(file=f, purpose="assistants")
    return file_obj.id


# -----------------------------
# 3. Create Assistant w/ Tool
# -----------------------------


def create_assistant_with_tool() -> str:
    assistant = openai.beta.assistants.create(
        name="Saints Data Extractor",
        instructions="Extract structured saints data from the PDF. For each saint entry, identify the month, day, name, canonization status, category, biography, footnotes, reflection, volume, page number, and year of death. Return the data by calling the save_saints_data function.",
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "save_saints_data",
                    "description": "Extract a list of saints from a PDF.",
                    "parameters": Saints.model_json_schema(),
                },
            }
        ],
        model="gpt-4o",
    )
    return assistant.id


# -----------------------------
# 4. Create Thread and Run
# -----------------------------


def create_thread() -> str:
    thread = openai.beta.threads.create()
    return thread.id


def run_thread(assistant_id: str, thread_id: str, file_id: str) -> str:
    # Attach the file to the message
    openai.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=[
            {
                "type": "text",
                "text": "Extract the saints data from this PDF and return it using the function tool save_saints_data.",
            },
            {"type": "file_attachment", "file_id": file_id},
        ],
    )
    run = openai.beta.threads.runs.create(thread_id=thread_id, assistant_id=assistant_id)
    return run.id


# -----------------------------
# 5. Wait for Completion
# -----------------------------


def wait_for_completion(thread_id: str, run_id: str):
    while True:
        run = openai.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
        if run.status == "completed":
            return
        elif run.status in ["failed", "cancelled", "expired"]:
            raise RuntimeError(f"Run failed with status: {run.status}")
        time.sleep(2)


# -----------------------------
# 6. Extract Tool Call Arguments
# -----------------------------


def get_function_call_arguments(thread_id: str) -> Saints:
    messages = openai.beta.threads.messages.list(thread_id=thread_id)
    print(f"Found {len(messages.data)} messages")

    for msg in reversed(messages.data):
        print(f"Message role: {msg.role}")
        for content in msg.content:
            print(f"Content type: {content.type}")
            if content.type == "tool_calls":
                for tool_call in content.tool_calls:
                    print(f"Tool call function name: {tool_call.function.name}")
                    if tool_call.function.name == "save_saints_data":
                        args = tool_call.function.arguments
                        import json

                        parsed_args = json.loads(args)
                        return Saints(**parsed_args)

    # If we reach here, print more details about the messages
    print("No tool call found. Message content details:")
    for msg in messages.data:
        print(f"- Role: {msg.role}, Created at: {msg.created_at}")
        print(f"- Content types: {[c.type for c in msg.content]}")

    raise ValueError("No tool call found with the expected function name.")


# -----------------------------
# 7. Run the Pipeline
# -----------------------------


def parse_saints_pdf(file_path: str) -> Saints:
    file_id = upload_pdf(file_path)
    assistant_id = create_assistant_with_tool()
    thread_id = create_thread()
    run_id = run_thread(assistant_id, thread_id, file_id)
    wait_for_completion(thread_id, run_id)
    return get_function_call_arguments(thread_id)


# -----------------------------
# 🧪 Example Usage
# -----------------------------


def start():
    pdf_folder = "saints/butlers_lives_of_the_saints"
    pdf_paths = sorted([os.path.join(pdf_folder, file) for file in os.listdir(pdf_folder) if file.endswith(".pdf")])
    pdf_path = pdf_paths[0]  # Use the first PDF for testing
    structured_data = parse_saints_pdf(pdf_path)
    print("\n✅ Parsed Saints Data:")
    print(structured_data.json(indent=2))
