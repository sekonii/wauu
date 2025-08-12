
# Deployment Guide

This Flask application is configured to work on multiple hosting platforms.

## Replit (Current Setup)
- Already configured with `.replit` file
- Uses gunicorn workflow
- Database: PostgreSQL via Replit Database
- Environment variables: Set in Secrets tab

## Railway
1. Connect GitHub repository to Railway
2. Set environment variables in Railway dashboard:
   - `DATABASE_URL` (auto-provided by Railway PostgreSQL)
   - `SESSION_SECRET`
3. Deploy automatically using `railway.toml`

## Heroku
1. Install Heroku CLI and login
2. Create app: `heroku create your-app-name`
3. Add PostgreSQL: `heroku addons:create heroku-postgresql:mini`
4. Set environment variables:
   ```bash
   heroku config:set SESSION_SECRET="your-secret-key"
   ```
5. Deploy: `git push heroku main`

## Render
1. Connect GitHub repository to Render
2. Create Web Service using `render.yaml`
3. Add PostgreSQL database
4. Set environment variables in Render dashboard

## Vercel (Serverless)
1. Install Vercel CLI: `npm i -g vercel`
2. Deploy: `vercel --prod`
3. Add PostgreSQL database (external service like PlanetScale)
4. Set environment variables in Vercel dashboard

## Environment Variables Required
- `DATABASE_URL`: PostgreSQL connection string
- `SESSION_SECRET`: Secure session key
- `PORT`: Port number (auto-provided on most platforms)

## Local Development
1. Copy `.env.example` to `.env`
2. Fill in your database credentials
3. Run: `python main.py`
