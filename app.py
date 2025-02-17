import streamlit as st
from typing import List
from dataclasses import dataclass
import json
import os
import re
from groq import Groq
from fpdf import FPDF

@dataclass
class Question:
    question: str
    answer: str
    difficulty: str
    topic: str

class InterviewGenerator:
    """Simplified interview generator that makes a single API call"""
    
    def __init__(self, api_key: str):
        self.client = Groq(api_key=api_key)
        self.model = "llama3-70b-8192"
        
    def generate_interview(self, topic: str, difficulty: str, num_questions: int = 5) -> List[Question]:
        """Generate interview questions with a single API call"""
        prompt = f"""
        You are an expert in {topic}. Generate {num_questions} {difficulty}-level interview questions.
        Focus strictly on {topic} concepts without deviating into subfields.
        For example, if the topic is Data Science, stay within data science concepts 
        without focusing specifically on machine learning, statistics, or other subfields. 
        And whenever the same topic is given by user give different questions each and every time 
        based on the difficulty level. Add reference link as source for each and evry question where it took the answer from 
        
        The response MUST be valid JSON in exactly this format, with no additional text:
        {{
            "topic": "{topic}",
            "questions": [
                {{
                    "question": "The question text",
                    "answer": "The answer text"
                }}
            ]
        }}

        Requirements:
        1. All questions must be specifically about {topic} at {difficulty} level
        2. Questions should cover gdifficulty level based concepts in {topic}
        3. Do not focus on specific subfields or subtopics
        4. Provide detailed, informative answers
        5. Generate exactly {num_questions} questions
        6. Ensure questions are appropriate for {difficulty} level interviews
        7. Add reference link as source for each and every question
        8. Ensure proper JSON formatting
        """
        
        try:
            response = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system", 
                        "content": f"You are a {difficulty}-level interview expert in {topic}. "
                                 f"Focus only on general {topic} concepts without deviating into specific subfields."
                    },
                    {"role": "user", "content": prompt}
                ],
                model=self.model,
                temperature=0.7,
                max_tokens=4000
            )
            
            content = response.choices[0].message.content.strip()
            
            # Clean the response to ensure valid JSON
            content = content.replace('\n', ' ').replace('\r', '')
            
            # Remove any non-JSON text before or after the JSON object
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            if start_idx != -1 and end_idx != 0:
                content = content[start_idx:end_idx]
            
            # Parse the JSON
            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                print(f"JSON parsing error: {str(e)}")
                print(f"Content causing error: {content}")
                raise
            
            # Convert to Question objects
            questions = []
            for q in data["questions"]:
                questions.append(Question(
                    question=q["question"],
                    answer=q["answer"],
                    difficulty=difficulty,
                    topic=topic
                ))
            
            return questions
                
        except Exception as e:
            print(f"Error generating interview: {str(e)}")
            # Return a single fallback question
            return [Question(
                question=f"Please explain a key concept in {topic}",
                answer="This is a placeholder answer. Please try regenerating the questions.",
                difficulty=difficulty,
                topic=topic
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
                
                # Draw full border around page content area
                self.set_draw_color(200, 200, 200)  # Light gray
                self.rect(15, 15, 180, 267)  # Rectangle: x, y, width, height
            
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
            self.set_font('Arial', 'B', 40)
            self.cell(0, 20, "Interview Questions", 0, 1, 'C')
            
            # topic
            self.ln(10)
            self.set_font('Arial', '', 38)
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
    
    # Draw border on the first content page (since header won't draw it on first page)
    pdf.set_draw_color(200, 200, 200)  # Light gray
    pdf.rect(15, 15, 180, 267)  # Rectangle: x, y, width, height
    
    # Content
    for i, question in enumerate(questions, 1):
        # Question - indent content to give space from border
        pdf.set_font('Arial', 'B', 13)
        pdf.set_x(20)  # Indent from left margin
        pdf.multi_cell(170, 10, f"Question {i}:", 0)
        
        pdf.set_font('Arial', '', 12)
        pdf.set_x(20)  # Indent from left margin
        pdf.multi_cell(170, 10, question.question)
        pdf.ln(5)
        
        # Answer
        pdf.set_x(20)  # Indent from left margin
        # Set text color to red for the word "Answer:"
        pdf.set_text_color(255, 0, 0)
        pdf.set_font('Arial', 'B', 13)
        pdf.cell(0, 10, "Answer:", 0, 1)

        # Set text color back to black for the content
        pdf.set_text_color(0, 0, 0)
        
        # Check for code blocks in triple backticks
        if "```" in question.answer:
            # Handle existing triple backtick code blocks
            parts = question.answer.split("```")
            
            # Write text before first code block
            if parts[0].strip():
                pdf.set_x(20)  # Indent from left margin
                pdf.multi_cell(170, 10, parts[0].strip())
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
                        pdf.set_x(20)  # Indent from left margin
                        pdf.multi_cell(170, 7, line.rstrip(), fill=True)
                    
                    pdf.ln(5)
                    
                    # Reset for normal text
                    pdf.set_font('Arial', '', 12)
                    
                    # Write text after code block
                    if j + 1 < len(parts) and parts[j + 1].strip():
                        pdf.set_x(20)  # Indent from left margin
                        pdf.multi_cell(170, 10, parts[j + 1].strip())
                        pdf.ln(5)
        else:
            # Define patterns for code and mathematical formulas
            code_patterns = [
                r'import\s+\w+',       # Import statements
                r'from\s+\w+\s+import', # Import statements
                r'def\s+\w+\(.*\):',    # Function definitions
                r'class\s+\w+\(.*\):',  # Class definitions
                r'for\s+\w+\s+in\s+\w+', # For loops
                r'if\s+.*:',            # If statements
                r'while\s+.*:',         # While loops
                r'try:',                # Try blocks
                r'except:',             # Except blocks
                r'return\s+',           # Return statements
                r'print\(',             # Print statements
                r'\w+\s*=\s*\w+\(',     # Function calls with assignment
                r'\w+\[\w+\]',          # Array indexing
                r'\w+\.\w+\(',          # Method calls
            ]
            
            math_patterns = [
                r'\$.*\$',              # Inline LaTeX
                r'\\begin\{equation\}', # LaTeX equation blocks
                r'\\sum_',              # Summation
                r'\\prod_',             # Product
                r'\\frac{',             # Fractions
                r'\\int_',              # Integrals
                r'[xy]\s*=\s*\d+[+\-*/]', # Basic equations
                r'\w+\s*=\s*\d+\s*[+\-*/]\s*\d+', # Assignments with calculations
                r'[a-zA-Z_]\w*\s*[+\-*/]\s*[a-zA-Z_]\w*', # Variable operations
                r'np\.\w+\(',           # NumPy functions
                r'scipy\.\w+\(',        # SciPy functions
                r'math\.\w+\(',         # Math module functions
            ]
            
            # Get all lines in the answer
            lines = question.answer.split('\n')
            
            current_mode = 'normal'  # Can be 'normal' or 'code'
            temp_code_lines = []
            
            # Process each line
            for line in lines:
                # Check if this line matches a code or math pattern
                is_code_or_math = (
                    any(re.search(pattern, line) for pattern in code_patterns) or
                    any(re.search(pattern, line) for pattern in math_patterns)
                )
                
                if is_code_or_math and current_mode == 'normal':
                    # Switch to code mode
                    if temp_code_lines:
                        # Write any pending normal text
                        pdf.set_font('Arial', '', 12)
                        pdf.set_x(20)
                        for normal_line in temp_code_lines:
                            pdf.multi_cell(170, 10, normal_line)
                        temp_code_lines = []
                    
                    current_mode = 'code'
                    temp_code_lines.append(line)
                
                elif not is_code_or_math and current_mode == 'code':
                    # Switch back to normal mode after writing code
                    pdf.set_fill_color(240, 240, 240)
                    pdf.set_font('Courier', '', 10)
                    pdf.set_x(20)
                    for code_line in temp_code_lines:
                        pdf.multi_cell(170, 7, code_line, fill=True)
                    temp_code_lines = []
                    
                    current_mode = 'normal'
                    temp_code_lines.append(line)
                
                else:
                    # Continue in current mode
                    temp_code_lines.append(line)
            
            # Handle any remaining lines
            if temp_code_lines:
                if current_mode == 'code':
                    pdf.set_fill_color(240, 240, 240)
                    pdf.set_font('Courier', '', 10)
                    pdf.set_x(20)
                    for code_line in temp_code_lines:
                        pdf.multi_cell(170, 7, code_line, fill=True)
                else:
                    pdf.set_font('Arial', '', 12)
                    pdf.set_x(20)
                    for normal_line in temp_code_lines:
                        pdf.multi_cell(170, 10, normal_line)
        
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
        api_key = st.text_input("Enter Groq API Key:", type="password")
        topic = st.text_input("Enter topic (e.g., Data Science)")
        difficulty = st.selectbox("Select Difficulty", ["Beginner", "Intermediate", "Expert"])
        num_questions = st.number_input("Number of Questions", min_value=1, max_value=20, value=5)
        generate_btn = st.button("Generate Questions")
    
    st.markdown("## 🎓 Interview Question Generator")
    st.write("Generate topic-specific interview questions with detailed answers.")
    
    if not api_key:
        st.warning("⚠️ Please enter your Groq API Key to proceed.")
        return
    
    if generate_btn:
        with st.spinner(f"Generating {num_questions} {difficulty}-level questions for {topic}..."):
            try:
                generator = InterviewGenerator(api_key)
                questions = generator.generate_interview(topic, difficulty, int(num_questions))
                
                if questions:
                    for i, q in enumerate(questions, 1):
                        with st.expander(f"Question {i}"):
                            st.write(f"**Q:** {q.question}")
                            st.write(f"**A:** {q.answer}")
                    
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
