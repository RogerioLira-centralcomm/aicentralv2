# Monitora até HTTPS válido em ai.centralcomm.media (após colar script no Hostinger).
param([int]$MaxAttempts = 40, [int]$IntervalSec = 15)
for ($i = 1; $i -le $MaxAttempts; $i++) {
    $exit = 0
    $out = & curl.exe -sI --connect-timeout 8 https://ai.centralcomm.media/ 2>&1
  $exit = $LASTEXITCODE
  $tcp = New-Object System.Net.Sockets.TcpClient
  try {
    $tcp.Connect('ai.centralcomm.media', 443)
    $ssl = New-Object System.Net.Security.SslStream($tcp.GetStream(), $false, ({ $true }))
    $ssl.AuthenticateAsClient('ai.centralcomm.media')
    $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($ssl.RemoteCertificate)
    $subj = $cert.Subject
    $ssl.Close()
    $tcp.Close()
  } catch {
    $subj = "connect failed"
  }
  Write-Host ("[{0}/{1}] curl exit={2} cert={3}" -f $i, $MaxAttempts, $exit, $subj)
  if ($exit -eq 0 -and $subj -notmatch 'Easypanel') {
    $out | Select-Object -First 6
    Write-Host "HTTPS restaurado."
    exit 0
  }
  Start-Sleep -Seconds $IntervalSec
}
Write-Host "Ainda com Easypanel ou cert inválido — cole o script no terminal Hostinger."
exit 1