# Vercel Deployment Guide

## Prerequisites
1. Install Vercel CLI: `npm i -g vercel`
2. Sign up at https://vercel.com if you haven't already

## Step-by-Step Deployment

### 1. Prepare Your Project
✅ All configuration files are already set up:
- `vercel.json` - Deployment configuration
- `.env.example` - Environment template
- `requirements.txt` - Dependencies
- `.gitignore` - Files to exclude

### 2. Set Environment Variables
Before deploying, you need to set environment variables in Vercel:

**Option A: Via Vercel Dashboard**
1. Go to https://vercel.com/dashboard
2. Select your project (or create new)
3. Go to Settings → Environment Variables
4. Add the following variables:

```
PORT=8001
CORS_ORIGINS=https://your-frontend-domain.vercel.app,http://localhost:3000
```

**Option B: Via CLI**
```bash
vercel env add PORT
# Enter: 8001

vercel env add CORS_ORIGINS
# Enter: https://your-frontend-domain.vercel.app
```

### 3. Deploy

**First Time Deployment:**
```bash
cd /home/davis/Documents/MYPROJECTS/kibera-sp/backend
vercel
```

Follow the prompts:
- Set up and deploy? **Y**
- Which scope? Select your account
- Link to existing project? **N** (first time)
- Project name? **kibera-sp-backend** (or your choice)
- Directory? **./** (current directory)
- Override settings? **N**

**Subsequent Deployments:**
```bash
vercel --prod
```

### 4. Verify Deployment
After deployment, Vercel will provide a URL like:
- Preview: `https://kibera-sp-backend-xxxxx.vercel.app`
- Production: `https://kibera-sp-backend.vercel.app`

Test the API:
```bash
curl https://your-deployment-url.vercel.app/
```

### 5. Update Frontend CORS
Once deployed, update your `.env` file to include the production URL:
```
CORS_ORIGINS=https://your-frontend.vercel.app,http://localhost:3000
```

Then redeploy:
```bash
vercel --prod
```

## Common Issues & Solutions

### Issue: Module Not Found
**Solution:** Ensure all dependencies are in `requirements.txt`
```bash
pip freeze > requirements.txt
vercel --prod
```

### Issue: CORS Errors
**Solution:** Add your frontend URL to `CORS_ORIGINS` environment variable in Vercel dashboard

### Issue: Build Timeout
**Solution:** Large dependencies (like GeoPandas, OSMnx) may cause timeouts. Consider:
- Using Vercel Pro plan for longer build times
- Optimizing dependencies
- Using lighter alternatives if possible

### Issue: Runtime Errors
**Solution:** Check logs:
```bash
vercel logs <deployment-url>
```

## API Endpoints
Once deployed, your API will be available at:
- Health: `GET https://your-url.vercel.app/`
- Docs: `GET https://your-url.vercel.app/docs`
- Optimize: `POST https://your-url.vercel.app/optimize`
- Simulate: `POST https://your-url.vercel.app/simulate`

## Monitoring
- View deployment status: https://vercel.com/dashboard
- Check logs: `vercel logs`
- View analytics: Vercel Dashboard → Analytics

## Local Testing
Test the production build locally:
```bash
vercel dev
```

## Rolling Back
If something goes wrong:
```bash
vercel rollback
```

## Additional Resources
- [Vercel Python Runtime](https://vercel.com/docs/runtimes/python)
- [FastAPI Deployment Guide](https://fastapi.tiangolo.com/deployment/vercel/)
- [Environment Variables](https://vercel.com/docs/environment-variables)

---

**Need Help?**
- Vercel Support: https://vercel.com/support
- FastAPI Docs: https://fastapi.tiangolo.com/
