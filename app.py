import streamlit as st
from typing import List
from dataclasses import dataclass
import json
import os
import re
import requests
from typing import Optional
from urllib.parse import urlparse
from fpdf import FPDF
from openai import OpenAI

@dataclass
class Question:
    question: str
    answer: str
    difficulty: str
    topic: str
    reference: str = ""  # Add a reference field

# API Configuration for different providers
API_CONFIGS = {
    "Groq - llama3-70b-8192": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama3-70b-8192",
        "api_key_prefix": "groq"
    },
    "OpenAI - GPT-4": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4",
        "api_key_prefix": "openai"
    },
    "OpenAI - GPT-3.5 Turbo": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-3.5-turbo",
        "api_key_prefix": "openai"
    },
    "Groq - Deepseek-R1-70B": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "deepseek-r1-distill-llama-70b",
        "api_key_prefix": "groq"
    }
}

def is_valid_url(url):
    """Basic URL validation"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def validate_url(url, timeout=3):
    """Check if URL is accessible"""
    if not is_valid_url(url):
        return False
    
    try:
        # Just check the head to save time
        response = requests.head(url, timeout=timeout)
        return response.status_code < 400
    except:
        return False
def validate_url_access(url: str) -> bool:
    """Verify if a URL is accessible."""
    try:
        response = requests.head(url, timeout=5, allow_redirects=True)
        return response.status_code == 200
    except:
        return False

def search_alternative_url(topic: str, question: str) -> Optional[str]:
    """Search for alternative reference URLs based on the question content."""
    search_bases = [
        "https://docs.python.org/3/",
        "https://developer.mozilla.org/en-US/docs/",
        "https://learn.microsoft.com/en-us/docs/",
        "https://www.geeksforgeeks.org/",
        "https://www.w3schools.com/",
        "https://www.tutorialspoint.com/"
    ]
    
    # Extract key terms from question
    keywords = re.findall(r'\b\w+\b', question.lower())
    keywords = [word for word in keywords if len(word) > 3]
    
    # Try each base URL with the keywords
    for base in search_bases:
        try:
            search_url = f"{base}{'-'.join(keywords[:3])}"
            if validate_url_access(search_url):
                return search_url
        except:
            continue
    
    return None

class InterviewGenerator:
    """Multi-model interview generator"""
    
    def __init__(self, api_key: str, api_config: dict):
        self.api_key = api_key
        self.api_config = api_config
        
    def generate_interview(self, topic: str, difficulty: str, num_questions: int = 5) -> List[Question]:
        """Generate interview questions using selected model"""
        prompt = f"""
        You are an expert in {topic}. Generate {num_questions} based on {difficulty}-level interview questions.
        Focus strictly on {topic} concepts without deviating into subfields.
        For example, if the topic is Data Science, stay within data science concepts 
        without focusing specifically on machine learning, statistics, or other subfields. 
        And whenever the same topic is given by user give different questions each and every time 
        based on the difficulty level. 
        
        For every question and answer, you MUST include a reference link to a reliable source. 
        The reference link must be:
        1. A valid, publicly accessible URL for that particular question (starting with http:// or https://)
        2. From a reputable source like academic journals, educational websites, or industry documentation, technical documentation
        3. Directly relevant to the specific question and answer
        4. If the Link is invalid then alternative valid URLs will be searched
        
        The reference link should be added at the end of the answer in the following format:
        'Source: [URL]'
        
        The response MUST be valid JSON in exactly this format, with no additional text:
        {{
            "topic": "{topic}",
            "questions": [
                {{
                    "question": "detailed question text",
                    "answer": "detailed answer explanation",
                    "reference": "valid URL to source material"
                }}
            ]
        }}
        """
        
        try:
            client = OpenAI(
                api_key=self.api_key,
                base_url=self.api_config["base_url"]
            )
            
            response = client.chat.completions.create(
                messages=[
                    {
                        "role": "system", 
                        "content": f"You are a {difficulty}-level interview expert in {topic}. "
                                 f"Focus only on general {topic} concepts without deviating into specific subfields."
                    },
                    {"role": "user", "content": prompt}
                ],
                model=self.api_config["model"],
                temperature=0.7,
                max_tokens=4000
            )
            
            content = response.choices[0].message.content.strip()
            content = content.replace('\n', ' ').replace('\r', '')
            
            # Clean JSON content
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            if start_idx != -1 and end_idx != 0:
                content = content[start_idx:end_idx]
            
            data = json.loads(content)
            questions = []
            
            for q in data["questions"]:
                answer = q["answer"]
                reference = q.get("reference", "")
                
                # Extract reference from answer if not provided in JSON
                if not reference and "Source:" in answer:
                    parts = answer.split("Source:")
                    if len(parts) > 1:
                        potential_url = parts[-1].strip()
                        if is_valid_url(potential_url):
                            reference = potential_url
                            answer = parts[0].strip()
                
                # Validate URL and search for alternative if invalid
                if not reference or not is_valid_url(reference) or not validate_url_access(reference):
                    alternative_url = search_alternative_url(topic, q["question"])
                    if alternative_url:
                        reference = alternative_url
                
                questions.append(Question(
                    question=q["question"],
                    answer=answer,
                    difficulty=difficulty,
                    topic=topic,
                    reference=reference
                ))
            
            return questions
                
        except Exception as e:
            print(f"Error generating interview: {str(e)}")
            return [Question(
                question=f"Please explain a key concept in {topic}",
                answer="This is a placeholder answer. Please try regenerating the questions.",
                difficulty=difficulty,
                topic=topic,
                reference=""
            )]

# Create PDF function
def generate_pdf(questions: List[Question]):
    class PDF(FPDF):
        def __init__(self):
            super().__init__()
            self.is_first_page = True
            self.topic = questions[0].topic if questions else "Interview Questions"
            self.set_auto_page_break(auto=True, margin=15)
            
        def header(self):
            if not self.is_first_page:
                # Set text color to black for header
                self.set_text_color(0, 0, 0)
                self.set_font('Arial', 'B', 12)
                self.cell(0, 10, 'Interview Questions', 0, 1, 'C')
                self.ln(5)
                
        def footer(self):
            if not self.is_first_page:
                # Set text color to black for footer
                self.set_text_color(0, 0, 0)
                self.set_y(-25)

        def create_cover_page(self):
            # Background
            self.set_fill_color(0, 47, 255)
            self.rect(0, 0, 210, 297, 'F')
            
            # Company name
            self.set_text_color(255, 255, 255)
            self.set_font('Arial', 'B', 35)
            self.set_xy(20, 30)
            self.cell(0, 20, "accredian", 0, 1, 'C')
            
            # Tagline
            self.set_font('Arial', '', 18)
            self.set_xy(20, 45)
            self.cell(0, 10, "credentials that matter", 0, 1, 'C')
            
            # Title
            self.ln(60)
            self.set_font('Arial', 'B', 45)
            self.cell(0, 20, "Interview Questions", 0, 1, 'C')
            
            # topic
            self.ln(10)
            self.set_font('Arial', '', 40)
            self.cell(0, 15, self.topic, 0, 1, 'C')
            
            self.is_first_page = False

    # Initialize PDF
    pdf = PDF()
    
    # Add cover page
    pdf.add_page()
    pdf.create_cover_page()
    
    # Add content pages
    pdf.add_page()
    # Reset text color to black for content
    pdf.set_text_color(0, 0, 0)
    
    # Content
    for i, question in enumerate(questions, 1):
        # Question
        pdf.set_font('Arial', 'B', 13)
        pdf.multi_cell(0, 10, f"Question {i}:", 0)
        
        pdf.set_font('Arial', '', 12)
        pdf.multi_cell(0, 10, question.question)
        pdf.ln(5)
        
        # Answer
        # Set text color to red for the word "Answer:"
        pdf.set_text_color(255, 0, 0)  # RGB for red (255, 0, 0)

        # Set font to Arial, bold, size 13 for the label "Answer:"
        pdf.set_font('Arial', 'B', 13)
        pdf.cell(0, 10, "Answer:", 0, 1)

        # Set text color to black for the content (default)
        pdf.set_text_color(0, 0, 0)  # RGB for black (0, 0, 0)

        # Set font to Arial, normal, size 12 for the content
        pdf.set_font('Arial', '', 12)
        
        # Handle code blocks in answer
        if "```" in question.answer:
            parts = question.answer.split("```")
            
            # Write text before first code block
            if parts[0].strip():
                pdf.multi_cell(0, 10, parts[0].strip())
                pdf.ln(5)
            
            # Process code blocks
            for j in range(1, len(parts), 2):
                if j < len(parts):
                    code = parts[j].strip()
                    
                    # Set gray background for code
                    pdf.set_fill_color(240, 240, 240)
                    pdf.set_font('Courier', '', 10)
                    
                    # Split code into lines and write each line
                    code_lines = code.split('\n')
                    for line in code_lines:
                        pdf.multi_cell(0, 7, line.rstrip(), fill=True)
                    
                    pdf.ln(5)
                    
                    # Reset for normal text
                    pdf.set_font('Arial', '', 12)
                    
                    # Write text after code block
                    if j + 1 < len(parts) and parts[j + 1].strip():
                        pdf.multi_cell(0, 10, parts[j + 1].strip())
                        pdf.ln(5)
        else:
            pdf.multi_cell(0, 10, question.answer)
        
        # Add reference if available
        if question.reference:
            pdf.ln(5)
            pdf.set_font('Arial', 'I', 10)
            pdf.set_text_color(0, 0, 255)  # Blue for references
            pdf.cell(0, 10, f"Source: {question.reference}", 0, 1, 'L', link=question.reference)
            pdf.set_text_color(0, 0, 0)  # Reset to black
        
        # Add spacing between questions
        pdf.ln(10)
        
        # Add separator line between questions
        if i < len(questions):
            pdf.set_draw_color(200, 200, 200)
            pdf.line(20, pdf.get_y(), 190, pdf.get_y())
            pdf.ln(10)

    # Save the PDF
    pdf_output = "/tmp/interview_questions.pdf"
    pdf.output(pdf_output)
    return pdf_output

# Streamlit UI
def main():
    st.set_page_config(page_title="Interview Question Generator", layout="wide")
    
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Model selection
        selected_model = st.selectbox(
            "Select Model",
            options=list(API_CONFIGS.keys()),
            index=0
        )
        
        # API key based on selected model
        api_key_prefix = API_CONFIGS[selected_model]["api_key_prefix"]
        api_key_label = f"Enter {api_key_prefix.capitalize()} API Key:"
        api_key = st.text_input(api_key_label, type="password")
        
        # Other config options
        topic = st.text_input("Enter topic (e.g., Data Science)")
        difficulty = st.selectbox("Select Difficulty", ["Beginner", "Intermediate", "Expert"])
        num_questions = st.number_input("Number of Questions", min_value=1, max_value=20, value=5)
        validate_links = st.checkbox("Validate reference links", value=True)
        generate_btn = st.button("Generate Questions")
    
    st.markdown("## 🎓 Interview Question Generator")
    model_info = f"Using: {selected_model}"
    st.write(f"Generate topic-specific interview questions with detailed answers and validated references. {model_info}")
    
    if not api_key:
        st.warning(f"⚠️ Please enter your {api_key_prefix.capitalize()} API Key to proceed.")
        return
    
    if generate_btn:
        with st.spinner(f"Generating {num_questions} {difficulty}-level questions for {topic} using {selected_model}..."):
            try:
                api_config = API_CONFIGS[selected_model]
                generator = InterviewGenerator(api_key, api_config)
                questions = generator.generate_interview(topic, difficulty, int(num_questions))
                
                if questions:
                    # Validate references if option selected
                    if validate_links:
                        with st.status("Validating reference links..."):
                            for q in questions:
                                if q.reference:
                                    is_valid = validate_url(q.reference)
                                    if not is_valid:
                                        st.warning(f"Invalid reference detected: {q.reference}")
                                        q.reference += " (Link might be invalid)"
                    
                    for i, q in enumerate(questions, 1):
                        with st.expander(f"Question {i}"):
                            st.write(f"**Q:** {q.question}")
                            st.write(f"**A:** {q.answer}")
                            if q.reference:
                                st.write(f"**Source:** [{q.reference}]({q.reference})")
                    
                    pdf_file = generate_pdf(questions)
                    with open(pdf_file, "rb") as file:
                        st.download_button(
                            "📥 Download PDF",
                            file,
                            file_name="interview_questions.pdf",
                            mime="application/pdf"
                        )
            except Exception as e:
                st.error(f"Error: {str(e)}")
                st.error("Please try again with different parameters.")
    
if __name__ == "__main__":
    main()