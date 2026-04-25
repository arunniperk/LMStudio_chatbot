# chatbot.ps1
$ErrorActionPreference = "SilentlyContinue"
$Host.UI.RawUI.WindowTitle = "LM Studio Chatbot"

# Check if LM Studio server is running on port 1234
try {
    $response = Invoke-WebRequest -Uri "http://localhost:1234/v1/models" -UseBasicParsing
} catch {
    Write-Host "`n LM Studio server not detected on port 1234." -ForegroundColor Yellow
    Write-Host " Please open LM Studio, load a model (like DeepSeek R1 or Qwen), and click 'Start Server'."
    Write-Host " Press any key to continue launching..."
    $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") | Out-Null
}

# Launch the app using pythonw to hide the background console
pythonw app.py
if ($LASTEXITCODE -ne 0) {
    # Fallback to standard python if pythonw fails to reveal errors
    python app.py
}