import { app, shell, BrowserWindow, ipcMain, dialog } from 'electron'
import { join } from 'path'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import { spawn, ChildProcess } from 'child_process'
import { existsSync, mkdirSync, statSync, unlinkSync, renameSync, appendFileSync } from 'fs'

// ---------------------------------------------------------------------------
// Native Logging Setup
// ---------------------------------------------------------------------------
const isDev = !app.isPackaged
const logsDir = isDev 
  ? join(__dirname, '../../../../.lithe/logs')
  : join(app.getPath('appData'), 'Lithe', 'logs')

if (!existsSync(logsDir)) {
  mkdirSync(logsDir, { recursive: true })
}

const mainLogFile = join(logsDir, 'electron.log')
const childLogFile = join(logsDir, 'child.log')

function appendLog(file: string, message: string) {
  try {
    if (existsSync(file)) {
      const stats = statSync(file)
      if (stats.size > 5 * 1024 * 1024) {
        // Rotate: keep 1 backup
        const backup = file + '.1'
        if (existsSync(backup)) unlinkSync(backup)
        renameSync(file, backup)
      }
    }
    const timestamp = new Date().toISOString()
    
    // Mask GEMINI_API_KEY if present
    const maskedMessage = message.replace(/(GEMINI_API_KEY\s*[=:]\s*['"]?)[^\s'"]+(['"]?)/g, '$1********$2')
    
    appendFileSync(file, `[${timestamp}] ${maskedMessage}\n`)
  } catch (err) {
    // Failsafe: print to stdout
    process.stdout.write(`Failed to write to log file: ${err}\n`)
  }
}

function logMain(message: string) {
  appendLog(mainLogFile, message)
  process.stdout.write(message + '\n')
}

function logChild(message: string) {
  appendLog(childLogFile, message)
  process.stdout.write(message + '\n')
}

// Global exception handlers
process.on('uncaughtException', (error) => {
  logMain(`[Uncaught Exception] ${error.message}\n${error.stack}`)
})

process.on('unhandledRejection', (reason) => {
  logMain(`[Unhandled Rejection] ${reason}`)
})

// ---------------------------------------------------------------------------
// Python server management
// ---------------------------------------------------------------------------
const PYTHON_SERVER_PORT = 8321
const PYTHON_SERVER_URL = `http://127.0.0.1:${PYTHON_SERVER_PORT}`

let pythonProcess: ChildProcess | null = null

/**
 * Resolves the path to the Python backend executable or script.
 *
 * In production (packaged): uses the bundled lithe-server.exe from extraResources.
 * In development: uses `python -m src.backend.server` from the project root.
 */
function startPythonServer(): void {
  if (is.dev) {
    // --- Development mode: run Python directly ---
    // Resolve the project root (3 levels up from src/frontend/out/main)
    const projectRoot = join(__dirname, '..', '..', '..', '..')

    pythonProcess = spawn('python', ['-m', 'src.backend.server'], {
      cwd: projectRoot,
      stdio: 'pipe',
      env: { ...process.env }
    })
  } else {
    // --- Production mode: spawn the bundled PyInstaller executable ---
    // extraResources are placed at: <app>/resources/python-backend/
    const resourcesPath = join(process.resourcesPath, 'python-backend')
    const serverExe = join(resourcesPath, 'lithe-server.exe')

    if (!existsSync(serverExe)) {
      process.stderr.write(
        `[Lithe] ERROR: Python backend not found at: ${serverExe}\n`
      )
      return
    }

    pythonProcess = spawn(serverExe, [], {
      cwd: resourcesPath,
      stdio: 'pipe',
      env: { ...process.env }
    })
  }

  pythonProcess.stdout?.on('data', (data: Buffer) => {
    const msg = data.toString().trim()
    if (msg) logChild(`[STDOUT] ${msg}`)
  })

  pythonProcess.stderr?.on('data', (data: Buffer) => {
    const msg = data.toString().trim()
    if (msg) logChild(`[STDERR] ${msg}`)
  })

  pythonProcess.on('error', (err: Error) => {
    logMain(`[Lithe] Failed to start Python server: ${err.message}`)
  })
}

function stopPythonServer(): void {
  if (pythonProcess && !pythonProcess.killed) {
    pythonProcess.kill()
    pythonProcess = null
  }
}

async function checkBackendHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${PYTHON_SERVER_URL}/api/health`)
    return response.ok
  } catch {
    return false
  }
}

async function waitForPythonServer(maxRetries = 30, delayMs = 500): Promise<boolean> {
  for (let i = 0; i < maxRetries; i++) {
    if (await checkBackendHealth()) return true
    await new Promise((resolve) => setTimeout(resolve, delayMs))
  }
  return false
}

// ---------------------------------------------------------------------------
// Window creation
// ---------------------------------------------------------------------------
function createWindow(): BrowserWindow {
  // Resolve icon path (works in both dev and production)
  const iconPath = is.dev
    ? join(__dirname, '..', '..', '..', '..', 'docs', 'lithe-brand', 'icon.ico')
    : join(process.resourcesPath, 'icon.ico')

  const mainWindow = new BrowserWindow({
    width: 1100,
    height: 720,
    minWidth: 900,
    minHeight: 600,
    resizable: true,
    title: 'Lithe',
    backgroundColor: '#08080a',
    icon: iconPath,
    show: false,
    autoHideMenuBar: true,
    titleBarStyle: 'hidden',
    titleBarOverlay: {
      color: '#0e0e11',
      symbolColor: '#c9c9ce',
      height: 32
    },
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false,
      contextIsolation: true,
      nodeIntegration: false
    }
  })

  mainWindow.on('ready-to-show', () => {
    mainWindow.show()
  })

  mainWindow.webContents.setWindowOpenHandler((details) => {
    shell.openExternal(details.url)
    return { action: 'deny' }
  })

  // Load the renderer — dev server in dev, file in production
  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }

  ipcMain.handle('get-health', async () => {
    return checkBackendHealth()
  })
  
  ipcMain.handle('log-error', (_, message: string, stack: string) => {
    logMain(`[Renderer Error] ${message}\n${stack}`)
  })

  ipcMain.handle('open-logs-folder', () => {
    shell.openPath(logsDir)
  })

  ipcMain.handle('dialog:showOpenDialog', async () => {
    const { canceled, filePaths } = await dialog.showOpenDialog(mainWindow, {
      properties: ['openDirectory', 'multiSelections']
    })
    return canceled ? [] : filePaths
  })

  return mainWindow
}

// ---------------------------------------------------------------------------
// App lifecycle
// ---------------------------------------------------------------------------
app.whenReady().then(async () => {
  electronApp.setAppUserModelId('com.lithe.app')

  app.on('browser-window-created', (_, window) => {
    optimizer.watchWindowShortcuts(window)
  })

  // Start the Python backend if not already running
  const alreadyRunning = await checkBackendHealth()
  if (!alreadyRunning) {
    startPythonServer()
    const serverReady = await waitForPythonServer()

    if (!serverReady) {
      process.stderr.write(
        '[Lithe] Python server failed to start. Make sure Python is installed and dependencies are available.\n'
      )
    }
  } else {
    process.stdout.write('[Lithe] Backend already running on port 8321. Connecting to it.\n')
  }

  createWindow()

  app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  stopPythonServer()
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('will-quit', () => {
  stopPythonServer()
})

