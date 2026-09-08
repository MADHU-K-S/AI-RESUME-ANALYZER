# AI Resume Analyzer

An AI-powered ATS Resume Analyzer that compares a candidate's resume with a job description and generates an ATS compatibility score.

## Features

- Upload resume in PDF format
- Extract resume text automatically
- Enter a job description
- AI-powered resume analysis using Google Gemini
- ATS compatibility score
- Resume quality score
- Skill match score
- Experience score
- Education score
- Required skills detection
- Matched skills detection
- Missing skills detection
- Keyword analysis
- Skill-by-skill evidence
- Personalized recommendations
- ATS score breakdown
- Resume analysis history
- Saved resumes

## Technologies Used

### Frontend

- HTML
- CSS
- JavaScript

### Backend

- Python
- Flask
- Flask-CORS
- PyMuPDF
- python-dotenv

### AI

- Google Gemini API

## Project Structure

AI-Resume-Analyzer/

│
├── .vscode/
│   └── settings.json
│
├── backend/
│   ├── data/
│   │   ├── analyses.json
│   │   └── resumes.json
│   ├── uploads/
│   ├── app.py
│   ├── .env.example
│   ├── requirements.txt
│   └── start_server.py
│
├── .gitignore
├── index.html
├── README.md
└── RUN_PROJECT.md

## How to Run

### Prerequisites

Make sure Python is installed on your system.

### Step 1: Open the backend folder

Open PowerShell or Command Prompt in the project folder and run:

```powershell
cd backend