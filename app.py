import streamlit as st
from typing import List
from dataclasses import dataclass
import json
import os
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
        
    def generate_interview(self, domain: str, difficulty: str, num_questions: int = 5) -> List[Question]:
        """Generate interview questions with a single API call"""
        prompt = f"""
        You are an expert in {domain}. Generate {num_questions} {difficulty}-level interview questions
        which will be asked in a real life interview Or consider yourself as an interviewer and ask questions
        accordingly.
        Focus strictly on {domain} concepts without deviating into subfields.
        For example, if the domain is Data Science, stay within data science concepts 
        without focusing specifically on machine learning, statistics, or other subfields. 
        And whenever the same domain is given by user give different questions each and every time 
        based on the difficulty level.
        
        The response MUST be valid JSON in exactly this format, with no additional text:
        {{
            "domain": "{domain}",
            "questions": [
                {{
                    "question": "detailed question text",
                    "answer": "detailed answer explanation"
                }}
            ]
        }}

        Requirements:
        1. All questions must be specifically about {domain} at {difficulty} level
        2. Questions should cover difficulty level-based concepts in {domain}
        3. Do not focus on specific subfields or subtopics
        4. Provide detailed, informative 5 to 6 line answers depending on the question
        5. Provide codes when it is necessary, if its coding related question.
        5. Generate exactly {num_questions} questions
        6. Ensure questions are appropriate for {difficulty} level interviews
        """
        
        try:
            response = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system", 
                        "content": f"You are a {difficulty}-level interview expert in {domain}. "
                                 f"Focus only on general {domain} concepts without deviating into specific subfields."
                    },
                    {"role": "user", "content": prompt}
                ],
                model=self.model,
                temperature=0.7,
                max_tokens=4000
            )
            
            content = response.choices[0].message.content.strip()
            
            # Try to parse JSON content
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                # Look for JSON-like structure
                start_idx = content.find('{')
                end_idx = content.rfind('}') + 1
                if start_idx != -1 and end_idx != 0:
                    json_str = content[start_idx:end_idx]
                    data = json.loads(json_str)
                else:
                    raise
            
            # Convert to Question objects
            questions = []
            for q in data["questions"]:
                questions.append(Question(
                    question=q["question"],
                    answer=q["answer"],
                    difficulty=difficulty,
                    topic=data["domain"]
                ))
            
            return questions
                
        except Exception as e:
            print(f"Error generating interview: {str(e)}")
            # Return a basic question if there's an error
            return [Question(
                question=f"Explain a fundamental concept in {domain}",
                answer="Please provide a comprehensive explanation.",
                difficulty=difficulty,
                topic=domain
            )]

# Create PDF function
def generate_pdf(questions: List[Question]):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    # Title
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="Interview Questions", ln=True, align="C")
    pdf.ln(10)

    # Content
    pdf.set_font("Arial", size=12)
    for i, question in enumerate(questions, 1):
        pdf.multi_cell(0, 10, f"Question {i}: {question.question}")
        pdf.multi_cell(0, 10, f"Answer: {question.answer}")
        pdf.ln(5)

    # Save the PDF to a file
    pdf_output = "/tmp/interview_questions.pdf"
    pdf.output(pdf_output)
    
    return pdf_output

# Streamlit UI
def main():
    st.set_page_config(page_title="Interview Question Generator", layout="wide")
    
    with st.sidebar:
        st.header("⚙️ Configuration")
        api_key = st.text_input("Enter Groq API Key:", type="password")
        domain = st.text_input("Enter Domain (e.g., Data Science)")
        difficulty = st.selectbox("Select Difficulty", ["Beginner", "Intermediate", "Expert"])
        num_questions = st.text_input("Number of Questions(eg., 5,6,20)")
        generate_btn = st.button("Generate Questions")
    
    st.markdown("## 🎓 Interview Question Generator")
    st.write("Generate domain-specific interview questions with detailed answers.")
    
    if not api_key:
        st.warning("⚠️ Please enter your Groq API Key to proceed.")
        return
    
    if generate_btn:
        st.write(f"### Generating {num_questions} {difficulty}-level questions for {domain}...")
        generator = InterviewGenerator(api_key)
        questions = generator.generate_interview(domain, difficulty, num_questions)
        
        if questions:
            for i, q in enumerate(questions, 1):
                with st.expander(f"Question {i}"):
                    st.write(f"**Q:** {q.question}")
                    st.write(f"**A:** {q.answer}")
            
            pdf_file = generate_pdf(questions)
            with open(pdf_file, "rb") as file:
                st.download_button("📥 Download PDF", file, file_name="interview_questions.pdf", mime="application/pdf")
    
if __name__ == "__main__":
    main()
