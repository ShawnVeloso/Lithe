# Lithe Quick Reference

This is a personal cheatsheet for common commands used in the Lithe project.

## Git Workflow

To commit and push updates to the repository:

```bash
git add .
git commit -m "Lithe desktop app updates"
git push origin main
```

## How to Start the App

You need two terminals to run both the backend and frontend simultaneously.

**Terminal 1: Start Python Backend**
```bash
cd d:\Lithe
python -m src.backend.server
```

**Terminal 2: Start Electron Frontend**
```bash
cd d:\Lithe\src\frontend
npm run dev
```
