# Deployment Guide - Kibera SP Backend

## ⚠️ Important: Vercel Limitation

Your project uses heavy geospatial libraries (OSMnx, GeoPandas, GDAL) that exceed Vercel's 250 MB serverless function limit. 

**Recommended Platforms:** Railway or Render (they support larger applications)

---

## 🚂 Option 1: Deploy to Railway (Recommended)

Railway supports larger applications and is perfect for FastAPI + geospatial projects.

### Steps:

1. **Sign up at Railway**
   - Go to https://railway.app
   - Sign in with GitHub

2. **Deploy from GitHub**
   ```bash
   # Push your code to GitHub first
   git add .
   git commit -m "Prepare for Railway deployment"
   git push origin main
   ```

3. **Create New Project**
   - Click "New Project" in Railway dashboard
   - Select "Deploy from GitHub repo"
   - Choose your repository
   - Railway will auto-detect Python and deploy

4. **Set Environment Variables**
   In Railway dashboard → Variables:
   ```
   PORT=8001
   CORS_ORIGINS=https://your-frontend.vercel.app,http://localhost:3000
   ```

5. **Get Your URL**
   - Railway will provide: `https://your-app.up.railway.app`
   - Copy this URL for your frontend

**Pricing:** Free tier includes $5/month credit (enough for testing)

---

## 🎨 Option 2: Deploy to Render

Another excellent alternative for Python apps.

### Steps:

1. **Sign up at Render**
   - Go to https://render.com
   - Sign in with GitHub

2. **Create Web Service**
   - Dashboard → "New" → "Web Service"
   - Connect your GitHub repository
   - Render auto-detects settings from `render.yaml`

3. **Configure** (if needed)
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
   - Environment: Python 3.11

4. **Environment Variables**
   ```
   CORS_ORIGINS=https://your-frontend.vercel.app
   ```

5. **Deploy**
   - Click "Create Web Service"
   - Get URL: `https://your-app.onrender.com`

**Pricing:** Free tier available (apps spin down after inactivity)

---

## 🔧 Option 3: Try Vercel (Not Recommended)

Vercel likely won't work due to size limits, but if you want to try:

### Minimal Dependencies Approach

Create `requirements-vercel.txt`:
```txt
fastapi==0.104.1
uvicorn==0.24.0
python-dotenv==1.0.0
pydantic==2.12.5
requests==2.32.5
```

**Warning:** This removes geospatial features, breaking core functionality.

---

## 🐳 Option 4: Docker + Any Cloud

For full control, use Docker:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for geospatial libs
RUN apt-get update && apt-get install -y \
    gdal-bin \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]
```

Deploy to:
- Railway (supports Docker)
- Render (supports Docker)
- Fly.io
- DigitalOcean App Platform
- AWS/GCP/Azure

---

## 📊 Comparison

| Platform | Free Tier | Geo Support | Deploy Time | Best For |
|----------|-----------|-------------|-------------|----------|
| **Railway** | ✅ $5/mo | ✅ Yes | Fast | This project |
| **Render** | ✅ Limited | ✅ Yes | Fast | This project |
| Vercel | ✅ Yes | ❌ Size limit | Fast | Frontend/Light APIs |
| Fly.io | ✅ Limited | ✅ Yes | Medium | Docker apps |

---

## 🚀 Quick Deploy (Railway)

```bash
# 1. Install Railway CLI
npm i -g @railway/cli

# 2. Login
railway login

# 3. Initialize and deploy
railway init
railway up

# 4. Set environment variables
railway variables set CORS_ORIGINS=https://your-frontend.vercel.app

# 5. Get your URL
railway domain
```

---

## 📝 After Deployment

1. **Get your deployment URL** (e.g., `https://your-app.up.railway.app`)

2. **Update frontend** to use the new backend URL

3. **Test API endpoints:**
   ```bash
   curl https://your-app.up.railway.app/
   curl https://your-app.up.railway.app/docs
   ```

4. **Update CORS** in backend `.env`:
   ```
   CORS_ORIGINS=https://your-frontend.vercel.app,https://your-app.up.railway.app
   ```

---

## 🆘 Troubleshooting

### Railway/Render Build Fails
- Check build logs
- Ensure Python 3.11 is specified in `runtime.txt`
- Verify all dependencies in `requirements.txt`

### CORS Errors
- Add frontend URL to `CORS_ORIGINS` environment variable
- Ensure no trailing slashes in URLs

### App Crashes
- Check application logs
- Verify PORT environment variable
- Ensure dependencies installed correctly

---

## 📚 Resources

- [Railway Docs](https://docs.railway.app/)
- [Render Docs](https://render.com/docs)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)

---

**Recommendation:** Use Railway for the best experience with your geospatial Python app.
