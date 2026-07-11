import { app, shell, BrowserWindow } from 'electron'
import { join } from 'path'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import { spawn, ChildProcess } from 'child_process'

// ---------------------------------------------------------------------------
// Python server management
// ---------------------------------------------------------------------------
const PYTHON_SERVER_PORT = 8321
const PYTHON_SERVER_URL = `http://127.0.0.1:${PYTHON_SERVER_PORT}`

let pythonProcess: ChildProcess | null = null

function startPythonServer(): void {
  // Resolve the project root (3 levels up from src/frontend/out/main)
  const projectRoot = join(__dirname, '..', '..', '..', '..')

  pythonProcess = spawn('python', ['-m', 'src.backend.server'], {
    cwd: projectRoot,
    stdio: 'pipe',
    env: { ...process.env }
  })

  pythonProcess.stdout?.on('data', (data: Buffer) => {
    const msg = data.toString().trim()
    if (msg) process.stdout.write(`[Lithe Python] ${msg}\n`)
  })

  pythonProcess.stderr?.on('data', (data: Buffer) => {
    const msg = data.toString().trim()
    if (msg) process.stderr.write(`[Lithe Python] ${msg}\n`)
  })

  pythonProcess.on('error', (err: Error) => {
    process.stderr.write(`[Lithe] Failed to start Python server: ${err.message}\n`)
  })
}

function stopPythonServer(): void {
  if (pythonProcess && !pythonProcess.killed) {
    pythonProcess.kill()
    pythonProcess = null
  }
}

async function waitForPythonServer(maxRetries = 20, delayMs = 500): Promise<boolean> {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const response = await fetch(`${PYTHON_SERVER_URL}/api/health`)
      if (response.ok) return true
    } catch {
      // Server not ready yet — retry
    }
    await new Promise((resolve) => setTimeout(resolve, delayMs))
  }
  return false
}

// ---------------------------------------------------------------------------
// Window creation
// ---------------------------------------------------------------------------
function createWindow(): BrowserWindow {
  const mainWindow = new BrowserWindow({
    width: 1000,
    height: 700,
    resizable: false,
    title: 'Lithe',
    backgroundColor: '#0a0e1a',
    show: false,
    autoHideMenuBar: true,
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

  // Start the Python backend
  startPythonServer()
  const serverReady = await waitForPythonServer()

  if (!serverReady) {
    process.stderr.write(
      '[Lithe] Python server failed to start. Make sure Python is installed and dependencies are available.\n'
    )
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
