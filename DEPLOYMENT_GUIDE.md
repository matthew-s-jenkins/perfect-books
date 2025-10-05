# Perfect Books - Deployment Guide

## Deploy to Railway.app (FREE & EASY)

### Step 1: Create Railway Account
1. Go to https://railway.app
2. Click "Login" → Sign in with GitHub (or create account)
3. Verify your email

### Step 2: Initialize Git Repository
Open terminal in the Perfect_Books folder and run:
```bash
git init
git add .
git commit -m "Initial commit - Perfect Books v2.1"
```

### Step 3: Deploy to Railway
1. Go to https://railway.app/new
2. Click "Deploy from GitHub repo"
3. Click "Configure GitHub App"
4. Select your Perfect_Books repository
5. Click "Deploy Now"

### Step 4: Add MySQL Database
1. In your Railway project, click "+ New"
2. Select "Database" → "MySQL"
3. Wait for it to provision (takes ~30 seconds)

### Step 5: Connect Database to App
1. Click on your web service (not the database)
2. Go to "Variables" tab
3. Click "+ New Variable" and add these:

```
DB_HOST = ${{MySQL.MYSQLHOST}}
DB_PORT = ${{MySQL.MYSQLPORT}}
DB_USER = ${{MySQL.MYSQLUSER}}
DB_PASSWORD = ${{MySQL.MYSQLPASSWORD}}
DB_NAME = ${{MySQL.MYSQLDATABASE}}
PORT = ${{PORT}}
```

### Step 6: Initialize Database
1. Click on the MySQL database service
2. Go to "Data" tab
3. Click "Query" and paste:

```sql
CREATE DATABASE IF NOT EXISTS railway;
USE railway;
```

Then paste the contents of `fresh_setup.sql`

### Step 7: Get Your URL
1. Click on your web service
2. Go to "Settings" tab
3. Click "Generate Domain"
4. Copy the URL (e.g., `your-app-name.up.railway.app`)

### Step 8: Share with Your Mom!
Send her the URL - that's it! She can:
- Visit the URL from any device
- Create her account
- Start using Perfect Books

## Security Notes
- The app uses HTTPS automatically (Railway provides SSL)
- Sessions are secure
- Passwords are encrypted with bcrypt
- Each user has their own isolated data

## Costs
- **FREE** tier includes:
  - 500 hours/month runtime
  - $5 credit/month
  - Perfect for 1-2 users

## Backup
To backup the database:
1. Go to Railway dashboard
2. Click MySQL service
3. Go to "Data" tab
4. Click "Backup" → Download

## Troubleshooting
If deployment fails:
1. Check the "Deployments" tab for error logs
2. Make sure all files are committed to git
3. Verify environment variables are set correctly

Need help? Contact: mjenkins@example.com
