# 🚀 How to Run AI Resume Analyzer in VS Code

## Prerequisites
- Python 3.8+ installed
- VS Code installed
- All dependencies installed (will install if needed)

---

## ✅ QUICK START (Recommended)

### Option 1: Quick Start
1. **Open VS Code** in the project folder
2. **Open Terminal** (Ctrl + `)
3. **Run this command:**
   ```powershell
   python backend/start_server.py
   ```
4. **Wait for:** `Running on http://127.0.0.1:5000`
5. **Open in Browser:** Go to `file:///C:/Users/Acer/OneDrive/Desktop/AI-Resume-Analyzer/index.html`

---

## 📋 Manual Setup (Step-by-Step)

### Step 1: Install Dependencies
```powershell
cd backend
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Step 2: Create a Local .env File
Create `backend/.env` from a local copy of `backend/.env.example` and add your own Gemini API key:
```
GEMINI_API_KEY=YOUR_API_KEY_HERE
```
Do not commit your real key to the repository.

### Step 3: Start the Backend Server
```powershell
cd backend
python app.py
```

You should see:
```
========================================
       ResumeAI Backend Server
========================================
Server: http://127.0.0.1:5000
Health: http://127.0.0.1:5000/health
...
Running on http://127.0.0.1:5000
```

### Step 4: Open the Frontend
1. In VS Code, right-click on `index.html`
2. Select "Open with Live Server" (if installed)
3. OR manually open: `file:///C:/Users/Acer/OneDrive/Desktop/AI-Resume-Analyzer/index.html`

---

## 🔧 Troubleshooting

### Issue: "Module not found" error
**Fix:** Run this in the `backend` folder:
```powershell
python -m pip install -r requirements.txt
```

### Issue: Port 5000 already in use
**Fix:** Kill the existing process:
```powershell
Get-Process python | Where-Object {$_.Path -like '*Flask*'} | Stop-Process -Force
```
Then restart the server.

### Issue: "Cannot find fitz module"
**Fix:** PyMuPDF is required for PDF parsing:
```powershell
python -m pip install PyMuPDF
```

### Issue: CORS errors in browser console
**Fix:** Make sure the backend is running AND you're accessing the file with the correct URL format.

### Issue: Backend returns errors
**Check logs:** Look at the terminal where the backend is running for error messages.

---

## 🎯 Workflow

1. **Terminal 1 (Backend):**
   ```powershell
   cd backend
   python app.py
   ```

2. **Terminal 2 or Browser:**
   - Open `index.html` in your browser
   - Go to Dashboard → My Resumes
   - Upload a PDF resume
   - Add a job description
   - Click "Analyze Resume"

---

## 📊 Testing the Backend

To verify the backend is working:

```powershell
Invoke-WebRequest http://localhost:5000/health -UseBasicParsing
```

You should get a response like:
```json
{
  "status": "healthy",
  "gemini_configured": true,
  "gemini_models": ["gemini-3.6-flash", "gemini-3.5-flash-lite"],
  "local_ats_available": true
}
```

---

## 🌐 API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Health check |
| `/health` | GET | Detailed health status |
| `/upload-resume` | POST | Upload PDF resume |
| `/resumes` | GET | List all uploaded resumes |
| `/analyze` | POST | Analyze resume vs job description |
| `/analyses` | GET | View analysis history |

---

## 📱 Features to Test

- ✅ Upload PDF resume
- ✅ Enter job description
- ✅ View ATS compatibility score
- ✅ Check matched/missing skills
- ✅ See AI recommendations
- ✅ View analysis history

---

**Need help?** Check the backend server logs for detailed error messages.
