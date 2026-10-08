# FDE Data Studio 백업 — DB(PostgreSQL) 덤프와 업로드 원본 파일을 backups\날짜시각 폴더에 저장한다.
# 사용 (프로젝트 폴더에서, 서비스가 떠 있는 상태):
#   powershell -ExecutionPolicy Bypass -File scripts\backup.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

function Compose {
    & docker compose @args
    if ($LASTEXITCODE -ne 0) { throw "실패: docker compose $($args -join ' ')" }
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dir = Join-Path (Join-Path (Get-Location) "backups") $stamp
New-Item -ItemType Directory -Force -Path $dir | Out-Null

Write-Host "1/2 데이터베이스 덤프 중..."
Compose exec -T db pg_dump -U fde -d fde -Fc -f /tmp/fde.dump
Compose cp db:/tmp/fde.dump (Join-Path $dir "fde.dump")
Compose exec -T db rm -f /tmp/fde.dump

Write-Host "2/2 업로드 파일 묶는 중..."
Compose exec -T backend tar czf /tmp/storage.tgz -C /data/storage .
Compose cp backend:/tmp/storage.tgz (Join-Path $dir "storage.tgz")
Compose exec -T backend rm -f /tmp/storage.tgz

Write-Host ""
Write-Host "백업 완료: $dir"
Get-ChildItem $dir | Format-Table Name, Length -AutoSize
